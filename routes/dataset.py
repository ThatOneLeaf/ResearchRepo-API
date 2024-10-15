# dataset.py code (modified to include Keyword)
# created by Nicole Cabansag (Oct. 7, 2024)

from flask import Blueprint, jsonify
from sqlalchemy import func, desc
import pandas as pd
from models import College, Program, ResearchOutput, Publication, Status, Conference, ResearchOutputAuthor, Account, UserProfile, Keywords, Panel, SDG, db

dataset = Blueprint('dataset', __name__)

@dataset.route('/fetch_dataset', methods=['GET'])
def retrieve_dataset():
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
    
    adviser_subquery = db.session.query(
        ResearchOutput.research_id,
        func.concat(
            UserProfile.first_name,
            ' ',
            func.coalesce(UserProfile.middle_name, ''),
            ' ',
            UserProfile.last_name,
            ' ',
            func.coalesce(UserProfile.suffix, '')
        ).label('adviser_name')
    ).join(Account, ResearchOutput.adviser_id == Account.user_id) \
     .join(UserProfile, Account.user_id == UserProfile.researcher_id) \
     .group_by(ResearchOutput.research_id, UserProfile.first_name, UserProfile.middle_name, UserProfile.last_name, UserProfile.suffix).subquery()
    
    # Adjusted panels_subquery
    panels_subquery = db.session.query(
        Panel.research_id,
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
        ).label('concatenated_panels')
    ).join(Account, Panel.panel_id == Account.user_id) \
     .join(UserProfile, Account.user_id == UserProfile.researcher_id) \
     .group_by(Panel.research_id).subquery()

    # Subquery to concatenate keywords
    keywords_subquery = db.session.query(
        Keywords.research_id,
        func.string_agg(Keywords.keyword, '; ').label('concatenated_keywords')
    ).group_by(Keywords.research_id).subquery()

    # Subquery to concatenate sdg
    sdg_subquery = db.session.query(
        SDG.research_id,
        func.string_agg(SDG.sdg, '; ').label('concatenated_sdg')
    ).group_by(SDG.research_id).subquery()

    # Main query
    query = db.session.query(
        College.college_id,
        Program.program_id,
        Program.program_name,
        sdg_subquery.c.concatenated_sdg,
        ResearchOutput.research_id,
        ResearchOutput.title,
        adviser_subquery.c.adviser_name,
        panels_subquery.c.concatenated_panels,
        ResearchOutput.date_approved,
        ResearchOutput.research_type,
        authors_subquery.c.concatenated_authors,
        keywords_subquery.c.concatenated_keywords,
        Publication.journal,
        Publication.date_published,
        Publication.scopus,
        Conference.conference_venue,
        Conference.conference_title,
        Conference.conference_date,
        latest_status_subquery.c.status,
        latest_status_subquery.c.timestamp,
    ).join(College, ResearchOutput.college_id == College.college_id) \
     .join(Program, ResearchOutput.program_id == Program.program_id) \
     .outerjoin(Publication, ResearchOutput.research_id == Publication.research_id) \
     .outerjoin(Conference, Publication.conference_id == Conference.conference_id) \
     .outerjoin(latest_status_subquery, (Publication.publication_id == latest_status_subquery.c.publication_id) & (latest_status_subquery.c.rn == 1)) \
     .outerjoin(authors_subquery, ResearchOutput.research_id == authors_subquery.c.research_id) \
     .outerjoin(keywords_subquery, ResearchOutput.research_id == keywords_subquery.c.research_id) \
     .outerjoin(adviser_subquery, ResearchOutput.research_id == adviser_subquery.c.research_id) \
     .outerjoin(panels_subquery, ResearchOutput.research_id == panels_subquery.c.research_id) \
     .outerjoin(sdg_subquery, ResearchOutput.research_id ==  sdg_subquery.c.research_id)

    result = query.all()

    # Formatting results into a list of dictionaries
    data = [{
                'college_id': row.college_id if pd.notnull(row.college_id) else 'Unknown',
                'program_name': row.program_name if pd.notnull(row.program_name) else 'N/A',
                'program_id': row.program_id if pd.notnull(row.program_id) else None,
                'research_id': row.research_id,
                'title': row.title if pd.notnull(row.title) else 'Untitled',
                'year': row.date_approved.year if pd.notnull(row.date_approved) else None,
                'date_approved': row.date_approved,
                'concatenated_authors': row.concatenated_authors if pd.notnull(row.concatenated_authors) else 'Unknown Authors',
                'concatenated_keywords': row.concatenated_keywords if pd.notnull(row.concatenated_keywords) else 'No Keywords',
                'sdg': row.concatenated_sdg if pd.notnull(row.concatenated_sdg) else 'Not Specified',
                'research_type': row.research_type if pd.notnull(row.research_type) else 'Unknown Type',
                'journal': row.journal if pd.notnull(row.journal) else 'unpublished',
                'scopus': row.scopus if pd.notnull(row.scopus) else 'N/A',
                'date_published': row.date_published,
                'published_year': int(row.date_published.year) if pd.notnull(row.date_published) else None,
                'conference_venue': row.conference_venue if pd.notnull(row.conference_venue) else 'Unknown Venue',
                'conference_title': row.conference_title if pd.notnull(row.conference_title) else 'No Conference Title',
                'conference_date': row.conference_date,
                'status': row.status if pd.notnull(row.status) else "READY",
                'timestamp': row.timestamp,
                'country': row.conference_venue.split(",")[-1].strip() if pd.notnull(row.conference_venue) else 'Unknown Country'
            } for row in result]

    return jsonify({"dataset": [dict(row) for row in data]})

