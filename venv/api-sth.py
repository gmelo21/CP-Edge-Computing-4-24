import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go
import requests
from datetime import datetime
import pytz

# Constants for IP address, port, and number of recent data points
IP_ADDRESS = "191.235.32.167"
PORT_STH = 8666
DASH_HOST = "0.0.0.0"
lastN = 30  # Number of most recent data points to retrieve

# Function to get data from the API for a specific attribute
def get_data(attribute, lastN):
    url = f"http://{IP_ADDRESS}:{PORT_STH}/STH/v1/contextEntities/type/Lamp/id/urn:ngsi-ld:Lamp:EDGE4/attributes/{attribute}?lastN={lastN}"
    headers = {
        'Content-Type': 'application/json',
        'fiware-service': 'smart',
        'fiware-servicepath': '/'
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        try:
            return data['contextResponses'][0]['contextElement']['attributes'][0]['values']
        except KeyError:
            return []  # Return an empty list if the expected data structure is not found
    else:
        print(f"Error accessing {url}: {response.status_code}, {response.text}")
        return []  # Return an empty list if the request fails

# Function to convert UTC timestamps to São Paulo time
def convert_to_sao_paulo_time(timestamps):
    utc = pytz.utc  # UTC timezone
    sao_paulo = pytz.timezone('America/Sao_Paulo')  # São Paulo timezone
    converted_timestamps = []
    for timestamp in timestamps:
        try:
            timestamp = timestamp.replace('T', ' ').replace('Z', '')
            converted_time = utc.localize(datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S.%f')).astimezone(sao_paulo)
        except ValueError:
            converted_time = utc.localize(datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')).astimezone(sao_paulo)
        converted_timestamps.append(converted_time)
    return converted_timestamps

app = dash.Dash(__name__)

# Define the layout of the Dash app
app.layout = html.Div([
    html.H1('Luminosity, Humidity, and Temperature Data Viewer'),  # Title of the app
    dcc.Graph(id='data-graph'),  # Graph component to display the data
    dcc.Store(id='data-store', data={'timestamps': [], 'luminosity_values': [], 'humidity_values': [], 'temperature_values': []}),
    dcc.Interval(id='interval-component', interval=10*1000, n_intervals=0)  # Update data every 10 seconds
])

# Callback to update the data store with new data from the API
@app.callback(
    Output('data-store', 'data'),
    Input('interval-component', 'n_intervals'),
    State('data-store', 'data')
)
def update_data_store(n, stored_data):
    luminosity_data = get_data('luminosity', lastN)
    humidity_data = get_data('humidity', lastN)
    temperature_data = get_data('temperature', lastN)

    if luminosity_data:
        luminosity_values = [float(entry['attrValue']) for entry in luminosity_data]
        timestamps = [entry['recvTime'] for entry in luminosity_data]
        timestamps = convert_to_sao_paulo_time(timestamps)

        # Sort the timestamps and associated data to ensure chronological order
        sorted_data = sorted(zip(timestamps, luminosity_values))
        sorted_timestamps, sorted_luminosity_values = zip(*sorted_data)

        stored_data['timestamps'] = list(sorted_timestamps)  # Overwrite with sorted data
        stored_data['luminosity_values'] = list(sorted_luminosity_values)

    if humidity_data:
        humidity_values = [float(entry['attrValue'].replace('%', '').strip()) for entry in humidity_data]
        stored_data['humidity_values'] = humidity_values

    if temperature_data:
        temperature_values = [float(entry['attrValue'].replace('°C', '').strip()) for entry in temperature_data]
        stored_data['temperature_values'] = temperature_values

    return stored_data

# Callback to update the graph with the new data
@app.callback(
    Output('data-graph', 'figure'),
    Input('data-store', 'data')
)
def update_graph(stored_data):
    if stored_data['timestamps']:
        trace_luminosity = go.Scatter(
            x=stored_data['timestamps'],
            y=stored_data['luminosity_values'],
            mode='lines+markers',
            name='Luminosity',
            line=dict(color='orange')
        )
        trace_humidity = go.Scatter(
            x=stored_data['timestamps'],
            y=stored_data['humidity_values'],
            mode='lines+markers',
            name='Humidity',
            line=dict(color='green')
        )
        trace_temperature = go.Scatter(
            x=stored_data['timestamps'],
            y=stored_data['temperature_values'],
            mode='lines+markers',
            name='Temperature',
            line=dict(color='blue')
        )

        fig_data = go.Figure(data=[trace_luminosity, trace_humidity, trace_temperature])
        fig_data.update_layout(
            title='Luminosity, Humidity, and Temperature Over Time',
            xaxis_title='Timestamp',
            yaxis_title='Values',
            hovermode='closest'
        )

        return fig_data

    return {}  # Return an empty figure if no data is available

if __name__ == '__main__':
    app.run_server(debug=True, host=DASH_HOST, port=8051)
