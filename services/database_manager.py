import pandas as pd
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, func, desc
from models import College, Program, ResearchOutput, Publication, Status, Conference, ResearchOutputAuthor, Account, UserProfile, Keywords, SDG, ResearchArea, ResearchOutputArea, ResearchTypes, PublicationFormat, UserEngagement
from services.data_fetcher import ResearchDataFetcher
from collections import Counter
import re
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk import pos_tag

nltk.download('punkt')
nltk.download('stopwords')
nltk.download('averaged_perceptron_tagger')
nltk.download('averaged_perceptron_tagger_eng')
nltk.download('punkt_tab')

class DatabaseManager:
    def __init__(self, database_uri):
        self.engine = create_engine(database_uri)
        self.Session = sessionmaker(bind=self.engine)
        self.df = None
        self.stop_words = set(stopwords.words('english'))

        self.get_all_data()

    def get_data_from_model(self,model):
        fetcher = ResearchDataFetcher(model)
        data = fetcher.get_data_from_model()
        return data

    def get_all_data(self):
        session = self.Session()
        try:
            # Subquery to get the latest status for each publication
            latest_status_subquery = session.query(
                Status.publication_id,
                Status.status,
                func.row_number().over(
                    partition_by=Status.publication_id,
                    order_by=desc(Status.timestamp)
                ).label('rn')
            ).subquery()

            # Subquery to concatenate authors
            authors_subquery = session.query(
                ResearchOutputAuthor.research_id,
                func.string_agg(
                    func.concat(
                        ResearchOutputAuthor.author_last_name, ', ',  # Surname first
                        func.substring(ResearchOutputAuthor.author_first_name, 1, 1), '. ',  # First name initial
                        func.coalesce(func.substring(ResearchOutputAuthor.author_middle_name, 1, 1) + '.', '') 
                    ), '; '
                ).label('concatenated_authors')
            ).group_by(ResearchOutputAuthor.research_id).subquery()

            # Subquery to concatenate keywords
            keywords_subquery = session.query(
                Keywords.research_id,
                func.string_agg(Keywords.keyword, '; ').label('concatenated_keywords')
            ).group_by(Keywords.research_id).subquery()

            # Subquery to concatenate SDG
            sdg_subquery = session.query(
                SDG.research_id,
                func.string_agg(SDG.sdg, '; ').label('concatenated_sdg')
            ).group_by(SDG.research_id).subquery()

            # Subquery to get the research areas for each publication
            area_subquery = session.query(
                ResearchOutputArea.research_id,
                func.string_agg(
                    func.concat(
                        ResearchArea.research_area_name), '; '
                ).label('concatenated_areas')
            ).join(ResearchArea, ResearchOutputArea.research_area_id == ResearchArea.research_area_id) \
            .group_by(ResearchOutputArea.research_id).subquery()

            agg_user_engage = session.query(
                UserEngagement.research_id,
                func.sum(UserEngagement.view).label('sum_views'),
                func.count(func.distinct(UserEngagement.user_id)).label('distinct_user_ids'),
                func.sum(UserEngagement.download).label('sum_downloads')
            ).group_by(
                UserEngagement.research_id
            ).subquery()

            # Main query
            query = session.query(
                College.college_id,
                College.color_code,
                Program.program_id,
                Program.program_name,
                sdg_subquery.c.concatenated_sdg,
                ResearchOutput.research_id,
                ResearchOutput.title,
                ResearchOutput.school_year,
                ResearchOutput.term,
                ResearchOutput.date_uploaded,
                ResearchTypes.research_type_name,
                authors_subquery.c.concatenated_authors,
                keywords_subquery.c.concatenated_keywords,
                Publication.publication_name,
                PublicationFormat.pub_format_name,
                Publication.scopus,
                Publication.date_published,
                Conference.conference_venue,
                Conference.conference_title,
                Conference.conference_date,
                latest_status_subquery.c.status,
                area_subquery.c.concatenated_areas,
                ResearchOutput.abstract,
                agg_user_engage.c.sum_views,
                agg_user_engage.c.distinct_user_ids,
                agg_user_engage.c.sum_downloads,
            ).join(College, ResearchOutput.college_id == College.college_id) \
            .join(Program, ResearchOutput.program_id == Program.program_id) \
            .outerjoin(Publication, ResearchOutput.research_id == Publication.research_id) \
            .outerjoin(Conference, Publication.conference_id == Conference.conference_id) \
            .outerjoin(latest_status_subquery, (Publication.publication_id == latest_status_subquery.c.publication_id) & (latest_status_subquery.c.rn == 1)) \
            .outerjoin(authors_subquery, ResearchOutput.research_id == authors_subquery.c.research_id) \
            .outerjoin(keywords_subquery, ResearchOutput.research_id == keywords_subquery.c.research_id) \
            .outerjoin(sdg_subquery, ResearchOutput.research_id == sdg_subquery.c.research_id) \
            .outerjoin(area_subquery, ResearchOutput.research_id == area_subquery.c.research_id) \
            .outerjoin(ResearchTypes, ResearchOutput.research_type_id == ResearchTypes.research_type_id) \
            .outerjoin(PublicationFormat, Publication.pub_format_id == PublicationFormat.pub_format_id) \
            .outerjoin(agg_user_engage, agg_user_engage.c.research_id == ResearchOutput.research_id)

            result = query.all()

            # Add this check for empty results
            if not result:
                print("Warning: Query returned no results. Creating empty DataFrame.")
                # Create an empty DataFrame with all expected columns
                columns = ['research_id', 'college_id', 'color_code', 'program_name', 'program_id', 
                           'title', 'school_year', 'term', 'date_uploaded', 'research_type_name', 
                           'concatenated_authors', 'concatenated_keywords', 'publication_name',
                           'pub_format_name', 'scopus', 'date_published', 'conference_venue',
                           'conference_title', 'conference_date', 'status', 'concatenated_areas',
                           'abstract', 'sum_views', 'distinct_user_ids', 'sum_downloads']
                
                self.df = pd.DataFrame(columns=columns)
                self.df['combined'] = ''  # Add empty combined column
                self.df['top_nouns'] = [[]]  # Add empty top_nouns column
                return

            # Formatting results into a list of dictionaries with safe handling for missing data
            data = [{
                'research_id': row.research_id if pd.notnull(row.research_id) else 'Unknown',
                'college_id': row.college_id if pd.notnull(row.college_id) else 'Unknown',
                'color_code': row.color_code if pd.notnull(row.color_code) else '#000',
                'program_name': row.program_name if pd.notnull(row.program_name) else 'N/A',
                'program_id': row.program_id if pd.notnull(row.program_id) else None,
                'title': row.title if pd.notnull(row.title) else 'Untitled',
                'year': row.school_year if pd.notnull(row.school_year) else None,
                'term': row.term if pd.notnull(row.term) else None,
                'concatenated_authors': row.concatenated_authors if pd.notnull(row.concatenated_authors) else 'Unknown Authors',
                'concatenated_keywords': row.concatenated_keywords if pd.notnull(row.concatenated_keywords) else 'No Keywords',
                'sdg': row.concatenated_sdg if pd.notnull(row.concatenated_sdg) else 'Not Specified',
                'research_type': row.research_type_name if pd.notnull(row.research_type_name) else 'Unknown Type',
                'journal': row.pub_format_name if pd.notnull(row.pub_format_name) else 'unpublished',
                'scopus': row.scopus if pd.notnull(row.scopus) else 'N/A',
                'date_published': row.date_published,
                'date_uploaded': row.date_uploaded,
                'published_year': int(row.date_published.year) if pd.notnull(row.date_published) else None,
                'conference_venue': row.conference_venue if pd.notnull(row.conference_venue) else 'Unknown Venue',
                'conference_title': row.conference_title if pd.notnull(row.conference_title) else 'No Conference Title',
                'conference_date': row.conference_date,
                'status': row.status if pd.notnull(row.status) else "READY",
                'country': row.conference_venue.split(",")[-1].strip() if pd.notnull(row.conference_venue) else 'Unknown Country',
                'abstract': row.abstract if pd.notnull(row.abstract) else '',
                'concatenated_areas': row.concatenated_areas if pd.notnull(row.concatenated_areas) else 'No Research Areas',
                'views': row.sum_views,
                'downloads': row.sum_downloads,
                'unique_views':row.distinct_user_ids

            } for row in result]

            # Convert the list of dictionaries to a DataFrame
            self.df = pd.DataFrame(data)
            # Combine the title and concatenated_keywords columns
            self.df['combined'] = self.df['title'].astype(str) + ' ' + self.df['concatenated_keywords'].astype(str) + ' ' + self.df['abstract'].astype(str)

            # Apply the function to extract top nouns
            self.df['top_nouns'] = self.df['combined'].apply(lambda x: self.top_nouns(x, 10))

        finally:
            session.close()

        return self.df
    
    def get_college_colors(self):
        session = self.Session()
        
        query = session.query(College.college_id, College.color_code)
        colleges = query.all()

        # Convert the list of tuples into a dictionary
        college_colors = {college_id: color_code for college_id, color_code in colleges}
    
        return college_colors

    def get_unique_values(self, column_name):
        if self.df is not None and column_name in self.df.columns:
            unique_values = self.df[column_name].dropna().unique()
            if len(unique_values) == 0:
                print(f"Warning: Column '{column_name}' exists but contains no values.")
            return unique_values
        else:
            return []  # Return an empty list if the column doesn't exist or has no values

    def get_unique_values_by(self, target_column, filter_column, filter_value):
        """Get unique values from target_column where filter_column equals filter_value"""
        if not hasattr(self, 'df') or self.df is None:
            self.get_all_data()
            
        # Filter the dataframe
        filtered_df = self.df[self.df[filter_column] == filter_value]
        
        # Get unique values from the target column
        unique_values = filtered_df[target_column].unique().tolist()
        
        return unique_values

    def get_columns(self):
        return self.df.columns.tolist() if self.df is not None else []

    def filter_data(self, column_name1, value1, column_name2=None, value2=None, invert=False):
        if self.df is not None:
            if column_name1 in self.df.columns and (column_name2 is None or column_name2 in self.df.columns):
                if column_name2 is None:
                    # Single column filter
                    if invert:
                        return self.df[self.df[column_name1] != value1]
                    else:
                        return self.df[self.df[column_name1] == value1]
                else:
                    # Two-column filter
                    if invert:
                        return self.df[(self.df[column_name1] != value1) | (self.df[column_name2] != value2)]
                    else:
                        return self.df[(self.df[column_name1] == value1) & (self.df[column_name2] == value2)]
            else:
                missing_column = column_name1 if column_name1 not in self.df.columns else column_name2
                raise ValueError(f"Column '{missing_column}' does not exist in the DataFrame.")
        else:
            raise ValueError("Data not loaded. Please call 'get_all_data()' first.")

    def filter_data_by_list(self, column_name, values, invert=False):
        if self.df is not None:
            if column_name in self.df.columns:
                if invert:
                    return self.df[~self.df[column_name].isin(values)]
                else:
                    return self.df[self.df[column_name].isin(values)]
            else:
                raise ValueError(f"Column '{column_name}' does not exist in the DataFrame.")
        else:
            raise ValueError("Data not loaded. Please call 'get_all_data()' first.")

    def get_min_value(self, column_name):
        if self.df is not None and column_name in self.df.columns:
            return self.df[column_name].min()
        else:
            raise ValueError(f"Column '{column_name}' does not exist in the DataFrame.")

    def get_max_value(self, column_name):
        if self.df is not None and column_name in self.df.columns:
            return self.df[column_name].max()
        else:
            raise ValueError(f"Column '{column_name}' does not exist in the DataFrame.")

    def get_filtered_data(self, selected_colleges, selected_status, selected_years):
        if self.df is not None:
            filtered_df = self.df[
                (self.df['college_id'].isin(selected_colleges)) & 
                (self.df['status'].isin(selected_status)) & 
                (self.df['year'].between(selected_years[0], selected_years[1]))
            ]
            return filtered_df
        else:
            raise ValueError("Data not loaded. Please call 'get_all_data()' first.")
        
    def get_filtered_data_with_term(self, selected_colleges, selected_status, selected_years, selected_terms):
        if self.df is not None:
            filtered_df = self.df[
                (self.df['college_id'].isin(selected_colleges)) & 
                (self.df['status'].isin(selected_status)) & 
                (self.df['term'].isin(selected_terms)) & 
                (self.df['year'].between(selected_years[0], selected_years[1]))
            ]
            return filtered_df
        else:
            raise ValueError("Data not loaded. Please call 'get_all_data()' first.")
    
    def get_filtered_data_bycollege(self, selected_program, selected_status, selected_years):
        if self.df is not None:
            filtered_df = self.df[
                (self.df['program_id'].isin(selected_program)) & 
                (self.df['status'].isin(selected_status)) & 
                (self.df['year'].between(selected_years[0], selected_years[1]))
            ]
            print("Filtered by program:",filtered_df)
            return filtered_df
        else:
            raise ValueError("Data not loaded. Please call 'get_all_data()' first.")
        
    def get_filtered_data_text_display(self, selected_colleges, selected_status, selected_years, selected_terms):
        if self.df is not None:
            filtered_df = self.df[
                (self.df['college_id'].isin(selected_colleges)) & 
                (self.df['status'].isin(selected_status)) & 
                (self.df['term'].isin(selected_terms)) & 
                (self.df['year'].between(selected_years[0], selected_years[1]))
            ]
            print("Filtered by program:",filtered_df)
            return filtered_df
        else:
            raise ValueError("Data not loaded. Please call 'get_all_data()' first.")
        
    def get_filtered_data_bycollege_text_display(self, selected_programs, selected_status, selected_years, selected_terms):
        if self.df is not None:
            filtered_df = self.df[
                (self.df['program_id'].isin(selected_programs)) & 
                (self.df['status'].isin(selected_status)) & 
                (self.df['term'].isin(selected_terms)) & 
                (self.df['year'].between(selected_years[0], selected_years[1]))
            ]
            #print("Filtered by program:",filtered_df)
            return filtered_df
        else:
            raise ValueError("Data not loaded. Please call 'get_all_data()' first.")
        
    def get_filtered_data_bycollege_with_term(self, selected_program, selected_status, selected_years, selected_terms):
        if self.df is not None:
            filtered_df = self.df[
                (self.df['program_id'].isin(selected_program)) & 
                (self.df['status'].isin(selected_status)) & 
                (self.df['term'].isin(selected_terms)) & 
                (self.df['year'].between(selected_years[0], selected_years[1]))
            ]
            print("Filtered by program:",filtered_df)
            return filtered_df
        else:
            raise ValueError("Data not loaded. Please call 'get_all_data()' first.")
        
    def top_nouns(self,text, top_n=10):
        # Remove punctuation using regex
        text = re.sub(r'[^\w\s]', '', text)  # This removes punctuation (e.g. % / \ < > etc.)

        # Tokenize the text
        words = word_tokenize(text.lower())  # Tokenize and convert to lowercase

        # Remove stopwords and words with less than 3 letters
        words = [word for word in words if word not in self.stop_words and len(word) >= 3]

        # Get part-of-speech tags for the words
        pos_tags = pos_tag(words)

        # Filter for nouns (NN, NNS, NNP, NNPS)
        nouns = [word for word, tag in pos_tags if tag in ['NN', 'NNS', 'NNP', 'NNPS']]

        # Count the occurrences of the nouns
        word_counts = Counter(nouns)
        top_n_words = word_counts.most_common(top_n)

        # Convert the top_n_words to a nested list format [noun, count]
        top_n_words_nested = [word for word, _ in top_n_words]

        return top_n_words_nested # Return the top n most common nouns as a nested list
    

    def get_words(self,selected_colleges, selected_status, selected_years):
        if self.df is not None:
            df_copy = self.df.copy()

            
            filtered_df = df_copy[
                (df_copy['college_id'].isin(selected_colleges)) & 
                (df_copy['status'].isin(selected_status)) & 
                (df_copy['year'].between(selected_years[0], selected_years[1]))
            ]
            return filtered_df
        else:
            raise ValueError("Data not loaded. Please call 'get_all_data()' first.")

        
