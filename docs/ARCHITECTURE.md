# Décisions d’architecture

## Conserver le socle

Le dépôt possédait FastAPI, les intégrations USDA/TheMealDB et une première interface. Le premier commit de cette intervention sauvegarde ces modifications préexistantes. Les étapes suivantes complètent ce socle sans remplacer la stack.

## Supabase et séparation des comptes

Supabase Auth est la source des comptes. Trois tables Postgres complètent le domaine : `profiles`, `fridge_items`, `planned_meals`. Elles référencent `auth.users`, sont protégées par Row Level Security et ne laissent chaque utilisateur agir que sur ses propres lignes. Le profil est stocké sous forme JSON validée par Pydantic. La génération de journée est une fonction Postgres transactionnelle : une journée déjà remplie n’est pas remplacée.

Le schéma est versionné dans `supabase/migrations/`. SQLite demeure un secours local tant que Supabase n’est pas configuré, ce qui permet aux tests et à la démo de rester autonomes. Les comptes SQLite ne sont pas migrés automatiquement, car leurs mots de passe ne peuvent pas être transférés à Supabase Auth.

## Authentification

Avec Supabase configuré, Supabase Auth gère les mots de passe, la signature, l’expiration et le renouvellement des sessions. L’API vérifie le jeton auprès d’Auth et le transmet à PostgREST pour que les règles RLS soient actives. Le précédent flux PyJWT/scrypt est conservé uniquement pour le mode local sans Supabase. Une protection locale limite les tentatives d’authentification et la création de démos.

Le choix PyJWT remplit le besoin JWT du brief avec une bibliothèque dédiée ; il remplace la suggestion python-jose. Le navigateur envoie le jeton dans Authorization. La session de l’onglet permet le rechargement sans conserver le jeton entre sessions de navigateur.

## Intégrations

Le client httpx est géré par le cycle de vie FastAPI. Les recherches d’ingrédients sont concurrentes, limitées à 12 ingrédients distincts pour les suggestions. Les résultats partiels des recherches restent utilisables ; une panne totale renvoie 502. Les erreurs réseau, quotas et formats invalides sont convertis en erreurs métier.

Les ingrédients USDA sont recherchés en parallèle. La sélection est volontairement simple, sans modèle probabiliste ni correction automatique de densité. Le mapping lexical réduit les différences français/anglais et britannique/américain. Les totaux incomplets sont signalés et ne servent pas à composer un plan automatique.

## Interface

Jinja2 sert le HTML ; JavaScript orchestre les API. Tailwind est compilé localement et complété par une feuille graphique dédiée. Les chaînes issues des utilisateurs et des fournisseurs sont échappées avant insertion HTML. Les dialogues natifs gèrent le focus ; les retours d’action utilisent des zones de statut et les contrôles ont des libellés accessibles. Une préférence de réduction des animations est respectée.

## Tests et limites de validation

Tests automatisés avec SQLite temporaire et `httpx.MockTransport`. Parcours de démonstration vérifié dans le navigateur sur ordinateur et à 390 px de large. Les services externes ne sont pas validés de bout en bout avec une clé USDA réelle dans cette livraison. La CI est ajoutée au dépôt mais son exécution distante attend un push.
