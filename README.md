# Plateforme de gestion Intégrale Academy

Application Flask déployable sur Render.

## Lancer en local
1. Installer les dépendances :
   ```bash
   pip install -r requirements.txt
   ```
2. Définir les variables d'environnement minimales :
   ```bash
   export SECRET_KEY="change-me"
   export ADMIN_USER="admin@example.com"
   export ADMIN_PASSWORD="motdepassefort"
   ```
3. Lancer l'application :
   ```bash
   flask --app app.py run --debug
   ```

## Variables Render à créer
- `SECRET_KEY` : clé de session Flask.
- `ADMIN_USER` : identifiant admin.
- `ADMIN_PASSWORD` : mot de passe admin (protège `/planning`, `/calendrier`, etc.).
- `PERSIST_DIR` (recommandé) : dossier persistant pour SQLite (ex: `/mnt/data`).
- `DATA_DIR` (optionnel) : dossier de persistance des autres JSON de l'application.

## Déploiement Render
1. Créer un **Web Service** Python.
2. Build command: `pip install -r requirements.txt`.
3. Start command: `gunicorn app:app -b 0.0.0.0:$PORT --timeout 120 --workers 2`.
4. Attacher un disque persistant Render.
5. Définir `PERSIST_DIR=/mnt/data` pour conserver `formations.db`.

## Module planning formations / salles
- Route principale : `/planning`.
- Ajout : `/formation/ajouter`.
- Modification : `/formation/<id>/modifier`.
- Suppression : `/formation/<id>/supprimer`.
- Calendrier : `/calendrier`.
- Vérification dispo (AJAX) : `POST /planning/disponibilites`.

### Fonctionnement de l’affectation automatique des salles
Salles gérées : `Salle 1`, `Salle 2`, `Salle 1B`, `Salle 2B`, `Salle 3B`.

- Si une salle est demandée dans le formulaire :
  - l'application vérifie qu'aucune autre formation de cette salle ne chevauche la période,
  - si disponible, la salle est attribuée,
  - sinon message clair: la salle demandée n'est pas disponible.
- Si aucune salle n'est demandée :
  - l'application cherche automatiquement la première salle libre parmi les 5,
  - si aucune salle n'est libre, l'ajout est refusé avec :
    `Aucune salle disponible sur cette période`.

### Règle de conflit
Deux formations sont en conflit si :
1. elles sont dans la même salle,
2. et leurs dates se chevauchent (`date_debut_A <= date_fin_B` et `date_debut_B <= date_fin_A`).

## Stockage SQLite
Table `formations` :
- `id`
- `nom`
- `type`
- `date_debut`
- `date_fin`
- `salle`
- `nombre_stagiaires`
- `commentaire`
- `created_at`

Chemin DB:
- si `PERSIST_DIR` existe: `PERSIST_DIR/formations.db`
- sinon: `./formations.db`
