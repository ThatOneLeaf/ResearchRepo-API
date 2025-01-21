from flask import Blueprint, request, jsonify
from sqlalchemy.exc import SQLAlchemyError
from models import db, Publication , ResearchOutput, Status, Conference, PublicationFormat
from services.auth_services import formatting_id, log_audit_trail
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, date
from services.tracking_services import insert_status, update_status
from sqlalchemy import func, desc, nulls_last
from services.mail import send_notification_email
from services.data_fetcher import get_field_attribute

track = Blueprint('track', __name__)

@track.route('/research_status', methods=['GET'])
@track.route('/research_status/<research_id>', methods=['GET', 'POST'])
@jwt_required()
def get_research_status(research_id=None):
    if request.method == 'GET':
        try:
            # Build the query
            query = (
                db.session.query(
                    ResearchOutput.research_id,
                    Publication.publication_id,
                    Status.status,
                    Status.timestamp,
                    ResearchOutput.date_approved
                )
                .outerjoin(Publication, Publication.research_id == ResearchOutput.research_id)
                .outerjoin(Status, Status.publication_id == Publication.publication_id)
                .order_by(Status.timestamp)  # Always order by most recent timestamp
            )

            # Apply filter if research_id is provided
            if research_id:
                query = query.filter(ResearchOutput.research_id == research_id)

            # Fetch results
            result = query.all()

            # Process results into a JSON-serializable format
            data = [
                {
                    'research_id':row.research_id,
                    'status': row.status if row.status else "READY",
                    'time': row.timestamp.strftime('%B %d, %Y') if row.timestamp else row.date_approved.strftime('%B %d, %Y') 
                }
                for row in result
            ]

            # Return appropriate response based on query results
            if not data:
                return jsonify({
                    "message": "No records found",
                    "research_id": research_id,
                    "dataset": []  # Always return an empty array in the 'dataset' key
                }), 404

            return jsonify(data), 200

        except SQLAlchemyError as e:
            db.session.rollback()  # Rollback in case of an error
            return jsonify({
                "error": "Database error occurred",
                "details": str(e),
                "dataset": []  # Ensure 'dataset' is always an array, even on error
            }), 500

    elif request.method == 'POST':
        try:
            new_status = ""
            # Retrieve data from request body (JSON)
            publication = Publication.query.filter(Publication.research_id == research_id).first()

            if publication is None:
                return jsonify({"message": "Fill in the forms first"}), 400
            
            # Retrieve the latest status
            current_status = Status.query.filter(Status.publication_id == publication.publication_id).order_by(desc(Status.timestamp)).first()

            # Handle case where current_status is None
            if current_status is None:
                # If no status exists, set the initial status to "SUBMITTED"
                new_status = "SUBMITTED"
                # Call the function to insert the new status for the publication
                changed_status, error = insert_status(publication.publication_id, new_status)
            else:
                # If there is a current status, handle status transitions
                if current_status.status == "PULLOUT":
                    return jsonify({"message": "Paper already pulled out"}), 400
                elif current_status.status == "SUBMITTED":
                    new_status = "ACCEPTED"
                elif current_status.status == "ACCEPTED":
                    new_status = "PUBLISHED"
                elif current_status.status == "PUBLISHED":
                    return jsonify({"message": "Paper already published"}), 400

                # Call the function to insert the new status
                changed_status, error = insert_status(current_status.publication_id, new_status)

            # If there was an error inserting the status, handle it
            if error:
                return jsonify({"error": "Database error occurred", "details": error}), 500

            # Send email asynchronously (optional)
            send_notification_email("NEW PUBLICATION STATUS UPDATE",
                                f'Research paper by {research_id} has been updated to {changed_status.status}.')
            
            # Log audit trail here asynchronously (optional)
            # Get the current user's identity
            user_id = get_jwt_identity()
            log_audit_trail(
                user_id=user_id,
                table_name='Publication and Status',
                record_id=research_id,
                operation='UPDATE',
                action_desc='Updated research output status')

            return jsonify({"message": "Status entry created successfully", "status_id": changed_status.status_id}), 201

        except SQLAlchemyError as e:
            db.session.rollback()  # Rollback in case of an error
            return jsonify({"error": "Database error occurred", "details": str(e)}), 500


        
