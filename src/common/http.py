import requests
from tenacity import retry, stop_after_attempt, wait_exponential


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, max=60), reraise=True)
def get_json(url: str, **kwargs) -> dict:
    r = requests.get(url, timeout=30, **kwargs)
    r.raise_for_status()
    return r.json()
