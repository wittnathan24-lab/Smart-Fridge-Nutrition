# Validation Supabase — 20 septembre 2026

Projet : `tocsvignvijwxdghurzf` (région Europe, Irlande).

Le schéma `202609180001_smart_fridge.sql` a été appliqué dans SQL Editor dans une transaction. Les tables `profiles`, `fridge_items` et `planned_meals`, leurs politiques RLS, le déclencheur de profil et la fonction `create_meal_plan` sont en place. L'application locale utilise l'URL et la clé publique du projet depuis `.env`, exclu de Git. La clé serveur Supabase est utilisée uniquement côté serveur pour créer les comptes confirmés.

Les sessions invitées sont activées avec l'accord du propriétaire. Les inscriptions classiques sont confirmées directement côté serveur, sans envoi d'e-mail.

## Contrôles réussis

- 50 tests automatisés locaux ; analyse Ruff sans erreur.
- Test réel `python -m scripts.check_supabase` : deux comptes invités distincts, création et lecture du profil, ajout/modification/suppression d'ingrédient, création et suppression de repas, refus d'un second plan le même jour et renouvellement de session.
- Isolation réelle : le second compte ne voit pas les données du premier, ne peut pas les supprimer et ne peut pas créer une ligne au nom du premier. Une requête sans session ne reçoit aucune ligne privée.
- Navigateur : le bouton Démo charge le profil et le frigo depuis Supabase ; l'autocomplétion propose Carotte et l'ajout de 250 g fonctionne.

## Présentation

Lancer `python -m uvicorn main:app --host 127.0.0.1 --port 8000`, ouvrir `http://127.0.0.1:8000`, puis choisir **Explorer la démo**. Dans Supabase, **Table Editor > fridge_items** permet de montrer les ingrédients persistés et leur `user_id`.

Les comptes de test invités et leurs ingrédients de départ restent dans la base pour inspection. Le site fonctionne localement avec une base distante ; aucun hébergement public du serveur n'a été réalisé dans cette étape. Le parcours d'inscription sans e-mail de confirmation doit être vérifié avec une adresse personnelle sur le projet Supabase cible.
