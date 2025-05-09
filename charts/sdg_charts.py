from database.sdg_queries import get_research_count, get_research_percentage, get_research_type_distribution, get_geographical_distribution,get_conference_participation,get_local_vs_foreign_participation,get_research_with_keywords,get_research_area_data, get_sdg_research,count_sdg_impact,get_proceeding_research
import pandas as pd
import plotly.express as px
from services.sdg_colors import sdg_colors
from dashboards import db_manager
from models import ResearchTypes
import numpy as np
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from nltk.tokenize import word_tokenize
import base64
from io import BytesIO
import dash_html_components as html
import plotly.graph_objects as go
import networkx as nx
from dashboards.usable_methods import get_gradient_color
from config import stop_words,lemmatizer
from collections import Counter
from nltk.tag import pos_tag

import pandas as pd
import plotly.express as px
import numpy as np

def create_sdg_plot(selected_colleges, selected_status, selected_years, sdg_dropdown_value, selected_pub_form):
    all_sdgs = [f'SDG {i}' for i in range(1, 18)]
    
    print("Selected SDG:", sdg_dropdown_value)

    selected_colleges = selected_colleges.tolist() if isinstance(selected_colleges, np.ndarray) else [selected_colleges]
    selected_status = selected_status.tolist() if isinstance(selected_status, np.ndarray) else [selected_status]
    max_year = max(selected_years)  # Ensure graph extends to the latest selected year

    research_data = get_research_count(
        start_year=min(selected_years)-1,
        end_year=max_year,
        sdg_filter=[sdg_dropdown_value] if sdg_dropdown_value != "ALL" else None,
        status_filter=selected_status,
        pub_format_filter=selected_pub_form,
        college_filter=selected_colleges
    )

    print("Query Parameters:", {
        "Start Year": min(selected_years),
        "End Year": max_year,
        "SDG Filter": sdg_dropdown_value,
        "Status Filter": selected_status,
        "Pub Filter": selected_pub_form,
        "College Filter": selected_colleges
    })

    df = pd.DataFrame(research_data)
    print("Unique SDGs in Data:", df['school_year'].unique() if not df.empty else "No data")

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            x=0.5, y=0.5,
            xref="paper", yref="paper",
            showarrow=False,
            font=dict(size=20, color="gray")
        )
        fig.update_layout(
            title="Research Output Over Time",
            template="plotly_white",
            height=350, width=650,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            margin=dict(l=10, r=10, t=30, b=10)
        )


        return fig

    df.rename(columns={'research_count': 'Count', 'sdg': 'sdg', 'school_year': 'school_year', 'college_id': 'College'}, inplace=True)
    df.sort_values(by='school_year', inplace=True)
    # Determine the correct starting year
    # Fetch the true minimum year from the database

    # Ensure the year range is generated correctly
    all_years = list(range(min(selected_years)-1, max_year + 1))
    sdg_list = df['sdg'].unique()

    # Create a DataFrame with all SDGs and all years filled with 0
    full_range_df = pd.DataFrame([(year, sdg, 0) for year in all_years for sdg in sdg_list], columns=['school_year', 'sdg', 'Count'])

    # Merge original data, ensuring missing values are filled with 0
    df = pd.merge(full_range_df, df, on=['school_year', 'sdg'], how='left')
    print(df)
    df['Count'] = df['Count_y'].fillna(df['Count_x']).fillna(0).astype(int)
    df = df[['school_year', 'sdg', 'Count']]  # Keep only necessary columns

    # Define color map and category orders
    if sdg_dropdown_value == "ALL":
        color_map = sdg_colors
        category_orders = {'sdg': all_sdgs}
    else:
        color_map = sdg_colors
        category_orders = None

    fig = px.line(
        df,
        x='school_year',
        y='Count',
        color='sdg',
        title=f'Research Outputs Over Time{" by SDG: " + sdg_dropdown_value if sdg_dropdown_value != "ALL" else ""}',
        labels={'school_year': 'Year', 'Count': 'Number of Research Outputs', 'sdg': 'SDG'},
        color_discrete_map=color_map,
        category_orders=category_orders
    )
    fig.update_traces(
        hovertemplate="Year: %{x}<br>"
                      "Number of Research Outputs: %{y}<extra></extra>"
        )
    
    fig.update_layout(
        title_font_size=14,
        template="plotly_white",
        width=650,
        height=350,
        margin=dict(l=10, r=10, t=30, b=10),
    )

    return fig







