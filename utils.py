import requests

from config import ENDPOINT_URL, API_TOKEN, API_TIMEOUT


def send_to_api(data: dict):
    headers = {
        "X-API-TOKEN": API_TOKEN,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(ENDPOINT_URL, json=data, headers=headers, timeout=API_TIMEOUT)
        return response
    except requests.exceptions.RequestException as e:
        print("[API CONNECTION ERROR]", e)

        # Вернём объект-заглушку с .ok = False и текстом ошибки
        class DummyResponse:
            ok = False
            status_code = 503
            text = str(e)

        return DummyResponse()
