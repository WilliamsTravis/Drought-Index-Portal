import dash
from dash.dependencies import Input, Output
import dash_html_components as html

app = dash.Dash(__name__)

app.layout = html.Div([

    html.H2('Thank Mbkupfer for this modal'),

    html.Div([  # modal div
        html.Div([  # content div
            html.Div([
                'This is the content of the modal',

            ]),

            html.Hr(),
            html.Button('Close', id='modal-close-button')
        ],
            style={'textAlign': 'center', },
            className='modal-content',
        ),
    ],
        id='modal',
        className='modal',
        style={"display": "block"},
    )
])


@app.callback(Output('modal', 'style'),
              [Input('modal-close-button', 'n_clicks')])
def close_modal(n):
    if (n is not None) and (n > 0):
        return {"display": "none"}


if __name__ == '__main__':
    app.run_server()