@dataset.route('/fetch_researches/<college_dept>', methods=['PUT'])
def retrieve_dataset_by_dept(college_dept):
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
    
    adviser_subquery = db.session.query(
        ResearchOutput.research_id,
        func.concat(
            UserProfile.first_name,
            ' ',
            func.coalesce(UserProfile.middle_name, ''),
            ' ',
            UserProfile.last_name,
            ' ',
            func.coalesce(UserProfile.suffix, '')
        ).label('adviser_name')
    ).join(Account, ResearchOutput.adviser_id == Account.user_id) \
     .join(UserProfile, Account.user_id == UserProfile.researcher_id) \
     .group_by(ResearchOutput.research_id, UserProfile.first_name, UserProfile.middle_name, UserProfile.last_name, UserProfile.suffix).subquery()
    
    # Adjusted panels_subquery
    panels_subquery = db.session.query(
        Panel.research_id,
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
        ).label('concatenated_panels')
    ).join(Account, Panel.panel_id == Account.user_id) \
     .join(UserProfile, Account.user_id == UserProfile.researcher_id) \
     .group_by(Panel.research_id).subquery()

    # Subquery to concatenate keywords
    keywords_subquery = db.session.query(
        Keywords.research_id,
        func.string_agg(Keywords.keyword, '; ').label('concatenated_keywords')
    ).group_by(Keywords.research_id).subquery()

    # Subquery to concatenate sdg
    sdg_subquery = db.session.query(
        SDG.research_id,
        func.string_agg(SDG.sdg, '; ').label('concatenated_sdg')
    ).group_by(SDG.research_id).subquery()

    # Main query with filtering and sorting
    query = db.session.query(
        College.college_id,
        Program.program_id,
        Program.program_name,
        sdg_subquery.c.concatenated_sdg,
        ResearchOutput.research_id,
        ResearchOutput.title,
        adviser_subquery.c.adviser_name,
        panels_subquery.c.concatenated_panels,
        ResearchOutput.date_approved,
        ResearchOutput.research_type,
        authors_subquery.c.concatenated_authors,
        keywords_subquery.c.concatenated_keywords,
        Publication.journal,
        Publication.date_published,
        Publication.scopus,
        Conference.conference_venue,
        Conference.conference_title,
        Conference.conference_date,
        latest_status_subquery.c.status,
        latest_status_subquery.c.timestamp,
    ).join(College, ResearchOutput.college_id == College.college_id) \
     .join(Program, ResearchOutput.program_id == Program.program_id) \
     .outerjoin(Publication, ResearchOutput.research_id == Publication.research_id) \
     .outerjoin(Conference, Publication.conference_id == Conference.conference_id) \
     .outerjoin(latest_status_subquery, (Publication.publication_id == latest_status_subquery.c.publication_id) & (latest_status_subquery.c.rn == 1)) \
     .outerjoin(authors_subquery, ResearchOutput.research_id == authors_subquery.c.research_id) \
     .outerjoin(keywords_subquery, ResearchOutput.research_id == keywords_subquery.c.research_id) \
     .outerjoin(adviser_subquery, ResearchOutput.research_id == adviser_subquery.c.research_id) \
     .outerjoin(panels_subquery, ResearchOutput.research_id == panels_subquery.c.research_id) \
     .outerjoin(sdg_subquery, ResearchOutput.research_id == sdg_subquery.c.research_id) \
     .filter(College.college_id == college_dept) \
     .order_by(desc(ResearchOutput.date_approved))  # Order by date_approved descending

    result = query.all()

    # Formatting results into a list of dictionaries
    data = [{
                'college_id': row.college_id if pd.notnull(row.college_id) else 'Unknown',
                'program_name': row.program_name if pd.notnull(row.program_name) else 'N/A',
                'program_id': row.program_id if pd.notnull(row.program_id) else None,
                'research_id': row.research_id,
                'title': row.title if pd.notnull(row.title) else 'Untitled',
                'year': row.date_approved.year if pd.notnull(row.date_approved) else None,
                'date_approved': row.date_approved,
                'concatenated_authors': row.concatenated_authors if pd.notnull(row.concatenated_authors) else 'Unknown Authors',
                'concatenated_keywords': row.concatenated_keywords if pd.notnull(row.concatenated_keywords) else 'No Keywords',
                'sdg': row.concatenated_sdg if pd.notnull(row.concatenated_sdg) else 'Not Specified',
                'research_type': row.research_type if pd.notnull(row.research_type) else 'Unknown Type',
                'journal': row.journal if pd.notnull(row.journal) else 'unpublished',
                'scopus': row.scopus if pd.notnull(row.scopus) else 'N/A',
                'date_published': row.date_published,
                'published_year': int(row.date_published.year) if pd.notnull(row.date_published) else None,
                'conference_venue': row.conference_venue if pd.notnull(row.conference_venue) else 'Unknown Venue',
                'conference_title': row.conference_title if pd.notnull(row.conference_title) else 'No Conference Title',
                'conference_date': row.conference_date,
                'status': row.status if pd.notnull(row.status) else "READY",
                'timestamp': row.timestamp,
                'country': row.conference_venue.split(",")[-1].strip() if pd.notnull(row.conference_venue) else 'Unknown Country'
            } for row in result]

    return jsonify({"dataset": [dict(row) for row in data]})