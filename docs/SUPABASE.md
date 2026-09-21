# Base de données Supabase

L'application utilise Supabase Auth pour les comptes et Postgres pour les profils, le frigo et le plan de repas. Chaque table active Row Level Security (RLS) : un utilisateur authentifié ne peut lire ou modifier que les lignes associées à son propre identifiant.

## Première connexion

1. Créer un projet dans le tableau de bord Supabase.
2. Dans **SQL Editor**, exécuter le contenu de `supabase/migrations/202609180001_smart_fridge.sql`.
3. Dans **Settings > API**, copier l'URL du projet et la clé **anon/publishable** dans un fichier local `.env` :

   ```env
   SUPABASE_URL=https://votre-projet.supabase.co
   SUPABASE_ANON_KEY=votre-cle-anon-ou-publishable
   ```

4. Dans **Authentication > Sign In / Providers**, activer Email. L'inscription serveur confirme directement les comptes et n'envoie pas d'e-mail. Le bouton Démo utilise désormais un compte permanent partagé ; il ne crée plus de compte invité.
5. Redémarrer FastAPI puis créer un compte dans l'application.

6. Dans **Authentication > URL Configuration**, régler **Site URL** sur l'adresse réelle de l'application : `http://127.0.0.1:8000` pour la démonstration locale. Le réglage par défaut `http://localhost:3000` ne correspond pas à ce projet. Après publication, remplacer cette valeur par l'adresse publique du site.

L'inscription crée le compte via l'API serveur Supabase avec `email_confirm: true`, puis ouvre immédiatement une session. Aucun SMTP n'est nécessaire pour créer un compte. Le minimum de 10 caractères s'applique à l'inscription, pas à la connexion à un compte existant.

`SUPABASE_SECRET_KEY` est réservée au serveur, dans `.env` exclu de Git. Elle sert uniquement à vérifier les comptes existants avant inscription et à provisionner le compte démo. Les requêtes de profils, frigos et repas continuent d'utiliser la clé publique et le jeton de l'utilisateur pour maintenir RLS. Ne jamais transmettre la clé secrète au navigateur.

## Compte démo permanent

Renseigner la clé serveur puis exécuter `python -m scripts.setup_demo_account` une seule fois. Le script crée un compte confirmé réservé à la démonstration et enregistre un mot de passe aléatoire ainsi que son identifiant dans `.env`. Une nouvelle exécution conserve le compte et ses données. Redémarrer le serveur après cette configuration.

Chaque clic sur Démo se connecte ensuite à ce même compte. Son frigo, son profil et ses repas sont partagés et ne sont pas réinitialisés à la connexion. Les comptes personnels gardent leurs données séparées. Les anciens comptes invités ne sont pas supprimés automatiquement.

L'inscription refuse avec HTTP 409 une adresse déjà présente, même en attente de confirmation. La recherche côté serveur parcourt toutes les pages des comptes et ne renvoie pas leur liste au navigateur. Supabase conserve également sa contrainte d'unicité. Pour un grand volume d'utilisateurs, remplacer cette recherche paginée par un index serveur dédié.

## Déploiement du schéma avec la CLI

Depuis la racine du dépôt, initialiser la CLI si besoin avec `supabase init`, puis effectuer `supabase login` et `supabase link`. Enfin, lancer :

```powershell
supabase db push
```

Le schéma crée les tables `profiles`, `fridge_items`, `planned_meals`, leurs index, les règles RLS, le profil créé à l'inscription et une fonction transactionnelle de génération du plan.

## Données existantes

La base SQLite locale reste active tant que les deux variables Supabase sont absentes. Il n'y a pas de migration automatique des comptes locaux, car les mots de passe ne peuvent pas être transférés vers Supabase Auth. Les utilisateurs créent donc un nouveau compte après l'activation de Supabase.

## Vérification réelle

La commande `python -m scripts.check_supabase` ouvre deux sessions sur le compte démo existant, sans créer d'utilisateur. Elle vérifie la connexion par mot de passe, le refus de réinscription, le renouvellement, le profil, les opérations sur le frigo et la génération de repas. Elle supprime uniquement l'ingrédient et les repas ajoutés par son scénario. Elle n'affiche aucune clé ni aucun jeton.

Les tests ordinaires (`python -m pytest`) restent isolés sur SQLite, même lorsque `.env` pointe vers Supabase. Une configuration Supabase partielle provoque une erreur explicite au lieu de basculer silencieusement en local.

Pour une publication publique, limiter les abus sur le compte démo partagé et ne jamais y saisir de données personnelles.