def create_sdg_pie_chart(selected_colleges, selected_status, selected_years, sdg_dropdown_value,selected_pub_form):
    """
    Creates a pie chart showing the percentage distribution of research outputs by SDG or College.

    :param selected_colleges: List of selected colleges
    :param selected_status: List of selected statuses
    :param selected_years: List of selected school years
    :param sdg_dropdown_value: Selected SDG filter
    :return: Plotly pie chart figure
    """
    all_sdgs = [f'SDG {i}' for i in range(1, 18)]

    # Convert arrays to lists if needed
    if isinstance(selected_colleges, np.ndarray):
        selected_colleges = selected_colleges.tolist()
    if isinstance(selected_status, np.ndarray):
        selected_status = selected_status.tolist()
    
    # Fetch data based on filter
    research_data = get_research_percentage(
        start_year=min(selected_years), 
        end_year=max(selected_years),
        sdg_filter=None if sdg_dropdown_value == "ALL" else [sdg_dropdown_value],
        status_filter=selected_status,
        pub_format_filter=selected_pub_form,
        college_filter=selected_colleges
    )
    df = pd.DataFrame(research_data)

    if sdg_dropdown_value == "ALL":
        # Group by SDG if SDG filter is "ALL"
        df['sdg'] = pd.Categorical(df['sdg'], categories=all_sdgs, ordered=True)
        df = df.sort_values('sdg')

        fig = px.pie(
            df,
            names='sdg',
            values='percentage',
            title='Percentage of Research Outputs by SDG',
            labels={'sdg': 'SDG', 'percentage': 'Percentage of Total Outputs'},
            category_orders={"sdg": all_sdgs}  # Ensure legend follows all_sdgs order
            
        )
    else:
        # Group by College for distribution if SDG filter is not "ALL"
        college_distribution = df.groupby('college_id').sum().reset_index()
        college_distribution['Percentage'] = (college_distribution['research_count'] / college_distribution['research_count'].sum()) * 100
        
        fig = px.pie(
            college_distribution,
            names='college_id',
            values='Percentage',
            title='Percentage of Research Outputs by College',
            labels={'college_id': 'College', 'Percentage': 'Percentage of Total Outputs'}
        )

    fig.update_layout(
        title_font_size=14,  
        legend_title_font_size=12,  
        template="plotly_white",
        width=450,  
        height=350,  
        margin=dict(l=10, r=10, t=30, b=10),  
        uniformtext_minsize=10,  
        uniformtext_mode='hide',
        legend=dict(
            orientation="v",  # Vertical legend
            x=1.02,  # Position the legend outside on the right
            y=1,  # Align legend to the top
            yanchor="top",
            xanchor="left",
            traceorder="normal",
            itemsizing="constant",
            title_font_size=12,
            font=dict(size=10)
        ))

    return fig


def create_sdg_research_chart(selected_colleges, selected_status, selected_years, sdg_dropdown_value, selected_pub_form):
    """
    Generates a stacked bar chart showing research type distribution by SDG or by research type (depending on selection).
    
    :param selected_colleges: List of selected colleges
    :param selected_status: List of selected statuses
    :param selected_years: List of selected school years
    :param sdg_dropdown_value: Selected SDG filter
    :param selected_pub_form: List of selected publication formats
    :return: Plotly figure (stacked bar chart)
    """
    all_sdgs = [f'SDG {i}' for i in range(1, 18)]  # Ensuring SDG order

    # Convert arrays to lists if needed
    if isinstance(selected_colleges, np.ndarray):
        selected_colleges = selected_colleges.tolist()
    if isinstance(selected_status, np.ndarray):
        selected_status = selected_status.tolist()
    if isinstance(selected_pub_form, np.ndarray):
        selected_pub_form = selected_pub_form.tolist()

    types = [rt.research_type_name for rt in ResearchTypes.query_all()]

    # Fetch research type distribution from the database
    research_data = get_research_type_distribution(
        start_year=min(selected_years),
        end_year=max(selected_years),
        sdg_filter=None if sdg_dropdown_value == "ALL" else [sdg_dropdown_value],
        status_filter=selected_status,
        college_filter=selected_colleges,
        pub_format_filter=selected_pub_form  # <<< ADDED this line
    )

    # Convert to DataFrame
    df = pd.DataFrame(research_data)

    if df.empty:
        # Return a blank figure with centered text
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            x=0.5, y=0.5,
            xref="paper", yref="paper",
            showarrow=False,
            font=dict(size=20, color="gray")
        )
        fig.update_layout(
            title="Research Type Distribution by SDG",
            template="plotly_white",
            height=150, width=1200,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            margin=dict(l=10, r=10, t=30, b=10)
        )
        return fig

    # Ensure SDG and Research Type are categorical (for correct ordering)
    df['research_type_name'] = pd.Categorical(df['research_type_name'], categories=types, ordered=True)
    df['sdg'] = pd.Categorical(df['sdg'], categories=all_sdgs, ordered=True)  # Order SDGs correctly

    if sdg_dropdown_value == "ALL":
        # SDGs on x-axis, research types stacked
        fig = px.bar(
            df,
            x="sdg",
            y="research_count",
            color="research_type_name",
            title="Research Type Distribution by SDG",
            labels={"sdg": "Sustainable Development Goals (SDGs)", "research_count": "Research Count", "research_type_name": "Research Type"},
            template="plotly_white",
            color_discrete_map=sdg_colors,
            barmode="stack",
            category_orders={"sdg": all_sdgs}  # Ensures SDGs are ordered correctly
        )
        x_title = "Sustainable Development Goals (SDGs)"
        x_angle = 0  # Rotate SDG labels for readability
    else:
        # Research types on x-axis, bars grouped by SDG
        fig = px.bar(
            df,
            x="research_type_name",
            y="research_count",
            color="sdg",
            title=f"Research Type Distribution for {sdg_dropdown_value}",
            labels={"research_type_name": "Research Type", "research_count": "Research Count", "sdg": "SDG"},
            template="plotly_white",
            color_discrete_sequence=px.colors.qualitative.Safe,
            barmode="stack",
            category_orders={"sdg": all_sdgs}  # Ensures SDGs are ordered correctly
        )
        x_title = "Research Type"
        x_angle = 0  # Keep labels horizontal

    # Apply common layout settings
    fig.update_layout(
        title_font_size=14,
        width=1200,
        height=150,
        margin=dict(l=10, r=10, t=30, b=30),
        xaxis_title=x_title,
        yaxis_title="Research Count",
        xaxis=dict(tickangle=x_angle),
        showlegend=True
    )
    fig.update_traces(
        hovertemplate="Category: %{x}<br>"
                      "Research Count: %{y}<extra></extra>"
    )

    return fig




