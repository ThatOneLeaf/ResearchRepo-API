# dataset.py code (modified to include Keyword)
# created by Nicole Cabansag (Oct. 7, 2024)

from flask import Blueprint, jsonify
from sqlalchemy import func, desc, nulls_last, extract, case
import pandas as pd
from models import College, Program, ResearchOutput, Publication, Status, Conference, ResearchOutputAuthor, Account, UserProfile, Keywords, Panel, SDG, db, ResearchArea, ResearchOutputArea, ResearchTypes, PublicationFormat, UserEngagement, AggrUserEngagement
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import case

dataset = Blueprint('dataset', __name__)

# used for research tracking
@dataset.route('/fetch_dataset', methods=['GET'])
@dataset.route('/fetch_dataset/<research_id>', methods=['GET'])
@jwt_required()
def retrieve_dataset(research_id=None):
    # Subquery to get the latest status for each publication
    latest_status_subquery = db.session.query(
        Status.publication_id,
        Status.status,
        Status.timestamp,
        func.row_number().over(
            partition_by=Status.publication_id,
            order_by=desc(Status.timestamp)
        ).label('rn')
    ).subquery()

    # Subquery to concatenate authors
    ordered_authors = db.session.query(
        ResearchOutputAuthor.research_id,
        ResearchOutputAuthor.author_first_name,
        ResearchOutputAuthor.author_middle_name,
        ResearchOutputAuthor.author_last_name,
        ResearchOutputAuthor.author_suffix,
        ResearchOutputAuthor.author_order
    ).order_by(ResearchOutputAuthor.research_id, ResearchOutputAuthor.author_order).subquery()

    # Modified authors subquery to return array of JSON objects with proper formatting
    authors_subquery = db.session.query(
        ordered_authors.c.research_id,
        func.array_agg(
            func.json_build_object(
                'name', func.concat(
                    ordered_authors.c.author_first_name,
                    ' ',
                    # Add period after middle name if present
                    case(
                        (func.coalesce(ordered_authors.c.author_middle_name, '') != '', 
                         func.concat(ordered_authors.c.author_middle_name, '. ')),
                        else_=''
                    ),
                    ordered_authors.c.author_last_name,
                    # Add space before suffix only if present
                    case(
                        (func.coalesce(ordered_authors.c.author_suffix, '') != '', 
                         func.concat(' ', ordered_authors.c.author_suffix)),
                        else_=''
                    )
                )
            )
        ).label('authors_array')
    ).group_by(ordered_authors.c.research_id).subquery()

    # Modified panels subquery to return array of JSON objects
    panels_subquery = db.session.query(
        Panel.research_id,
        func.array_agg(
            func.json_build_object(
                'name', func.concat(
                    Panel.panel_first_name,
                    ' ',
                    # Add period after middle name if present
                    case(
                        (func.coalesce(Panel.panel_middle_name, '') != '', 
                         func.concat(Panel.panel_middle_name, '. ')),
                        else_=''
                    ),
                    Panel.panel_last_name,
                    # Add space before suffix only if present
                    case(
                        (func.coalesce(Panel.panel_suffix, '') != '', 
                         func.concat(' ', Panel.panel_suffix)),
                        else_=''
                    )
                )
            )
        ).label('panels_array')
    ).group_by(Panel.research_id).subquery()

    # Modified keywords subquery to return array
    keywords_subquery = db.session.query(
        Keywords.research_id,
        func.array_agg(Keywords.keyword).label('keywords_array')
    ).group_by(Keywords.research_id).subquery()

    # Subquery to concatenate sdg
    sdg_subquery = db.session.query(
        SDG.research_id,
        func.string_agg(SDG.sdg, '; ').label('concatenated_sdg')
    ).group_by(SDG.research_id).subquery()

    # Update adviser subquery to use the new columns and properly create a subquery
    adviser_subquery = (
        db.session.query(
            ResearchOutput.research_id,
            func.json_build_object(
                'name', func.concat(
                    ResearchOutput.adviser_first_name,
                    ' ',
                    # Add period after middle name if present
                    case(
                        (func.coalesce(ResearchOutput.adviser_middle_name, '') != '', 
                         func.concat(ResearchOutput.adviser_middle_name, '. ')),
                        else_=''
                    ),
                    ResearchOutput.adviser_last_name,
                    # Add space before suffix only if present
                    case(
                        (func.coalesce(ResearchOutput.adviser_suffix, '') != '', 
                         func.concat(' ', ResearchOutput.adviser_suffix)),
                        else_=''
                    )
                )
            ).label('adviser_info')
        )
    ).subquery()

    # Add this new subquery with the existing subqueries
    research_areas_subquery = db.session.query(
        ResearchOutput.research_id,
        func.array_agg(
            func.json_build_object(
                'research_area_id', ResearchArea.research_area_id,
                'research_area_name', ResearchArea.research_area_name
            )
        ).label('research_areas_array')
    ).join(ResearchOutputArea, ResearchOutput.research_id == ResearchOutputArea.research_id) \
     .join(ResearchArea, ResearchOutputArea.research_area_id == ResearchArea.research_area_id) \
     .group_by(ResearchOutput.research_id).subquery()
    
    # Define subquery for AggrUserEngagement aggregation
    aggr_engagement_subquery = db.session.query(
        AggrUserEngagement.research_id,
        func.sum(AggrUserEngagement.total_views).label("total_aggr_views"),
        func.sum(AggrUserEngagement.total_downloads).label("total_aggr_downloads")
    ).group_by(AggrUserEngagement.research_id).distinct().subquery()

    # Define subquery for Engagement aggregation
    engagement_subquery = db.session.query(
        UserEngagement.research_id,
        func.sum(UserEngagement.view).label("total_views"),
        func.sum(UserEngagement.download).label("total_downloads")
    ).group_by(UserEngagement.research_id).distinct().subquery()

    # Join the two subqueries and calculate the combined totals
    combined_engagement_subquery = db.session.query(
        engagement_subquery.c.research_id,
        (func.coalesce(engagement_subquery.c.total_views, 0) + 
        func.coalesce(aggr_engagement_subquery.c.total_aggr_views, 0)).label("combined_total_views"),
        (func.coalesce(engagement_subquery.c.total_downloads, 0) + 
        func.coalesce(aggr_engagement_subquery.c.total_aggr_downloads, 0)).label("combined_total_downloads")
    ).outerjoin(
        aggr_engagement_subquery, 
        engagement_subquery.c.research_id == aggr_engagement_subquery.c.research_id
    ).subquery()

    base_query = db.session.query(
        ResearchOutput.research_id
    ).select_from(ResearchOutput)

    if research_id:
        base_query = base_query.filter(ResearchOutput.research_id == research_id)

    research_ids = base_query.all()
    
    # Main query using the filtered research_ids
    query = db.session.query(
        ResearchOutput.research_id,
        College.college_id,
        College.college_name,
        Program.program_id,
        Program.program_name,
        sdg_subquery.c.concatenated_sdg,
        ResearchOutput.title,
        ResearchOutput.abstract,
        ResearchOutput.full_manuscript,
        combined_engagement_subquery.c.combined_total_views,
        combined_engagement_subquery.c.combined_total_downloads,
        panels_subquery.c.panels_array,
        ResearchOutput.school_year,
        ResearchOutput.term,
        ResearchTypes.research_type_name,
        authors_subquery.c.authors_array,
        keywords_subquery.c.keywords_array,
        PublicationFormat.pub_format_name,
        Publication.date_published,
        Publication.scopus,
        Conference.conference_venue,
        Conference.conference_title,
        Conference.conference_date,
        latest_status_subquery.c.status,
        latest_status_subquery.c.timestamp,
        adviser_subquery.c.adviser_info,
        research_areas_subquery.c.research_areas_array,
        ResearchOutput.date_uploaded
    ).select_from(ResearchOutput) \
    .join(College, ResearchOutput.college_id == College.college_id) \
    .join(Program, ResearchOutput.program_id == Program.program_id) \
    .outerjoin(Publication, ResearchOutput.research_id == Publication.research_id) \
    .outerjoin(Conference, Publication.conference_id == Conference.conference_id) \
    .outerjoin(latest_status_subquery, (Publication.publication_id == latest_status_subquery.c.publication_id) & (latest_status_subquery.c.rn == 1)) \
    .outerjoin(authors_subquery, ResearchOutput.research_id == authors_subquery.c.research_id) \
    .outerjoin(keywords_subquery, ResearchOutput.research_id == keywords_subquery.c.research_id) \
    .outerjoin(panels_subquery, ResearchOutput.research_id == panels_subquery.c.research_id) \
    .outerjoin(sdg_subquery, ResearchOutput.research_id == sdg_subquery.c.research_id) \
    .outerjoin(adviser_subquery, ResearchOutput.research_id == adviser_subquery.c.research_id) \
    .outerjoin(research_areas_subquery, ResearchOutput.research_id == research_areas_subquery.c.research_id) \
    .outerjoin(ResearchTypes, ResearchOutput.research_type_id == ResearchTypes.research_type_id) \
    .outerjoin(PublicationFormat, Publication.pub_format_id == PublicationFormat.pub_format_id) \
    .outerjoin(combined_engagement_subquery, ResearchOutput.research_id == combined_engagement_subquery.c.research_id) \
    .filter(ResearchOutput.research_id.in_([r.research_id for r in research_ids])) \
    .order_by(desc(latest_status_subquery.c.timestamp), nulls_last(latest_status_subquery.c.timestamp))

    result = query.all()

    # Formatting results into a list of dictionaries
    data = [{
                'college_id': row.college_id if pd.notnull(row.college_id) else 'Unknown',
                'program_name': row.program_name if pd.notnull(row.program_name) else 'N/A',
                'program_id': row.program_id if pd.notnull(row.program_id) else None,
                'research_id': row.research_id,
                'title': row.title if pd.notnull(row.title) else 'Untitled',
                'year': row.school_year if pd.notnull(row.school_year) else None,
                'term': row.term if pd.notnull(row.term) else None,
                'view_count': row.combined_total_views if pd.notnull(row.combined_total_views) else '0',
                'download_count': row.combined_total_downloads if pd.notnull(row.combined_total_downloads) else '0',
                'authors': row.authors_array if row.authors_array else [],
                'keywords': row.keywords_array if row.keywords_array else [],
                'panels': row.panels_array if row.panels_array else [],
                'sdg': row.concatenated_sdg if pd.notnull(row.concatenated_sdg) else 'Not Specified',
                'research_type': row.research_type_name if pd.notnull(row.research_type_name) else 'Unknown Type',
                'journal': row.pub_format_name if pd.notnull(row.pub_format_name) else 'unpublished',
                'scopus': row.scopus if pd.notnull(row.scopus) else 'N/A',
                'date_published': row.date_published,
                'published_year': int(row.date_published.year) if pd.notnull(row.date_published) else None,
                'conference_venue': row.conference_venue if pd.notnull(row.conference_venue) else 'Unknown Venue',
                'conference_title': row.conference_title if pd.notnull(row.conference_title) else 'No Conference Title',
                'conference_date': row.conference_date,
                'status': row.status if pd.notnull(row.status) else "READY",
                'timestamp': row.timestamp if pd.notnull(row.status) else "N/A",
                'country': row.conference_venue.split(",")[-1].strip() if pd.notnull(row.conference_venue) else 'Unknown Country',
                'adviser': {
                    'name': row.adviser_info['name'] if row.adviser_info is not None else None,
                } if row.adviser_info is not None else {
                    'name': None,
                },
                'research_areas': row.research_areas_array if row.research_areas_array else [],
            } for row in result]

    return jsonify({"dataset": [dict(row) for row in data]})

