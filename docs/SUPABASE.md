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

4. Dans **Authentication > Sign In / Providers**, garder Email et **Confirm email** activés. Pour le bouton Démo, activer **Allow anonymous sign-ins** : chaque visiteur obtient son propre compte invité protégé par RLS, sans adresse fictive ni désactivation de la confirmation des comptes classiques.
5. Redémarrer FastAPI puis créer un compte dans l'application.

6. Dans **Authentication > URL Configuration**, régler **Site URL** sur l'adresse réelle de l'application : `http://127.0.0.1:8000` pour la démonstration locale. Le réglage par défaut `http://localhost:3000` ne correspond pas à ce projet. Après publication, remplacer cette valeur par l'adresse publique du site.

Le formulaire permet de renvoyer un lien de confirmation sans ressaisir le mot de passe. Le retour du lien rétablit la session et retire les jetons de la barre d'adresse. Les erreurs distinguent une adresse non confirmée, des identifiants incorrects et une limite d'envoi atteinte. Le minimum de 10 caractères s'applique à l'inscription, pas à la connexion à un compte existant.

Sans SMTP personnalisé, Supabase limite les destinataires et le nombre d'e-mails de confirmation. Configurer un fournisseur SMTP pour ouvrir les inscriptions au public : https://supabase.com/docs/guides/auth/auth-smtp. Ne pas confondre un échec de livraison avec une base de données indisponible.

La clé `service_role` ne doit jamais être ajoutée au projet : l'application utilise uniquement la clé anon/publishable et le jeton de l'utilisateur connecté, afin que les règles RLS restent effectives.

## Déploiement du schéma avec la CLI

Depuis la racine du dépôt, initialiser la CLI si besoin avec `supabase init`, puis effectuer `supabase login` et `supabase link`. Enfin, lancer :

```powershell
supabase db push
```

Le schéma crée les tables `profiles`, `fridge_items`, `planned_meals`, leurs index, les règles RLS, le profil créé à l'inscription et une fonction transactionnelle de génération du plan.

## Données existantes

La base SQLite locale reste active tant que les deux variables Supabase sont absentes. Il n'y a pas de migration automatique des comptes locaux, car les mots de passe ne peuvent pas être transférés vers Supabase Auth. Les utilisateurs créent donc un nouveau compte après l'activation de Supabase.

## Vérification réelle

La commande `python -m scripts.check_supabase` crée deux comptes invités dans le projet configuré. Elle vérifie les sessions, leur renouvellement, le profil, les opérations sur le frigo, le plan de repas et le refus d'accès aux données d'un autre utilisateur. Elle conserve les comptes invités et leurs ingrédients initiaux pour inspection ; elle supprime uniquement l'ingrédient et le repas ajoutés par son scénario. Elle n'affiche aucune clé ni aucun jeton.

Les tests ordinaires (`python -m pytest`) restent isolés sur SQLite, même lorsque `.env` pointe vers Supabase. Une configuration Supabase partielle provoque une erreur explicite au lieu de basculer silencieusement en local.

Pour une publication publique, configurer la protection CAPTCHA des sessions invitées et prévoir leur nettoyage périodique. Une session invitée perdue ne peut pas être récupérée par e-mail.