def create_geographical_heatmap(selected_colleges, selected_status, selected_years, sdg_dropdown_value):
    """
    Generates a choropleth heatmap for the geographical distribution of research outputs.

    :param start_year: Start school year (integer)
    :param end_year: End school year (integer)
    :param sdg_filter: List of SDG filters (list of strings, optional)
    :param status_filter: List of status filters (list of strings, optional)
    :param college_filter: List of college filters (list of strings, optional)
    :param program_filter: List of program filters (list of strings, optional)
    :return: Plotly figure object
    """
        # Convert arrays to lists if needed
    if isinstance(selected_colleges, np.ndarray):
        selected_colleges = selected_colleges.tolist()
    if isinstance(selected_status, np.ndarray):
        selected_status = selected_status.tolist()
    df = get_geographical_distribution(
        start_year=min(selected_years),
        end_year=max(selected_years),
        sdg_filter=None if sdg_dropdown_value == "ALL" else [sdg_dropdown_value],
        status_filter=selected_status,
        college_filter=selected_colleges)

    # Ensure df is a DataFrame
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame(df)

    if df.empty:
        # Return a blank figure with centered text
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            x=0.5, y=0.5,
            xref="paper", yref="paper",
            showarrow=False,
            font=dict(size=20, color="gray")
        )
        fig.update_layout(
            title="Geographical Distribution of Research Outputs",
            template="plotly_white",
            height=300, width=800,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            margin=dict(l=10, r=10, t=30, b=10)
        )
        return fig

    # Aggregate by country
    df_country = df.groupby('country', as_index=False)['research_count'].sum()
    fig = px.choropleth(
        df_country,
        locations="country",
        locationmode="country names",
        color="research_count",
        hover_name="country",
        hover_data={"research_count": True},
        color_continuous_scale="Viridis",
        title="Geographical Distribution of Research Outputs",
        labels={'research_count': 'Count'}
    )

    # Customize layout
    fig.update_geos(
        showcoastlines=True, coastlinecolor="Black",
        showland=True, landcolor="lightgray",
        showocean=True, oceancolor="white",
        projection_type="natural earth"
    )

    fig.update_layout(
        title_font_size=14,
        geo_scope="world",
        template="plotly_white",
        width=800,
        height=300,
        margin=dict(l=0, r=0, t=23, b=0)  # Reduce unnecessary spacing
    )
    fig.update_traces(
        hovertemplate="Country: %{hovertext}<br>"
                      "Research Count: %{z}<extra></extra>"
    )


    return fig

def create_geographical_treemap(selected_colleges, selected_status, selected_years, sdg_dropdown_value):
    """
    Generates a treemap for the geographical distribution of research outputs,
    with countries as the main category and cities as the subcategory.
    
    Only the top 10 countries with the highest research count are included.

    :param selected_colleges: List of selected colleges (list of strings)
    :param selected_status: List of selected research statuses (list of strings)
    :param selected_years: List of selected years (list of integers)
    :param sdg_dropdown_value: Selected SDG goal (string)
    :return: Plotly figure object
    """
    # Convert arrays to lists if needed
    if isinstance(selected_colleges, np.ndarray):
        selected_colleges = selected_colleges.tolist()
    if isinstance(selected_status, np.ndarray):
        selected_status = selected_status.tolist()

    # Fetch data
    df = get_geographical_distribution(
        start_year=min(selected_years),
        end_year=max(selected_years),
        sdg_filter=None if sdg_dropdown_value == "ALL" else [sdg_dropdown_value],
        status_filter=selected_status,
        college_filter=selected_colleges
    )

    # Ensure df is a DataFrame
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame(df)

    if df.empty:
        # Return a blank figure with centered text
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            x=0.5, y=0.5,
            xref="paper", yref="paper",
            showarrow=False,
            font=dict(size=20, color="gray")
        )
        fig.update_layout(
            title="Top Research Conference Locations",
            template="plotly_white",
            height=350, width=350,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            margin=dict(l=10, r=10, t=30, b=10)
        )
        return fig

    # Aggregate research count by country and city
    df_grouped = df.groupby(['country', 'city'], as_index=False)['research_count'].sum()

    # Get the top 10 countries with the highest total research count
    top_countries = (
        df_grouped.groupby('country', as_index=False)['research_count']
        .sum()
        .sort_values(by='research_count', ascending=False)
        .head(10)['country']
    )

    # Filter dataset to include only these top countries
    df_filtered = df_grouped[df_grouped['country'].isin(top_countries)]

    # Create treemap with country as the main category and city as subcategory
    fig = px.treemap(
        df_filtered,
        path=['country', 'city'],  # Main category: country, Sub-category: city
        values='research_count',
        color='research_count',
        color_continuous_scale='Viridis',
        title="Top Research Conference Locations",
        labels={'research_count': 'Count'}
    )

    fig.update_layout(
        title_font_size=14,
        template="plotly_white",
        width=350,
        height=350,
        margin=dict(l=0, r=0, t=25, b=0)  # Reduce margins to remove extra spacing
    )
    fig.update_traces(
        hovertemplate="Country: %{parent}<br>"
                      "City: %{label}<br>"
                      "Research Count: %{value}<extra></extra>"
    )

    return fig

