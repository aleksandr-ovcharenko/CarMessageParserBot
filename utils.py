import aiohttp
import logging

# Ensure logging is configured the same as main.py
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)

from config import ENDPOINT_URL, API_TIMEOUT


async def send_to_api(data: dict, api_token: str):
    """
    Asynchronously sends data to the API endpoint
    Returns the API response
    """
    headers = {
        "X-API-TOKEN": api_token,
        "Content-Type": "application/json"
    }

    print(f"[API IMPORT REQUEST] URL: {ENDPOINT_URL}\nPayload: {data}")
    logging.info(f"[API IMPORT REQUEST] URL: {ENDPOINT_URL}\nPayload: {data}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                ENDPOINT_URL, 
                json=data, 
                headers=headers, 
                timeout=API_TIMEOUT
            ) as response:
                print(f"[API IMPORT RESPONSE] Status: {response.status}, Body: {await response.text()}")
                logging.info(f"[API IMPORT RESPONSE] Status: {response.status}, Body: {await response.text()}")
                
                # Create a response object similar to requests for compatibility
                class AsyncResponse:
                    def __init__(self, status, text, json_data=None):
                        self.status_code = status
                        self._text = text
                        self._json = json_data
                    
                    @property
                    def text(self):
                        return self._text
                    
                    def json(self):
                        return self._json if self._json else {}
                
                # Get response text once to avoid "Response payload is not completed" error
                response_text = await response.text()
                json_data = None
                try:
                    json_data = await response.json()
                except:
                    pass
                
                return AsyncResponse(response.status, response_text, json_data)
                
    except aiohttp.ClientError as e:
        print("[API CONNECTION ERROR]", e)
        logging.error(f"[API CONNECTION ERROR] {e}")

        # Return a dummy response object
        class DummyResponse:
            status_code = 503
            _text = str(e)
            
            @property
            def text(self):
                return self._text
            
            def json(self):
                return {}

        return DummyResponse()