# used for manage papers and collections
@dataset.route('/fetch_ordered_dataset', methods=['GET'])
@dataset.route('/fetch_ordered_dataset/<research_id>', methods=['GET'])
@jwt_required()
def fetch_ordered_dataset(research_id=None):
    # Subquery to get the latest status for each publication
    latest_status_subquery = db.session.query(
        Status.publication_id,
        Status.status,
        Status.timestamp,
        func.row_number().over(
            partition_by=Status.publication_id,
            order_by=desc(Status.timestamp)
        ).label('rn')
    ).subquery()

    # Subquery to concatenate authors
    ordered_authors = db.session.query(
        ResearchOutputAuthor.research_id,
        ResearchOutputAuthor.author_first_name,
        ResearchOutputAuthor.author_middle_name,
        ResearchOutputAuthor.author_last_name,
        ResearchOutputAuthor.author_suffix,
        ResearchOutputAuthor.author_order
    ).order_by(ResearchOutputAuthor.research_id, ResearchOutputAuthor.author_order).subquery()

    # Modified authors subquery to return array of JSON objects with proper formatting
    authors_subquery = db.session.query(
        ordered_authors.c.research_id,
        func.array_agg(
            func.json_build_object(
                'name', func.concat(
                    ordered_authors.c.author_first_name,
                    ' ',
                    # Add period after middle name if present
                    case(
                        (func.coalesce(ordered_authors.c.author_middle_name, '') != '', 
                         func.concat(ordered_authors.c.author_middle_name, '. ')),
                        else_=''
                    ),
                    ordered_authors.c.author_last_name,
                    # Add space before suffix only if present
                    case(
                        (func.coalesce(ordered_authors.c.author_suffix, '') != '', 
                         func.concat(' ', ordered_authors.c.author_suffix)),
                        else_=''
                    )
                )
            )
        ).label('authors_array')
    ).group_by(ordered_authors.c.research_id).subquery()

    # Modified panels subquery to use the new name columns
    panels_subquery = db.session.query(
        Panel.research_id,
        func.array_agg(
            func.json_build_object(
                'name', func.concat(
                    Panel.panel_first_name,
                    ' ',
                    # Add period after middle name if present
                    case(
                        (func.coalesce(Panel.panel_middle_name, '') != '', 
                         func.concat(Panel.panel_middle_name, '. ')),
                        else_=''
                    ),
                    Panel.panel_last_name,
                    # Add space before suffix only if present
                    case(
                        (func.coalesce(Panel.panel_suffix, '') != '', 
                         func.concat(' ', Panel.panel_suffix)),
                        else_=''
                    )
                )
            )
        ).label('panels_array')
    ).group_by(Panel.research_id).subquery()

    # Modified keywords subquery to return array
    keywords_subquery = db.session.query(
        Keywords.research_id,
        func.array_agg(Keywords.keyword).label('keywords_array')
    ).group_by(Keywords.research_id).subquery()

    # Subquery to concatenate sdg
    sdg_subquery = db.session.query(
        SDG.research_id,
        func.string_agg(SDG.sdg, '; ').label('concatenated_sdg')
    ).group_by(SDG.research_id).subquery()

    # Update adviser subquery to use the new columns and properly create a subquery
    adviser_subquery = (
        db.session.query(
            ResearchOutput.research_id,
            func.json_build_object(
                'name', func.concat(
                    ResearchOutput.adviser_first_name,
                    ' ',
                    # Add period after middle name if present
                    case(
                        (func.coalesce(ResearchOutput.adviser_middle_name, '') != '', 
                         func.concat(ResearchOutput.adviser_middle_name, '. ')),
                        else_=''
                    ),
                    ResearchOutput.adviser_last_name,
                    # Add space before suffix only if present
                    case(
                        (func.coalesce(ResearchOutput.adviser_suffix, '') != '', 
                         func.concat(' ', ResearchOutput.adviser_suffix)),
                        else_=''
                    )
                )
            ).label('adviser_info')
        )
    ).subquery()

    # Add this new subquery with the existing subqueries
    research_areas_subquery = db.session.query(
        ResearchOutput.research_id,
        func.array_agg(
            func.json_build_object(
                'research_area_id', ResearchArea.research_area_id,
                'research_area_name', ResearchArea.research_area_name
            )
        ).label('research_areas_array')
    ).join(ResearchOutputArea, ResearchOutput.research_id == ResearchOutputArea.research_id) \
     .join(ResearchArea, ResearchOutputArea.research_area_id == ResearchArea.research_area_id) \
     .group_by(ResearchOutput.research_id).subquery()
    
    # Define subquery for AggrUserEngagement aggregation
    aggr_engagement_subquery = db.session.query(
        AggrUserEngagement.research_id,
        func.sum(AggrUserEngagement.total_views).label("total_aggr_views"),
        func.sum(AggrUserEngagement.total_downloads).label("total_aggr_downloads")
    ).group_by(AggrUserEngagement.research_id).distinct().subquery()

    # Define subquery for Engagement aggregation
    engagement_subquery = db.session.query(
        UserEngagement.research_id,
        func.sum(UserEngagement.view).label("total_views"),
        func.sum(UserEngagement.download).label("total_downloads")
    ).group_by(UserEngagement.research_id).distinct().subquery()

    # Join the two subqueries and calculate the combined totals
    combined_engagement_subquery = db.session.query(
        engagement_subquery.c.research_id,
        (func.coalesce(engagement_subquery.c.total_views, 0) + 
        func.coalesce(aggr_engagement_subquery.c.total_aggr_views, 0)).label("combined_total_views"),
        (func.coalesce(engagement_subquery.c.total_downloads, 0) + 
        func.coalesce(aggr_engagement_subquery.c.total_aggr_downloads, 0)).label("combined_total_downloads")
    ).outerjoin(
        aggr_engagement_subquery, 
        engagement_subquery.c.research_id == aggr_engagement_subquery.c.research_id
    ).subquery()


    query = db.session.query(
        College.college_id,
        College.college_name,
        Program.program_id,
        Program.program_name,
        sdg_subquery.c.concatenated_sdg,
        ResearchOutput.research_id,
        ResearchOutput.title,
        ResearchOutput.abstract,
        ResearchOutput.full_manuscript,
        ResearchOutput.extended_abstract,
        combined_engagement_subquery.c.combined_total_views,
        combined_engagement_subquery.c.combined_total_downloads,
        panels_subquery.c.panels_array,
        ResearchOutput.school_year,
        ResearchOutput.term,
        ResearchTypes.research_type_name,
        authors_subquery.c.authors_array,
        keywords_subquery.c.keywords_array,
        PublicationFormat.pub_format_name,
        Publication.date_published,
        Publication.scopus,
        Conference.conference_venue,
        Conference.conference_title,
        Conference.conference_date,
        latest_status_subquery.c.status,
        latest_status_subquery.c.timestamp,
        adviser_subquery.c.adviser_info,
        research_areas_subquery.c.research_areas_array,
        ResearchOutput.date_uploaded
    ).join(College, ResearchOutput.college_id == College.college_id) \
    .join(Program, ResearchOutput.program_id == Program.program_id) \
    .outerjoin(Publication, ResearchOutput.research_id == Publication.research_id) \
    .outerjoin(Conference, Publication.conference_id == Conference.conference_id) \
    .outerjoin(latest_status_subquery, (Publication.publication_id == latest_status_subquery.c.publication_id) & (latest_status_subquery.c.rn == 1)) \
    .outerjoin(authors_subquery, ResearchOutput.research_id == authors_subquery.c.research_id) \
    .outerjoin(keywords_subquery, ResearchOutput.research_id == keywords_subquery.c.research_id) \
    .outerjoin(panels_subquery, ResearchOutput.research_id == panels_subquery.c.research_id) \
    .outerjoin(sdg_subquery, ResearchOutput.research_id == sdg_subquery.c.research_id) \
    .outerjoin(adviser_subquery, ResearchOutput.research_id == adviser_subquery.c.research_id) \
    .outerjoin(research_areas_subquery, ResearchOutput.research_id == research_areas_subquery.c.research_id) \
    .outerjoin(ResearchTypes, ResearchOutput.research_type_id == ResearchTypes.research_type_id) \
    .outerjoin(PublicationFormat, Publication.pub_format_id == PublicationFormat.pub_format_id) \
    .outerjoin(combined_engagement_subquery, ResearchOutput.research_id == combined_engagement_subquery.c.research_id) \
    .order_by(desc(ResearchOutput.date_uploaded))

    #filter by research_id if provided
    if research_id:
        query = query.filter(ResearchOutput.research_id == research_id)

    result = query.all()

    # Formatting results into a list of dictionaries
    data = [{
        'abstract': row.abstract,
        'college_name': row.college_name if pd.notnull(row.college_name) else 'Unknown',
        'college_id': row.college_id if pd.notnull(row.college_id) else 'Unknown',
        'program_name': row.program_name if pd.notnull(row.program_name) else 'N/A',
        'program_id': row.program_id if pd.notnull(row.program_id) else None,
        'research_id': row.research_id,
        'title': row.title if pd.notnull(row.title) else 'Untitled',
        'full_manuscript': row.full_manuscript,
        'extended_abstract': row.extended_abstract,
        'year': row.school_year if pd.notnull(row.school_year) else None,
        'term': row.term if pd.notnull(row.term) else None,
        'view_count': row.combined_total_views if pd.notnull(row.combined_total_views) else '0',
        'download_count': row.combined_total_downloads if pd.notnull(row.combined_total_downloads) else '0',
        'authors': row.authors_array if row.authors_array else [],
        'keywords': row.keywords_array if row.keywords_array else [],
        'panels': row.panels_array if row.panels_array else [],
        'sdg': row.concatenated_sdg if pd.notnull(row.concatenated_sdg) else 'Not Specified',
        'research_type': row.research_type_name if pd.notnull(row.research_type_name) else 'Unknown Type',
        'journal': row.pub_format_name if pd.notnull(row.pub_format_name) else 'unpublished',
        'scopus': row.scopus if pd.notnull(row.scopus) else 'N/A',
        'date_published': row.date_published,
        'published_year': int(row.date_published.year) if pd.notnull(row.date_published) else None,
        'conference_venue': row.conference_venue if pd.notnull(row.conference_venue) else 'Unknown Venue',
        'conference_title': row.conference_title if pd.notnull(row.conference_title) else 'No Conference Title',
        'conference_date': row.conference_date,
        'status': row.status if pd.notnull(row.status) else "READY",
        'timestamp': row.timestamp if pd.notnull(row.status) else "N/A",
        'country': row.conference_venue.split(",")[-1].strip() if pd.notnull(row.conference_venue) else 'Unknown Country',
        'adviser': {
            'name': row.adviser_info['name'] if row.adviser_info is not None else None
        } if row.adviser_info is not None else {
            'name': None,
        },
        'research_areas': row.research_areas_array if row.research_areas_array else [],
    } for row in result]

    return jsonify({"dataset": [dict(row) for row in data]})

@dataset.route('/fetch_date_range', methods=['GET'])
@jwt_required()
def fetch_date_range():
    # Query to get the min and max year
    result = db.session.query(
        func.min(ResearchOutput.school_year).label('min_year'),
        func.max(ResearchOutput.school_year).label('max_year')
    ).one()

    # Prepare the result as a JSON object
    response = {
        "min_year": int(result.min_year) if result.min_year else None,  # Convert to int if not None
        "max_year": int(result.max_year) if result.max_year else None   # Convert to int if not None
    }

    # Return as a JSON response
    return jsonify({"date_range": response})