def create_conference_participation_bar_chart(selected_colleges, selected_status, selected_years, sdg_dropdown_value):
    """
    Generates a bar chart showing the number of conference participations per year.

    :param selected_colleges: List of selected colleges (list of strings)
    :param selected_status: List of selected research statuses (list of strings)
    :param selected_years: List of selected years (list of integers)
    :param sdg_dropdown_value: Selected SDG goal (string)
    :return: Plotly figure object
    """
    # Convert arrays to lists if needed
    if isinstance(selected_colleges, np.ndarray):
        selected_colleges = selected_colleges.tolist()
    if isinstance(selected_status, np.ndarray):
        selected_status = selected_status.tolist()

    all_sdgs = [f'SDG {i}' for i in range(1, 18)]

    # Fetch data
    df = get_conference_participation(
        start_year=min(selected_years),
        end_year=max(selected_years),
        sdg_filter=None if sdg_dropdown_value == "ALL" else [sdg_dropdown_value],
        status_filter=selected_status,
        college_filter=selected_colleges
    )

    # Ensure df is a DataFrame
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame(df)

    if df.empty:
        # Return a blank figure with centered text
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            x=0.5, y=0.5,
            xref="paper", yref="paper",
            showarrow=False,
            font=dict(size=20, color="gray")
        )
        fig.update_layout(
            title="Conference Participation",
            template="plotly_white",
            height=200, width=800,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            margin=dict(l=10, r=10, t=30, b=10)
        )
        return fig

    # Determine grouping based on filters
    if sdg_dropdown_value != "ALL":
        group_column = 'college'
        tick_labels = df['college'].unique().tolist()
        
        if len(selected_colleges) == 1:
            group_column = 'program'
            tick_labels = df['program'].unique().tolist()
    else:
        group_column = 'sdg'
        tick_labels = all_sdgs

    # Aggregate participation count per chosen category
    df_grouped = df.groupby([group_column], as_index=False)['participation_count'].sum()

    # Ensure all categories are included (fill missing categories with zero participation)
    df_grouped = df_grouped.set_index(group_column).reindex(tick_labels, fill_value=0).reset_index()

    # Create a bar chart
    fig = px.bar(
        df_grouped,
        x=group_column,
        y='participation_count',
        labels={group_column: "Program" if group_column == "program" else "College" if group_column == "college" else "SDG", 'participation_count': 'Count'},
        title="Conference Participation" + (" by Program" if group_column == "program" else " by College" if group_column == "college" else " Per SDG"),
        color='participation_count',
        color_continuous_scale='Viridis'
    )

    # Improve hover text
    fig.update_traces(
        textposition='outside',
        hovertemplate="%{x}<br>Participation Count: %{y}<extra></extra>"
    )

    fig.update_layout(
        title_font_size=14,
        template="plotly_white",
        width=800,
        height=200,
        margin=dict(l=0, r=0, t=25, b=0),
        xaxis=dict(
            type='category',
            tickangle=45,  # Make x-axis labels readable
            tickmode='array',
            tickvals=tick_labels,
            ticktext=tick_labels
        ),
        yaxis_title="Participation Count"
    )

    return fig




def create_local_vs_foreign_donut_chart(selected_colleges, selected_status, selected_years, sdg_dropdown_value):
    """
    Generates a donut chart comparing local vs. foreign research proceedings.

    :param selected_colleges: List of selected colleges (list of strings)
    :param selected_status: List of selected research statuses (list of strings)
    :param selected_years: List of selected years (list of integers)
    :param sdg_dropdown_value: Selected SDG goal (string)
    :return: Plotly figure object
    """

    # Convert arrays to lists if needed
    if isinstance(selected_colleges, np.ndarray):
        selected_colleges = selected_colleges.tolist()
    if isinstance(selected_status, np.ndarray):
        selected_status = selected_status.tolist()

    # Fetch data using the function that categorizes local vs. foreign
    df = get_proceeding_research(
        start_year=min(selected_years),
        end_year=max(selected_years),
        sdg_filter=None if sdg_dropdown_value == "ALL" else [sdg_dropdown_value],
        status_filter=selected_status,
        college_filter=selected_colleges
    )

    # Ensure df is a DataFrame
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame(df, columns=['sdg', 'research_id', 'country'])

    if df.empty:
        # Return a blank figure with centered text
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            x=0.5, y=0.5,
            xref="paper", yref="paper",
            showarrow=False,
            font=dict(size=20, color="gray")
        )
        fig.update_layout(
            title="Local vs. Foreign Research Proceedings",
            template="plotly_white",
            height=150, width=350,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            margin=dict(l=10, r=10, t=30, b=10)
        )
        return fig

    # Define local countries (e.g., Philippines)
    local_countries = ['Philippines']  # Modify or expand as needed

    # Categorize each country as 'Local' or 'Foreign'
    df['location_category'] = df['country'].apply(lambda x: 'Local' if x in local_countries else 'Foreign')

    # If SDG dropdown is not "ALL", filter by the selected SDG and count unique research IDs
    if sdg_dropdown_value != "ALL":
        df = df[df['sdg'] == sdg_dropdown_value]  # Filter by selected SDG

    # Count unique research IDs for 'Local' and 'Foreign'
    location_counts = df.groupby('location_category')['research_id'].nunique().reset_index()
    location_counts.columns = ['location_category', 'research_count']

    # Create a donut chart using Plotly
    fig = px.pie(
        location_counts,
        names='location_category',
        values='research_count',
        hole=0.4,  # Creates the donut effect
        title="Local vs. Foreign Research Proceedings",
        color='location_category',
        color_discrete_map={"Local": "blue", "Foreign": "red"}  # Custom colors
    )

    fig.update_traces(
        textinfo='percent+label',
        pull=[0.05, 0],  # Slightly separate the larger slice for effect
        texttemplate="%{label}: %{value}"  # Show both count and category
    )
    fig.update_layout(
        title_font_size=14,
        template="plotly_white",
        height=150,
        width=350,
        margin=dict(l=0, r=0, t=25, b=0)
    )

    return fig





