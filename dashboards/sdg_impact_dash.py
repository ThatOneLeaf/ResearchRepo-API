import dash
import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, State, html
from components.DashboardHeader import DashboardHeader
from components.Tabs import Tabs
from components.KPI_Card import KPI_Card
from components.CollageContainer import CollageContainer
from dash import dcc
from urllib.parse import parse_qs, urlparse
from . import db_manager
from services.sdg_colors import sdg_colors
from charts.sdg_charts import get_total_proceeding_count,create_sdg_plot, create_sdg_pie_chart,create_sdg_research_chart,create_geographical_heatmap,create_geographical_treemap,create_conference_participation_bar_chart,create_local_vs_foreign_donut_chart,get_word_cloud,generate_research_area_visualization,generate_sdg_bipartite_graph,visualize_sdg_impact

def default_if_empty(selected_values, default_values):
    return selected_values if selected_values else default_values


class SDG_Impact_Dash:
    def __init__(self, server, title=None, college=None, program=None, **kwargs):
        self.dash_app = Dash(
            __name__,
            server=server,
            url_base_pathname=kwargs.get('url_base_pathname', '/sdg-impact/'),
            external_stylesheets=[dbc.themes.BOOTSTRAP, "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css"]
        )
        self.title = title
        self.college = college
        self.program = program

        self.palette_dict = db_manager.get_college_colors()
        self.sdg_colors=sdg_colors
        self.all_sdgs = [f'SDG {i}' for i in range(1, 18)]
        # Get default values
        self.default_colleges = db_manager.get_unique_values('college_id')
        self.default_statuses = db_manager.get_unique_values('status')
        self.default_years = [db_manager.get_min_value('year'), db_manager.get_max_value('year')]
        

        self.set_layout()
        self.add_callbacks()

    def set_layout(self):

        college = html.Div(
            [
                dbc.Label("Select College:", style={"color": "#08397C"}),
                dbc.Checklist(
                    id="college",
                    options=[{'label': value, 'value': value} for value in db_manager.get_unique_values('college_id')],
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
        sdgs = html.Div(
            [
                dbc.Label("Select SDG:", style={"color": "#08397C"}),
                dcc.Dropdown(
                    id="sdg-dropdown",
                    options=[
                        # Add the "ALL" option at the top of the dropdown list
                        {"label": "ALL", "value": "ALL", "disabled": False},
                        *[
                            {
                                "label": sdg,
                                "value": sdg,
                                "disabled": sdg not in self.all_sdgs,
                            }
                            for sdg in sorted(
                                self.all_sdgs,
                                key=lambda x: int(x.split()[1])  # Extract the numeric part and sort
                            )
                        ]
                    ],
                    multi=False,
                    placeholder="Select SDGs",
                    value="ALL",  # Default to "ALL"
                    style={
                        "width": "100%",
                    },
                )
            ],
             className="mb-4",
        )
        # Collage Section
        self.collage = dbc.Container([
            dbc.Row([
                dbc.Col(
                    dbc.Card(
                        dcc.Loading(
                            id='loading-sdg-time-series',
                            type='circle',  # Choose the type of spinner (e.g., 'circle', 'dot', 'default')
                            children=dcc.Graph(id='sdg-time-series')
                        ),
                        body=True,
                        style={"width": "auto", "height": "auto"}
                    ),
                    width="auto", className='p-0'
                ),
                dbc.Col(
                    dbc.Card(
                        dcc.Loading(
                            id='loading-sdg-pie',
                            type='circle', 
                            children=dcc.Graph(id='sdg-pie')
                        ),
                        body=True,
                        style={"width": "auto", "height": "auto"}
                    ),
                    width="auto", className='p-0'
                ),
            ], className='g-0 d-flex'),  # Margin-bottom for spacing

            dbc.Row([
                dbc.Col(
                    dbc.Card(
                        dcc.Loading(
                            id='loading-sdg-research-type',
                            type='circle',
                            children=dcc.Graph(id='sdg-research-type')
                        ),
                        body=True,
                        style={"width": "100%", "height": "auto"}
                    ),
                    width="auto", className='p-0'
                ),
            ], className='g-0 d-flex')
        ], fluid=True)  # Set container to fluid for responsiveness


        # Map Section
        self.map = dbc.Container([
            dbc.Row([
                dbc.Alert("Initial alert message", id="alert-message", color="primary", is_open=True,style={"width": "100%", "padding": "2px", "fontSize": "14px"} ),
            ], className='g-0 d-flex'),  # Ensure no space around the alert

            dbc.Row([
                dbc.Col([
                    dbc.Card(
                        dcc.Loading(
                            id='loading-local-vs-foreign',
                            type='circle',
                            children=dcc.Graph(id='local-vs-foreign')
                        ),
                        body=True,
                        style={"width": "100%", "height": "auto"}
                    ),
                    dbc.Card(
                        dcc.Loading(
                            id='loading-tree-map',
                            type='circle',
                            children=dcc.Graph(id='tree-map')
                        ),
                        body=True,
                        style={"width": "100%", "height": "auto"}
                    ),
                ], width="auto", className='p-0'),
                dbc.Col([
                    dbc.Card(
                        dcc.Loading(
                            id='loading-sdg-map',
                            type='circle',
                            children=dcc.Graph(id='sdg-map')
                        ),
                        body=True,
                        style={"width": "100%", "height": "auto"}
                    ),
                    dbc.Card(
                        dcc.Loading(
                            id='loading-participation-graph',
                            type='circle',
                            children=dcc.Graph(id='participation-graph')
                        ),
                        body=True,
                        style={"width": "100%", "height": "auto"}
                    ),
                ], width="auto", className='p-0')
            ], className='g-0 d-flex')
        ])



        # Trend Section
        self.trend = dbc.Container([
            dbc.Row([
                dbc.Col([
                    dbc.Card(
                        dcc.Loading(
                            id='loading-word-cloud',
                            type='circle',
                            children=dcc.Graph(id='word-cloud')
                        ),
                        body=True,
                        style={"width": "100%", "height": "auto"}
                    ),
                    dbc.Card(
                        dcc.Loading(
                            id='loading-research-areas',
                            type='circle',
                            children=dcc.Graph(id='research-areas')
                        ),
                        body=True,
                        style={"width": "100%", "height": "auto"}
                    ),
                ], width="auto", className='p-0'),
                dbc.Col(
                    dbc.Card(
                        dcc.Loading(
                            id='loading-sdg-graph',
                            type='circle',
                            children=dcc.Graph(id='sdg-graph')
                        ),
                        body=True,
                        style={"width": "100%", "height": "auto"}
                    ),
                    width="auto", className='p-0'
                )
            ])
        ])



        sidebar = dbc.Col([  # Added array brackets
            html.H4("Filters", style={"margin": "10px 0px", "color": "red"}),
            sdgs,
            college,
            status,
            slider,
            button
        ], width=2, className="p-3", 
        style={"background": "#d3d8db", "height": "100vh", "position": "fixed", "left": 0, "top": 0, "zIndex": 1000})


        main_content = dbc.Col([
            dcc.Location(id="url", refresh=False),
            html.Div(id="dynamic-header"),
            html.Div(id="tabs-container", children=Tabs(
                tabs_data=[
                    ("Institutional SDG Impact", self.collage),
                    ("Global Research Proceedings", self.map),
                    ("Research Trends and Collaboration", self.trend)
                ]
            )),
        ], width=10, className="p-3", style={"marginLeft": "16.67%"})



        self.dash_app.layout = html.Div([
            dbc.Container([
                dcc.Interval(id="data-refresh-interval", interval=1000, n_intervals=0),
                dbc.Row(
                    [sidebar, main_content], 
                    className="g-0 flex-grow-1"
                )
            ], 
            fluid=True, 
            className="d-flex flex-column w-100 h-100"
            )
        ], 
        className="vh-100 vw-100 d-flex flex-column"
        )

    def add_callbacks(self):
        @self.dash_app.callback(
            [Output('college', 'value'),
            Output('status', 'value'),
            Output('years', 'value'),
            Output('sdg-dropdown', 'value')],
            [Input('reset_button', 'n_clicks')],
            prevent_initial_call=True
        )
        def reset_filters(n_clicks):
            return [], [], [db_manager.get_min_value('year'), db_manager.get_max_value('year')], "ALL"

        @self.dash_app.callback(
            Output("dynamic-header", "children"),
            Input("url", "search")  # Extracts the query string (e.g., "?user=John&role=Admin")
        )
        def update_header(search):
            if search:
                params = parse_qs(search.lstrip("?"))  # Parse query parameters
                user_role = params.get("user-role",["Guest"])[0]
                college = params.get("college", [""])[0]
                program = params.get("program", [""])[0]

            view=""

            if user_role == "02":
                view="RPCO Director"    
                college=""
                program=""
            elif user_role =="03":
                view="Head Executive"    
                college=""
                program=""
            else:
                view="Unknown"
            return DashboardHeader(left_text=college, title=f"SDG IMPACT DASHBOARD ")
    
        @self.dash_app.callback(
            Output('sdg-time-series', 'figure'),                
            [Input('college', 'value'), 
            Input('status', 'value'), 
            Input('years', 'value'),
            Input('sdg-dropdown', 'value')]
            )
        def update_all(selected_colleges, selected_status, selected_years,sdg_dropdown_value):
            selected_colleges = default_if_empty(selected_colleges, self.default_colleges)
            selected_status = default_if_empty(selected_status, self.default_statuses)
            selected_years = selected_years if selected_years else self.default_years
            return create_sdg_plot(selected_colleges, selected_status, selected_years,sdg_dropdown_value)
        
        @self.dash_app.callback(
            Output('sdg-pie', 'figure'),                
            [Input('college', 'value'), 
            Input('status', 'value'), 
            Input('years', 'value'),
            Input('sdg-dropdown', 'value')]
            )
        def update_all(selected_colleges, selected_status, selected_years,sdg_dropdown_value):
            selected_colleges = default_if_empty(selected_colleges, self.default_colleges)
            selected_status = default_if_empty(selected_status, self.default_statuses)
            selected_years = selected_years if selected_years else self.default_years
            return visualize_sdg_impact(selected_colleges, selected_status, selected_years,sdg_dropdown_value)
        @self.dash_app.callback(
            Output('sdg-research-type', 'figure'),
            [Input('college', 'value'), 
             Input('status', 'value'), 
             Input('years', 'value'),
             Input('sdg-dropdown', 'value')]
        )
        def update_fig1(selected_colleges, selected_status, selected_years,sdg_dropdown_value):
            selected_colleges = default_if_empty(selected_colleges, self.default_colleges)
            selected_status = default_if_empty(selected_status, self.default_statuses)
            selected_years = selected_years if selected_years else self.default_years
            return create_sdg_research_chart(selected_colleges, selected_status, selected_years, sdg_dropdown_value)
        @self.dash_app.callback(
            Output('sdg-map', 'figure'),
            [Input('college', 'value'), 
             Input('status', 'value'), 
             Input('years', 'value'),
             Input('sdg-dropdown', 'value')]
        )
        def update_fig(selected_colleges, selected_status, selected_years,sdg_dropdown_value):
            selected_colleges = default_if_empty(selected_colleges, self.default_colleges)
            selected_status = default_if_empty(selected_status, self.default_statuses)
            selected_years = selected_years if selected_years else self.default_years
            return create_geographical_heatmap(selected_colleges, selected_status, selected_years,sdg_dropdown_value)
        
        @self.dash_app.callback(
            Output('tree-map', 'figure'),
            [Input('college', 'value'), 
             Input('status', 'value'), 
             Input('years', 'value'),
             Input('sdg-dropdown', 'value')]
        )
        def update_fig(selected_colleges, selected_status, selected_years,sdg_dropdown_value):
            selected_colleges = default_if_empty(selected_colleges, self.default_colleges)
            selected_status = default_if_empty(selected_status, self.default_statuses)
            selected_years = selected_years if selected_years else self.default_years
            return create_geographical_treemap(selected_colleges, selected_status, selected_years,sdg_dropdown_value)
        @self.dash_app.callback(
            Output('participation-graph', 'figure'),
            [Input('college', 'value'), 
             Input('status', 'value'), 
             Input('years', 'value'),
             Input('sdg-dropdown', 'value')]
        )
        def update_fig(selected_colleges, selected_status, selected_years,sdg_dropdown_value):
            selected_colleges = default_if_empty(selected_colleges, self.default_colleges)
            selected_status = default_if_empty(selected_status, self.default_statuses)
            selected_years = selected_years if selected_years else self.default_years
            return create_conference_participation_bar_chart(selected_colleges, selected_status, selected_years,sdg_dropdown_value)
        @self.dash_app.callback(
            Output('local-vs-foreign', 'figure'),
            [Input('college', 'value'), 
             Input('status', 'value'), 
             Input('years', 'value'),
             Input('sdg-dropdown', 'value')]
        )
        def update_fig(selected_colleges, selected_status, selected_years,sdg_dropdown_value):
            selected_colleges = default_if_empty(selected_colleges, self.default_colleges)
            selected_status = default_if_empty(selected_status, self.default_statuses)
            selected_years = selected_years if selected_years else self.default_years
            return create_local_vs_foreign_donut_chart(selected_colleges, selected_status, selected_years,sdg_dropdown_value)
        @self.dash_app.callback(
            Output('word-cloud', 'figure'),
            [Input('college', 'value'), 
             Input('status', 'value'), 
             Input('years', 'value'),
             Input('sdg-dropdown', 'value')]
        )
        def update_fig(selected_colleges, selected_status, selected_years,sdg_dropdown_value):
            selected_colleges = default_if_empty(selected_colleges, self.default_colleges)
            selected_status = default_if_empty(selected_status, self.default_statuses)
            selected_years = selected_years if selected_years else self.default_years
            return get_word_cloud(selected_colleges, selected_status, selected_years,sdg_dropdown_value)
        @self.dash_app.callback(
            Output('research-areas', 'figure'),
            [Input('college', 'value'), 
             Input('status', 'value'), 
             Input('years', 'value'),
             Input('sdg-dropdown', 'value')]
        )
        def update_fig(selected_colleges, selected_status, selected_years,sdg_dropdown_value):
            selected_colleges = default_if_empty(selected_colleges, self.default_colleges)
            selected_status = default_if_empty(selected_status, self.default_statuses)
            selected_years = selected_years if selected_years else self.default_years
            return generate_research_area_visualization(selected_colleges, selected_status, selected_years,sdg_dropdown_value)
        @self.dash_app.callback(
            Output('sdg-graph', 'figure'),
            [Input('college', 'value'), 
             Input('status', 'value'), 
             Input('years', 'value'),
             Input('sdg-dropdown', 'value')]
        )
        def update_fig(selected_colleges, selected_status, selected_years,sdg_dropdown_value):
            selected_colleges = default_if_empty(selected_colleges, self.default_colleges)
            selected_status = default_if_empty(selected_status, self.default_statuses)
            selected_years = selected_years if selected_years else self.default_years
            return generate_sdg_bipartite_graph(selected_colleges, selected_status, selected_years,sdg_dropdown_value)
        @self.dash_app.callback([
                Output("alert-message", "children"),
                Output("alert-message", "color")],  # ✅ Change color dynamically
                [
                Input('college', 'value'), 
                Input('status', 'value'), 
                Input('years', 'value'),
                Input('sdg-dropdown', 'value')]
        )
        def update_alert_message(selected_colleges, selected_status, selected_years,sdg_dropdown_value):
            selected_colleges = default_if_empty(selected_colleges, self.default_colleges)
            selected_status = default_if_empty(selected_status, self.default_statuses)
            selected_years = selected_years if selected_years else self.default_years

            return get_total_proceeding_count(selected_colleges, selected_status, selected_years,sdg_dropdown_value)



 