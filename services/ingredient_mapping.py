"""Mapping anglais britannique (TheMealDB) -> americain (USDA).

TheMealDB utilise des noms d'ingredients en anglais britannique qui n'ont
souvent aucune correspondance directe dans USDA FoodData Central, redige en
anglais americain. Ce dictionnaire sert de secours (fallback) quand une
recherche USDA directe ne renvoie aucun resultat.
"""

BRITISH_TO_AMERICAN = {
    "aubergine": "eggplant",
    "courgette": "zucchini",
    "coriander": "cilantro",
    "spring onion": "scallion",
    "beetroot": "beet",
    "mince": "ground meat",
    "mangetout": "snow peas",
    "prawns": "shrimp",
    "chickpeas": "garbanzo beans",
    "plain flour": "all-purpose flour",
    "caster sugar": "superfine sugar",
    "icing sugar": "powdered sugar",
    "cornflour": "cornstarch",
    "double cream": "heavy cream",
    "single cream": "light cream",
    "rocket": "arugula",
    "swede": "rutabaga",
    "gammon": "ham",
    "streaky bacon": "bacon",
    "black treacle": "molasses",
    "tomato puree": "tomato paste",
    "wholemeal flour": "whole wheat flour",
}


def to_american_english(ingredient_name: str) -> str | None:
    """Renvoie l'equivalent americain connu, ou None si pas de mapping."""
    return BRITISH_TO_AMERICAN.get(ingredient_name.strip().lower())