@track.route('next_status/<research_id>',methods=['GET'])
@jwt_required()
def get_next_status(research_id):
    new_status=""
    # Retrieve data from request body (JSON)
    try:

        publication = Publication.query.filter(Publication.research_id==research_id).first()

        if publication is None:
            new_status="SUBMITTED"
        
        current_status = Status.query.filter(Status.publication_id == publication.publication_id).order_by(desc(Status.timestamp)).first()
        if current_status.status == "PULLOUT":
            new_status="PULLOUT"
        elif current_status.status is None:
            new_status="SUBMITTED"
        elif current_status.status == "SUBMITTED":
            new_status="ACCEPTED"
        elif current_status.status == "ACCEPTED":
            new_status="PUBLISHED"
        elif current_status.status == "PUBLISHED":
            new_status="COMPLETED"

        return jsonify(new_status), 200
    except Exception as e:
        
        new_status="SUBMITTED"
        db.session.rollback()  # Rollback in case of error
        return jsonify(new_status), 200



@track.route('research_status/pullout/<research_id>',methods=['POST'])    
@jwt_required()
def pullout_paper(research_id):
    publication = Publication.query.filter(Publication.research_id==research_id).first()
    if publication is None:
        return jsonify({"message": "No publication."}), 400
    
    current_status = Status.query.filter(Status.publication_id == publication.publication_id).order_by(desc(Status.timestamp)).first()
    if current_status.status is None:
        return jsonify({"message": "No submission occured."}), 400
    elif current_status.status == "PUBLISHED":
        return jsonify({"message": "Paper already published"}), 400
    else:
        changed_status, error = insert_status(current_status.publication_id, "PULLOUT")
        if error:
                return jsonify({"error": "Database error occurred", "details": error}), 500

            # Send email asynchronously (optional)
        send_notification_email("NOTIFICATION",
                                f'Research paper by {research_id} has been pulled out.')

        # Log audit trail here asynchronously (optional)
        # Get the current user's identity
        user_id = get_jwt_identity()
        log_audit_trail(
                user_id=user_id,
                table_name='Publication and Status',
                record_id=research_id,
                operation='UPDATE',
                action_desc='Updated research output status')
            
        return jsonify({"message": "Status entry created successfully", "status_id": changed_status.status_id}), 201


