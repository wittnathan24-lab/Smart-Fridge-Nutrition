# Smart Fridge & Nutrition Coach

Application web fullstack de coaching nutritionnel intelligent. Elle permettra de renseigner son profil corporel, de gérer le contenu de son frigo virtuel et de recevoir des suggestions de recettes avec leurs apports caloriques et macronutritionnels.

## Démarrage rapide

Créer un environnement virtuel puis installer les dépendances :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Lancer l'API en développement :

```powershell
uvicorn main:app --reload
```

L'API est disponible sur `http://127.0.0.1:8000`.

- Documentation interactive : `http://127.0.0.1:8000/docs`
- Vérification de santé : `http://127.0.0.1:8000/health`

## Stack prévue

- FastAPI et Pydantic
- Jinja2 et Tailwind CSS
- SQLite puis PostgreSQL
- TheMealDB et USDA FoodData Central
- Authentification JWT
