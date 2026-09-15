import httpx

from config import get_settings
from schemas import RecipeDetail, RecipeSummary

REQUEST_TIMEOUT_SECONDS = 10.0


class TheMealDBError(Exception):
    """Erreur lors d'un appel a TheMealDB (timeout, 429, statut inattendu)."""


async def search_recipes_by_ingredient(
    client: httpx.AsyncClient, ingredient: str
) -> list[RecipeSummary]:
    settings = get_settings()
    try:
        response = await client.get(
            f"{settings.themealdb_base_url}/filter.php",
            params={"i": ingredient},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        response.json()
    except httpx.RequestError as exc:
        raise TheMealDBError(
            f"Timeout lors de la recherche de recettes pour '{ingredient}'"
        ) from exc
    except ValueError as exc:
        raise TheMealDBError("Réponse externe invalide") from exc
    except httpx.HTTPStatusError as exc:
        raise TheMealDBError(
            _status_error_message(exc, f"la recherche de recettes pour '{ingredient}'")
        ) from exc

    try:
        meals = response.json().get("meals") or []
        return [RecipeSummary.model_validate(meal) for meal in meals]
    except (ValueError, AttributeError, TypeError) as exc:
        raise TheMealDBError("Format TheMealDB invalide") from exc


async def get_recipe_detail(client: httpx.AsyncClient, meal_id: str) -> RecipeDetail | None:
    settings = get_settings()
    try:
        response = await client.get(
            f"{settings.themealdb_base_url}/lookup.php",
            params={"i": meal_id},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        response.json()
    except httpx.RequestError as exc:
        raise TheMealDBError(f"Timeout lors de la recuperation de la recette {meal_id}") from exc
    except ValueError as exc:
        raise TheMealDBError("Réponse externe invalide") from exc
    except httpx.HTTPStatusError as exc:
        raise TheMealDBError(
            _status_error_message(exc, f"la recuperation de la recette {meal_id}")
        ) from exc

    try:
        meals = response.json().get("meals") or []
        if not meals:
            return None
        return RecipeDetail.model_validate(meals[0])
    except (ValueError, AttributeError, TypeError, KeyError) as exc:
        raise TheMealDBError("Format TheMealDB invalide") from exc


def _status_error_message(exc: httpx.HTTPStatusError, action: str) -> str:
    if exc.response.status_code == 429:
        return f"Trop de requetes vers TheMealDB (429) pendant {action}"
    return f"Erreur TheMealDB ({exc.response.status_code}) pendant {action}"