@track.route('/publication/<research_id>', methods=['GET', 'POST', 'PUT'])
@jwt_required()
def publication_papers(research_id=None):
    user_id = get_jwt_identity()
    try:
        if request.method == 'GET':
            # Fetch publication details
            query = (
                db.session.query(
                    PublicationFormat.pub_format_id,
                    Conference.conference_title,
                    Conference.conference_venue,
                    Conference.conference_date,
                    Publication.publication_id,
                    Publication.publication_name,
                    Publication.date_published,
                    Publication.date_submitted,
                    Publication.scopus
                )
                .join(ResearchOutput, Publication.research_id == ResearchOutput.research_id)
                .outerjoin(Conference, Conference.conference_id == Publication.conference_id)
                .outerjoin(PublicationFormat, PublicationFormat.pub_format_id == Publication.pub_format_id)
                .filter(ResearchOutput.research_id == research_id)
            )
            result = query.all()

            # Prepare response data
            data = [
                {
                    'publication_id': row.publication_id,
                    'journal': row.pub_format_id,
                    'conference_title': row.conference_title,
                    'city': row.conference_venue.split(',')[0].strip() if row.conference_venue else None,
                    'country': row.conference_venue.split(',')[1].strip() if row.conference_venue and ',' in row.conference_venue else None,
                    'conference_date': row.conference_date.strftime('%Y-%m-%d') if row.conference_date else None,
                    'publication_name': row.publication_name,
                    'date_published': row.date_published.strftime('%Y-%m-%d') if row.date_published else None,
                    'date_submitted': row.date_submitted.strftime('%Y-%m-%d') if row.date_submitted else None,
                    'scopus': row.scopus
                }
                for row in result
            ]

            return jsonify({"dataset": data}), 200

        elif request.method == 'POST':
            # Handle publication creation
            research_output = db.session.query(ResearchOutput).filter(ResearchOutput.research_id == research_id).first()
            if not research_output:
                return jsonify({'message': 'ResearchOutput not found'}), 404

            # Prevent duplicate publications
            publication_exists = db.session.query(Publication).filter(Publication.research_id == research_id).first()
            if publication_exists:
                return jsonify({'message': 'Publication already exists'}), 400

            conference_title = request.form.get('conference_title')
            if conference_title:
                conference = db.session.query(Conference).filter(
                    Conference.conference_title.ilike(conference_title),
                    Conference.conference_venue.ilike(f"{request.form.get('city')}, {request.form.get('country')}"),
                    Conference.conference_date == datetime.strptime(request.form.get('conference_date'), '%Y-%m-%d') if request.form.get('conference_date') else None
                ).first()

                if not conference:
                    cf_id = formatting_id("CF", Conference, 'conference_id')  # Generate new CF_ID
                    conference_date = datetime.strptime(request.form.get('conference_date'), '%Y-%m-%d') if request.form.get('conference_date') else None

                    conference = Conference(
                        conference_id=cf_id,
                        conference_title=conference_title,
                        conference_venue=f"{request.form.get('city')}, {request.form.get('country')}",
                        conference_date=conference_date
                    )
                    
                    db.session.add(conference)  # Add new conference to the database
                    db.session.commit()  # Commit changes
                    log_audit_trail(
                        user_id=user_id,
                        table_name='Conference',
                        record_id=cf_id,
                        operation='CREATE',
                        action_desc=f"Added new conference: {conference.conference_title}"
                    )

            # Create publication
            publication_id = formatting_id("PBC", Publication, 'publication_id')
            date_published = datetime.strptime(request.form.get('date_published'), '%Y-%m-%d') if request.form.get('date_published') else None
            new_publication = Publication(
                publication_id=publication_id,
                research_id=research_id,
                publication_name=request.form.get('publication_name'),
                conference_id=conference.conference_id if conference_title else None,
                pub_format_id=request.form.get('pub_format_id'),
                user_id=user_id,
                date_published=date_published,
                scopus=request.form.get('scopus')
            )
            db.session.add(new_publication)
            db.session.commit()

            # Log audit trail
            log_audit_trail(
                user_id=user_id,
                table_name='Publication',
                record_id=publication_id,
                operation='CREATE',
                action_desc=f"Added new publication: {new_publication.publication_name}"
            )

            return jsonify({'message': 'Publication created successfully'}), 201

        elif request.method == 'PUT':
            # Extract publication ID from request
            publication_id = request.form.get('publication_id')

            # Find the existing publication
            publication = db.session.query(Publication).filter(Publication.publication_id == publication_id, Publication.research_id == research_id).first()
            if not publication:
                return jsonify({'message': 'Publication not found'}), 404

            # Store previous data
            previous_data = {
                'publication_name': publication.publication_name,
                'conference_id': publication.conference_id,
                'pub_format_id': publication.pub_format_id,
                'date_published': publication.date_published,
                'scopus': publication.scopus
            }

            # Update conference information if provided
            conference_title = request.form.get('conference_title')
            if conference_title:
                conference = db.session.query(Conference).filter(
                    Conference.conference_title.ilike(conference_title),
                    Conference.conference_venue.ilike(f"{request.form.get('city')}, {request.form.get('country')}"),
                    Conference.conference_date == datetime.strptime(request.form.get('conference_date'), '%Y-%m-%d') if request.form.get('conference_date') else None
                ).first()

                if not conference:
                    cf_id = formatting_id("CF", Conference, 'conference_id')  # Generate new CF_ID
                    conference_date = datetime.strptime(request.form.get('conference_date'), '%Y-%m-%d') if request.form.get('conference_date') else None

                    conference = Conference(
                        conference_id=cf_id,
                        conference_title=conference_title,
                        conference_venue=f"{request.form.get('city')}, {request.form.get('country')}",
                        conference_date=conference_date
                    )

                    db.session.add(conference)  # Add new conference to the database
                    db.session.commit()  # Commit changes
                    log_audit_trail(
                        user_id=user_id,
                        table_name='Conference',
                        record_id=cf_id,
                        operation='CREATE',
                        action_desc=f"Added new conference: {conference.conference_title}"
                    )

                publication.conference_id = conference.conference_id

            # Update publication fields
            publication.publication_name = request.form.get('publication_name', publication.publication_name)
            publication.pub_format_id = request.form.get('pub_format_id', publication.pub_format_id)
            publication.date_published = datetime.strptime(request.form.get('date_published'), '%Y-%m-%d') if request.form.get('date_published') else publication.date_published
            publication.scopus = request.form.get('scopus', publication.scopus)

            db.session.commit()

            # Generate the action description with previous and new data
            action_desc = (
                f"Updated publication: {publication.publication_name}\n"
                f"Previous Data: {previous_data}\n"
                f"New Data: {{'publication_name': {publication.publication_name}, "
                f"conference_id': {publication.conference_id}, "
                f"pub_format_id': {publication.pub_format_id}, "
                f"date_published': {publication.date_published}, "
                f"scopus': {publication.scopus}}}"
            )

            # Log audit trail with previous and new data
            log_audit_trail(
                user_id=user_id,
                table_name='Publication',
                record_id=publication_id,
                operation='UPDATE',
                action_desc=action_desc
            )

            return jsonify({'message': 'Publication updated successfully'}), 200


    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


