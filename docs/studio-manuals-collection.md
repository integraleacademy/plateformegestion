# Collection Manuels illustrés

42 modèles : 6 compositions pour chacun des univers APS, SSIAP 1, A3P, VTC,
direction d’entreprise de sécurité, BTS et communication générale.

## Compositions

- Couverture : grand titre, scène illustrée et appel à l’action.
- Session : invitation, illustration et date personnalisable.
- Immersion : scène de métier et légende sur fond bleu nuit.
- Compétences : scène et trois repères modifiables.
- Parcours : illustration et trois étapes d’accompagnement.
- Pratique : diptyque de deux illustrations et message éditorial.

Chaque modèle possède des textes propres à son métier, des champs modifiables
et une géométrie pour les quatre formats du studio. Aucune date de session,
durée, disponibilité ou promesse de financement n’est inventée. La date par
défaut des invitations est « Dates sur demande ».

## Illustrations

18 fichiers WebP locaux, environ 3,1 Mo au total. Six illustrations sont
extraites du manuel SSIAP 1 fourni par le propriétaire. Les douze autres sont
générées avec l’outil imagegen intégré, à partir du style de l’illustration
du plan d’évacuation (page 8) : contours bleu marine, aplats et ombrages nets,
anatomie adulte, décors lumineux et gestes professionnels.

Scènes générées : accueil et poste de sécurité APS ; accompagnement et
briefing A3P ; accueil et préparation VTC ; pilotage d’équipe et projet
d’entreprise ; campus et tutorat BTS ; entretien d’orientation et travail
de groupe. Les références et dimensions figurent dans
`static/studio_visuals/img/manuals/sources.json`.

## Intégration

Filtre « MANUELS ILLUSTRÉS · 42 modèles », filtres par univers et accès direct
dans le panneau Modèles. Les créations déjà enregistrées restent conservées.
Le changement de formation garde la composition illustrée quand un univers
correspondant existe. Les modèles utilisent les fonctions natives de texte,
logo, historique, validation et export.

Le catalogue de démonstration `static/studio_visuals/manuals-preview.html`
ne contient que les modèles publics et leurs textes d’exemple. Il ne contacte
aucune API d’administration et n’expose aucune donnée enregistrée.

## Vérification

Commande : `node --test tests/studio-manual-regressions.mjs tests/studio-new3-regressions.mjs tests/studio-template-structure.mjs tests/studio-layout-regressions.mjs`.

Contrôles effectués : identifiants uniques, présence des 18 images, champs
éditables, conservation des textes personnalisés, échappement HTML et
non-régression des compositions existantes. Les 15 tests passent.

Le contrôle de géométrie des 168 combinaisons peut être lancé avec
`static/studio_visuals/manuals-preview.html?audit=1`. Il utilise le moteur,
les styles, les polices et la validation réels du studio. Il vérifie aussi
la surface disponible pour les illustrations et le placement du logo.
Le bouton d’export utilise le même exporteur PNG que l’éditeur.

L’aperçu est public et autonome pour le contrôle des exemples. Le fichier
`studio-manual-preview.bundle.js` regroupe les dépendances afin de limiter
les requêtes au démarrage. Le régénérer après toute modification du moteur :

```sh
npx --yes esbuild@0.28.2 static/studio_visuals/js/studio-manual-preview.js --bundle --format=iife --minify --outfile=static/studio_visuals/js/studio-manual-preview.bundle.js
```

La collection a été fusionnée sur `main` et déployée sur Render après
l’accord explicite du propriétaire le 4 octobre 2026.
