from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
from sqlalchemy import create_engine
from sklearn.cluster import KMeans
import requests

app = Flask(__name__)
CORS(app)

# Database connection details
host = "dpg-cobrpren7f5s73ftpqrg-a.oregon-postgres.render.com"
database = "sheshank_sonji"
user = "sheshank_sonji_user"
password = "Lo2Ze5zVZSRPGxDLCg5WAKUXUfxo7rrZ"

# Establish a connection to the PostgreSQL database
engine = create_engine(f"postgresql://{user}:{password}@{host}/{database}")

# Function to get the nearest police station for a given latitude and longitude
def get_nearest_police_station(latitude, longitude, api_key):
    url = f"https://dev.virtualearth.net/REST/v1/Locations/{latitude},{longitude}?key={api_key}"
    
    response = requests.get(url)
    data = response.json()
    
    if response.status_code == 200:
        try:
            address = data["resourceSets"][0]["resources"][0]["name"]
            coordinates = data["resourceSets"][0]["resources"][0]["point"]["coordinates"]
            return address, coordinates[0], coordinates[1]
        except (IndexError, KeyError):
            print("Error: Unable to extract data from API response")
            return None, None, None
    else:
        print("Error: Failed to fetch data from Bing Maps API")
        return None, None, None

# Function to find the closest hospitals using Bhuvan API
def find_closest_hospitals_bhv(latitude, longitude, token, buffer=3000):
    url = f"https://bhuvan-app1.nrsc.gov.in/api/api_proximity/curl_hos_pos_prox.php?theme=hospital&lat={latitude}&lon={longitude}&buffer={buffer}&token={token}"
    response = requests.get(url)

    hospitals = []
    try:
        data = response.json()
        if "hospitals" in data:
            for hospital in data["hospitals"]:
                name = hospital["name"]
                address = hospital["address"]
                lat = float(hospital["lat"])
                lng = float(hospital["lon"])
                hospitals.append((name, address, lat, lng))
    except Exception as e:
        print("Error:", e)
    
    return hospitals

@app.route('/crime_locations', methods=['GET'])
def get_crime_locations():
    # Load the dataset from PostgreSQL using a SQL query
    query = """
        SELECT "latitude", "longitude"
        FROM "tool7"
    """
    data = pd.read_sql_query(query, engine)

    # Remove rows with missing values
    data.dropna(inplace=True)

    # Define features (latitude and longitude)
    X = data[['latitude', 'longitude']]

    # Choose the number of clusters (future locations)
    num_clusters = 5

    # Initialize the KMeans model
    kmeans = KMeans(n_clusters=num_clusters, random_state=0)

    # Fit the model on the latitude and longitude data
    kmeans.fit(X)

    # Predict the centroids of the clusters as future latitude and longitude
    future_locations = kmeans.cluster_centers_

    # Your Bing Maps API key and Bhuvan API token
    bing_api_key = "AjMNQNjkQra1lSLBQp7QsXk-IqUfE9o-Ml1jPPfJuiQIlFx3EmM3fzAF5tXYyP_k"
    bhuvan_token = "f0b50e5fac0ebb72705648240186ed3442f3b74a"

    # Get the nearest police station and hospitals for each future location
    locations_info = []
    for centroid in future_locations:
        latitude, longitude = centroid
        # Predicted Crime Locations
        location_info = {
            'Type': 'Predicted Crime Location',
            'Latitude': latitude,
            'Longitude': longitude
        }
        locations_info.append(location_info)

        # Police stations
        address, lat, lng = get_nearest_police_station(latitude, longitude, bing_api_key)
        if lat is not None and lng is not None:
            location_info = {
                'Type': 'Police Station',
                'Name': address,
                'Latitude': lat,
                'Longitude': lng
            }
            locations_info.append(location_info)
        
        # Hospitals using Bhuvan API
        nearest_hospitals = find_closest_hospitals_bhv(latitude, longitude, bhuvan_token)
        for hospital in nearest_hospitals:
            location_info = {
                'Type': 'Hospital',
                'Name': hospital[0],
                'Address': hospital[1],
                'Latitude': hospital[2],
                'Longitude': hospital[3]
            }
            locations_info.append(location_info)

    # Return the location information as JSON
    return jsonify(locations_info)

