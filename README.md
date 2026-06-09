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

## Nouvelles options avancées planning
- Exports: CSV (`/planning/export.csv`), Excel (`/planning/export.xlsx`), impression (`/planning/impression`).
- Filtres planning: recherche globale, salle, type, statut.
- Nouvelles pages:
  - `/salles` : gestion des salles (capacité, équipements, indisponibilités, statut).
  - `/formateurs-planning` : gestion des formateurs planning.
  - `/planning/historique` : historique des actions (création, modification, suppression).
- Calendrier FullCalendar conservé avec vues jour/semaine/mois/liste.

## Important : persistance des formations
Si les formations “disparaissent”, c'est généralement que la base SQLite était stockée sur un disque non persistant.

- Chemin utilisé maintenant :
  1. `PERSIST_DIR/formations.db` si `PERSIST_DIR` est défini
  2. sinon `DATA_DIR/formations.db`
- Une migration automatique est prévue depuis l'ancien emplacement local `./formations.db` vers le nouveau chemin persistant si besoin.

## Module de prospection des centres de formation sécurité

L'interface protégée est accessible depuis la tuile **Prospection sécurité** du tableau de bord, ou directement sur **`/admin`** (l'alias **`/prospection`** redirige également vers cette page). Elle permet de scanner les sources publiques, scorer les organismes, suivre leur statut commercial, préparer un email personnalisé et exporter le pipeline au format Excel.

### Sources et fonctionnement

- **Liste publique des organismes de formation (DGEFP / data.gouv.fr)** : la ressource CSV ou Excel est découverte automatiquement depuis l'API du catalogue data.gouv.fr.
- **RNE / Annuaire des Entreprises** : recherche des entreprises dont l'activité principale est `85.59A` via l'API publique de recherche d'entreprises, alimentée notamment par les données du RNE/Sirene.
- **Recherche web optionnelle** : activée si `SERPER_API_KEY` est définie.
- Les doublons sont fusionnés à partir du SIRET, du SIREN ou, à défaut, du nom et de la ville.
- Le score sur 100 tient compte du code APE, des mots-clés sécurité, de la récence de création, de Qualiopi et des coordonnées disponibles.

### Variables d'environnement supplémentaires

- `OPENAI_API_KEY` : active la génération de mails personnalisés via l'API Responses OpenAI. Sans clé, un modèle de mail local reste disponible.
- `OPENAI_MODEL` (optionnel) : modèle OpenAI utilisé, `gpt-5-mini` par défaut.
- `SERPER_API_KEY` (optionnel) : active les résultats de recherche web.
- `PROSPECT_SCAN_LIMIT` (optionnel) : nombre maximal de lignes traitées par source et par scan, `250` par défaut.
- `CRON_SECRET` : secret requis par la route de scan planifié.
- `PERSIST_DIR=/mnt/data` : stocke `prospects.db` et `formations.db` sur le disque persistant Render.

### Configuration Render recommandée

1. Créer un disque persistant monté sur `/mnt/data`.
2. Utiliser `pip install -r requirements.txt` comme commande de build.
3. Le `Procfile` fournit la commande Gunicorn de démarrage.
4. Définir `SECRET_KEY`, `ADMIN_USER`, `ADMIN_PASSWORD`, `PERSIST_DIR` et, si souhaité, `OPENAI_API_KEY` / `SERPER_API_KEY`.
5. Déployer puis ouvrir `/admin` après authentification.

Le scan est déclenché manuellement depuis l'interface. Pour une veille planifiée, configurer un Render Cron Job qui appelle `GET /cron-prospects-scan?key=<CRON_SECRET>` ou transmet `Authorization: Bearer <CRON_SECRET>`.