from datetime import datetime
def parse_date(date_string):
    """Parse a date string or return None if invalid."""
    try:
        if date_string:  # Check if the value is not None or empty
            return datetime.strptime(date_string, "%Y-%m-%d").date()
        return None
    except (ValueError, TypeError):
        return None
    
@track.route('/published_paper/<research_id>', methods=['GET'])
def check_uploaded_paper(research_id=None):
    if research_id:
        # Query the database for the research output with the given ID
        query = ResearchOutput.query.filter_by(research_id=research_id).first()
        
        # Check if the research output exists
        if query is None:
            return jsonify({"message": "No research output exists"}), 404
        
        # Check if the extended abstract is uploaded
        if query.extended_abstract is None:
            return jsonify({"message": "No extended abstract uploaded. Please upload one."}), 400  # Bad request
        
        # Return success if the research output and extended abstract are found
        return jsonify({
            "message": "Research output and extended abstract found"
        }), 200
    
    # Return a message if research_id is not provided
    return jsonify({"message": "No research ID provided"}), 400

@track.route('data_fetcher/<table>/<field>', methods=['GET'])
def field_contents(table,field):
    TABLE_MODELS = {
        'publications': Publication,
        'conference': Conference,
    }
    if table and field:
        try:
            # Dynamically get the model based on the table name
            model = TABLE_MODELS.get(table.lower())

            if model is None:
                return jsonify({'message': f"Table '{table}' does not exist."}), 400

            # Dynamically get the field attribute from the model
            field_attribute = get_field_attribute(model, field)

            if not field_attribute:
                return jsonify({'message': f"Field '{field}' not found in table '{table}'."}), 400

            return jsonify(field_attribute), 200

        except Exception as e:
            return jsonify({'message': f"An error occurred: {str(e)}"}), 500
    else:
        return jsonify({'message': "No table or field provided"}), 400
    

@track.route("/fetch_data/<table>", methods=['GET'])
def fetch_all_contents(table):
    TABLE_MODELS = {
        'publications': Publication,
        'conference': Conference,
        'pub_format': PublicationFormat
    }

    if table:
        try:
            # Dynamically get the model based on the table name
            model = TABLE_MODELS.get(table.lower())

            if model is None:
                return jsonify({
                    'message': f"Table '{table}' does not exist. Available tables: {list(TABLE_MODELS.keys())}"
                }), 400

            # Query all records from the table
            records = db.session.query(model).all()
            if not records:
                return jsonify({'message': "No data found in the table."}), 404

            # Dynamically serialize records to dictionaries
            response_data = [
                {column.name: getattr(record, column.name) for column in model.__table__.columns}
                for record in records
            ]

            return jsonify(response_data), 200

        except Exception as e:
            return jsonify({'message': f"An error occurred: {str(e)}"}), 500
    else:
        return jsonify({'message': "No table provided."}), 400