def preprocess_text(text):
    """
    Cleans and preprocesses text using tokenization, stopword removal, and lemmatization.
    """
    words = word_tokenize(text.lower())  # Tokenize and lowercase
    processed_words = [
        lemmatizer.lemmatize(word) for word in words
        if word.isalpha() and word not in stop_words  # Keep only words (no numbers/punctuation)
    ]
    return " ".join(processed_words)


def get_word_cloud(selected_colleges, selected_status, selected_years, sdg_dropdown_value, pub_format_filter=None):
    """
    Generates a word cloud from research titles, abstracts, and keywords and returns it as a Plotly Figure.
    
    :param selected_colleges: List of selected colleges (or a single value)
    :param selected_status: List of selected research statuses (or a single value)
    :param selected_years: List of selected school years
    :param sdg_dropdown_value: Selected SDG filter (string, "ALL" for no filtering)
    :param pub_format_filter: List of publication formats to filter (or None for all)
    :return: Plotly figure object
    """
    # Convert arrays to lists if needed
    if isinstance(selected_colleges, np.ndarray):
        selected_colleges = selected_colleges.tolist()
    if isinstance(selected_status, np.ndarray):
        selected_status = selected_status.tolist()

    # Fetch data using get_research_with_keywords
    data = get_research_with_keywords(
        start_year=min(selected_years),
        end_year=max(selected_years),
        sdg_filter=None if sdg_dropdown_value == "ALL" else [sdg_dropdown_value],
        status_filter=selected_status,
        college_filter=selected_colleges,
        pub_format_filter=pub_format_filter  # Add pub_format_filter here
    )

    # Convert to DataFrame if it's a list
    df = pd.DataFrame(data) if isinstance(data, list) else data

    # Check if DataFrame is empty
    if df.empty:
        # Return a blank figure with centered text
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            x=0.5, y=0.5,
            xref="paper", yref="paper",
            showarrow=False,
            font=dict(size=20, color="gray")
        )
        fig.update_layout(
            title=f"Common Topics for {sdg_dropdown_value}" if sdg_dropdown_value != "ALL" else "Common Topics for All SDGs",
            template="plotly_white",
            height=250, width=550,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            margin=dict(l=10, r=10, t=30, b=10)
        )
        return fig

    # Ensure necessary columns exist
    required_columns = ["title", "abstract", "keywords"]
    if not all(col in df.columns for col in required_columns):
        return go.Figure().update_layout(title="Missing Necessary Columns in Dataset")

    # Combine text fields
    df["Combined_Text"] = df[["title", "abstract", "keywords"]].astype(str).agg(" ".join, axis=1)

    # Convert to a single string
    text = " ".join(df["Combined_Text"].dropna())

    # Text Preprocessing
    words = word_tokenize(text.lower())  # Convert to lowercase and tokenize
    words = [word for word in words if word.isalnum() and word not in stop_words]  # Remove punctuation and stopwords

    # Part-of-Speech (POS) Tagging
    tagged_words = pos_tag(words)  # POS tagging

    # Extract only Nouns (NN, NNS, NNP, NNPS)
    nouns = [word for word, pos in tagged_words if pos in ["NN", "NNS", "NNP", "NNPS"]]

    # Frequency Analysis for Nouns
    word_freq = Counter(nouns)
    common_nouns = word_freq.most_common(20)

    # Generate word cloud
    wordcloud = WordCloud(
        background_color="white",
        width=830,  # Set width to 400
        height=400,  # Set height to 200
        max_words=100
    ).generate(" ".join(words))

    # Convert word cloud to an image buffer
    img_buffer = BytesIO()
    wordcloud.to_image().save(img_buffer, format="PNG")
    img_buffer.seek(0)

    # Encode image to base64
    encoded_img = base64.b64encode(img_buffer.getvalue()).decode("utf-8")
    img_src = f"data:image/png;base64,{encoded_img}"

    # Create a Plotly figure
    fig = go.Figure()

    fig.add_layout_image(
        dict(
            source=img_src,
            xref="paper",
            yref="paper",
            x=0,
            y=1,
            sizex=1,
            sizey=1,
            xanchor="left",
            yanchor="top",
            layer="below"
        )
    )

    # Ensure the figure scales properly with the image
    fig.update_xaxes(visible=False, range=[0, 1], domain=[0, 1])
    fig.update_yaxes(visible=False, range=[0, 1], scaleanchor="x", domain=[0, 1])

    # Remove margins to fit the image exactly
    fig.update_layout(
        title=f"Common Topics for {sdg_dropdown_value}" if sdg_dropdown_value != "ALL" else "Common Topics for All SDGs",
        margin=dict(l=0, r=0, t=30, b=0),
        width=550,  # Match word cloud width
        height=300   # Match word cloud height
    )

    return fig




