# created by Jelly Mallari
# continued by Nicole Cabansag (for other charts and added reset_button function)

import dash
from dash import Dash, html, dcc, dash_table
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
from . import db_manager
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from database.institutional_performance_queries import get_data_for_performance_overview, get_data_for_research_type_bar_plot, get_data_for_research_status_bar_plot, get_data_for_scopus_section, get_data_for_jounal_section, get_data_for_sdg, get_data_for_modal_contents, get_data_for_text_displays
from urllib.parse import parse_qs, urlparse
from components.DashboardHeader import DashboardHeader
from components.Tabs import Tabs
import io
import pandas as pd
from dash.dcc import send_data_frame, send_file
from components.KPI_Card import KPI_Card
import os
import datetime
from pathlib import Path

def default_if_empty(selected_values, default_values):
    """
    Returns default_values if selected_values is empty.
    """
    return selected_values if selected_values else default_values

def ensure_list(value):
    """
    Ensures that the given value is always returned as a list.
    - If it's a NumPy array, convert it to a list.
    - If it's a string, wrap it in a list.
    - If it's already a list, return as is.
    """
    if isinstance(value, np.ndarray):
        return value.tolist()
    elif isinstance(value, str):
        return [value]
    return value  # Return as is if already a list or another type

def download_file(df, file):
    """Handles saving the file and returns the file path."""
    downloads_folder = str(Path.home() / "Downloads")  # Works for Windows, Mac, Linux
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"{file}_{timestamp}.xlsx"
    file_path = os.path.join(downloads_folder, file_name)

    # Save the file
    df.to_excel(file_path, index=False)

    return file_path

