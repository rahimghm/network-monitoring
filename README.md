# Monitoring Réseau — Vue.js + FastAPI + PostgreSQL

Application web permettant d'ajouter un équipement réseau via son **hostname**,
puis de lancer un diagnostic SNMP complet (statut, CPU, RAM, température,
interfaces, trafic, vitesse) en un clic, avec stockage en base.

## Architecture

```
frontend/  (Vue.js 3 + Vite + vue-router)
    ↓ HTTP (axios, JWT en header) + WebSocket (session de diagnostic live)
backend/   (FastAPI)
    ↓ auth JWT (python-jose) + RBAC (Admin / Technician / Supervisor)
    ↓ résolution hostname → IP (socket.gethostbyname)
    ↓ requêtes SNMP (pysnmp, verrouillées via threading.Lock)
switches simulés (VM OVS + snmpd) ou vrais équipements
    ↓
PostgreSQL (users / equipments / diagnostics / interface_metrics /
            alert_thresholds / alert_events / snapshots / snapshot_items)
    ↑
Grafana (lecture directe, dashboards de comparaison/tendances)
```

## 1. Base de données

```bash
sudo -u postgres psql
```
```sql
CREATE DATABASE monitoring;
CREATE USER monitor_user WITH PASSWORD 'changeme';
GRANT ALL PRIVILEGES ON DATABASE monitoring TO monitor_user;
\c monitoring
GRANT ALL ON SCHEMA public TO monitor_user;
\q
```

Charger le schéma (inclut désormais `users`, `alert_thresholds`,
`alert_events`, `snapshots`, `snapshot_items` en plus des tables existantes) :
```bash
psql -U rahim -d monitoring -h localhost -f "C:\Users\User\Desktop\monitoring-appA\database\schema.sql"

## 2. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # adapte les identifiants DB si besoin
```

Charge les variables d'environnement puis lance le serveur :
```bash
# Linux/macOS
export $(cat .env | xargs)
uvicorn app.main:app --reload --port 8000

# Windows (PowerShell) — ou utilise python-dotenv si tu préfères
$env:DB_PASSWORD="changeme"; uvicorn app.main:app --reload --port 8000
```

L'API est alors disponible sur `http://localhost:8000` (doc interactive sur `/docs`).

## 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Ouvre `http://localhost:5173`.

## 4. Premier lancement — créer le compte Admin

1. Ouvre `http://localhost:5173` → redirigé vers `/login`
2. Clique **"Premier lancement ? Créer le compte admin"**
3. Choisis un nom d'utilisateur + mot de passe → ce premier compte devient
   automatiquement **Admin**
4. Une fois connecté, l'Admin peut créer les comptes Technician/Supervisor
   via `POST /users` (pas encore d'écran dédié — utilise `/docs` en attendant,
   ou ajoute une page si besoin)

**Rôles :**
- **Admin** : tout, y compris gérer les utilisateurs et les seuils d'alerte
- **Technician** : ajouter/supprimer des équipements, lancer des diagnostics,
  prendre des snapshots, consulter l'historique
- **Supervisor** : lecture seule (dashboard, historique, Grafana) + export

## 5. Utilisation — diagnostic multi-équipements en temps réel

1. Dans le formulaire à gauche, entre un **nom** et le **hostname** de
   l'équipement — par exemple `switch1.local` (résolu via mDNS/Avahi) ou
   directement une IP fixe (`192.168.2.132`)
2. Clique **Ajouter**
3. **Coche** un ou plusieurs équipements dans la liste (ou "Tout sélectionner")
4. Clique **Démarrer** — une connexion WebSocket (`/ws/diagnose`) s'ouvre,
   et chaque équipement coché est diagnostiqué **en continu, toutes les 5s,
   en parallèle** — un panneau s'affiche par équipement, avec ses métriques
   qui se mettent à jour en direct
5. **Pause** suspend l'envoi de mises à jour sans fermer la session ;
   **Reprendre** relance ; **Stop** termine tout
6. **Snapshot** fige les dernières valeurs connues de tous les équipements
   de la session dans un enregistrement consultable ensuite dans **Historique**

Chaque panneau garde aussi son bouton **"Re-diagnostiquer"** pour un diagnostic
ponctuel immédiat (hors du rythme 5s de la session), et son propre graphique
CPU/RAM (alimenté par le polling automatique backend, voir section 6).

## 6. Polling automatique global (toutes les 20s) + graphique CPU/RAM

Indépendamment des sessions WebSocket manuelles, le backend lance dès son
démarrage un job en arrière-plan (APScheduler) qui diagnostique **tous les
équipements enregistrés toutes les `POLL_INTERVAL_SECONDS`** (20s par défaut,
réglable dans `.env`) — ça alimente en continu l'historique et les graphiques,
même sans session WebSocket active.

Concurrence : le module SNMP (`snmp_poller.py`) utilise un seul moteur
`pysnmp` protégé par un verrou (`threading.Lock`) — plusieurs diagnostics en
parallèle (session WS + job automatique + bouton manuel en même temps)
restent sûrs : les requêtes sont traitées l'une après l'autre au niveau
réseau, sans corruption de réponse.

