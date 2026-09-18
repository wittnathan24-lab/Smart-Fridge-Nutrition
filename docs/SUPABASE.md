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

4. Dans **Authentication > Providers > Email**, activer Email. Pour un parcours local immédiat, désactiver temporairement **Confirm email**. Si la confirmation reste activée, l'inscription invite l'utilisateur à confirmer son adresse avant la connexion.
5. Redémarrer FastAPI puis créer un compte dans l'application.

La clé `service_role` ne doit jamais être ajoutée au projet : l'application utilise uniquement la clé anon/publishable et le jeton de l'utilisateur connecté, afin que les règles RLS restent effectives.

## Déploiement du schéma avec la CLI

Depuis la racine du dépôt, initialiser la CLI si besoin avec `supabase init`, puis effectuer `supabase login` et `supabase link`. Enfin, lancer :

```powershell
supabase db push
```

Le schéma crée les tables `profiles`, `fridge_items`, `planned_meals`, leurs index, les règles RLS, le profil créé à l'inscription et une fonction transactionnelle de génération du plan.

## Données existantes

La base SQLite locale reste active tant que les deux variables Supabase sont absentes. Il n'y a pas de migration automatique des comptes locaux, car les mots de passe ne peuvent pas être transférés vers Supabase Auth. Les utilisateurs créent donc un nouveau compte après l'activation de Supabase.
