from flask import Blueprint, request, jsonify
from sqlalchemy.exc import SQLAlchemyError
from models import db, Publication , ResearchOutput, Status,ResearchOutputAuthor,UserProfile,Account, Conference
from services.auth_services import formatting_id, log_audit_trail
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from services.tracking_services import insert_status
from sqlalchemy import func, desc, nulls_last


track = Blueprint('track', __name__)

@track.route('/research_status/<research_id>', methods=['GET', 'POST'])
def get_research_status(research_id=None):
    if request.method == 'GET':
        try:
            # Fetch data based on research_id
            query = (
                db.session.query(
                    ResearchOutput.research_id,
                    Publication.publication_id,
                    Status.status
                )
                .join(Publication, Publication.research_id == ResearchOutput.research_id)
                .join(Status, Status.publication_id == Publication.publication_id)
                .filter(ResearchOutput.research_id == research_id)
            )

            result = query.all()

            # Process results into a JSON-serializable format
            data = [
                {
                    'research_id': row.research_id,
                    'publication_id': row.publication_id,
                    'status': row.status
                }
                for row in result
            ]

            if not data:
                return jsonify({"error": f"No data found for research_id {research_id}"}), 404
            
            return jsonify({'dataset': data}), 200

        except SQLAlchemyError as e:
            db.session.rollback()  # Rollback in case of an error
            return jsonify({"error": "Database error occurred", "details": str(e)}), 500

    elif request.method == 'POST':
        try:
            # Retrieve data from request body (JSON)
            data = request.get_json()
            publication_id = data.get('publication_id')
            status_value = data.get('status')

            # Validate input data
            if not all([publication_id, status_value]):
                return jsonify({"error": "publication_id and status are required"}), 400

            # Call the function to insert status
            new_status, error = insert_status(publication_id, status_value)

            if error:
                return jsonify({"error": "Database error occurred", "details": error}), 500

            # Send email asynchronously (optional)
            # Log audit trail here asynchronously (optional)

            return jsonify({"message": "Status entry created successfully", "status_id": new_status.status_id}), 201
        except SQLAlchemyError as e:
            db.session.rollback()  # Rollback in case of an error
            return jsonify({"error": "Database error occurred", "details": str(e)}), 500
        

@track.route('/publication/<research_id>',methods=['GET','POST','PUT'])
#@jwt_required()
def publication_papers(research_id=None):
    if request.method == 'GET':
        authors_subquery = db.session.query(
            ResearchOutputAuthor.research_id,
            func.string_agg(
                func.concat(
                    UserProfile.first_name,
                    ' ',
                    func.coalesce(UserProfile.middle_name, ''),
                    ' ',
                    UserProfile.last_name,
                    ' ',
                    func.coalesce(UserProfile.suffix, '')
                ), '; '
            ).label('concatenated_authors')
        ).join(Account, ResearchOutputAuthor.author_id == Account.user_id) \
        .join(UserProfile, Account.user_id == UserProfile.researcher_id) \
        .group_by(ResearchOutputAuthor.research_id).subquery()

        query = (db.session.query(
            ResearchOutput.research_id,
            ResearchOutput.title,
            authors_subquery.c.concatenated_authors,
            ResearchOutput.extended_abstract,
            Publication.journal,
            Conference.conference_title,
            Conference.conference_venue,
            Conference.conference_date,
            Publication.publication_name,        
            Publication.date_published,
            Publication.scopus

        )).outerjoin(authors_subquery, ResearchOutput.research_id==authors_subquery.c.research_id)\
        .outerjoin(Publication,Publication.research_id==ResearchOutput.research_id)\
        .outerjoin(Conference, Conference.conference_id==Publication.conference_id)\
        .filter(ResearchOutput.research_id == research_id)

        result=query.all()
        data = [
            {
                'research_id': row.research_id,
                'title': row.title,
                'authors': row.concatenated_authors,
                'extended_abstract': row.extended_abstract,
                'journal': row.journal,
                'conference_title': row.conference_title,
                'conference_venue': row.conference_venue,
                'conference_date': row.conference_date,
                'publication_name': row.publication_name,
                'date_published': row.date_published,
                'scopus': row.scopus
            }
            for row in result
        ]
        
        return jsonify({"dataset":data}), 200
    elif request.method == 'POST':
        data = request.get_json()  # Get the JSON data sent in the request
        try:
            # Check if ResearchOutput exists
            research_output = db.session.query(ResearchOutput).filter(ResearchOutput.research_id == research_id).first()

            if not research_output:
                return jsonify({'message': 'ResearchOutput not found'}), 404

            # Check if conference exists or create a new one
            conference_title = data.get('conference_title')
            conference = db.session.query(Conference).filter(Conference.conference_title.ilike(conference_title)).first()

            if not conference:
                # Generate a unique conference_id
                cf_id = formatting_id("CF", Conference, 'conference_id')

                # Create a new Conference
                conference = Conference(
                    conference_id=cf_id,
                    conference_title=data.get('conference_title'),
                    conference_venue=data.get('conference_venue'),
                    conference_date=data.get('conference_date')
                )
                db.session.add(conference)
            else:
                cf_id = conference.conference_id  # Use existing conference_id
            
            publication_id=formatting_id("PBC", Publication, 'publication_id'),  # Ensure unique publication_id

            # Create Publication
            new_publication = Publication(
                publication_id=publication_id,
                research_id=research_id,
                publication_name=data.get('publication_name'),
                conference_id=cf_id,
                journal=data.get('journal'),
                user_id=data.get('user_id'),  # Ensure user_id is provided in request data
                date_published=data.get('date_published'),
                scopus=data.get('scopus')
            )
            db.session.add(new_publication)
            db.session.commit()

            # Audit trail logging
            """log_audit_trail(
                user_id=data.get('user_id'),
                table_name='Publication and Conference',
                record_id=new_publication.publication_id,
                operation='CREATE',
                action_desc='Creating Publication and associated Conference details')"""

            return jsonify({'message': 'Publication and Conference created successfully'}), 201

        except Exception as e:
            db.session.rollback()  # Rollback in case of error
            return jsonify({'error': str(e)}), 400
        
    elif request.method == 'PUT':
        # Handle PUT request - Update an existing publication entry
        data = request.get_json()  # Get the JSON data sent in the request

        try:
            # Check if ResearchOutput exists
            research_output = db.session.query(ResearchOutput).filter(ResearchOutput.research_id == research_id).first()
            
            if research_output:
                # Now update the Publication
                publication = db.session.query(Publication).filter(Publication.research_id == research_id).first()

                if publication:
                    publication.journal = data.get('journal', publication.journal)
                    publication.publication_name = data.get('publication_name', publication.publication_name)
                    publication.date_published = data.get('date_published', publication.date_published)
                    publication.scopus = data.get('scopus', publication.scopus)


                    conference = db.session.query(Conference).filter(Conference.conference_id == publication.conference_id).first()
                    # Otherwise, update existing conference details
                    conference.conference_title = data.get('conference_title', conference.conference_title)
                    conference.conference_venue = data.get('conference_venue', conference.conference_venue)
                    conference.conference_date = data.get('conference_date', conference.conference_date)

                    publication.conference = conference

                    db.session.commit()
                    return jsonify({'message': 'Publication updated successfully'}), 200
                else:
                    return jsonify({'message': 'Publication not found'}), 404
            else:
                return jsonify({'message': 'ResearchOutput not found'}), 404
        
        except Exception as e:
            db.session.rollback()  # Rollback in case of error
            return jsonify({'error': str(e)}), 400