def generate_research_area_visualization(selected_colleges, selected_status, selected_years, sdg_dropdown_value="ALL", pub_format_filter=None):
    """
    Generates an interactive stacked bar chart of research areas per SDG.
    Displays top 5 research areas per SDG if 'ALL' is selected, 
    or top 10 research areas per SDG if a specific SDG is selected.

    :param selected_colleges: List of selected colleges (or a single value)
    :param selected_status: List of selected research statuses (or a single value)
    :param selected_years: List of selected school years
    :param sdg_dropdown_value: Selected SDG filter (string, "ALL" for no filtering)
    :param pub_format_filter: List of publication formats to filter (or None for all)
    :return: Plotly figure object
    """
    # Convert arrays to lists if needed
    def convert_to_python_list(value):
        return value.tolist() if isinstance(value, np.ndarray) else value

    selected_colleges = convert_to_python_list(selected_colleges)
    selected_status = convert_to_python_list(selected_status)
    selected_years = convert_to_python_list(selected_years)

    # Ensure years are integers
    if isinstance(selected_years, list) and len(selected_years) > 0:
        selected_years = [int(year) for year in selected_years]  # Convert all elements to int
    elif isinstance(selected_years, np.ndarray) and selected_years.size == 1:
        selected_years = int(selected_years.item())  # Extract scalar if it's a single-value array

    # Ensure valid year range
    start_year = selected_years[0] if selected_years else None
    end_year = selected_years[-1] if selected_years else None

    # Fetch data
    df = get_research_area_data(
        start_year=start_year,
        end_year=end_year,
        sdg_filter=[sdg_dropdown_value] if sdg_dropdown_value != "ALL" else None,
        status_filter=selected_status if selected_status else None,
        college_filter=selected_colleges if selected_colleges else None,
        pub_format_filter=pub_format_filter
    )

    # Ensure df is a DataFrame
    if isinstance(df, list):
        df = pd.DataFrame(df)

    # Check if df is empty (after ensuring it's a DataFrame)
    if df.empty:
        print("No data available for the selected filters.")

        # Return a blank figure with centered text
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            x=0.5, y=0.5,
            xref="paper", yref="paper",
            showarrow=False,
            font=dict(size=20, color="gray")
        )
        fig.update_layout(
            title=f"Top Research Areas for {sdg_dropdown_value}",
            template="plotly_white",
            height=200, width=550,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            margin=dict(l=0, r=0, t=40, b=0)
        )
        return fig


    # Convert research count to integer
    df["research_count"] = df["research_count"].astype(int)

    # Ensure SDG ordering
    all_sdgs = [f'SDG {i}' for i in range(1, 18)]  # SDG 1 to SDG 17
    df["sdg"] = pd.Categorical(df["sdg"], categories=all_sdgs, ordered=True)

    # Rename column for consistency
    df = df.rename(columns={"research_area_name": "Research Area"})

    # Aggregate research areas
    df_grouped = df.groupby(["sdg", "Research Area"])["research_count"].sum().reset_index()

    # Get top research areas per SDG
    if sdg_dropdown_value == "ALL":
        top_n = 5
        chart_title = "Top 5 Research Areas per SDG"
        df_grouped = df_grouped.sort_values("research_count", ascending=False)
        top_research_areas = df_grouped.groupby("sdg").head(top_n)
        x_axis = "sdg"
    else:
        top_n = 10
        chart_title = f"Top 10 Research Areas for {sdg_dropdown_value}"
        
        # Ensure SDG filtering only applies when needed
        filtered_df = df_grouped[df_grouped["sdg"] == sdg_dropdown_value]
        
        if filtered_df.empty:
            print(f"No research areas found for {sdg_dropdown_value}. Returning empty chart.")

            # Return a blank figure with centered text
            fig = go.Figure()
            fig.add_annotation(
                text="No data available",
                x=0.5, y=0.5,
                xref="paper", yref="paper",
                showarrow=False,
                font=dict(size=20, color="gray")
            )
            fig.update_layout(
                template="plotly_white",
                height=200, width=550,
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                margin=dict(l=0, r=0, t=40, b=0)
            )
            return fig

        filtered_df = filtered_df.sort_values("research_count", ascending=False)
        top_research_areas = filtered_df.groupby("sdg").head(top_n)
        x_axis = "Research Area"

    # Create stacked bar chart
    fig = px.bar(
        top_research_areas,
        x=x_axis,
        y="research_count",
        color="Research Area",
        title=chart_title,  # Dynamic title
        labels={"sdg": "Sustainable Development Goals (SDGs)", "research_count": "Number of Research Papers"},
        template="plotly_white",
        height=200,
        width=550,
        category_orders={"sdg": all_sdgs}  # Ensure SDG order
    )
    fig.update_traces(
        hovertemplate="SDG: %{x}<br>"
                    "Research Area: %{customdata[0]}<br>"
                    "Research Count: %{y}<extra></extra>",
        customdata=top_research_areas[["Research Area"]].values  # Pass Research Area explicitly
    )

    # Update layout
    fig.update_layout(
        xaxis_title="Research Area" if sdg_dropdown_value != "ALL" else "SDGs",
        yaxis_title="Count",
        barmode="stack",
        margin=dict(l=0, r=0, t=40, b=0),
        showlegend=False
    )

    return fig