## 7. Alertes (seuils configurables)

Va dans **Alertes** (Admin uniquement) pour définir des seuils — globaux
(tous équipements) ou spécifiques à un équipement — sur CPU (%), RAM (%) ou
température (°C), avec condition "supérieur à" / "inférieur à".

Pendant une session de diagnostic en direct, tout dépassement :
- surligne en **rouge** la carte métrique concernée, en temps réel
- déclenche un **toast** dans l'app (coin supérieur droit)
- est enregistré dans `alert_events` (table historique des alertes)

Le polling automatique (section 6) évalue aussi les seuils à chaque cycle,
même sans session WebSocket ouverte — seul l'affichage temps réel (rouge +
toast) nécessite une session active ou la page dashboard ouverte.

## 8. Historique (snapshots)

La page **Historique** liste tous les snapshots pris via le bouton
**Snapshot** (section 5), avec filtres par équipement et par plage de dates.
Cliquer sur un snapshot affiche le détail (mêmes panneaux qu'en direct, en
lecture seule), avec export **PDF** et **XLSX** du contenu.

## 9. Intégration Grafana

Grafana tourne **en dehors** de cette app, connecté directement à la même
base PostgreSQL (lecture seule recommandée) :

```bash
# Exemple rapide avec Docker
docker run -d -p 3000:3000 --name grafana grafana/grafana-oss
```

1. Ouvre `http://localhost:3000` (admin/admin par défaut)
2. **Connections → Data sources → PostgreSQL** :
   - Host : `host.docker.internal:5432` (ou l'IP de ta machine si Grafana
     est dans un conteneur séparé de PostgreSQL)
   - Database : `monitoring`, User/password : tes identifiants
   - **Recommandé** : crée un utilisateur PostgreSQL en lecture seule dédié
     à Grafana plutôt que d'utiliser le compte applicatif :
     ```sql
     CREATE USER grafana_reader WITH PASSWORD '...';
     GRANT CONNECT ON DATABASE monitoring TO grafana_reader;
     GRANT USAGE ON SCHEMA public TO grafana_reader;
     GRANT SELECT ON ALL TABLES IN SCHEMA public TO grafana_reader;
     ```
3. Crée un dashboard avec un panel "Comparaison CPU entre équipements",
   requête SQL type :
   ```sql
   SELECT d.collected_at AS "time", e.name AS metric, d.cpu_usage AS value
   FROM diagnostics d JOIN equipments e ON e.id = d.equipment_id
   WHERE $__timeFilter(d.collected_at)
   ORDER BY d.collected_at
   ```
4. Pour l'embed dans l'app : active `allow_embedding = true` dans
   `grafana.ini` (section `[security]`), puis colle l'URL du panel (mode
   partage → "Embed") dans la page **Grafana** de l'app

## 10. Prérequis côté équipement (switch simulé OVS + snmpd)

Le backend s'appuie sur :
- **IF-MIB** (standard) pour les interfaces, statut, vitesse, trafic —
  actif par défaut avec `snmpd`.
- **UCD-SNMP-MIB** pour le CPU (`ssCpuIdle`) et la RAM (`memTotalReal`,
  `memAvailReal`) — disponible par défaut sur net-snmp/Linux, aucune
  config supplémentaire nécessaire.
- **NET-SNMP-EXTEND-MIB** pour la température — **optionnel**. Si aucune
  extend n'est configurée sur le switch, `temperature_c` reste `null`
  (affiché "N/A" côté frontend) sans faire échouer le diagnostic.

  Pour simuler une température, ajoute dans `/etc/snmp/snmpd.conf` :
  ```
  extend temperature /bin/sh -c "echo 42.5"
  ```
  puis `sudo systemctl restart snmpd`.

## 11. Notes de robustesse et limites connues

- Si le hostname ne se résout pas ou si le switch ne répond pas en SNMP,
  le diagnostic est quand même enregistré en base avec `is_up=false` et
  un `error_message` explicite — rien ne plante côté API/frontend.
- Le backend est agnostique de ce qui répond derrière l'IP : que ce soit
  une VM Open vSwitch + snmpd, un nœud GNS3, ou un vrai switch Huawei
  (une fois les OIDs propriétaires ajoutés dans `snmp_poller.py`), le
  frontend et la base de données n'ont besoin d'aucune modification.
- **Fermer un panneau** (✕) dans une session en direct l'enlève juste de
  l'affichage — le backend continue de sonder cet équipement jusqu'au
  clic sur **Stop** (qui arrête toute la session, pas équipement par
  équipement). Limite connue, acceptable pour ce cas d'usage.
- **`pysnmp==4.4.12` est incompatible avec Python 3.12** (le module
  `asyncore` a été supprimé) — utilise **Python 3.11** pour le backend.
- Pas encore d'écran dédié pour créer des utilisateurs (Technician/
  Supervisor) — l'Admin utilise `POST /users` via `/docs` en attendant.
- `JWT_SECRET` dans `.env.example` est une valeur de développement —
  génère une vraie valeur aléatoire longue avant tout déploiement réel.
