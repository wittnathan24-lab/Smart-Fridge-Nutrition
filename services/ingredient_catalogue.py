"""Shared, offline catalogue: display labels and aliases use the API mapping."""

from services.ingredient_mapping import BRITISH_TO_AMERICAN, FRENCH_TO_AMERICAN, _key

SPELLINGS = {
    "boeuf hache": "Bœuf haché",
    "porc hache": "Porc haché",
    "cotelette": "Côtelette",
    "huitre": "Huître",
    "farine complete": "Farine complète",
    "farine de mais": "Farine de maïs",
    "chou de bruxelles": "Chou de Bruxelles",
    "piment de cayenne": "Piment de Cayenne",
    "mure": "Mûre",
    "pasteque": "Pastèque",
    "peche": "Pêche",
    "celeri": "Céleri",
    "epinard": "Épinard",
    "mais": "Maïs",
    "boeuf": "Bœuf",
    "oeuf": "Œuf",
    "creme fraiche": "Crème fraîche",
    "creme liquide": "Crème liquide",
    "creme": "Crème",
    "pates": "Pâtes",
    "pates completes": "Pâtes complètes",
    "riz basmati": "Riz basmati",
    "ble": "Blé",
    "semoule de ble": "Semoule de blé",
    "pois casse": "Pois cassé",
    "cacahuete": "Cacahuète",
    "graines de sesame": "Graines de sésame",
    "beurre de cacahuete": "Beurre de cacahuète",
    "huile de sesame": "Huile de sésame",
    "concentre de tomate": "Concentré de tomate",
    "bouillon de legumes": "Bouillon de légumes",
    "gruyere": "Gruyère",
}


def build_catalogue():
    by_english = {}
    for french, english in FRENCH_TO_AMERICAN.items():
        entry = by_english.setdefault(
            {"eggs": "egg", "sausages": "sausage"}.get(english, english),
            {"name": SPELLINGS.get(french, french.capitalize()), "aliases": set()},
        )
        entry["aliases"].update([_key(french), _key(english)])
        if not french.endswith(("s", "x")):
            entry["aliases"].add(_key(french + "s"))
    for british, american in BRITISH_TO_AMERICAN.items():
        if american in by_english:
            by_english[american]["aliases"].add(_key(british))
    return sorted(
        [{"name": e["name"], "aliases": sorted(e["aliases"])} for e in by_english.values()],
        key=lambda e: _key(e["name"]),
    )


CATALOGUE = build_catalogue()
LOOKUP = {
    alias: entry["name"]
    for entry in CATALOGUE
    for alias in [*entry["aliases"], _key(entry["name"])]
}


def canonical_name(name: str) -> str:
    recognized = LOOKUP.get(_key(name))
    if recognized is None:
        raise ValueError("Choisissez un ingrédient reconnu dans les suggestions.")
    return recognized
