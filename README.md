# Smart Fridge & Nutrition Coach

Application web fullstack de coaching nutritionnel intelligent. Elle permettra de renseigner son profil corporel, de gérer le contenu de son frigo virtuel et de recevoir des suggestions de recettes avec leurs apports caloriques et macronutritionnels.

## Démarrage rapide

Créer un environnement virtuel puis installer les dépendances :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copier `.env.example` en `.env` et y renseigner votre clé USDA FoodData Central
(`USDA_API_KEY`, fournie par l'intervenant) :

```powershell
copy .env.example .env
```

Lancer l'API en développement :

```powershell
uvicorn main:app --reload
```

L'API est disponible sur `http://127.0.0.1:8000`.

- Interface utilisateur : `http://127.0.0.1:8000/app`
- Documentation interactive : `http://127.0.0.1:8000/docs`
- Vérification de santé : `http://127.0.0.1:8000/health`

## Premier calcul nutritionnel

L'endpoint `POST /profile/nutrition` accepte un profil et renvoie le métabolisme de base,
la dépense énergétique totale et la cible calorique selon l'objectif.

```json
{
	"weight_kg": 70,
	"height_cm": 175,
	"age": 30,
	"sex": "male",
	"activity_level": "moderate",
	"goal": "loss"
}
```

Le frigo est actuellement conservé en mémoire pour préparer l’intégration future de la base
de données. Les endpoints disponibles sont `POST /fridge/items` et `GET /fridge/items`.

## Recettes et nutrition (TheMealDB + USDA)

- `GET /recipes/search?ingredient=salmon` — recherche de recettes TheMealDB contenant
  un ingrédient.
- `GET /recipes/{meal_id}` — détail d'une recette, avec les ingrédients aplatis en
  `list[IngredientQuantity]` (TheMealDB éclate ces données sur 20 paires de clés en interne).
- `GET /recipes/{meal_id}/nutrition` — croise la recette avec USDA FoodData Central :
  calories et macros (protéines/glucides/lipides) par ingrédient identifiées via leurs IDs
  officiels (1008/1003/1005/1004), filtrées sur `dataType: ["SR Legacy", "Foundation"]` pour
  exclure les plats industriels. Les ingrédients introuvables dans l'USDA (même après le
  mapping anglais britannique → américain, ex. *aubergine* → *eggplant*) sont listés dans
  `unmatched_ingredients` plutôt que de faire échouer tout le calcul. Seules les quantités
  exprimées en grammes/kilogrammes sont converties dans le total estimé ; les autres unités
  (`cup`, `tbsp`...) restent disponibles par ingrédient via `nutrients_per_100g` sans entrer
  dans le total, faute de table de conversion fiable.
- `GET /fridge/suggestions` — recettes TheMealDB correspondant à au moins un ingrédient
  du frigo courant.

Les ingrédients peuvent être saisis en français dans le frigo (`poivron rouge`, `crème
fraîche`, `œufs`, etc.). Le dictionnaire de traduction couvre les fruits, légumes, viandes,
poissons, produits laitiers, céréales, légumineuses, noix, herbes, épices, huiles et sauces,
avec normalisation des accents et compatibilité avec les variantes anglaises de TheMealDB.

Les appels TheMealDB/USDA sont résilients aux timeouts et aux réponses `429 Too Many
Requests` (levée d'une erreur métier traduite en `502` plutôt qu'un crash serveur).

## Stack prévue

- FastAPI et Pydantic
- Jinja2 et Tailwind CSS
- SQLite puis PostgreSQL
- TheMealDB et USDA FoodData Central
- Authentification JWT
