import os
import requests

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
    response = requests.get(API_NINJAS_CARS_URL, headers=headers, params=params, timeout=10)

    if response.status_code == 200:
        data = response.json()
        if data:
            # API returns a list of dicts with keys like 'make', 'model', etc.
            return {"make": data[0].get("make"), "model": data[0].get("model")}
        return None
    else:
        print(f"[API NINJAS ERROR] Status: {response.status_code}, Body: {response.text}")
        return None
