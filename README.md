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

- **Annuaire des Entreprises** : un appel borné à l'API publique recherche les entreprises actives ayant l'activité principale `85.59A` et reconnues comme organismes de formation. Le scan manuel ne télécharge plus le fichier national DGEFP, trop volumineux et généré dynamiquement.
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

### Qualification par signal récent

La vue `/admin` n'affiche plus par défaut l'ensemble des sociétés APE 85.59A. Elle affiche uniquement les prospects non archivés ayant un signal daté de moins de 90 jours. Le code APE est un indicateur secondaire (+10) et ne suffit jamais à rendre un prospect récent.

Les signaux reconnus sont notamment : création récente de l'entreprise ou de l'établissement, nouvel organisme de formation, Qualiopi récent, recrutement de formateur sécurité, nouvelle page de formation sécurité et ouverture de centre. Une société créée depuis plus de 12 mois sans signal récent est automatiquement archivée et reste consultable avec le filtre **Archives / anciens prospects**.

À chaque scan, le module déduplique par SIRET puis SIREN, actualise les données, conserve un signal récent encore valable et recalcule le score, la récence et l'archivage.

### Compteur des dossiers stagiaires

Le tableau de bord récupère le compteur depuis `STAGIAIRES_DOCS_TO_CONTROL_URL`. Si cette route est protégée, définir la même valeur secrète sur les deux services avec `STAGIAIRES_DOCS_TO_CONTROL_TOKEN`. La plateforme transmet ce secret dans les en-têtes `Authorization: Bearer ...` et `X-API-Key`. En cas d'indisponibilité temporaire du service stagiaires, la dernière réponse valide est conservée en mémoire et affichée comme donnée en cache.

## Intégration Yousign — signature électronique des contrats formateurs

L'application peut envoyer un contrat PDF rattaché à une fiche formateur ou à un contrat formateur APS vers Yousign, synchroniser le statut de signature et recevoir les webhooks sur `POST /webhooks/yousign`. Pour le site Render actuel, l'URL webhook à renseigner dans Yousign est `https://plateformegestion.onrender.com/webhooks/yousign` (méthode POST), pas une URL de page `/sessions/...`. La clé API reste exclusivement côté serveur.

Variables d'environnement :
- `YOUSIGN_API_KEY` : clé API Yousign v3, obligatoire pour activer l'intégration.
- `YOUSIGN_API_BASE_URL` (optionnel, alias accepté : `YOUSIGN_BASE_URL`) : URL de l'API, `https://api.yousign.app/v3` par défaut. Utiliser `https://api-sandbox.yousign.app/v3` pour les tests sandbox et vérifier que la clé API appartient au même environnement.
- `YOUSIGN_WEBHOOK_SECRET` (optionnel) : secret partagé utilisé pour vérifier une signature HMAC SHA-256 si Yousign transmet un en-tête compatible (`X-Yousign-Signature`, `Yousign-Signature` ou `X-Hub-Signature-256`).
- `YOUSIGN_CONTRACT_TEMPLATE_ID` (optionnel) : identifiant de template conservé en configuration pour une évolution template.
- `YOUSIGN_SIGNATURE_LEVEL` (optionnel) : niveau de signature envoyé à Yousign, `electronic_signature` par défaut.
- `YOUSIGN_AUTHENTICATION_MODE` (optionnel) : mode d'authentification, `no_otp` par défaut.
- `YOUSIGN_DELIVERY_MODE` (optionnel) : mode d'envoi de la demande, `email` par défaut.

Workflow : depuis une fiche formateur, déposer un PDF de contrat dans les documents du formateur, idéalement sur une ligne contenant “Contrat”, puis utiliser **Envoyer pour signature Yousign**. Les contrats formateurs APS peuvent aussi être envoyés depuis la page session. L'application stocke les identifiants Yousign, le statut, les dates d'envoi/synchronisation/webhook, le lien de signature éventuel et la dernière erreur. Une demande active (`draft`, `approval` ou `ongoing`) n'est pas recréée automatiquement afin d'éviter les doublons.

Événements webhook Yousign minimum à activer : `signature_request.done`, `signature_request.declined`, `signature_request.expired`, `signature_request.canceled`, `signer.done`, `signer.declined`, `signer.notification_delivery_failed`, `signer.error`. La route `/webhooks/yousign` est publique via la liste blanche serveur, accepte uniquement POST, n'est pas protégée par l'authentification utilisateur, ne dépend pas de CSRF Flask-WTF, vérifie la signature HMAC SHA-256 lorsque `YOUSIGN_WEBHOOK_SECRET` est configuré, journalise les événements reçus, puis met à jour le statut Yousign du formateur ou du contrat formateur APS correspondant.

En cas de `403` lors de `POST /signature_requests`, le webhook n'est généralement pas en cause. Vérifier sur Render : `YOUSIGN_API_KEY`, `YOUSIGN_API_BASE_URL`/`YOUSIGN_BASE_URL`, la cohérence sandbox/production, le workspace éventuel associé à la clé, les scopes/droits de la clé API et le plan/add-on Yousign autorisant la création de demandes de signature en production.