class MainDashboard:
    def __init__(self, flask_app):
        """
        Initialize the MainDashboard class and set up the Dash app.
        """
        self.dash_app = Dash(__name__, server=flask_app, url_base_pathname='/dashboard/overview/', 
                             external_stylesheets=[dbc.themes.BOOTSTRAP, "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css"])

        self.palette_dict = db_manager.get_college_colors()
        
        # Get default values
        self.default_colleges = db_manager.get_unique_values('college_id')
        self.default_statuses = db_manager.get_unique_values('status')
        self.default_terms = db_manager.get_unique_values('term')
        self.default_years = [db_manager.get_min_value('year'), db_manager.get_max_value('year')]
        self.create_layout()
        self.set_callbacks()

        self.all_sdgs = [
            'SDG 1', 'SDG 2', 'SDG 3', 'SDG 4', 'SDG 5', 'SDG 6', 'SDG 7', 
            'SDG 8', 'SDG 9', 'SDG 10', 'SDG 11', 'SDG 12', 'SDG 13', 
            'SDG 14', 'SDG 15', 'SDG 16', 'SDG 17'
        ]

    def create_layout(self):
        """
        Create the layout of the dashboard.
        """

        college = html.Div(
            [
                dbc.Label("Select College/s:", style={"color": "#08397C"}),
                dbc.Checklist(
                    id="college",
                    options=[{'label': value, 'value': value} for value in db_manager.get_unique_values('college_id')],
                    value=[],
                    inline=True,
                ),
            ],
            className="mb-4",
        )

        terms = sorted(db_manager.get_unique_values('term'))

        term = html.Div(
            [
                dbc.Label("Select Term/s:", style={"color": "#08397C"}),
                dbc.Checklist(
                    id="terms",
                    options=[{'label': value, 'value': value} for value in terms],
                    value=[],
                    inline=True,
                ),
            ],
            className="mb-4",
        )

        status = html.Div(
            [
                dbc.Label("Select Status:", style={"color": "#08397C"}),
                dbc.Checklist(
                    id="status",
                    options=[{'label': value, 'value': value} for value in sorted(
                        db_manager.get_unique_values('status'), key=lambda x: (x != 'READY', x != 'PULLOUT', x)
                    )],
                    value=[],
                    inline=True,
                ),
            ],
            className="mb-4",
        )

        slider = html.Div(
            [
                dbc.Label("Select Years: ", style={"color": "#08397C"}),
                dcc.RangeSlider(
                    min=db_manager.get_min_value('year'), 
                    max=db_manager.get_max_value('year'), 
                    step=1, 
                    id="years",
                    marks=None,
                    tooltip={"placement": "bottom", "always_visible": True},
                    value=[db_manager.get_min_value('year'), db_manager.get_max_value('year')],
                    className="p-0",
                ),
            ],
            className="mb-4",
        )

        button = html.Div(
            [
                dbc.Button("Reset", color="primary", id="reset_button"),
            ],
            className="d-grid gap-2",
        )

        controls = dbc.Col(
            dbc.Card(
                [
                    html.H4("Filters", style={"margin": "10px 0px", "color": "red"}),  # Set the color to red
                    html.Div(
                        [college, status, term, slider, button], 
                        style={"font-size": "0.85rem", "padding": "5px"}  # Reduce font size and padding
                    ),
                ],
                body=True,
                style={
                    "background": "#d3d8db",
                    "height": "100vh",  # Full-height sidebar
                    "position": "sticky",  # Sticky position instead of fixed
                    "top": 0,
                    "padding": "10px",  # Reduce padding for a more compact layout
                    "border-radius": "0",  # Remove rounded corners
                },
            )
        )

        main_dash = dbc.Container([
            dbc.Row([  # Row for the line and pie charts
                dbc.Col(
                    dcc.Loading(
                        id="loading-college-line",
                        type="circle",
                        children=dcc.Graph(
                            id='college_line_plot',
                            config={"responsive": True},
                            style={"height": "400px"}  # Applied chart height from layout
                        )
                    ), 
                    width=8, 
                    style={"height": "auto", "overflow": "hidden", "paddingTop": "20px"}
                ),
                dbc.Col(
                    dcc.Loading(
                        id="loading-college-pie",
                        type="circle",
                        children=dcc.Graph(
                            id='college_pie_chart',
                            config={"responsive": True},
                            style={"height": "400px"}  # Applied chart height from layout
                        )
                    ), 
                    width=4, 
                    style={"height": "auto", "overflow": "hidden", "paddingTop": "20px"}
                )
            ], style={"margin": "10px"}),
        ], fluid=True, style={"border": "2px solid #FFFFFF", "borderRadius": "5px", "transform": "scale(1)", "transform-origin": "0 0"})  # Adjust the scale as needed

        sub_dash1 = dbc.Container([
            dbc.Row([
                dbc.Col(
                    dcc.Loading(
                        id="loading-research-status",
                        type="circle",
                        children=dcc.Graph(id='research_status_bar_plot'),
                    ), 
                    width=6, 
                    style={"height": "auto", "overflow": "hidden"}
                ),
                dbc.Col(
                    dcc.Loading(
                        id="loading-research-type",
                        type="circle",
                        children=dcc.Graph(id='research_type_bar_plot'),
                    ), 
                    width=6, 
                    style={"height": "auto", "overflow": "hidden"}
                )
            ], style={"margin": "10px"})
        ], fluid=True, style={"border": "2px solid #FFFFFF", "borderRadius": "5px", "transform": "scale(1)", "transform-origin": "0 0"})  # Adjust the scale as needed

        sub_dash2 = dbc.Container([
            dbc.Row([
                dbc.Col([
                    dcc.Tabs(
                        id='nonscopus_scopus_tabs',
                        value='line',
                        children=[
                            dcc.Tab(label='Line Chart', value='line', style={"font-size": "10px"}),
                            dcc.Tab(label='Pie Chart', value='pie', style={"font-size": "12px"})
                        ],
                        style={"font-size": "14px"}  # Adjust overall font size of tabs
                    ),
                    dcc.Loading(
                        id="loading-nonscopus-scopus1",
                        type="circle",
                        children=dcc.Graph(
                            id='nonscopus_scopus_graph',
                            config={"responsive": True},
                            style={"height": "300px"}  # Applied chart height from layout
                        )
                    )
                ], width=6, style={"height": "auto", "overflow": "hidden"}),
                dbc.Col(
                    dcc.Loading(
                        id="loading-nonscopus-scopus2",
                        type="circle",
                        children=dcc.Graph(id='nonscopus_scopus_bar_plot')
                    ),
                    width=6,
                    style={"height": "auto", "overflow": "hidden"}
                )
            ], style={"margin": "10px"})
        ], fluid=True, style={"border": "2px solid #FFFFFF", "borderRadius": "5px", "transform": "scale(1)", "transform-origin": "0 0"})


        sub_dash3 = dbc.Container([
            dbc.Row([
                dbc.Col(
                    dcc.Loading(
                        id="loading-sdg-bar",
                        type="circle",
                        children=dcc.Graph(id='sdg_bar_plot'),
                    ), 
                    width=12
                )
            ], style={"margin": "10px"})
        ], fluid=True, style={"border": "2px solid #FFFFFF", "borderRadius": "5px", "transform": "scale(1)", "transform-origin": "0 0"})

        sub_dash4 = dbc.Container([
            dbc.Row([
                dbc.Col([
                dcc.Tabs(
                    id='proceeding_conference_tabs',
                    value='line',  # Default view is the line chart
                    children=[
                        dcc.Tab(label='Line Chart', value='line', style={"font-size": "10px"}),
                        dcc.Tab(label='Pie Chart', value='pie', style={"font-size": "12px"})
                    ],
                    style={"font-size": "14px"}  # Adjust overall font size of tabs
                ),
                dcc.Loading(
                    id="loading-proceeding-conference1",
                    type="circle",
                    children=dcc.Graph(
                        id='proceeding_conference_graph',
                        config={"responsive": True},
                        style={"height": "300px"}  # Applied chart height from layout
                    )
                )
            ], width=6, style={"height": "auto", "overflow": "hidden"}),
                dbc.Col(
                    dcc.Loading(
                        id="loading-proceeding-conference2",
                        type="circle",
                        children=dcc.Graph(id='proceeding_conference_bar_plot')
                    ),
                    width=6,
                    style={"height": "auto", "overflow": "hidden"}
                )
            ], style={"margin": "10px"})
        ], fluid=True, style={"border": "2px solid #FFFFFF", "borderRadius": "5px", "transform": "scale(1)", "transform-origin": "0 0"})

        text_display = dbc.Container([
            dbc.Row(
                [
                    dbc.Col(KPI_Card("Research Output(s)", "0", id="open-total-modal", icon="fas fa-book-open", color="primary"), width="auto"),
                    dbc.Col(KPI_Card("Ready for Publication", "0", id="open-ready-modal", icon="fas fa-file-import", color="info"), width="auto"),
                    dbc.Col(KPI_Card("Submitted Paper(s)", "0", id="open-submitted-modal", icon="fas fa-file-export", color="warning"), width="auto"),
                    dbc.Col(KPI_Card("Accepted Paper(s)", "0", id="open-accepted-modal", icon="fas fa-check-circle", color="success"), width="auto"),
                    dbc.Col(KPI_Card("Published Paper(s)", "0", id="open-published-modal", icon="fas fa-file-alt", color="danger"), width="auto"),
                    dbc.Col(KPI_Card("Pulled-out Paper(s)", "0", id="open-pullout-modal", icon="fas fa-file-excel", color="secondary"), width="auto")
                ],
                className="g-2",  # Mas maliit na gap
                justify="center",
                style={"padding-top": "0", "padding-bottom": "0", "margin-top": "-10px"}  # Tinaas ang row
            ),
        ], className="p-0", style={"padding-top": "0", "padding-bottom": "0"})


        self.dash_app.layout = html.Div([
            dcc.Location(id='url', refresh=False),
            dcc.Interval(id="data-refresh-interval", interval=1000, n_intervals=0),  # 1-second refresh interval
            dcc.Store(id="shared-data-store"),  # Shared data store to hold the updated dataset
            dcc.Download(id="total-download-link"), # For download feature (modal content)
            dcc.Download(id="ready-download-link"), # For download feature (modal content)
            dcc.Download(id="submitted-download-link"), # For download feature (modal content)
            dcc.Download(id="accepted-download-link"), # For download feature (modal content)
            dcc.Download(id="published-download-link"), # For download feature (modal content)
            dcc.Download(id="pullout-download-link"), # For download feature (modal content)
            dbc.Container([
                dbc.Row([
                    # Sidebar controls
                    dbc.Col(
                        controls,
                        width={"size": 2, "order": 1},  # Adjust width for sidebar
                        style={"height": "100%", "padding": "0", "overflow-y": "auto"}
                    ),
                    # Main dashboard content
                    dbc.Col(
                        html.Div([
                            html.Div(id="dynamic-header"),
                            # Buttons in a single row
                            text_display,
                            
                            # Modals for each button
                            dbc.Modal([
                                dbc.ModalHeader(dbc.ModalTitle("Research Output(s)")),
                                dbc.ModalBody(id="total-modal-content"),
                                dbc.ModalFooter(
                                    dbc.ModalFooter([
                                        dbc.Button("Export", id="total-download-btn", color="success", className="mr-2", n_clicks=0),
                                        dbc.Col(dbc.Button("Close", id="close-total-modal", className="ms-auto", n_clicks=0))
                                    ])
                                ) 
                            ], id="total-modal", scrollable=True, is_open=False, size="xl"),
                            
                            dbc.Modal([
                                dbc.ModalHeader(dbc.ModalTitle("Ready for Publication")),
                                dbc.ModalBody(id="ready-modal-content"),
                                dbc.ModalFooter(
                                    dbc.ModalFooter([
                                        dbc.Button("Export", id="ready-download-btn", color="success", className="mr-2", n_clicks=0),
                                        dbc.Col(dbc.Button("Close", id="close-ready-modal", className="ms-auto", n_clicks=0))
                                    ])
                                ) 
                            ], id="ready-modal", scrollable=True, is_open=False, size="xl"),
                            
                            dbc.Modal([
                                dbc.ModalHeader(dbc.ModalTitle("Submitted Paper(s)")),
                                dbc.ModalBody(id="submitted-modal-content"),
                                dbc.ModalFooter(
                                    dbc.ModalFooter([
                                        dbc.Button("Export", id="submitted-download-btn", color="success", className="mr-2", n_clicks=0),
                                        dbc.Col(dbc.Button("Close", id="close-submitted-modal", className="ms-auto", n_clicks=0))
                                    ])
                                ) 
                            ], id="submitted-modal", scrollable=True, is_open=False, size="xl"),
                            
                            dbc.Modal([
                                dbc.ModalHeader(dbc.ModalTitle("Accepted Paper(s)")),
                                dbc.ModalBody(id="accepted-modal-content"),
                                dbc.ModalFooter(
                                    dbc.ModalFooter([
                                        dbc.Button("Export", id="accepted-download-btn", color="success", className="mr-2", n_clicks=0),
                                        dbc.Col(dbc.Button("Close", id="close-accepted-modal", className="ms-auto", n_clicks=0))
                                    ])
                                )  
                            ], id="accepted-modal", scrollable=True, is_open=False, size="xl"),
                            
                            dbc.Modal([
                                dbc.ModalHeader(dbc.ModalTitle("Published Paper(s)")),
                                dbc.ModalBody(id="published-modal-content"),
                                dbc.ModalFooter(
                                    dbc.ModalFooter([
                                        dbc.Button("Export", id="published-download-btn", color="success", className="mr-2", n_clicks=0),
                                        dbc.Col(dbc.Button("Close", id="close-published-modal", className="ms-auto", n_clicks=0))
                                    ])
                                )  
                            ], id="published-modal", scrollable=True, is_open=False, size="xl"),

                            dbc.Modal([
                                dbc.ModalHeader(dbc.ModalTitle("Pulled-out Paper(s)")),
                                dbc.ModalBody(id="pullout-modal-content"),
                                dbc.ModalFooter(
                                    dbc.ModalFooter([
                                        dbc.Button("Export", id="pullout-download-btn", color="success", className="mr-2", n_clicks=0),
                                        dbc.Col(dbc.Button("Close", id="close-pullout-modal", className="ms-auto", n_clicks=0))
                                    ])
                                )     
                            ], id="pullout-modal", scrollable=True, is_open=False, size="xl"),

                            # Tabs
                            html.Div(
                                id="dashboard-tabs",
                                children=Tabs(
                                    tabs_data=[
                                        ("Performance Overview", html.Div(main_dash, style={'border': '1px solid #e8e9eb', 'padding': '5px'})),
                                        ("Research Statuses and Types", html.Div(sub_dash1, style={'border': '1px solid #e8e9eb', 'padding': '5px'})),
                                        ("Scopus and Non-Scopus", html.Div(sub_dash2, style={'border': '1px solid #e8e9eb', 'padding': '5px'})),
                                        ("SDG Distribution", html.Div(sub_dash3, style={'border': '1px solid #e8e9eb', 'padding': '5px'})),
                                        ("Publication Types", html.Div(sub_dash4, style={'border': '1px solid #e8e9eb', 'padding': '5px'}))
                                    ]
                                )
                            ),
                          
                        ], style={
                            "height": "100%",
                            "display": "flex",
                            "flex-direction": "column",
                            "overflow-x": "hidden",  # Prevent horizontal overflow
                            "overflow-y": "auto",  # Enable vertical scrolling
                            "padding": "10px",
                        }),
                        width={"size": 10, "order": 2},  # Adjust main content width
                        style={
                            "height": "100%",
                            "display": "flex",
                            "flex-direction": "column"
                        }
                    ),
                ], style={
                    "height": "100vh",
                    "display": "flex",
                    "flex-wrap": "nowrap",  # Prevent wrapping to maintain layout
                }),
            ], fluid=True, style={
                "height": "100vh",
                "margin": "0",
                "padding": "0",
            }),
        ], style={
            "height": "100vh",
            "margin": "0",
            "padding": "0",
            "overflow": "hidden",  # Prevent outer scrolling
        })
    
    def get_program_colors(self, df):
        unique_programs = df['program_id'].unique()
        if not hasattr(self, "program_colors"):
            self.program_colors = {}  # Initialize if not exists

        available_colors = px.colors.qualitative.Set1  # Choose a color palette

        for i, program in enumerate(unique_programs):
            if program not in self.program_colors:
                self.program_colors[program] = available_colors[i % len(available_colors)]

    def update_line_plot(self, selected_colleges, selected_status, selected_years, selected_terms):
        # Ensure selected_colleges is a standard Python list or array
        selected_colleges = ensure_list(selected_colleges)
        selected_status = ensure_list(selected_status)
        selected_years = ensure_list(selected_years)
        selected_terms = ensure_list(selected_terms)

        # Fetch data using get_data_for_performance_overview
        filtered_data_with_term = get_data_for_performance_overview(selected_colleges, None, selected_status, selected_years, selected_terms)

        # Convert data to DataFrame
        df = pd.DataFrame(filtered_data_with_term)

        if len(selected_colleges) == 1:
            grouped_df = df.groupby(['program_id', 'year']).size().reset_index(name='TitleCount')
            color_column = 'program_id'
            title = f'Number of Research Outputs for {selected_colleges[0]}'
            self.get_program_colors(grouped_df) 
        else:
            grouped_df = df.groupby(['college_id', 'year']).size().reset_index(name='TitleCount')
            color_column = 'college_id'
            title = 'Number of Research Outputs per College'
        
        fig_line = px.line(
            grouped_df, 
            x='year', 
            y='TitleCount', 
            color=color_column, 
            markers=True,
            color_discrete_map=self.program_colors if len(selected_colleges) == 1 else self.palette_dict
        )
        
        fig_line.update_layout(
            title=dict(text=title, font=dict(size=12)),  # Smaller title
            xaxis_title=dict(text='Academic Year', font=dict(size=12)),
            yaxis_title=dict(text='Research Outputs', font=dict(size=12)),
            template='plotly_white',
            margin=dict(l=0, r=0, t=30, b=0),
            height=400,
            showlegend=True  
        )
        return fig_line
    
    def update_pie_chart(self, selected_colleges, selected_status, selected_years, selected_terms):
        # Ensure selected_colleges is a standard Python list or array
        selected_colleges = ensure_list(selected_colleges)
        selected_status = ensure_list(selected_status)
        selected_years = ensure_list(selected_years)
        selected_terms = ensure_list(selected_terms)

        # Fetch data using get_data_for_performance_overview
        filtered_data_with_term = get_data_for_performance_overview(selected_colleges, None, selected_status, selected_years, selected_terms)

        # Convert data to DataFrame
        df = pd.DataFrame(filtered_data_with_term)

        if len(selected_colleges) == 1:
            college_name = selected_colleges[0]
            filtered_df = df[df['college_id'] == college_name]
            detail_counts = filtered_df.groupby('program_id').size()
            self.get_program_colors(filtered_df) 
            title = f'Research Output Distribution for {selected_colleges[0]}'
        else:
            detail_counts = df.groupby('college_id').size()
            title = 'Research Output Distribution by College'
        
        fig_pie = px.pie(
            names=detail_counts.index,
            values=detail_counts,
            color=detail_counts.index,
            color_discrete_map=self.program_colors if len(selected_colleges) == 1 else self.palette_dict,
            labels={'names': 'Category', 'values': 'Number of Research Outputs'},
        )

        fig_pie.update_layout(
            template='plotly_white',
            margin=dict(l=0, r=0, t=30, b=0),
            height=400,
            title=dict(text=title, font=dict(size=12)),  # Smaller title
        )

        return fig_pie
    
    def update_research_type_bar_plot(self, selected_colleges, selected_status, selected_years, selected_terms):
        # Ensure selected_colleges is a standard Python list or array
        selected_colleges = ensure_list(selected_colleges)
        selected_status = ensure_list(selected_status)
        selected_years = ensure_list(selected_years)
        selected_terms = ensure_list(selected_terms)

        # Fetch data using get_data_for_research_type_bar_plot
        filtered_data_with_term = get_data_for_research_type_bar_plot(selected_colleges, None, selected_status, selected_years, selected_terms)

        # Convert data to DataFrame
        df = pd.DataFrame(filtered_data_with_term)

        if df.empty:
            return px.bar(title="No data available")
        
        fig = go.Figure()

        if len(selected_colleges) == 1:
            self.get_program_colors(df) 
            status_count = df.groupby(['research_type', 'program_id']).size().reset_index(name='Count')
            pivot_df = status_count.pivot(index='research_type', columns='program_id', values='Count').fillna(0)

            sorted_programs = sorted(pivot_df.columns)
            title = f"Comparison of Research Output Type Across Programs"

            for program in sorted_programs:
                fig.add_trace(go.Bar(
                    x=pivot_df.index,
                    y=pivot_df[program],
                    name=program,
                    marker_color=self.program_colors[program]
                ))
        else:
            status_count = df.groupby(['research_type', 'college_id']).size().reset_index(name='Count')
            pivot_df = status_count.pivot(index='research_type', columns='college_id', values='Count').fillna(0)
            title = 'Comparison of Research Output Type Across Colleges'
            
            for college in pivot_df.columns:
                fig.add_trace(go.Bar(
                    x=pivot_df.index,
                    y=pivot_df[college],
                    name=college,
                    marker_color=self.palette_dict.get(college, 'grey')
                ))

        fig.update_layout(
            barmode='group',
            xaxis_title=dict(text='Research Type', font=dict(size=12)),
            yaxis_title=dict(text='Research Outputs', font=dict(size=12)),
            title=dict(text=title, font=dict(size=12)),  # Smaller title
        )

        return fig

    def update_research_status_bar_plot(self, selected_colleges, selected_status, selected_years, selected_terms):
        # Ensure selected_colleges is a standard Python list or array
        selected_colleges = ensure_list(selected_colleges)
        selected_status = ensure_list(selected_status)
        selected_years = ensure_list(selected_years)
        selected_terms = ensure_list(selected_terms)

        # Fetch data using get_filtered_data_with_term
        filtered_data_with_term = get_data_for_research_status_bar_plot(selected_colleges, None, selected_status, selected_years, selected_terms)

        # Convert data to DataFrame
        df = pd.DataFrame(filtered_data_with_term)

        if df.empty:
            return px.bar(title="No data available")

        status_order = ['READY', 'SUBMITTED', 'ACCEPTED', 'PUBLISHED', 'PULLOUT']

        fig = go.Figure()

        if len(selected_colleges) == 1:
            self.get_program_colors(df) 
            status_count = df.groupby(['status', 'program_id']).size().reset_index(name='Count')
            pivot_df = status_count.pivot(index='status', columns='program_id', values='Count').fillna(0)

            sorted_programs = sorted(pivot_df.columns)
            title = f"Comparison of Research Status Across Programs"

            for program in sorted_programs:
                fig.add_trace(go.Bar(
                    x=pivot_df.index,
                    y=pivot_df[program],
                    name=program,
                    marker_color=self.program_colors[program]
                ))
        else:
            status_count = df.groupby(['status', 'college_id']).size().reset_index(name='Count')
            pivot_df = status_count.pivot(index='status', columns='college_id', values='Count').fillna(0)
            title = 'Comparison of Research Output Status Across Colleges'
            
            for college in pivot_df.columns:
                fig.add_trace(go.Bar(
                    x=pivot_df.index,
                    y=pivot_df[college],
                    name=college,
                    marker_color=self.palette_dict.get(college, 'grey')
                ))

        fig.update_layout(
            barmode='group',
            xaxis_title=dict(text='Research Status', font=dict(size=12)),
            yaxis_title=dict(text='Research Outputs', font=dict(size=12)),
            title=dict(text=title, font=dict(size=12)),  # Smaller title,
            xaxis=dict(
                tickvals=status_order,  # This should match the unique statuses in pivot_df index
                ticktext=status_order    # This ensures that the order of the statuses is displayed correctly
            )
        )

        # Ensure the x-axis is sorted in the defined order
        fig.update_xaxes(categoryorder='array', categoryarray=status_order)

        return fig
    
    def create_publication_bar_chart(self, selected_colleges, selected_status, selected_years, selected_terms):
        # Ensure selected_colleges is a standard Python list or array
        selected_colleges = ensure_list(selected_colleges)
        selected_status = ensure_list(selected_status)
        selected_years = ensure_list(selected_years)
        selected_terms = ensure_list(selected_terms)

        # Fetch data using get_data_for_scopus_section
        filtered_data_with_term = get_data_for_scopus_section(selected_colleges, None, selected_status, selected_years, selected_terms)

        # Convert data to DataFrame
        df = pd.DataFrame(filtered_data_with_term)

        df = df[df['scopus'] != 'N/A']

        if len(selected_colleges) == 1:
            grouped_df = df.groupby(['scopus', 'program_id']).size().reset_index(name='Count')
            x_axis = 'program_id'
            xaxis_title = 'Programs'
            title = f'Scopus vs. Non-Scopus per Program in {selected_colleges[0]}'
        else:
            grouped_df = df.groupby(['scopus', 'college_id']).size().reset_index(name='Count')
            x_axis = 'college_id'
            xaxis_title = 'Colleges'
            title = 'Scopus vs. Non-Scopus per College'
        
        fig_bar = px.bar(
            grouped_df,
            x=x_axis,
            y='Count',
            color='scopus',
            barmode='group',
            color_discrete_map=self.palette_dict,
            labels={'scopus': 'Scopus vs. Non-Scopus'}
        )
        
        fig_bar.update_layout(
            title=dict(text=title, font=dict(size=12)),  # Smaller title,
            xaxis_title=dict(text=xaxis_title, font=dict(size=12)),
            yaxis_title=dict(text='Research Outputs', font=dict(size=12)),
            template='plotly_white',
            height=400
        )

        return fig_bar
    
    def update_publication_format_bar_plot(self, selected_colleges, selected_status, selected_years, selected_terms):
        # Ensure selected_colleges is a standard Python list or array
        selected_colleges = ensure_list(selected_colleges)
        selected_status = ensure_list(selected_status)
        selected_years = ensure_list(selected_years)
        selected_terms = ensure_list(selected_terms)

        # Fetch data using get_data_for_jounal_section
        filtered_data_with_term = get_data_for_jounal_section(selected_colleges, None, selected_status, selected_years, selected_terms)

        # Convert data to DataFrame
        df = pd.DataFrame(filtered_data_with_term)

        df = df[df['journal'] != 'unpublished']
        df = df[df['status'] != 'PULLOUT']

        if len(selected_colleges) == 1:
            grouped_df = df.groupby(['journal', 'program_id']).size().reset_index(name='Count')
            x_axis = 'program_id'
            xaxis_title = 'Programs'
            title = f'Publication Types per Program in {selected_colleges[0]}'
        else:
            grouped_df = df.groupby(['journal', 'college_id']).size().reset_index(name='Count')
            x_axis = 'college_id'
            xaxis_title = 'Colleges'
            title = 'Publication Types per College'

        fig_bar = px.bar(
            grouped_df,
            x=x_axis,
            y='Count',
            color='journal',
            barmode='group',
            color_discrete_map=self.palette_dict,
            labels={'journal': 'Publication Type'}
        )
        
        fig_bar.update_layout(
            title=dict(text=title, font=dict(size=12)),  # Smaller title,
            xaxis_title=dict(text=xaxis_title, font=dict(size=12)),
            yaxis_title=dict(text='Research Outputs', font=dict(size=12)),
            template='plotly_white',
            height=400
        )

        return fig_bar


    def update_sdg_chart(self, selected_colleges, selected_status, selected_years, selected_terms):
        # Ensure selected_colleges is a standard Python list or array
        selected_colleges = ensure_list(selected_colleges)
        selected_status = ensure_list(selected_status)
        selected_years = ensure_list(selected_years)
        selected_terms = ensure_list(selected_terms)

        # Fetch data using get_data_for_sdg
        filtered_data_with_term = get_data_for_sdg(selected_colleges, None, selected_status, selected_years, selected_terms)

        # Convert data to DataFrame
        df = pd.DataFrame(filtered_data_with_term)

        if df.empty:
            return px.scatter(title="No data available")

        df_copy = df.copy()

        if len(selected_colleges) == 1:
            self.get_program_colors(df)
            df_copy = df_copy.set_index('program_id')['sdg'].str.split(';').apply(pd.Series).stack().reset_index(name='sdg')
            df_copy['sdg'] = df_copy['sdg'].str.strip()
            df_copy = df_copy.drop(columns=['level_1'])
            sdg_count = df_copy.groupby(['sdg', 'program_id']).size().reset_index(name='Count')
            title = f'Distribution of SDG-Targeted Research Across Programs in {selected_colleges[0]}'

            if sdg_count.empty:
                print("Data is empty after processing")
                return px.scatter(title="No data available")

            fig = go.Figure()

            for program in sdg_count['program_id'].unique():
                program_data = sdg_count[sdg_count['program_id'] == program]
                fig.add_trace(go.Scatter(
                    x=program_data['sdg'],
                    y=program_data['program_id'],
                    mode='markers',
                    marker=dict(
                        size=program_data['Count'],
                        color=self.program_colors.get(program, 'grey'),
                        sizemode='area',
                        sizeref=2. * max(sdg_count['Count']) / (100**2),  # Bubble size scaling
                        sizemin=4
                    ),
                    name=program
                ))
        else:
            df_copy = df_copy.set_index('college_id')['sdg'].str.split(';').apply(pd.Series).stack().reset_index(name='sdg')
            df_copy['sdg'] = df_copy['sdg'].str.strip()
            df_copy = df_copy.drop(columns=['level_1'])
            sdg_count = df_copy.groupby(['sdg', 'college_id']).size().reset_index(name='Count')
            title = 'Distribution of SDG-Targeted Research Across Colleges'

            if sdg_count.empty:
                print("Data is empty after processing")
                return px.scatter(title="No data available")

            fig = go.Figure()

            for college in sdg_count['college_id'].unique():
                college_data = sdg_count[sdg_count['college_id'] == college]
                fig.add_trace(go.Scatter(
                    x=college_data['sdg'],
                    y=college_data['college_id'],
                    mode='markers',
                    marker=dict(
                        size=college_data['Count'],
                        color=self.palette_dict.get(college, 'grey'),
                        sizemode='area',
                        sizeref=2. * max(sdg_count['Count']) / (100**2),  # Bubble size scaling
                        sizemin=4
                    ),
                    name=college
                ))

        fig.update_layout(
            xaxis_title='SDG Targeted',
            yaxis_title='Programs or Colleges',
            title=title,
            xaxis=dict(
                tickvals=self.all_sdgs,
                ticktext=self.all_sdgs
            ),
            yaxis=dict(autorange="reversed"),
            showlegend=True
        )

        return fig
    
    def scopus_line_graph(self, selected_colleges, selected_status, selected_years, selected_terms):
        # Ensure selected_colleges is a standard Python list or array
        selected_colleges = ensure_list(selected_colleges)
        selected_status = ensure_list(selected_status)
        selected_years = ensure_list(selected_years)
        selected_terms = ensure_list(selected_terms)

        # Fetch data using get_data_for_scopus_section
        filtered_data_with_term = get_data_for_scopus_section(selected_colleges, None, selected_status, selected_years, selected_terms)

        # Convert data to DataFrame
        df = pd.DataFrame(filtered_data_with_term)
 
        # Filter out rows where 'scopus' is 'N/A'
        df = df[df['scopus'] != 'N/A']

        # Group data by 'scopus' and 'year'
        grouped_df = df.groupby(['scopus', 'year']).size().reset_index(name='Count')

        # Ensure year and count are numeric
        grouped_df['year'] = grouped_df['year'].astype(int)
        grouped_df['Count'] = grouped_df['Count'].astype(int)

        # Create the line chart with markers
        fig_line = px.line(
            grouped_df,
            x='year',
            y='Count',
            color='scopus',
            color_discrete_map=self.palette_dict,
            labels={'scopus': 'Scopus vs. Non-Scopus'},
            markers=True
        )

        # Update layout for smaller text and responsive UI
        fig_line.update_traces(
            line=dict(width=1.5),  # Thinner lines
            marker=dict(size=5)  # Smaller marker points
        )

        fig_line.update_layout(
            title=dict(text='Scopus vs. Non-Scopus Publications Over Time', font=dict(size=12)),  # Smaller title
            xaxis_title=dict(text='Academic Year', font=dict(size=12)),
            yaxis_title=dict(text='Research Outputs', font=dict(size=12)),
            template='plotly_white',
            height=300,  # Smaller chart height
            margin=dict(l=5, r=5, t=30, b=30),  # Minimal margins for compact display
            xaxis=dict(
                type='linear',  
                tickangle=-45,  # Angled labels for better fit
                automargin=True,  # Prevent label overflow
                tickfont=dict(size=10)  # Smaller x-axis text
            ),
            yaxis=dict(
                automargin=True,  
                tickfont=dict(size=10)  # Smaller y-axis text
            ),
            legend=dict(font=dict(size=9)),  # Smaller legend text
        )

        return fig_line
    
    def scopus_pie_chart(self, selected_colleges, selected_status, selected_years, selected_terms):
        # Ensure selected_colleges is a standard Python list or array
        selected_colleges = ensure_list(selected_colleges)
        selected_status = ensure_list(selected_status)
        selected_years = ensure_list(selected_years)
        selected_terms = ensure_list(selected_terms)

        # Fetch data using get_data_for_scopus_section
        filtered_data_with_term = get_data_for_scopus_section(selected_colleges, None, selected_status, selected_years, selected_terms)

        # Convert data to DataFrame
        df = pd.DataFrame(filtered_data_with_term)
        
        # Filter out rows where 'scopus' is 'N/A'
        df = df[df['scopus'] != 'N/A']

        # Group data by 'scopus' and sum the counts
        grouped_df = df.groupby(['scopus']).size().reset_index(name='Count')

        # Create the pie chart
        fig_pie = px.pie(
            grouped_df,
            names='scopus',
            values='Count',
            color='scopus',
            color_discrete_map=self.palette_dict,
            labels={'scopus': 'Scopus vs. Non-Scopus'}
        )

        # Update layout for a smaller and more responsive design
        fig_pie.update_traces(
            textfont=dict(size=9),  # Smaller text inside the pie
            insidetextfont=dict(size=9),  # Smaller text inside the pie
            marker=dict(line=dict(width=0.5))  # Thinner slice borders
        )

        fig_pie.update_layout(
            title=dict(text='Scopus vs. Non-Scopus Research Distribution', font=dict(size=12)),  # Smaller title
            template='plotly_white',
            height=300,  # Smaller chart height
            margin=dict(l=5, r=5, t=30, b=30),  # Minimal margins
            legend=dict(font=dict(size=9)),  # Smaller legend text
        )

        return fig_pie

    def publication_format_line_plot(self, selected_colleges, selected_status, selected_years, selected_terms):
        # Ensure selected_colleges is a standard Python list or array
        selected_colleges = ensure_list(selected_colleges)
        selected_status = ensure_list(selected_status)
        selected_years = ensure_list(selected_years)
        selected_terms = ensure_list(selected_terms)

        # Fetch data using get_data_for_jounal_section
        filtered_data_with_term = get_data_for_jounal_section(selected_colleges, None, selected_status, selected_years, selected_terms)

        # Convert data to DataFrame
        df = pd.DataFrame(filtered_data_with_term)
        
        # Filter out rows with 'unpublished' journals and 'PULLOUT' status
        df = df[df['journal'] != 'unpublished']
        df = df[df['status'] != 'PULLOUT']

        # Group data by 'journal' and 'year'
        grouped_df = df.groupby(['journal', 'year']).size().reset_index(name='Count')

        # Ensure year and count are numeric
        grouped_df['year'] = grouped_df['year'].astype(int)
        grouped_df['Count'] = grouped_df['Count'].astype(int)

        # Create the line chart with markers
        fig_line = px.line(
            grouped_df,
            x='year',
            y='Count',
            color='journal',
            color_discrete_map=self.palette_dict,
            labels={'journal': 'Publication Type'},
            markers=True
        )

        # Update layout for smaller text and responsive UI
        fig_line.update_traces(
            line=dict(width=1.5),  # Thinner lines
            marker=dict(size=5)  # Smaller marker points
        )

        fig_line.update_layout(
            title=dict(text='Publication Types Over Time', font=dict(size=12)),  # Smaller title
            xaxis_title=dict(text='Academic Year', font=dict(size=12)),
            yaxis_title=dict(text='Research Outputs', font=dict(size=12)),
            template='plotly_white',
            height=300,  # Smaller chart height
            margin=dict(l=5, r=5, t=30, b=30),  # Minimal margins for compact display
            xaxis=dict(
                type='linear',  
                tickangle=-45,  # Angled labels for better fit
                automargin=True,  # Prevent label overflow
                tickfont=dict(size=10)  # Smaller x-axis text
            ),
            yaxis=dict(
                automargin=True,  
                tickfont=dict(size=10)  # Smaller y-axis text
            ),
            legend=dict(font=dict(size=9)),  # Smaller legend text
        )

        return fig_line
    
    def publication_format_pie_chart(self, selected_colleges, selected_status, selected_years, selected_terms):
        # Ensure selected_colleges is a standard Python list or array
        selected_colleges = ensure_list(selected_colleges)
        selected_status = ensure_list(selected_status)
        selected_years = ensure_list(selected_years)
        selected_terms = ensure_list(selected_terms)

        # Fetch data using get_data_for_jounal_section
        filtered_data_with_term = get_data_for_jounal_section(selected_colleges, None, selected_status, selected_years, selected_terms)

        # Convert data to DataFrame
        df = pd.DataFrame(filtered_data_with_term)
        
        # Filter out rows with 'unpublished' journals and 'PULLOUT' status
        df = df[df['journal'] != 'unpublished']
        df = df[df['status'] != 'PULLOUT']

        # Group data by 'journal' and sum the counts
        grouped_df = df.groupby(['journal']).size().reset_index(name='Count')

        # Create the pie chart
        fig_pie = px.pie(
            grouped_df,
            names='journal',
            values='Count',
            color='journal',
            color_discrete_map=self.palette_dict,
            labels={'journal': 'Publication Type'}
        )

        # Update layout for a smaller and more responsive design
        fig_pie.update_traces(
            textfont=dict(size=9),  # Smaller text inside the pie
            insidetextfont=dict(size=9),  # Smaller text inside the pie
            marker=dict(line=dict(width=0.5))  # Thinner slice borders
        )

        fig_pie.update_layout(
            title=dict(text='Publication Type Distribution', font=dict(size=12)),  # Smaller title
            template='plotly_white',
            height=300,  # Smaller chart height
            margin=dict(l=5, r=5, t=30, b=30),  # Minimal margins
            legend=dict(font=dict(size=9)),  # Smaller legend text
        )

        return fig_pie

    def set_callbacks(self):
        """
        Set up the callback functions for the dashboard.
        """

        @self.dash_app.callback(
            Output("dynamic-header", "children"),
            Input("url", "search"),  # Extracts the query string (e.g., "?user=John&role=Admin")
            prevent_initial_call=True  
        )
        def update_header(search):
            if search:
                params = parse_qs(search.lstrip("?"))  # Parse query parameters
                user_role = params.get("user-role",["Guest"])[0]
                college = params.get("college", [""])[0]
                program = params.get("program", [""])[0]

            view=""
            style=None

            if user_role == "02":
                view="RPCO Director"
                style = {"display": "block"}
                college = ""
                program = ""
            elif user_role =="04":
                view="College Dean"
                style ={"display": "none"}
                self.college = college
                self.program = program
            else:
                view="Unknown"
            return DashboardHeader(left_text=f"{college}", title=f"INSTITUTIONAL PERFORMANCE DASHBOARD", right_text=view)

        # Callback for reset button
        @self.dash_app.callback(
            [Output('college', 'value'),
            Output('status', 'value'),
            Output('terms', 'value'),
            Output('years', 'value')],
            [Input('reset_button', 'n_clicks')],
            prevent_initial_call=True
        )
        def reset_filters(n_clicks):
            return [], [], [], [db_manager.get_min_value('year'), db_manager.get_max_value('year')]

        @self.dash_app.callback(
            Output('college_line_plot', 'figure'),
            [
                Input('college', 'value'),
                Input('status', 'value'),
                Input('years', 'value'),
                Input('terms', 'value')
            ]
        )
        def update_lineplot(selected_colleges, selected_status, selected_years, selected_terms):
            selected_colleges = default_if_empty(selected_colleges, self.default_colleges)
            selected_status = default_if_empty(selected_status, self.default_statuses)
            selected_years = selected_years if selected_years else self.default_years
            selected_terms = default_if_empty(selected_terms, self.default_terms)
            return self.update_line_plot(selected_colleges, selected_status, selected_years, selected_terms)

        @self.dash_app.callback(
            Output('college_pie_chart', 'figure'),
            [
                Input('college', 'value'),
                Input('status', 'value'),
                Input('years', 'value'),
                Input('terms', 'value')
            ]
        )
        def update_piechart(selected_colleges, selected_status, selected_years, selected_terms):
            selected_colleges = default_if_empty(selected_colleges, self.default_colleges)
            selected_status = default_if_empty(selected_status, self.default_statuses)
            selected_years = selected_years if selected_years else self.default_years
            selected_terms = default_if_empty(selected_terms, self.default_terms)
            return self.update_pie_chart(selected_colleges, selected_status, selected_years, selected_terms)

        @self.dash_app.callback(
            Output('research_type_bar_plot', 'figure'),
            [
                Input('college', 'value'), 
                Input('status', 'value'), 
                Input('years', 'value'),
                Input('terms', 'value')
            ]
        )
        def update_research_type_bar_plot(selected_colleges, selected_status, selected_years, selected_terms):
            selected_colleges = default_if_empty(selected_colleges, self.default_colleges)
            selected_status = default_if_empty(selected_status, self.default_statuses)
            selected_years = selected_years if selected_years else self.default_years
            selected_terms = default_if_empty(selected_terms, self.default_terms)
            return self.update_research_type_bar_plot(selected_colleges, selected_status, selected_years, selected_terms)
        
        @self.dash_app.callback(
            Output('research_status_bar_plot', 'figure'),
            [
                Input('college', 'value'), 
                Input('status', 'value'), 
                Input('years', 'value'),
                Input('terms', 'value')
            ]
        )
        def update_research_status_bar_plot(selected_colleges, selected_status, selected_years, selected_terms):
            selected_colleges = default_if_empty(selected_colleges, self.default_colleges)
            selected_status = default_if_empty(selected_status, self.default_statuses)
            selected_years = selected_years if selected_years else self.default_years
            selected_terms = default_if_empty(selected_terms, self.default_terms)
            return self.update_research_status_bar_plot(selected_colleges, selected_status, selected_years, selected_terms)
        
        @self.dash_app.callback(
            Output('nonscopus_scopus_bar_plot', 'figure'),
            [Input('college', 'value'), 
             Input('status', 'value'), 
             Input('years', 'value'),
             Input('terms', 'value')]
        )
        def create_publication_bar_chart(selected_colleges, selected_status, selected_years, selected_terms):
            selected_colleges = default_if_empty(selected_colleges, self.default_colleges)
            selected_status = default_if_empty(selected_status, self.default_statuses)
            selected_years = selected_years if selected_years else self.default_years
            selected_terms = default_if_empty(selected_terms, self.default_terms)
            return self.create_publication_bar_chart(selected_colleges, selected_status, selected_years, selected_terms)
        
        @self.dash_app.callback(
            Output('proceeding_conference_bar_plot', 'figure'),
            [
                Input('college', 'value'), 
                Input('status', 'value'), 
                Input('years', 'value'),
                Input('terms', 'value')
            ]
        )
        def update_publication_format_bar_plot(selected_colleges, selected_status, selected_years, selected_terms):
            selected_colleges = default_if_empty(selected_colleges, self.default_colleges)
            selected_status = default_if_empty(selected_status, self.default_statuses)
            selected_years = selected_years if selected_years else self.default_years
            selected_terms = default_if_empty(selected_terms, self.default_terms)
            return self.update_publication_format_bar_plot(selected_colleges, selected_status, selected_years, selected_terms)
        
        @self.dash_app.callback(
            Output('sdg_bar_plot', 'figure'),
            [
                Input('college', 'value'), 
                Input('status', 'value'), 
                Input('years', 'value'),
                Input('terms', 'value')
            ]
        )
        def update_sdg_chart(selected_colleges, selected_status, selected_years, selected_terms):
            selected_colleges = default_if_empty(selected_colleges, self.default_colleges)
            selected_status = default_if_empty(selected_status, self.default_statuses)
            selected_years = selected_years if selected_years else self.default_years
            selected_terms = default_if_empty(selected_terms, self.default_terms)
            return self.update_sdg_chart(selected_colleges, selected_status, selected_years, selected_terms)
        
        @self.dash_app.callback(
            Output("shared-data-store", "data"),
            Input("data-refresh-interval", "n_intervals")
        )
        def refresh_shared_data_store(n_intervals):
            updated_data = db_manager.get_all_data()
            return updated_data.to_dict('records')
        
        @self.dash_app.callback(
            Output('nonscopus_scopus_graph', 'figure'),
            [
                Input('nonscopus_scopus_tabs', 'value'),
                Input('college', 'value'),
                Input('status', 'value'),
                Input('years', 'value'),
                Input('terms', 'value')
            ]
        )
        def update_scopus_graph(tab, selected_colleges, selected_status, selected_years, selected_terms):
            selected_colleges = default_if_empty(selected_colleges, self.default_colleges)
            selected_status = default_if_empty(selected_status, self.default_statuses)
            selected_years = selected_years if selected_years else self.default_years
            selected_terms = default_if_empty(selected_terms, self.default_terms)

            if tab == 'line':
                return self.scopus_line_graph(selected_colleges, selected_status, selected_years, selected_terms)
            else:
                return self.scopus_pie_chart(selected_colleges, selected_status, selected_years, selected_terms)
        
        @self.dash_app.callback(
            Output('proceeding_conference_graph', 'figure'),
            [
                Input('proceeding_conference_tabs', 'value'),
                Input('college', 'value'),
                Input('status', 'value'),
                Input('years', 'value'),
                Input('terms', 'value')
            ]
        )
        def update_proceeding_conference_graph(tab, selected_colleges, selected_status, selected_years, selected_terms):
            selected_colleges = default_if_empty(selected_colleges, self.default_colleges)
            selected_status = default_if_empty(selected_status, self.default_statuses)
            selected_years = selected_years if selected_years else self.default_years
            selected_terms = default_if_empty(selected_terms, self.default_terms)

            if tab == 'line':
                return self.publication_format_line_plot(selected_colleges, selected_status, selected_years, selected_terms)
            else:
                return self.publication_format_pie_chart(selected_colleges, selected_status, selected_years, selected_terms)
            
        # for text button (dynamic)
        @self.dash_app.callback(
            [
                Output('open-total-modal', 'children'),
                Output('open-ready-modal', 'children'),
                Output('open-submitted-modal', 'children'),
                Output('open-accepted-modal', 'children'),
                Output('open-published-modal', 'children'),
                Output('open-pullout-modal', 'children')
            ],
            [
                Input("data-refresh-interval", "n_intervals"),
                Input('college', 'value'),
                Input('status', 'value'),
                Input('years', 'value'),
                Input('terms', 'value')
            ]
        )
        def refresh_text_buttons(n_intervals, selected_colleges, selected_status, selected_years, selected_terms):
            selected_colleges = default_if_empty(selected_colleges, self.default_colleges)
            selected_status = default_if_empty(selected_status, self.default_statuses)
            selected_years = selected_years if selected_years else self.default_years
            selected_terms = default_if_empty(selected_terms, self.default_terms)

            selected_colleges = ensure_list(selected_colleges)
            selected_status = ensure_list(selected_status)
            selected_years = ensure_list(selected_years)
            selected_terms = ensure_list(selected_terms)

            # Apply filters
            filtered_data = get_data_for_text_displays(
                selected_colleges=selected_colleges, 
                selected_status=selected_status,
                selected_years=selected_years,
                selected_terms=selected_terms
            )

            df_filtered_data = pd.DataFrame(filtered_data)

            # Convert DataFrame to list of dictionaries
            df_filtered_data = df_filtered_data.to_dict(orient='records')

            # Create a dictionary for status counts
            status_counts = {d["status"]: d["total_count"] for d in df_filtered_data}

            total_research_outputs = sum(status_counts.values())

            return (
                [ html.H3(f'{total_research_outputs}', className="mb-0")],
                [ html.H3(f'{status_counts.get("READY", 0)}', className="mb-0")],
                [ html.H3(f'{status_counts.get("SUBMITTED", 0)}', className="mb-0")],
                [ html.H3(f'{status_counts.get("ACCEPTED", 0)}', className="mb-0")],
                [ html.H3(f'{status_counts.get("PUBLISHED", 0)}', className="mb-0")],
                [ html.H3(f'{status_counts.get("PULLOUT", 0)}', className="mb-0")]
            )

        # for total modal
        @self.dash_app.callback(
            Output("total-modal", "is_open"),
            Output("total-modal-content", "children"),
            Output("total-download-link", "data"),
            Output("total-download-btn", "style"),  # Control visibility
            Input("open-total-modal", "n_clicks"),
            Input("close-total-modal", "n_clicks"),
            Input("total-download-btn", "n_clicks"),
            State("total-modal", "is_open"),
            State("college", "value"),
            State("status", "value"),
            State("years", "value"),
            State("terms", "value"),
            prevent_initial_call=True
        )
        def toggle_modal(open_clicks, close_clicks, download_clicks, is_open, selected_colleges, selected_status, selected_years, selected_terms):
            ctx = dash.callback_context
            trigger_id = ctx.triggered_id

            selected_colleges = default_if_empty(selected_colleges, self.default_colleges)
            selected_status = default_if_empty(selected_status, self.default_statuses)
            selected_years = selected_years if selected_years else self.default_years
            selected_terms = default_if_empty(selected_terms, self.default_terms)

            selected_colleges = ensure_list(selected_colleges)
            selected_status = ensure_list(selected_status)
            selected_years = ensure_list(selected_years)
            selected_terms = ensure_list(selected_terms)

            # Apply filters
            filtered_data = get_data_for_modal_contents(
                selected_colleges=selected_colleges, 
                selected_status=selected_status,
                selected_years=selected_years,
                selected_terms=selected_terms
            )

            df_filtered_data = pd.DataFrame(filtered_data)

            if df_filtered_data is None:
                df_filtered_data = []
            elif isinstance(df_filtered_data, pd.DataFrame):  
                df_filtered_data = df_filtered_data.to_dict(orient="records")

            # Hide download button if there is no data
            download_btn_style = {"display": "none"} if not df_filtered_data else {"display": "block"}

            # Handle case where there's no data
            if not df_filtered_data:
                if trigger_id == "close-total-modal":
                    print("closed")
                    return False, "", None, download_btn_style  
                return True, "No data records.", None, download_btn_style  

            # Choose specific columns to display
            selected_columns = {
                "sdg": "SDG",
                "title": "Research Title",
                "concatenated_authors": "Author(s)",
                "program_name": "Program",
                "concatenated_keywords": "Keywords",
                "research_type": "Research Type"
            }

            df_filtered_data = pd.DataFrame(df_filtered_data)[list(selected_columns.keys())] if df_filtered_data else pd.DataFrame(columns=list(selected_columns.keys()))
            df_filtered_data = df_filtered_data.rename(columns=selected_columns)
            table = dbc.Table.from_dataframe(df_filtered_data, striped=True, bordered=True, hover=True)

            if trigger_id == "open-total-modal":
                return True, table, None, download_btn_style  

            elif trigger_id == "close-total-modal":
                return False, "", None, download_btn_style  

            elif trigger_id == "total-download-btn":
                if df_filtered_data is not None and not df_filtered_data.empty:
                    file_path = download_file(df_filtered_data, "total_papers")

                    download_message = dbc.Alert(
                        "The list of research outputs is downloaded. Check your Downloads folder.",
                        color="success",
                        dismissable=False
                    )

                    return is_open, download_message, send_file(file_path), {"display": "none"}  

            return is_open, "", None, download_btn_style
        
        # for ready modal
        @self.dash_app.callback(
            Output("ready-modal", "is_open"),
            Output("ready-modal-content", "children"),
            Output("ready-download-link", "data"),
            Output("ready-download-btn", "style"),  # Control visibility
            Input("open-ready-modal", "n_clicks"),
            Input("close-ready-modal", "n_clicks"),
            Input("ready-download-btn", "n_clicks"),
            State("ready-modal", "is_open"),
            State("college", "value"),
            State("status", "value"),
            State("years", "value"),
            State("terms", "value"),
            prevent_initial_call=True
        )
        def toggle_modal(open_clicks, close_clicks, download_clicks, is_open, selected_colleges, selected_status, selected_years, selected_terms):
            ctx = dash.callback_context
            trigger_id = ctx.triggered_id

            selected_colleges = default_if_empty(selected_colleges, self.default_colleges)
            selected_status = default_if_empty(selected_status, self.default_statuses)
            selected_years = selected_years if selected_years else self.default_years
            selected_terms = default_if_empty(selected_terms, self.default_terms)

            selected_colleges = ensure_list(selected_colleges)
            selected_status = ensure_list(selected_status)
            selected_years = ensure_list(selected_years)
            selected_terms = ensure_list(selected_terms)

            # Apply filters
            filtered_data = get_data_for_modal_contents(
                selected_colleges=selected_colleges, 
                selected_status=selected_status,
                selected_years=selected_years,
                selected_terms=selected_terms
            )

            df_filtered_data = pd.DataFrame(filtered_data)

            if df_filtered_data is None:
                df_filtered_data = []
            elif isinstance(df_filtered_data, pd.DataFrame):  
                df_filtered_data = df_filtered_data.to_dict(orient="records")

            # Filter only "READY" papers
            df_filtered_data = [d for d in df_filtered_data if d.get("status") == "READY"]

            # Hide download button if there is no data
            download_btn_style = {"display": "none"} if not df_filtered_data else {"display": "block"}

            # Handle case where there's no data
            if not df_filtered_data:
                if trigger_id == "close-ready-modal":
                    print("closed")
                    return False, "", None, download_btn_style  
                return True, "No data records.", None, download_btn_style  

            # Choose specific columns to display
            selected_columns = {
                "sdg": "SDG",
                "title": "Research Title",
                "concatenated_authors": "Author(s)",
                "program_name": "Program",
                "concatenated_keywords": "Keywords",
                "research_type": "Research Type"
            }

            df_filtered_data = pd.DataFrame(df_filtered_data)[list(selected_columns.keys())] if df_filtered_data else pd.DataFrame(columns=list(selected_columns.keys()))
            df_filtered_data = df_filtered_data.rename(columns=selected_columns)
            table = dbc.Table.from_dataframe(df_filtered_data, striped=True, bordered=True, hover=True)

            if trigger_id == "open-ready-modal":
                return True, table, None, download_btn_style  

            elif trigger_id == "close-ready-modal":
                return False, "", None, download_btn_style  

            elif trigger_id == "ready-download-btn":
                if df_filtered_data is not None and not df_filtered_data.empty:
                    file_path = download_file(df_filtered_data, "ready_papers")

                    download_message = dbc.Alert(
                        "The list of research outputs is downloaded. Check your Downloads folder.",
                        color="success",
                        dismissable=False
                    )

                    return is_open, download_message, send_file(file_path), {"display": "none"}  

            return is_open, "", None, download_btn_style
        
        # for submitted modal
        @self.dash_app.callback(
            Output("submitted-modal", "is_open"),
            Output("submitted-modal-content", "children"),
            Output("submitted-download-link", "data"),
            Output("submitted-download-btn", "style"),  # Control visibility
            Input("open-submitted-modal", "n_clicks"),
            Input("close-submitted-modal", "n_clicks"),
            Input("submitted-download-btn", "n_clicks"),
            State("submitted-modal", "is_open"),
            State("college", "value"),
            State("status", "value"),
            State("years", "value"),
            State("terms", "value"),
            prevent_initial_call=True
        )
        def toggle_modal(open_clicks, close_clicks, download_clicks, is_open, selected_colleges, selected_status, selected_years, selected_terms):
            ctx = dash.callback_context
            trigger_id = ctx.triggered_id

            selected_colleges = default_if_empty(selected_colleges, self.default_colleges)
            selected_status = default_if_empty(selected_status, self.default_statuses)
            selected_years = selected_years if selected_years else self.default_years
            selected_terms = default_if_empty(selected_terms, self.default_terms)

            selected_colleges = ensure_list(selected_colleges)
            selected_status = ensure_list(selected_status)
            selected_years = ensure_list(selected_years)
            selected_terms = ensure_list(selected_terms)

            # Apply filters
            filtered_data = get_data_for_modal_contents(
                selected_colleges=selected_colleges, 
                selected_status=selected_status,
                selected_years=selected_years,
                selected_terms=selected_terms
            )

            df_filtered_data = pd.DataFrame(filtered_data)

            if df_filtered_data is None:
                df_filtered_data = []
            elif isinstance(df_filtered_data, pd.DataFrame):  
                df_filtered_data = df_filtered_data.to_dict(orient="records")

            # Filter only "SUBMITTED" papers
            df_filtered_data = [d for d in df_filtered_data if d.get("status") == "SUBMITTED"]

            # Hide download button if there is no data
            download_btn_style = {"display": "none"} if not df_filtered_data else {"display": "block"}

            # Handle case where there's no data
            if not df_filtered_data:
                if trigger_id == "close-submitted-modal":
                    print("closed")
                    return False, "", None, download_btn_style  
                return True, "No data records.", None, download_btn_style  

            # Choose specific columns to display
            selected_columns = {
                "sdg": "SDG",
                "title": "Research Title",
                "concatenated_authors": "Author(s)",
                "program_name": "Program",
                "concatenated_keywords": "Keywords",
                "research_type": "Research Type"
            }

            df_filtered_data = pd.DataFrame(df_filtered_data)[list(selected_columns.keys())] if df_filtered_data else pd.DataFrame(columns=list(selected_columns.keys()))
            df_filtered_data = df_filtered_data.rename(columns=selected_columns)
            table = dbc.Table.from_dataframe(df_filtered_data, striped=True, bordered=True, hover=True)

            if trigger_id == "open-submitted-modal":
                return True, table, None, download_btn_style  

            elif trigger_id == "close-submitted-modal":
                return False, "", None, download_btn_style  

            elif trigger_id == "submitted-download-btn":
                if df_filtered_data is not None and not df_filtered_data.empty:
                    file_path = download_file(df_filtered_data, "submitted_papers")

                    download_message = dbc.Alert(
                        "The list of research outputs is downloaded. Check your Downloads folder.",
                        color="success",
                        dismissable=False
                    )

                    return is_open, download_message, send_file(file_path), {"display": "none"}  

            return is_open, "", None, download_btn_style
        
        # for accepted modal
        @self.dash_app.callback(
            Output("accepted-modal", "is_open"),
            Output("accepted-modal-content", "children"),
            Output("accepted-download-link", "data"),
            Output("accepted-download-btn", "style"),  # Control visibility
            Input("open-accepted-modal", "n_clicks"),
            Input("close-accepted-modal", "n_clicks"),
            Input("accepted-download-btn", "n_clicks"),
            State("accepted-modal", "is_open"),
            State("college", "value"),
            State("status", "value"),
            State("years", "value"),
            State("terms", "value"),
            prevent_initial_call=True
        )
        def toggle_modal(open_clicks, close_clicks, download_clicks, is_open, selected_colleges, selected_status, selected_years, selected_terms):
            ctx = dash.callback_context
            trigger_id = ctx.triggered_id

            selected_colleges = default_if_empty(selected_colleges, self.default_colleges)
            selected_status = default_if_empty(selected_status, self.default_statuses)
            selected_years = selected_years if selected_years else self.default_years
            selected_terms = default_if_empty(selected_terms, self.default_terms)

            selected_colleges = ensure_list(selected_colleges)
            selected_status = ensure_list(selected_status)
            selected_years = ensure_list(selected_years)
            selected_terms = ensure_list(selected_terms)

            # Apply filters
            filtered_data = get_data_for_modal_contents(
                selected_colleges=selected_colleges, 
                selected_status=selected_status,
                selected_years=selected_years,
                selected_terms=selected_terms
            )

            df_filtered_data = pd.DataFrame(filtered_data)

            if df_filtered_data is None:
                df_filtered_data = []
            elif isinstance(df_filtered_data, pd.DataFrame):  
                df_filtered_data = df_filtered_data.to_dict(orient="records")

            # Filter only "ACCEPTED" papers
            df_filtered_data = [d for d in df_filtered_data if d.get("status") == "ACCEPTED"]

            # Hide download button if there is no data
            download_btn_style = {"display": "none"} if not df_filtered_data else {"display": "block"}

            # Handle case where there's no data
            if not df_filtered_data:
                if trigger_id == "close-accepted-modal":
                    print("closed")
                    return False, "", None, download_btn_style  
                return True, "No data records.", None, download_btn_style  

            # Choose specific columns to display
            selected_columns = {
                "sdg": "SDG",
                "title": "Research Title",
                "concatenated_authors": "Author(s)",
                "program_name": "Program",
                "concatenated_keywords": "Keywords",
                "research_type": "Research Type"
            }

            df_filtered_data = pd.DataFrame(df_filtered_data)[list(selected_columns.keys())] if df_filtered_data else pd.DataFrame(columns=list(selected_columns.keys()))
            df_filtered_data = df_filtered_data.rename(columns=selected_columns)
            table = dbc.Table.from_dataframe(df_filtered_data, striped=True, bordered=True, hover=True)

            if trigger_id == "open-accepted-modal":
                return True, table, None, download_btn_style  

            elif trigger_id == "close-accepted-modal":
                return False, "", None, download_btn_style  

            elif trigger_id == "accepted-download-btn":
                if df_filtered_data is not None and not df_filtered_data.empty:
                    file_path = download_file(df_filtered_data, "accepted_papers")

                    download_message = dbc.Alert(
                        "The list of research outputs is downloaded. Check your Downloads folder.",
                        color="success",
                        dismissable=False
                    )

                    return is_open, download_message, send_file(file_path), {"display": "none"}  

            return is_open, "", None, download_btn_style
        
        # for published modal
        @self.dash_app.callback(
            Output("published-modal", "is_open"),
            Output("published-modal-content", "children"),
            Output("published-download-link", "data"),
            Output("published-download-btn", "style"),  # Control visibility
            Input("open-published-modal", "n_clicks"),
            Input("close-published-modal", "n_clicks"),
            Input("published-download-btn", "n_clicks"),
            State("published-modal", "is_open"),
            State("college", "value"),
            State("status", "value"),
            State("years", "value"),
            State("terms", "value"),
            prevent_initial_call=True
        )
        def toggle_modal(open_clicks, close_clicks, download_clicks, is_open, selected_colleges, selected_status, selected_years, selected_terms):
            ctx = dash.callback_context
            trigger_id = ctx.triggered_id

            selected_colleges = default_if_empty(selected_colleges, self.default_colleges)
            selected_status = default_if_empty(selected_status, self.default_statuses)
            selected_years = selected_years if selected_years else self.default_years
            selected_terms = default_if_empty(selected_terms, self.default_terms)

            selected_colleges = ensure_list(selected_colleges)
            selected_status = ensure_list(selected_status)
            selected_years = ensure_list(selected_years)
            selected_terms = ensure_list(selected_terms)

            # Apply filters
            filtered_data = get_data_for_modal_contents(
                selected_colleges=selected_colleges, 
                selected_status=selected_status,
                selected_years=selected_years,
                selected_terms=selected_terms
            )

            df_filtered_data = pd.DataFrame(filtered_data)

            if df_filtered_data is None:
                df_filtered_data = []
            elif isinstance(df_filtered_data, pd.DataFrame):  
                df_filtered_data = df_filtered_data.to_dict(orient="records")

            # Filter only "PUBLISHED" papers
            df_filtered_data = [d for d in df_filtered_data if d.get("status") == "PUBLISHED"]

            # Hide download button if there is no data
            download_btn_style = {"display": "none"} if not df_filtered_data else {"display": "block"}

            # Handle case where there's no data
            if not df_filtered_data:
                if trigger_id == "close-published-modal":
                    print("closed")
                    return False, "", None, download_btn_style  
                return True, "No data records.", None, download_btn_style  

            # Choose specific columns to display
            selected_columns = {
                "sdg": "SDG",
                "title": "Research Title",
                "concatenated_authors": "Author(s)",
                "program_name": "Program",
                "concatenated_keywords": "Keywords",
                "research_type": "Research Type"
            }

            df_filtered_data = pd.DataFrame(df_filtered_data)[list(selected_columns.keys())] if df_filtered_data else pd.DataFrame(columns=list(selected_columns.keys()))
            df_filtered_data = df_filtered_data.rename(columns=selected_columns)
            table = dbc.Table.from_dataframe(df_filtered_data, striped=True, bordered=True, hover=True)

            if trigger_id == "open-published-modal":
                return True, table, None, download_btn_style  

            elif trigger_id == "close-published-modal":
                return False, "", None, download_btn_style  

            elif trigger_id == "published-download-btn":
                if df_filtered_data is not None and not df_filtered_data.empty:
                    file_path = download_file(df_filtered_data, "published_papers")

                    download_message = dbc.Alert(
                        "The list of research outputs is downloaded. Check your Downloads folder.",
                        color="success",
                        dismissable=False
                    )

                    return is_open, download_message, send_file(file_path), {"display": "none"}  

            return is_open, "", None, download_btn_style

        # for pullout modal
        @self.dash_app.callback(
            Output("pullout-modal", "is_open"),
            Output("pullout-modal-content", "children"),
            Output("pullout-download-link", "data"),
            Output("pullout-download-btn", "style"),  # Control visibility
            Input("open-pullout-modal", "n_clicks"),
            Input("close-pullout-modal", "n_clicks"),
            Input("pullout-download-btn", "n_clicks"),
            State("pullout-modal", "is_open"),
            State("college", "value"),
            State("status", "value"),
            State("years", "value"),
            State("terms", "value"),
            prevent_initial_call=True
        )
        def toggle_modal(open_clicks, close_clicks, download_clicks, is_open, selected_colleges, selected_status, selected_years, selected_terms):
            ctx = dash.callback_context
            trigger_id = ctx.triggered_id

            selected_colleges = default_if_empty(selected_colleges, self.default_colleges)
            selected_status = default_if_empty(selected_status, self.default_statuses)
            selected_years = selected_years if selected_years else self.default_years
            selected_terms = default_if_empty(selected_terms, self.default_terms)

            selected_colleges = ensure_list(selected_colleges)
            selected_status = ensure_list(selected_status)
            selected_years = ensure_list(selected_years)
            selected_terms = ensure_list(selected_terms)

            # Apply filters
            filtered_data = get_data_for_modal_contents(
                selected_colleges=selected_colleges, 
                selected_status=selected_status,
                selected_years=selected_years,
                selected_terms=selected_terms
            )

            df_filtered_data = pd.DataFrame(filtered_data)

            if df_filtered_data is None:
                df_filtered_data = []
            elif isinstance(df_filtered_data, pd.DataFrame):  
                df_filtered_data = df_filtered_data.to_dict(orient="records")

            # Filter only "PULLOUT" papers
            df_filtered_data = [d for d in df_filtered_data if d.get("status") == "PULLOUT"]

            # Hide download button if there is no data
            download_btn_style = {"display": "none"} if not df_filtered_data else {"display": "block"}

            # Handle case where there's no data
            if not df_filtered_data:
                if trigger_id == "close-pullout-modal":
                    print("closed")
                    return False, "", None, download_btn_style  
                return True, "No data records.", None, download_btn_style  

            # Choose specific columns to display
            selected_columns = {
                "sdg": "SDG",
                "title": "Research Title",
                "concatenated_authors": "Author(s)",
                "program_name": "Program",
                "concatenated_keywords": "Keywords",
                "research_type": "Research Type"
            }

            df_filtered_data = pd.DataFrame(df_filtered_data)[list(selected_columns.keys())] if df_filtered_data else pd.DataFrame(columns=list(selected_columns.keys()))
            df_filtered_data = df_filtered_data.rename(columns=selected_columns)
            table = dbc.Table.from_dataframe(df_filtered_data, striped=True, bordered=True, hover=True)

            if trigger_id == "open-pullout-modal":
                return True, table, None, download_btn_style  

            elif trigger_id == "close-pullout-modal":
                return False, "", None, download_btn_style  

            elif trigger_id == "pullout-download-btn":
                if df_filtered_data is not None and not df_filtered_data.empty:
                    file_path = download_file(df_filtered_data, "pullout_papers")

                    download_message = dbc.Alert(
                        "The list of research outputs is downloaded. Check your Downloads folder.",
                        color="success",
                        dismissable=False
                    )

                    return is_open, download_message, send_file(file_path), {"display": "none"}  

            return is_open, "", None, download_btn_style  
