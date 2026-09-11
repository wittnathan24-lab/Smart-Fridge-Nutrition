import httpx

from config import get_settings
from schemas import USDAFoodMatch

REQUEST_TIMEOUT_SECONDS = 10.0

# Impose les bases officielles brutes pour ecarter les plats industriels/prepares.
ALLOWED_DATA_TYPES = ["SR Legacy", "Foundation"]


class USDAError(Exception):
    """Erreur lors d'un appel a USDA FoodData Central (timeout, 429, statut inattendu)."""


async def search_food(client: httpx.AsyncClient, query: str) -> USDAFoodMatch | None:
    settings = get_settings()
    try:
        response = await client.post(
            f"{settings.usda_base_url}/foods/search",
            params={"api_key": settings.usda_api_key},
            json={"query": query, "dataType": ALLOWED_DATA_TYPES, "pageSize": 1},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise USDAError(f"Timeout lors de la recherche USDA pour '{query}'") from exc
    except httpx.HTTPStatusError as exc:
        raise USDAError(_status_error_message(exc, query)) from exc

    foods = response.json().get("foods") or []
    if not foods:
        return None
    return USDAFoodMatch.model_validate(foods[0])


def _status_error_message(exc: httpx.HTTPStatusError, query: str) -> str:
    if exc.response.status_code == 429:
        return f"Trop de requetes vers USDA (429) pour '{query}'"
    return f"Erreur USDA ({exc.response.status_code}) pour '{query}'"
