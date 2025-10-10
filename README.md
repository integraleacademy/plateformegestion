
# Plateforme de gestion Intégrale Academy

Application Flask prête à déployer sur Render (avec disque persistant). Le disque est accessible via `/mnt/data`.

## Déploiement (Render)
1. Créez un nouveau **Web Service** depuis ce repo/zip.
2. Choisissez **Python**. Commande de build par défaut (Render détecte `requirements.txt`).
3. **Start command** : `gunicorn app:app -b 0.0.0.0:$PORT --timeout 120 --workers 2` (déjà présent dans `Procfile`).
4. Activez un **Disque persistant** si besoin (chemin conseillé : `/mnt/data`, taille selon l'usage).

## Routes
- `/` : Accueil avec les boutons et l'horloge en haut (Europe/Paris).
- `/sessions` : Page interne pour "Gestion des sessions" (à compléter ensemble).
- `/healthz` : Santé.

## Personnalisation
- Logo : `static/img/logo-integrale.png`
- Styles : `static/css/styles.css`
- JS (horloge) : `static/js/clock.js`