def visualize_sdg_impact(selected_colleges, selected_status, selected_years, sdg_dropdown_value, selected_pub_form):
    """
    Visualizes SDG research impact using a bar graph.
    
    - If "ALL" is selected for SDG, the Y-axis shows SDGs with total research counts.
    - If a specific SDG is selected, the Y-axis shows colleges with research counts for that SDG.
    - If only one college is selected, the Y-axis shows programs with research counts.

    :param selected_colleges: List of selected colleges (or a single value)
    :param selected_status: List of selected research statuses (or a single value)
    :param selected_years: List of selected school years
    :param sdg_dropdown_value: Selected SDG filter (string, "ALL" for no filtering)
    :param selected_pub_form: List of selected publication formats
    :return: Plotly figure object
    """
    print("Selected SDG:", sdg_dropdown_value)  # Debugging

    # Convert numpy arrays or strings to lists
    if isinstance(selected_status, np.ndarray):
        selected_status = selected_status.tolist()
    if isinstance(selected_colleges, np.ndarray):
        selected_colleges = selected_colleges.tolist()
    if isinstance(selected_pub_form, np.ndarray):
        selected_pub_form = selected_pub_form.tolist()

    # Fetch data from database
    research_data = count_sdg_impact(
        start_year=min(selected_years),
        end_year=max(selected_years),
        sdg_filter=[sdg_dropdown_value] if sdg_dropdown_value != "ALL" else None,
        status_filter=selected_status,
        college_filter=selected_colleges,
        pub_format_filter=selected_pub_form  # <<< ADDED this line
    )

    # Convert to DataFrame
    df = pd.DataFrame(research_data)
    if df.empty:
        # Return a blank figure with centered text
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            x=0.5, y=0.5,
            xref="paper", yref="paper",
            showarrow=False,
            font=dict(size=20, color="gray")
        )
        fig.update_traces(
            hovertemplate="%{y}: %{x} Research Outputs<extra></extra>"
        )
        fig.update_layout(
            title="SDG Research Impact",
            template="plotly_white",
            height=350, width=520,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            margin=dict(l=10, r=10, t=30, b=10)
        )
        return fig

    # Rename columns
    df.rename(columns={'research_count': 'Count', 'sdg': 'SDG', 'college_id': 'College', 'program_id': 'Program'}, inplace=True)

    if sdg_dropdown_value == "ALL":
        # Aggregate research counts per SDG
        df = df.groupby('SDG', as_index=False)['Count'].sum()
        
        all_sdgs = [f"SDG {i}" for i in range(1, 18)]
        sdg_df = pd.DataFrame({'SDG': all_sdgs})
        df = sdg_df.merge(df, on="SDG", how="left").fillna(0)
        y_axis = "SDG"
        title = "SDG Research Impact"
    else:
        if len(selected_colleges) == 1:
            # Aggregate research counts per Program if only one college is selected
            df = df.groupby('Program', as_index=False)['Count'].sum()
            y_axis = "Program"
            title = f"Research Impact by Program (SDG: {sdg_dropdown_value})"
        else:
            # Aggregate research counts per College for a specific SDG
            df = df.groupby('College', as_index=False)['Count'].sum()
            y_axis = "College"
            title = f"Research Impact by College (SDG: {sdg_dropdown_value})"
    
    # Sort by total count in descending order
    df.sort_values(by='Count', ascending=False, inplace=True)

    # Create bar chart
    fig = px.bar(
        df,
        x='Count',
        y=y_axis,
        orientation='h',  # Horizontal bar chart
        title=title,
        labels={'Count': 'Number of Research Outputs', y_axis: y_axis},
        template="plotly_white"
    )

    fig.update_layout(
        title_font_size=14,
        width=520,
        height=350,
        margin=dict(l=10, r=10, t=30, b=10),
        yaxis={'categoryorder': 'total ascending'}
    )
    fig.update_traces(
        hovertemplate="%{y}: %{x} Research Outputs<extra></extra>"
    )

    return fig





