# Smart Fridge & Nutrition Coach

Une application fullstack pour partir des ingrédients disponibles, explorer des recettes et composer une journée de repas avec un suivi énergétique et des macronutriments.

**FastAPI · Supabase Auth & Postgres · Pydantic · httpx/asyncio · Jinja2 · Tailwind CSS**

## Essayer en deux minutes

Python 3.11 ou supérieur.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn main:app --reload
```

Ouvrir **http://127.0.0.1:8000**, puis **Explorer la démo**. Aucune clé API n’est nécessaire pour cette démonstration. Chaque visiteur reçoit un espace distinct avec un profil fictif, quatre ingrédients et trois recettes illustratives. Sans variables Supabase, les données restent dans SQLite local pour faciliter le développement.

Pour activer la base cloud, suivre le [guide Supabase](docs/SUPABASE.md), renseigner `SUPABASE_URL` et `SUPABASE_ANON_KEY` dans `.env`, puis redémarrer l’application. Supabase Auth gère alors l’inscription, la connexion, les sessions et les accès Postgres.

Pour un compte personnel, utiliser **Se connecter → Créer mon compte**. Les recettes sont alors recherchées sur TheMealDB. Renseigner `USDA_API_KEY` dans `.env` pour obtenir leurs estimations nutritionnelles.

- Interface : `/` ou `/app`
- Documentation interactive : `/docs` (bouton **Authorize**, jeton obtenu avec `/auth/login`)
- Santé du serveur : `/health`
- Informations API : `/api`

## Fonctionnalités livrées

- Inscription et connexion via Supabase Auth ; sessions renouvelables et contrôle des accès Postgres avec RLS.
- Profil corporel persistant, calcul Mifflin–St Jeor, dépense énergétique et cible selon l’objectif.
- Frigo privé : ajout, modification de quantité et suppression.
- Autocomplétion locale des ingrédients avec recherche sans accents, suggestions pour les petites fautes, navigation clavier et noms canoniques validés côté serveur. Le catalogue partage le dictionnaire de traduction des intégrations ; il ne garantit pas qu’une recette ou une fiche USDA existe pour chaque ingrédient.
- Suggestions dédupliquées et classées par nombre d’ingrédients correspondants.
- Détail des recettes, préparation, ingrédients et apports estimés via USDA.
- Plan quotidien persistant, portions ajustables, ajout et retrait des repas.
- Génération de trois repas ajustés à la cible énergétique pour une journée vide.
- Jauges calories/protéines/glucides/lipides, états vides, erreurs lisibles et interface responsive.
- Mode de démonstration indépendant des services externes.

## Configuration

| Variable             | Usage                                                                                             |
| -------------------- | ------------------------------------------------------------------------------------------------- |
| `USDA_API_KEY`       | Clé FoodData Central ; facultative pour démarrer et pour la démo                                  |
| `JWT_SECRET`         | Secret aléatoire d’au moins 32 caractères ; requis pour conserver les sessions entre redémarrages |
| `DATABASE_PATH`      | Chemin SQLite, `smart_fridge.db` par défaut                                                       |
| `SUPABASE_URL`       | URL du projet Supabase ; active Supabase Auth et Postgres avec la clé ci-dessous                  |
| `SUPABASE_ANON_KEY`  | Clé anon/publishable Supabase, utilisée avec le jeton de l’utilisateur pour appliquer RLS         |
| `THEMEALDB_BASE_URL` | URL du service de recettes, configurable dans les settings                                        |
| `USDA_BASE_URL`      | URL du service nutritionnel, configurable dans les settings                                       |

Générer un secret avec `python -c "import secrets; print(secrets.token_urlsafe(48))"`, puis le placer dans `.env`. Sans secret configuré, une clé aléatoire de développement est créée au démarrage. Ne jamais versionner `.env` ni la base.

## Architecture

```text
Navigateur : Jinja2 + JavaScript + Tailwind compilé
                 │ JSON / Bearer JWT
                 ▼
