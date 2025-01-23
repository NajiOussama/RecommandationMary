from dotenv import load_dotenv
import os
import openai

# Charger les variables d'environnement depuis un fichier .env
load_dotenv()

# Récupérer la clé API directement depuis les variables d'environnement
openai.api_key = ""
from openai import OpenAI
import pandas as pd 
import geopy
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
import certifi
import ssl 
from geopy.exc import GeocoderTimedOut
import time
import numpy as np
import json

from unidecode import unidecode

client = OpenAI()

def get_lat_long(location_name):
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    geolocator = Nominatim(user_agent="france_zip_code_locator", ssl_context=ssl_context)
    try:
        location = geolocator.geocode(f"{location_name}, France")
        if location:
            return location.latitude, location.longitude
    except GeocoderTimedOut:
        print("Geocoding service timed out.")
    return None

with open('postal_code_coordinates.json', 'r') as file: #lire
    postal_code_coordinates = json.load(file)

def calculate_distance(row, client_location):
    vehicle_coords = postal_code_coordinates.get(row['ville'])
    if not vehicle_coords or len(vehicle_coords) != 2:
        # Gérer les cas où les coordonnées sont manquantes ou incorrectes
        return float('inf')
    
    return geodesic(client_location, vehicle_coords).kilometers

def recommender(full_description: str, 
                zip_code: str,
                max_mileage: int = None, 
                max_price: int = None, 
                brand: str = None, 
                model: str = None, 
                version: str = None, 
                energy: str = None,
                gearbox: str = None,
                seats_number: int = None,
                color: str = None):
    
    df = pd.read_csv('/Users/oussamanaji/Downloads/vo_vehicle (1).csv', encoding="ISO-8859-1", sep=";")
    
    if brand:
        filt = df['marque'] == unidecode(brand).upper()
        if model:
            filt &= df['search_modele'] == unidecode(model).upper()
    
    else:
        llm_call = client.chat.completions.create(
    messages=[
        {
            "role": "system",
            "content": f"Réponds à la description suivante avec un JSON comportant "
                       f"la clé 'vehicles' qui correspond à une liste de dictionnaires "
                       f"comportant chacun une clé 'brand', une clé 'model' et une clé 'version'. "
                       f"Tu ne précises la version que si elle est explicitement présente dans la description "
                       f"(null sinon). Parmi tes recommandations, tu dois lorsque c'est possible proposer en priorité "
                       f"des modèles Peugeot, Renault, Citroën, Dacia. Description : {full_description}"
        }
    ],
    model="gpt-4o-mini",
    response_format={"type": "json_object"}
)
        eligible_vehicles = json.loads(llm_call.choices[0].message.content).get("vehicles", [])
        print(eligible_vehicles)
        eligible_brands = [unidecode(vehicle.get("brand")).upper() for vehicle in eligible_vehicles]
        eligible_models = [unidecode(vehicle.get("model")).upper() for vehicle in eligible_vehicles]

        filt = (df['marque'].isin(eligible_brands)) & (df['search_modele'].isin(eligible_models))

    if max_mileage:
        filt &= df['kilometres'] <= max_mileage * 1.05

    if max_price:
        filt &= df['prix_ttc'] <= max_price * 1.1
    
    if energy:
        filt &= df['energie'] == energy
    
    if gearbox:
        filt &= df['type_boite'] == gearbox
    
    if seats_number:
        filt &= df['nb_places'] == seats_number
    
    if color:
        filt &= df['couleur'] == color

    df_filtered = df[filt].copy()
    
    df_filtered.loc[:, 'ville'] = df_filtered["ville"].astype(str).apply(lambda x: "0"*(5 - len(x)) + x)


    client_location = get_lat_long(zip_code)
    df_filtered.loc[:, 'distance'] = df_filtered.apply(lambda row: calculate_distance(row, client_location), axis=1)


    try:
        third_smallest_distance = sorted(df_filtered['distance'].unique())[2]
    except:
        third_smallest_distance = df_filtered['distance'].min()

    distance_filts = [df_filtered[df_filtered['distance'] == df_filtered['distance'].min()], df_filtered[df_filtered['distance'] <= third_smallest_distance], df_filtered[df_filtered['distance'] <= 50], df_filtered]

    for _, intent in enumerate(distance_filts):

        if intent.shape[0] > 2:
            break

    return intent[['ville', 'distance', 'marque', 'search_modele', 'prix_ttc']]