def generate_sdg_bipartite_graph(selected_colleges, selected_status, selected_years, sdg_dropdown_value, pub_format_filter=None):
    """
    Generates a bipartite graph showing relationships between SDGs based on shared research.

    :param selected_colleges: List of selected colleges (list of strings)
    :param selected_status: List of selected research statuses (list of strings)
    :param selected_years: List of selected years (list of integers)
    :param sdg_dropdown_value: Selected SDG goal (string)
    :param pub_format_filter: List of publication formats to filter (or None for all)
    :return: Plotly figure object
    """

    # Convert arrays to lists if needed
    if isinstance(selected_colleges, np.ndarray):
        selected_colleges = selected_colleges.tolist()
    if isinstance(selected_status, np.ndarray):
        selected_status = selected_status.tolist()

    # Convert years to integers if needed
    if isinstance(selected_years, np.ndarray):
        selected_years = selected_years.tolist()

    # Fetch data with pub_format_filter included
    data = get_sdg_research(
        start_year=min(selected_years),
        end_year=max(selected_years),
        sdg_filter=None if sdg_dropdown_value == "ALL" else [sdg_dropdown_value],
        status_filter=selected_status,
        college_filter=selected_colleges,
        pub_format_filter=pub_format_filter  # Adding pub_format_filter here
    )

    # Convert list to DataFrame
    df = pd.DataFrame(data, columns=["sdg", "research_id"])

    if df.empty:
        # Return a blank figure with centered text
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            x=0.5, y=0.5,
            xref="paper", yref="paper",
            showarrow=False,
            font=dict(size=20, color="gray")
        )
        fig.update_layout(
            title="SDG Research Collaboration Network",
            template="plotly_white",
            height=530, width=600,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            margin=dict(l=10, r=10, t=30, b=10)
        )
        return fig

    # Create an undirected graph
    G = nx.Graph()

    # Group research IDs by SDGs
    sdg_groups = df.groupby("research_id")["sdg"].apply(list)

    # Add nodes (SDGs)
    unique_sdgs = df["sdg"].unique()
    G.add_nodes_from(unique_sdgs)

    # Track edge weights (how often an SDG pair appears together)
    edge_weights = {}

    # Add edges and track occurrences
    for sdg_list in sdg_groups:
        for i in range(len(sdg_list)):
            for j in range(i + 1, len(sdg_list)):
                edge = tuple(sorted([sdg_list[i], sdg_list[j]]))  # Ensure unique key
                edge_weights[edge] = edge_weights.get(edge, 0) + 1

    # Add weighted edges to graph
    for edge, weight in edge_weights.items():
        G.add_edge(edge[0], edge[1], weight=weight)

    # Compute node degrees (how many connections each SDG has)
    degrees = dict(G.degree())
    
    min_degree = min(degrees.values()) if degrees else 1  # Lowest number of connections
    max_degree = max(degrees.values()) if degrees else 1  # Highest number of connections

    # Determine node colors
    node_colors = {}
    if sdg_dropdown_value == "ALL":
        # Use predefined SDG colors
        node_colors = {node: sdg_colors.get(node, "gray") for node in G.nodes()}
    else:
        # Use gradient coloring
        node_colors = {node: get_gradient_color(degrees[node], min_degree, max_degree) for node in G.nodes()}

    # Get node positions
    pos = nx.spring_layout(G, seed=42)  # Position nodes

    # Create edge traces
    edge_x, edge_y = [], []

    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=1, color="lightgray"),
        hoverinfo="none",
        mode="lines"
    )

    # Create node traces
    node_x, node_y, node_text, node_size, node_color = [], [], [], [], []

    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        node_text.append(node)
        node_size.append(10 + (degrees[node] / max_degree) * 30)  # Adjust size dynamically
        node_color.append(node_colors[node])  # Apply SDG colors or gradient

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode="markers+text",
        text=node_text,
        textposition="middle center",
        hoverinfo="text",
        marker=dict(
            size=node_size,
            color=node_color,
            line=dict(width=2, color="black")
        ),
        textfont=dict(
            family="Arial, sans-serif",
            size=12,  # Adjust size if needed
            color="black",
            weight="bold"  # Makes the text bold
        )
    )

    # Create the final figure
    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(
        title="SDG Research Collaboration Network",
        showlegend=False,
        margin=dict(l=0, r=0, t=40, b=0),
        height=530, 
        width=600,
        plot_bgcolor="white",  # Sets background color to white
        paper_bgcolor="white",  # Ensures the entire figure background is white
        xaxis=dict(showticklabels=False, zeroline=False, showgrid=False),  # Hide X-axis labels
        yaxis=dict(showticklabels=False, zeroline=False, showgrid=False)   # Hide Y-axis labels
    )

    return fig

def get_total_proceeding_count(selected_colleges, selected_status, selected_years, sdg_dropdown_value):
    """
    Computes the total count of research proceedings and determines the alert message color.

    :return: Tuple (alert message, alert color)
    """

    # Convert arrays to lists if needed
    if isinstance(selected_colleges, np.ndarray):
        selected_colleges = selected_colleges.tolist()
    if isinstance(selected_status, np.ndarray):
        selected_status = selected_status.tolist()

    # Fetch data
    df = get_proceeding_research(
        start_year=min(selected_years),
        end_year=max(selected_years),
        sdg_filter=None if sdg_dropdown_value == "ALL" else [sdg_dropdown_value],
        status_filter=selected_status,
        college_filter=selected_colleges,
    )
    df =pd.DataFrame(df)

    unique_research_count = df['research_id'].nunique() if 'research_id' in df.columns else 0


    # Determine message and color
    if unique_research_count == 0:
        alert_message = "No research proceedings data found."
        alert_color = "danger"  # Red color (Bootstrap)
    else:
        record_word = "record" if unique_research_count == 1 else "records"
        alert_message = f"Showing {unique_research_count} research proceedings {record_word}."
        alert_color = "warning"  # Yellow color (Bootstrap)

    return alert_message, alert_color  # ✅ Return both message and color