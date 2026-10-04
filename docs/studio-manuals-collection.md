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

Le contrôle visuel des 168 combinaisons et un export PNG réel restent à exécuter
dans un navigateur. Le harnais `tests/studio-manual-audit.html` permet ce contrôle ;
le même contrôle peut être lancé sur l’aperçu statique avec `?audit=1`.
L’accès au navigateur local est indisponible dans l’environnement de travail.
La publication sur la branche de production attend l’accord explicite du
propriétaire après le refus du contrôle automatique d’approbation.
