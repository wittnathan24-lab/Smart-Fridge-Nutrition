# Démonstration portfolio — 4 minutes

## Pitch

« Smart Fridge transforme un inventaire d’ingrédients en idées de repas, puis aide à comparer une journée de repas à des repères nutritionnels. J’ai construit une application FastAPI complète : comptes privés, persistance, intégration de deux API et interface responsive. »

## Parcours conseillé

1. **0:00 — Problème.** Ouvrir l’accueil : éviter de chercher une recette sans savoir ce que l’on a déjà.
2. **0:30 — Prise en main.** Cliquer sur Explorer la démo. Expliquer que les données sont fictives et que l’espace est individuel.
3. **1:00 — Personnalisation.** Modifier le niveau d’activité, sauvegarder et observer la cible calorique.
4. **1:30 — Inventaire.** Ajouter un ingrédient, modifier sa quantité. Montrer les trois recettes de démonstration.
5. **2:00 — Du plat au journal.** Ouvrir un bowl, lire la préparation et ajouter une demi-portion. Montrer les jauges mises à jour.
6. **2:30 — Génération.** Choisir une autre date vide et cliquer sur Composer ma journée automatiquement. Les trois repas s’ajustent à la cible énergétique.
7. **3:00 — Technique.** Ouvrir `/docs` et expliquer JWT, SQLite, les validateurs Pydantic et la recherche asynchrone.
8. **3:30 — Recul.** Expliquer pourquoi une tasse ne devient pas arbitrairement 100 g et pourquoi une donnée inconnue n’est pas zéro. Montrer les tests d’isolation des comptes.

## Points à défendre en entretien

- La frontière entre données brutes, modèles normalisés et présentation.
- Les 20 paires d’ingrédients TheMealDB aplaties dans un validateur.
- Les identifiants USDA plutôt que la position des nutriments dans un tableau.
- Des requêtes SQL paramétrées et filtrées par utilisateur pour éviter les accès croisés.
- Une démo déterministe pour montrer le produit même si une API est indisponible.
- Des limites explicites : ni exactitude nutritionnelle prétendue, ni conversion inventée.

## Captures utiles à réaliser

Accueil sur ordinateur ; profil et frigo remplis ; journée générée avec jauges ; fiche recette sur mobile. N’utiliser que le compte de démonstration dans les captures publiques.