FastAPI ─── auth.py : comptes et authentification
   │       personal.py : profils et journal quotidien
   │       models.py / schemas.py : validation et calculs
   │       database.py : Supabase Auth/Postgres avec RLS, SQLite local de secours
   └────── services/ : TheMealDB → normalisation → USDA → agrégation
```

Supabase Auth émet les jetons utilisateur. La couche de données transmet ce jeton à Postgres, afin que les politiques RLS filtrent chaque requête dans la base. Les tests vérifient également qu’un second compte ne peut ni lire ni modifier les données du premier. Les appels aux fournisseurs passent par un client HTTP partagé et les recherches indépendantes s’exécutent avec `asyncio.gather`.

## Calculs et limites assumées

- BMR : `10 × poids + 6,25 × taille − 5 × âge + offset` (5 ou −161). TDEE : BMR × facteur d’activité.
- Objectifs du brief : −500 kcal, maintien ou +300 kcal. La cible calculée ne descend pas sous le BMR. Le formulaire est limité aux adultes et à des bornes de saisie documentées dans `models.py`.
- Les repères de macros utilisent une répartition illustrative 25 % protéines, 45 % glucides, 30 % lipides. Il ne s’agit pas d’une prescription individuelle.
- USDA est interrogé en POST avec `dataType: ["SR Legacy", "Foundation"]`. Les nutriments sont identifiés par leurs IDs 1008, 1003, 1005 et 1004.
- Les mesures explicites en g/kg sont converties. Les fractions ambiguës, cuillères, tasses et pièces ne sont pas extrapolées sans densité fiable. Une donnée inconnue reste `null`, jamais zéro.
- Les totaux externes concernent la recette entière. La fraction saisie permet de répartir cette recette. Les recettes de démo sont explicitement données pour une portion.
- Une recette partiellement quantifiée reste consultable, mais son ajout au journal est désactivé. La génération réelle nécessite trois recettes entièrement quantifiées parmi les trois premières suggestions ; elle peut donc être indisponible avec les données TheMealDB.
- La génération ajuste l’énergie en répartissant 30/35/35 % sur trois repas ; elle ne garantit pas un optimum de macros ni une disponibilité suffisante des quantités dans le frigo.
- La sélection USDA prend le premier résultat brut : une correspondance lexicale ne garantit pas une équivalence parfaite cru/cuit. Les apports sont des estimations.

## Vérifier et contribuer

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m ruff check main.py auth.py config.py database.py demo.py middleware.py models.py personal.py schemas.py services tests
python -m ruff format --check main.py auth.py config.py database.py demo.py middleware.py models.py personal.py schemas.py services tests
```

Les tests utilisent des bases temporaires et des réponses HTTP simulées. Ils ne consomment aucun quota externe. Ils couvrent l’authentification, les données privées, les calculs, les mesures, les structures USDA/TheMealDB, les pannes et la génération d’une journée. La CI GitHub exécute ces contrôles à chaque push et pull request.

Pour modifier les styles (Node.js nécessaire uniquement à la compilation) :

```powershell
npm ci
npm run build:css
```

Le CSS compilé est versionné : le serveur Python n’a pas besoin de Node.js. Les polices Google disposent de polices système de remplacement.

## Présentation portfolio

Consulter [le scénario de démonstration](docs/PORTFOLIO.md) et [les décisions techniques](docs/ARCHITECTURE.md). L’historique Git conserve le socle existant puis les étapes sécurité, interface, génération et validation.

## Exécution et exploitation

Cette version est destinée à une démonstration locale. Avant exposition publique : HTTPS, secret stable, sauvegardes SQLite, limitation de requêtes au proxy, politique de conservation des comptes de démo et procédure de suppression des comptes. Le limiteur fourni couvre 20 tentatives d’authentification par minute et par adresse dans un seul processus. Il n’est pas distribué. Les JWT sont stockés dans la session de l’onglet ; se déconnecter les retire du navigateur mais ne révoque pas une copie déjà émise.

La réinitialisation des mots de passe, la gestion des allergies et le déploiement public restent à mettre en place.
