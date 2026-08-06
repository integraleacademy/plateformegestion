# Audit du Studio visuel (avant V2)

## Surface existante

- Route Jinja : `GET /admin/studio-visuels` dans `app.py`, rendue par
  `templates/admin/studio_visuals/editor.html`.
- Anciennes API : `GET/POST /api/admin/social-visuals`,
  `POST /api/admin/social-visuals/generate`, `POST /api/admin/studio/media` et
  `GET /media/studio/<filename>`.
- Composition : `static/studio_visuals/js/studio-renderer.js` produisait un DOM
  HTML/SVG à partir des recettes, puis `studio-exporter.js` le capturait avec
  `html-to-image@1.11.11`.
- Données : projets dans `DATA_DIR/social_visuals.json` via `social_visuals.py` ;
  médias dans `DATA_DIR/studio_media`; catalogue versionné dans
  `static/studio_visuals/data/templates.json`; thèmes, icônes et recettes dans
  le même dossier.
- IA : `social_visuals.generate_content_from_topic`, exposée par
  `services/studio_ai_service.py`, renvoie déjà des champs de contenu et non du
  code de rendu.

## Diagnostic du catalogue historique

Le catalogue déclarait plus de 60 entrées, mais seulement 24 miniatures et
structures initiales réellement différenciées. Les familles allant de l'affiche
typographique au CTA de fin sont les compositions distinctes conservables comme
références. La longue série suivante réutilisait systématiquement
`stats_big_number.svg` : ce sont des variantes de contenu/couleur, avec une
miniature trompeuse, et non des compositions distinctes. Les recettes DOM/SVG
qui dépendaient des dimensions calculées par CSS sont obsolètes pour V2. Les
cas produisant des débordements étaient corrigés tardivement par
`clampElementsToCanvas` à l'export : ils sont classés cassés plutôt que migrés
silencieusement.

## Architecture V2 retenue

- Fabric.js 6.7.1, état d'objets JSON par page et coordonnées aux dimensions du
  document ; le zoom n'agit que sur la présentation du conteneur.
- Modules dédiés sous `static/studio/` (API, canvas, historique, calques, export,
  orchestration et styles).
- Stockage isolé sous `STUDIO_STORAGE_DIR` (ou
  `DATA_DIR/studio_visuels`) avec projets, assets, miniatures, templates,
  métadonnées et sauvegardes.
- API V2 sous `/api/admin/studio-visuels`, authentification admin, CSRF pour les
  mutations, identifiants UUID, validation de schéma et écritures atomiques.

## Migration restante explicite

La V2 ne prétend pas que les anciennes variantes sont devenues 60 documents
Fabric distincts. Le catalogue complet doit encore être redessiné et ses
miniatures régénérées depuis Fabric avant de considérer les blocs 6 et 7 comme
terminés. Le moteur, les projets, les médias et l'export V2 constituent la base
de migration ; l'ancien renderer reste présent uniquement pour compatibilité
des données existantes et pourra être supprimé après migration vérifiée.