@track.route('/form/<operation>/<research_id>', methods=['POST'])
@jwt_required()
def manage_publication(operation, research_id):
    user_id = get_jwt_identity()
    # Validate the operation
    if operation.lower() not in ['submit', 'accept', 'publish']:
        return jsonify({'message': 'Invalid operation'}), 400

    # Fetch the ResearchOutput
    research_output = db.session.query(ResearchOutput).filter(ResearchOutput.research_id == research_id).first()
    if not research_output:
        return jsonify({'message': 'ResearchOutput not found'}), 404

    # Handle 'submit' operation
    if operation.lower() == 'submit':
        publication_exists = db.session.query(Publication).filter(Publication.research_id == research_id).first()
        if publication_exists:
            return jsonify({'message': 'Publication already exists'}), 400

        conference_title = request.form.get('conference_title')
        if conference_title:
            conference = db.session.query(Conference).filter(
                Conference.conference_title.ilike(conference_title),
                Conference.conference_venue.ilike(f"{request.form.get('city')}, {request.form.get('country')}"),
                Conference.conference_date == datetime.strptime(request.form.get('conference_date'), '%Y-%m-%d') if request.form.get('conference_date') else None
            ).first()

            if not conference:
                cf_id = formatting_id("CF", Conference, 'conference_id')
                conference_date = datetime.strptime(request.form.get('conference_date'), '%Y-%m-%d') if request.form.get('conference_date') else None

                conference = Conference(
                    conference_id=cf_id,
                    conference_title=conference_title,
                    conference_venue=f"{request.form.get('city')}, {request.form.get('country')}",
                    conference_date=conference_date
                )
                
                db.session.add(conference)
                db.session.commit()
                log_audit_trail(
                    user_id=user_id,
                    table_name='Conference',
                    record_id=cf_id,
                    operation='CREATE',
                    action_desc=f"Added new conference: {conference.conference_title}"
                )

        try:
            date_submitted = datetime.strptime(request.form.get('date_submitted'), '%Y-%m-%d')
            if date_submitted.date() > date.today():
                return jsonify({'message': 'Date submitted cannot be in the future'}), 400
        except (ValueError, TypeError):
            return jsonify({'message': 'Invalid date format for date_submitted'}), 400

        publication_id = formatting_id("PBC", Publication, 'publication_id')
        new_publication = Publication(
            publication_id=publication_id,
            research_id=research_id,
            publication_name=request.form.get('publication_name'),
            conference_id=conference.conference_id if conference_title else None,
            pub_format_id=request.form.get('pub_format_id'),
            user_id=user_id,
            date_submitted=date_submitted
        )
        db.session.add(new_publication)
        db.session.commit()

        status = update_status(research_id)
        if not status:
            print("error")
        else:
            log_audit_trail(
                user_id=user_id,
                table_name='Status',
                record_id=research_id,
                operation='UPDATE',
                action_desc=f'Updated {research_id} status to SUBMITTED')

        log_audit_trail(
            user_id=user_id,
            table_name='Publication',
            record_id=publication_id,
            operation='CREATE',
            action_desc=f"Added new publication: {new_publication.publication_name}"
        )

        return jsonify({'message': 'Publication submitted successfully'}), 201

    elif operation.lower() =='accept':
        status = update_status(research_id)
        if not status:
            print("error")
        else:
            log_audit_trail(
                user_id=user_id,
                table_name='Status',
                record_id=research_id,
                operation='UPDATE',
                action_desc=f'Updated {research_id} status to SUBMITTED')

    # Handle 'publish' operation
    elif operation.lower() == 'publish':
        publication = db.session.query(Publication).filter(Publication.research_id == research_id).first()
        if not publication:
            return jsonify({'message': 'Publication not found'}), 404

        before_date = None
        if publication.pub_format_id == "PC":
            conference = db.session.query(Conference).filter(Conference.conference_id == publication.conference_id).first()
            before_date = conference.conference_date
        else:
            before_date = publication.date_submitted

        try:
            pub_date = datetime.strptime(request.form.get('date_published'), '%Y-%m-%d').date()
            # Check if the published date is in the future
            if pub_date > date.today():
                return jsonify({'message': 'Date published cannot be in the future'}), 400
            # Check if the published date is earlier than the required date
            if pub_date < before_date:
                return jsonify({'message': f'Date published cannot be earlier than {before_date}'}, 400)
        except (ValueError, TypeError):
            return jsonify({'message': 'Invalid date format for date_published'}), 400

        publication.publication_name = request.form.get('publication_name')
        publication.date_published = pub_date
        publication.scopus = request.form.get('scopus')
        db.session.commit()

        log_audit_trail(
            user_id=user_id,
            table_name='Publication',
            record_id=publication.publication_id,
            operation='UPDATE',
            action_desc=f"Published publication: {publication.publication_name}"
        )

        status = update_status(research_id)
        if not status:
            print("error")
        else:
            log_audit_trail(
                user_id=user_id,
                table_name='Status',
                record_id=research_id,
                operation='UPDATE',
                action_desc=f'Updated {research_id} status to PUBLISHED')

        return jsonify({'message': 'Publication published successfully'}), 200