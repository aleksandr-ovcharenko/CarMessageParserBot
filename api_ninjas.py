import os
import requests
import logging

API_NINJAS_TOKEN = os.getenv("API_NINJAS_TOKEN")
API_NINJAS_CARS_URL = "https://api.api-ninjas.com/v1/cars"


def get_car_info_from_ninjas(description: str):
    """
    Uses API Ninjas Cars API to get car brand and model by description.
    Returns a dict with 'make' and 'model' if found, else None.
    """
    if not API_NINJAS_TOKEN:
        raise ValueError("API_NINJAS_TOKEN is not set in environment")

    headers = {"X-Api-Key": API_NINJAS_TOKEN}
    params = {"limit": 1, "query": description}
    print(f"[API NINJAS REQUEST] Query: {description}")
    logging.info(f"[API NINJAS REQUEST] Query: {description}")
    response = requests.get(API_NINJAS_CARS_URL, headers=headers, params=params, timeout=10)
    print(f"[API NINJAS RESPONSE] Status: {response.status_code}, Body: {response.text}")
    logging.info(f"[API NINJAS RESPONSE] Status: {response.status_code}, Body: {response.text}")

    if response.status_code == 200:
        data = response.json()
        if data:
            # API returns a list of dicts with keys like 'make', 'model', etc.
            return {"make": data[0].get("make"), "model": data[0].get("model")}
        return None
    else:
        return None
