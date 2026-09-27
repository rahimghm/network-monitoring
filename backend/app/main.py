import io
import re
from datetime import date, datetime, timedelta
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from apscheduler.schedulers.background import BackgroundScheduler

from .config import POLL_INTERVAL_SECONDS
from .database import get_cursor, get_db
from .schemas import (
    EquipmentCreate, EquipmentUpdate, EquipmentOut, DiagnosticOut, MetricPointOut,
    UserCreate, UserUpdate, PasswordChange, UserOut, TokenOut,
    ThresholdCreate, ThresholdOut,
    SnapshotOut, SnapshotUpdate, SnapshotDetailOut, AuditLogOut,
)
from .snmp_poller import collect_diagnostics
from .alerts import evaluate_thresholds
from .ws_manager import monitoring_hub
from .audit import record_audit
from .polling_control import is_automatic_polling_paused
from . import auth as authmod


# ============ Logique de diagnostic partagée ============

def run_diagnostic(equipment_id: int, hostname: str, community: str) -> dict:
    data = collect_diagnostics(hostname, community)

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE equipments SET is_up = %s, last_ip = %s WHERE id = %s",
            (data["is_up"], data["resolved_ip"], equipment_id)
        )
        cur.execute(
            """INSERT INTO diagnostics
               (equipment_id, resolved_ip, is_up, sys_descr, sys_uptime,
                cpu_usage, ram_total_kb, ram_used_kb, temperature_c, error_message)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id, collected_at""",
            (equipment_id, data["resolved_ip"], data["is_up"], data["sys_descr"],
             data["sys_uptime"], data["cpu_usage"], data["ram_total_kb"],
             data["ram_used_kb"], data["temperature_c"], data["error_message"])
        )
        diagnostic_id, collected_at = cur.fetchone()

        for iface in data["interfaces"]:
            cur.execute(
                """INSERT INTO interface_metrics
                   (diagnostic_id, if_index, if_descr, oper_status, admin_status,
                    speed_bps, in_octets, out_octets, in_packets, out_packets,
                    in_errors, out_errors, in_discards, out_discards, stp_state)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (diagnostic_id, iface["if_index"], iface["if_descr"],
                 iface["oper_status"], iface["admin_status"], iface["speed_bps"],
                 iface["in_octets"], iface["out_octets"], iface["in_packets"],
                 iface["out_packets"], iface["in_errors"], iface["out_errors"],
                 iface["in_discards"], iface["out_discards"], iface["stp_state"])
            )
        conn.commit()

    evaluate_thresholds(equipment_id, diagnostic_id, data)

    return {
        "id": diagnostic_id,
        "equipment_id": equipment_id,
        "collected_at": collected_at,
        **data,
    }


def poll_all_equipments():
    if is_automatic_polling_paused():
        return
    with get_cursor() as cur:
        cur.execute("SELECT id, hostname, community FROM equipments")
        equipments = cur.fetchall()
    for eq in equipments:
        try:
            run_diagnostic(eq["id"], eq["hostname"], eq["community"])
        except Exception as e:
            print(f"[poll] échec pour l'équipement {eq['id']} ({eq['hostname']}): {e}")


scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(poll_all_equipments, "interval", seconds=POLL_INTERVAL_SECONDS,
                       id="poll_all_equipments", replace_existing=True)
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Network Monitoring API",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


def snapshot_filename(label: str, extension: str) -> str:
    safe_label = re.sub(r'[<>:"/\\|?*]+', '-', label).strip() or "snapshot"
    return f"snapshot {safe_label}.{extension}"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health(user: dict = Depends(authmod.require_action("health.read"))):
    return {"status": "ok"}


@app.get("/config")
def get_config(user: dict = Depends(authmod.require_action("config.read"))):
    return {"poll_interval_seconds": POLL_INTERVAL_SECONDS}


# ============ Auth & RBAC (Feature 5) ============

@app.post("/auth/register", response_model=UserOut, status_code=201)
def register(payload: UserCreate):
    """
    Ouvert uniquement pour créer le tout premier compte (devient Admin).
    Ensuite, protégé — voir POST /users (Admin uniquement) pour créer d'autres comptes.
    """
    if authmod.users_exist():
        raise HTTPException(
            status_code=403,
            detail="Inscription libre fermée : utilisez POST /users (Admin) pour créer un compte."
        )
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (%s,%s,%s) RETURNING *",
            (payload.username, authmod.hash_password(payload.password), "admin")  # 1er compte = admin
        )
        created = cur.fetchone()
    record_audit(created, "auth.register", "user", created["id"])
    return created


@app.post("/auth/login", response_model=TokenOut)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM users WHERE username = %s", (form_data.username,))
        user = cur.fetchone()
    if user is None or not authmod.verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Identifiants invalides")

    token = authmod.create_access_token({"sub": user["username"], "role": user["role"]})
    record_audit(user, "auth.login", "user", user["id"])
    return {"access_token": token, "role": user["role"], "username": user["username"]}


@app.get("/auth/me", response_model=UserOut)
def me(user: dict = Depends(authmod.require_action("auth.me"))):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM users WHERE id = %s", (user["id"],))
        return cur.fetchone()


@app.patch("/auth/password", status_code=204)
def change_password(payload: PasswordChange,
                    user: dict = Depends(authmod.require_action("auth.change_password"))):
    with get_cursor() as cur:
        cur.execute("SELECT password_hash FROM users WHERE id = %s", (user["id"],))
        account = cur.fetchone()
        if account is None or not authmod.verify_password(payload.current_password, account["password_hash"]):
            raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")
        cur.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (authmod.hash_password(payload.new_password), user["id"]),
        )
    record_audit(user, "auth.change_password", "user", user["id"])
    return None


@app.post("/auth/logout", status_code=204)
def logout(user: dict = Depends(authmod.require_action("auth.logout"))):
    record_audit(user, "auth.logout", "user", user["id"])
    return None


@app.get("/users", response_model=List[UserOut])
def list_users(user: dict = Depends(authmod.require_action("users.manage"))):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM users ORDER BY created_at")
        return cur.fetchall()


@app.post("/users", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate, user: dict = Depends(authmod.require_action("users.manage"))):
    if payload.role not in authmod.ROLES:
        raise HTTPException(status_code=400, detail=f"Rôle invalide : {payload.role}")
    with get_cursor() as cur:
        try:
            cur.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (%s,%s,%s) RETURNING *",
                (payload.username, authmod.hash_password(payload.password), payload.role)
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Erreur création utilisateur: {e}")
        created = cur.fetchone()
    record_audit(user, "users.create", "user", created["id"], {"role": created["role"]})
    return created


@app.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdate,
                user: dict = Depends(authmod.require_action("users.manage"))):
    if payload.role is None and payload.password is None:
        raise HTTPException(status_code=400, detail="Aucune modification fournie")
    if payload.role is not None and payload.role not in authmod.ROLES:
        raise HTTPException(status_code=400, detail=f"Rôle invalide : {payload.role}")

    updates = []
    values = []
    if payload.role is not None:
        updates.append("role = %s")
        values.append(payload.role)
    if payload.password is not None:
        updates.append("password_hash = %s")
        values.append(authmod.hash_password(payload.password))
    values.append(user_id)

    with get_cursor() as cur:
        cur.execute("SELECT id, role FROM users WHERE id = %s", (user_id,))
        target = cur.fetchone()
        if target is None:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable")
        if (target["role"] == "admin" and payload.role == "technician") or (target["role"] == "admin" and payload.role == "supervisor"):
            cur.execute("SELECT COUNT(*) AS count FROM users WHERE role = 'admin'")
            if cur.fetchone()["count"] <= 1:
                raise HTTPException(status_code=400, detail="Impossible de retirer le rôle du dernier administrateur")
        cur.execute(
            f"UPDATE users SET {', '.join(updates)} WHERE id = %s RETURNING *",
            values,
        )
        updated = cur.fetchone()
    record_audit(user, "users.update", "user", user_id,
                 {"role": payload.role, "password_changed": payload.password is not None})
    return updated


@app.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, user: dict = Depends(authmod.require_action("users.manage"))):
    if user_id == user["id"]:
        raise HTTPException(status_code=400, detail="Impossible de supprimer son propre compte")
    with get_cursor() as cur:
        cur.execute("SELECT id, role FROM users WHERE id = %s", (user_id,))
        target = cur.fetchone()
        if target is None:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable")
        if target["role"] == "admin":
            cur.execute("SELECT COUNT(*) AS count FROM users WHERE role = 'admin'")
            if cur.fetchone()["count"] <= 1:
                raise HTTPException(status_code=400, detail="Impossible de supprimer le dernier administrateur")
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
    record_audit(user, "users.delete", "user", user_id)
    return None


@app.get("/audit-logs", response_model=List[AuditLogOut])
def list_audit_logs(limit: int = 200,
                    username: Optional[str] = None,
                    role: Optional[str] = None,
                    action: Optional[str] = None,
                    date_from: Optional[date] = None,
                    date_to: Optional[date] = None,
                    user: dict = Depends(authmod.require_action("audit.read"))):
    limit = max(1, min(limit, 1000))
    conditions = ["action <> 'monitoring.poll'"]
    params = []
    if username:
        conditions.append("username ILIKE %s")
        params.append(f"%{username.strip()}%")
    if role:
        conditions.append("role = %s")
        params.append(role)
    if action:
        conditions.append("action = %s")
        params.append(action)
    if date_from:
        conditions.append("created_at >= %s")
        params.append(date_from)
    if date_to:
        conditions.append("created_at < %s")
        params.append(date_to + timedelta(days=1))
    params.append(limit)
    with get_cursor() as cur:
        query = """SELECT id, user_id, username, role, action, resource, resource_id,
                          details, created_at
                   FROM audit_logs
                   WHERE """ + " AND ".join(conditions) + """
                   ORDER BY created_at DESC LIMIT %s"""
        cur.execute(
            query,
            params,
        )
        return cur.fetchall()


# ============ Équipements ============
# Admin + Technician gèrent (create/delete) ; Supervisor a un accès en lecture
# seule appliqué côté routeur Vue (les GET restent ouverts à tout utilisateur connecté).

@app.get("/equipments", response_model=List[EquipmentOut])
def list_equipments(user: dict = Depends(authmod.require_action("equipment.read"))):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM equipments ORDER BY created_at DESC")
        return cur.fetchall()


@app.post("/equipments", response_model=EquipmentOut, status_code=201)
def create_equipment(eq: EquipmentCreate,
                      user: dict = Depends(authmod.require_action("equipment.manage"))):
    with get_cursor() as cur:
        try:
            cur.execute(
                """INSERT INTO equipments (name, hostname, community)
                   VALUES (%s, %s, %s) RETURNING *""",
                (eq.name, eq.hostname, eq.community)
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Erreur création: {e}")
        equipment = cur.fetchone()
    record_audit(user, "equipment.create", "equipment", equipment["id"])
    return equipment


@app.patch("/equipments/{equipment_id}", response_model=EquipmentOut)
def update_equipment(equipment_id: int, payload: EquipmentUpdate,
                     user: dict = Depends(authmod.require_action("equipment.manage"))):
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="Aucune modification fournie")
    values = list(changes.values()) + [equipment_id]
    assignments = ", ".join(f"{field} = %s" for field in changes)
    with get_cursor() as cur:
        try:
            cur.execute(
                f"UPDATE equipments SET {assignments} WHERE id = %s RETURNING *",
                values,
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Erreur modification: {e}")
        equipment = cur.fetchone()
        if equipment is None:
            raise HTTPException(status_code=404, detail="Équipement introuvable")
    record_audit(user, "equipment.update", "equipment", equipment_id,
                 {"fields": list(changes)})
    return equipment


@app.delete("/equipments/{equipment_id}", status_code=204)
def delete_equipment(equipment_id: int,
                      user: dict = Depends(authmod.require_action("equipment.manage"))):
    with get_cursor() as cur:
        cur.execute("DELETE FROM equipments WHERE id = %s", (equipment_id,))
    record_audit(user, "equipment.delete", "equipment", equipment_id)
    return None


# ============ Diagnostic ponctuel + historique ============

@app.post("/equipments/{equipment_id}/diagnose", response_model=DiagnosticOut)
def diagnose_equipment(equipment_id: int,
                        user: dict = Depends(authmod.require_action("diagnostic.run"))):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM equipments WHERE id = %s", (equipment_id,))
        equipment = cur.fetchone()
    if equipment is None:
        raise HTTPException(status_code=404, detail="Équipement introuvable")
    result = run_diagnostic(equipment_id, equipment["hostname"], equipment["community"])
    record_audit(user, "diagnostic.run", "equipment", equipment_id)
    return result


@app.get("/equipments/{equipment_id}/diagnostics", response_model=List[DiagnosticOut])
def get_equipment_history(equipment_id: int, limit: int = 20,
                          user: dict = Depends(authmod.require_action("history.read"))):
    with get_cursor() as cur:
        cur.execute(
            """SELECT * FROM diagnostics WHERE equipment_id = %s
               ORDER BY collected_at DESC LIMIT %s""",
            (equipment_id, limit)
        )
        diagnostics = cur.fetchall()
        out = []
        for d in diagnostics:
            cur.execute("SELECT * FROM interface_metrics WHERE diagnostic_id = %s", (d["id"],))
            d["interfaces"] = cur.fetchall()
            out.append(d)
        return out


@app.get("/equipments/{equipment_id}/metrics/timeseries", response_model=List[MetricPointOut])
def get_metrics_timeseries(equipment_id: int, limit: int = 50,
                           user: dict = Depends(authmod.require_action("equipment.read"))):
    with get_cursor() as cur:
        cur.execute(
            """SELECT collected_at, cpu_usage, ram_total_kb, ram_used_kb, is_up
               FROM diagnostics WHERE equipment_id = %s
               ORDER BY collected_at DESC LIMIT %s""",
            (equipment_id, limit)
        )
        rows = cur.fetchall()
    return list(reversed(rows))


# ============ Feature 1 — WebSocket : diagnostic multi-équipements temps réel ============
# Auth via token en query param (un navigateur ne permet pas de header
# Authorization personnalisé sur une connexion WebSocket native).

@app.websocket("/ws/diagnose")
async def ws_diagnose(websocket: WebSocket, token: str = Query(...)):
    try:
        user = authmod.get_user_from_token(token)
    except HTTPException as error:
        await websocket.close(code=4401 if error.status_code == 401 else 4403)
        return

    await websocket.accept()
    await monitoring_hub.subscribe(websocket)
    try:
        while True:
            msg = await websocket.receive_json()
            action = msg.get("action")
            action_permission = {
                "start": "monitoring.control",
                "pause": "monitoring.control",
                "resume": "monitoring.control",
                "stop": "monitoring.control",
                "snapshot": "monitoring.snapshot.create",
            }.get(action)
            permissions = authmod.ROLE_ACTIONS.get(user["role"], set())
            if action_permission is None or ("*" not in permissions and action_permission not in permissions):
                await websocket.send_json({
                    "type": "error",
                    "status_code": 403,
                    "detail": f"Role '{user['role']}' is not permitted to perform '{action or 'unknown'}'",
                })
                continue

            if action == "start":
                await monitoring_hub.start(
                    msg.get("equipment_ids", []),
                    msg.get("interval_seconds", 5)
                )
                record_audit(user, "monitoring.start", "monitoring")
                await websocket.send_json({"type": "status", "status": "started"})

            elif action == "pause":
                monitoring_hub.pause()
                record_audit(user, "monitoring.pause", "monitoring")
                await websocket.send_json({"type": "status", "status": "paused"})

            elif action == "resume":
                monitoring_hub.resume()
                record_audit(user, "monitoring.resume", "monitoring")
                await websocket.send_json({"type": "status", "status": "resumed"})

            elif action == "stop":
                await monitoring_hub.stop()
                record_audit(user, "monitoring.stop", "monitoring")
                await websocket.send_json({"type": "status", "status": "stopped"})

            elif action == "snapshot":
                snapshot_id = monitoring_hub.snapshot(
                    msg.get("label", f"Snapshot {datetime.utcnow().isoformat()}"),
                    created_by=user["id"]
                )
                record_audit(user, "monitoring.snapshot", "snapshot", snapshot_id)
                await websocket.send_json({"type": "snapshot_saved", "snapshot_id": snapshot_id})

    except WebSocketDisconnect:
        monitoring_hub.unsubscribe(websocket)
    return


# ============ Feature 4 — Alertes / seuils ============

@app.get("/thresholds", response_model=List[ThresholdOut])
def list_thresholds(user: dict = Depends(authmod.require_action("threshold.read"))):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM alert_thresholds ORDER BY equipment_id NULLS FIRST, metric")
        return cur.fetchall()


@app.post("/thresholds", response_model=ThresholdOut, status_code=201)
def create_threshold(payload: ThresholdCreate,
                      user: dict = Depends(authmod.require_action("threshold.manage"))):
    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO alert_thresholds (equipment_id, metric, operator, threshold_value, enabled)
               VALUES (%s,%s,%s,%s,%s) RETURNING *""",
            (payload.equipment_id, payload.metric, payload.operator,
             payload.threshold_value, payload.enabled)
        )
        threshold = cur.fetchone()
    record_audit(user, "threshold.create", "threshold", threshold["id"])
    return threshold


@app.delete("/thresholds/{threshold_id}", status_code=204)
def delete_threshold(threshold_id: int, user: dict = Depends(authmod.require_action("threshold.manage"))):
    with get_cursor() as cur:
        cur.execute("DELETE FROM alert_thresholds WHERE id = %s", (threshold_id,))
    record_audit(user, "threshold.delete", "threshold", threshold_id)
    return None


# ============ Feature 3 — History page (snapshots) ============

@app.get("/snapshots", response_model=List[SnapshotOut])
def list_snapshots(
    equipment_id: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    user: dict = Depends(authmod.require_action("history.read")),
):
    query = "SELECT DISTINCT s.* FROM snapshots s"
    conditions, params = [], []
    if equipment_id is not None:
        query += " JOIN snapshot_items si ON si.snapshot_id = s.id"
        conditions.append("si.equipment_id = %s")
        params.append(equipment_id)
    if date_from is not None:
        conditions.append("s.created_at >= %s")
        params.append(date_from)
    if date_to is not None:
        conditions.append("s.created_at <= %s")
        params.append(date_to)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY s.created_at DESC"

    with get_cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


@app.get("/snapshots/{snapshot_id}", response_model=SnapshotDetailOut)
def get_snapshot(snapshot_id: int, user: dict = Depends(authmod.require_action("history.read"))):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM snapshots WHERE id = %s", (snapshot_id,))
        snapshot = cur.fetchone()
        if snapshot is None:
            raise HTTPException(status_code=404, detail="Snapshot introuvable")

        cur.execute(
            """SELECT d.*, e.name AS equipment_name, e.hostname AS equipment_hostname
               FROM snapshot_items si
               JOIN diagnostics d ON d.id = si.diagnostic_id
               JOIN equipments e ON e.id = d.equipment_id
               WHERE si.snapshot_id = %s""",
            (snapshot_id,)
        )
        diagnostics = cur.fetchall()
        for d in diagnostics:
            cur.execute("SELECT * FROM interface_metrics WHERE diagnostic_id = %s", (d["id"],))
            d["interfaces"] = cur.fetchall()
        cur.execute("SELECT to_regclass('public.snapshot_metrics') AS table_name")
        metrics_table = cur.fetchone()["table_name"]
        if metrics_table is None:
            metrics = []
        else:
            cur.execute(
                """SELECT equipment_id, collected_at, cpu_usage, ram_total_kb,
                          ram_used_kb, is_up
                   FROM snapshot_metrics
                   WHERE snapshot_id = %s
                   ORDER BY equipment_id, collected_at""",
                (snapshot_id,),
            )
            metrics = cur.fetchall()

    return {**snapshot, "diagnostics": diagnostics, "metrics": metrics}


@app.patch("/snapshots/{snapshot_id}", response_model=SnapshotOut)
def update_snapshot(snapshot_id: int, payload: SnapshotUpdate,
                    user: dict = Depends(authmod.require_action("monitoring.snapshot.manage"))):
    with get_cursor() as cur:
        cur.execute(
            "UPDATE snapshots SET label = %s WHERE id = %s RETURNING *",
            (payload.label, snapshot_id),
        )
        snapshot = cur.fetchone()
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Snapshot introuvable")
    record_audit(user, "monitoring.snapshot.update", "snapshot", snapshot_id)
    return snapshot


@app.delete("/snapshots/{snapshot_id}", status_code=204)
def delete_snapshot(snapshot_id: int,
                    user: dict = Depends(authmod.require_action("monitoring.snapshot.delete"))):
    with get_cursor() as cur:
        cur.execute("DELETE FROM snapshots WHERE id = %s", (snapshot_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Snapshot introuvable")
    record_audit(user, "monitoring.snapshot.delete", "snapshot", snapshot_id)
    return None


@app.get("/snapshots/{snapshot_id}/export/xlsx")
def export_snapshot_xlsx(snapshot_id: int, user: dict = Depends(authmod.require_action("history.export"))):
    from openpyxl import Workbook
    from openpyxl.chart import LineChart, Reference
    from openpyxl.chart.series import SeriesLabel

    detail = get_snapshot(snapshot_id, user)
    wb = Workbook()
    ws = wb.active
    ws.title = "Snapshot"
    ws.append(["Nom", "Hostname", "Statut", "IP", "Description", "Uptime (centisecondes)",
               "CPU %", "RAM utilisée (kB)", "RAM totale (kB)", "Température °C",
               "Erreur", "Relevé le"])
    for d in detail["diagnostics"]:
        ws.append([
            d["equipment_name"], d["equipment_hostname"], "UP" if d["is_up"] else "DOWN", d["resolved_ip"],
            d["sys_descr"], d["sys_uptime"], d["cpu_usage"], d["ram_used_kb"],
            d["ram_total_kb"], d["temperature_c"], d["error_message"],
            d["collected_at"].strftime("%Y-%m-%d %H:%M:%S"),
        ])

    interfaces = wb.create_sheet("Interfaces")
    interfaces.append([
        "Nom", "Hostname", "Index", "Interface", "Admin", "Opérationnel", "STP",
        "Vitesse (bps)", "Entrée octets", "Sortie octets", "Entrée paquets",
        "Sortie paquets", "Entrée erreurs", "Sortie erreurs", "Entrée rejets", "Sortie rejets",
    ])
    for d in detail["diagnostics"]:
        for iface in d["interfaces"]:
            interfaces.append([
                d["equipment_name"], d["equipment_hostname"], iface["if_index"], iface["if_descr"], iface["admin_status"],
                iface["oper_status"], iface["stp_state"], iface["speed_bps"], iface["in_octets"],
                iface["out_octets"], iface["in_packets"], iface["out_packets"], iface["in_errors"],
                iface["out_errors"], iface["in_discards"], iface["out_discards"],
            ])

    metrics_sheet = wb.create_sheet("Graphiques")
    metrics_sheet.append(["Nom", "Hostname", "Relevé le", "CPU %", "RAM utilisée (kB)", "RAM totale (kB)", "RAM %"])
    equipment_by_id = {d["equipment_id"]: d for d in detail["diagnostics"]}
    for metric in detail["metrics"]:
        equipment = equipment_by_id.get(metric["equipment_id"], {})
        ram_percent = None
        if metric["ram_total_kb"]:
            ram_percent = (metric["ram_used_kb"] or 0) / metric["ram_total_kb"] * 100
        metrics_sheet.append([
            equipment.get("equipment_name"), equipment.get("equipment_hostname"),
            metric["collected_at"].strftime("%Y-%m-%d %H:%M:%S"), metric["cpu_usage"],
            metric["ram_used_kb"], metric["ram_total_kb"], ram_percent,
        ])

    if metrics_sheet.max_row > 1:
        categories = Reference(metrics_sheet, min_col=3, min_row=2, max_row=metrics_sheet.max_row)
        last_metric = detail["metrics"][-1]
        last_cpu = last_metric["cpu_usage"]
        last_ram = None
        if last_metric["ram_total_kb"]:
            last_ram = (last_metric["ram_used_kb"] or 0) / last_metric["ram_total_kb"] * 100
        chart_definitions = (
            (4, f"CPU (%) - dernier: {last_cpu:.1f}%" if last_cpu is not None else "CPU (%) - dernier: N/A", "I2", "3B6FED"),
            (7, f"RAM (%) - dernier: {last_ram:.1f}%" if last_ram is not None else "RAM (%) - dernier: N/A", "I20", "D1453B"),
        )
        for value_column, title, anchor, color in chart_definitions:
            chart = LineChart()
            chart.title = title
            chart.y_axis.title = "Percent"
            chart.x_axis.title = "Relevé"
            chart.y_axis.scaling.min = 0
            chart.y_axis.scaling.max = 100
            chart.height = 7
            chart.width = 14
            chart.add_data(
                Reference(metrics_sheet, min_col=value_column, max_col=value_column,
                          min_row=1, max_row=metrics_sheet.max_row),
                titles_from_data=True,
                from_rows=False,
            )
            chart.set_categories(categories)
            chart.series[0].tx = SeriesLabel(v="CPU (%)" if value_column == 4 else "RAM (%)")
            chart.series[0].graphicalProperties.line.solidFill = color
            chart.series[0].graphicalProperties.line.width = 25000
            metrics_sheet.add_chart(chart, anchor)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{snapshot_filename(detail["label"], "xlsx")}"'}
    )


@app.get("/snapshots/{snapshot_id}/export/pdf")
def export_snapshot_pdf(snapshot_id: int, user: dict = Depends(authmod.require_action("history.export"))):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.graphics.shapes import Drawing, PolyLine, String, Line
    from reportlab.lib.enums import TA_LEFT
    try:
        from svglib.svglib import svg2rlg
    except ImportError:
        svg2rlg = None

    detail = get_snapshot(snapshot_id, user)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=24, leftMargin=24)
    styles = getSampleStyleSheet()
    brand_green = colors.HexColor("#007a3d")
    brand_green_dark = colors.HexColor("#005b2e")
    brand_yellow = colors.HexColor("#f4c542")
    brand_red = colors.HexColor("#d52b1e")
    soft_green = colors.HexColor("#e5f3eb")
    line_green = colors.HexColor("#cfe1d5")

    title_style = ParagraphStyle(
        "SonatrachTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=19, leading=23, textColor=brand_green_dark, alignment=TA_LEFT,
        spaceAfter=2,
    )
    subtitle_style = ParagraphStyle(
        "SonatrachSubtitle", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=8, leading=10, textColor=colors.HexColor("#66736b"),
        tracking=1.2,
    )
    heading_style = ParagraphStyle(
        "SonatrachHeading", parent=styles["Heading3"], fontName="Helvetica-Bold",
        fontSize=11, leading=14, textColor=brand_green_dark, spaceBefore=5,
        spaceAfter=5,
    )

    logo = None
    logo_path = Path(__file__).resolve().parents[2] / "frontend" / "src" / "photos" / "Sonatrach.svg"
    try:
        if svg2rlg is None:
            raise RuntimeError("svglib non installé")
        logo = svg2rlg(str(logo_path))
        scale = min(38 / logo.width, 44 / logo.height)
        logo.scale(scale, scale)
        logo.width = 38
        logo.height = 44
    except Exception:
        logo = None

    brand_content = [Paragraph("Sonatrach", title_style), Paragraph("NETWORK OPERATIONS", subtitle_style)]

    def draw_page(canvas, document):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#f3f7f4"))
        canvas.rect(0, 0, landscape(A4)[0], landscape(A4)[1], stroke=0, fill=1)
        canvas.setFillColor(brand_green)
        canvas.rect(0, landscape(A4)[1] - 6, landscape(A4)[0] * .72, 6, stroke=0, fill=1)
        canvas.setFillColor(brand_yellow)
        canvas.rect(landscape(A4)[0] * .72, landscape(A4)[1] - 6, landscape(A4)[0] * .14, 6, stroke=0, fill=1)
        canvas.setFillColor(brand_red)
        canvas.rect(landscape(A4)[0] * .86, landscape(A4)[1] - 6, landscape(A4)[0] * .14, 6, stroke=0, fill=1)
        canvas.setStrokeColor(line_green)
        canvas.line(24, 22, landscape(A4)[0] - 24, 22)
        canvas.setFillColor(colors.HexColor("#66736b"))
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(landscape(A4)[0] - 24, 11, f"Sonatrach Network Operations • Page {doc.page}")
        canvas.restoreState()

    elements = []
    if logo is not None:
        elements.extend([logo, Spacer(1, 3)])
    elements.extend([brand_content[0], brand_content[1], Spacer(1, 8)])
    elements.extend([Paragraph(f"Snapshot : {detail['label']}", title_style), Spacer(1, 12)])

    data = [["Nom", "Hostname", "Statut", "IP", "Uptime (cs)", "CPU %", "RAM (kB)",
             "Temp °C", "Erreur", "Relevé le"]]
    for d in detail["diagnostics"]:
        data.append([
            str(d["equipment_name"]), str(d["equipment_hostname"]),
            "UP" if d["is_up"] else "DOWN", str(d["resolved_ip"] or ""),
            str(d["sys_uptime"]), str(d["cpu_usage"]), f"{d['ram_used_kb']}/{d['ram_total_kb']}",
            str(d["temperature_c"]), str(d["error_message"] or ""),
            d["collected_at"].strftime("%Y-%m-%d %H:%M:%S"),
        ])

    table = Table(data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), brand_green),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, line_green),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, soft_green]),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    elements.append(table)

    for d in detail["diagnostics"]:
        elements.append(Spacer(1, 14))
        elements.append(Paragraph(
            f"{d['equipment_name']} - {d['equipment_hostname']} - Interfaces",
            heading_style,
        ))
        interface_data = [[
            "Index", "Interface", "Admin", "Op", "STP", "Vitesse", "In octets", "Out octets",
            "In paquets", "Out paquets", "In erreurs", "Out erreurs", "In rejets", "Out rejets",
        ]]
        for iface in d["interfaces"]:
            interface_data.append([
                str(iface["if_index"]), str(iface["if_descr"] or ""), str(iface["admin_status"] or ""),
                str(iface["oper_status"] or ""), str(iface["stp_state"] or ""), str(iface["speed_bps"] or ""),
                str(iface["in_octets"] or ""), str(iface["out_octets"] or ""), str(iface["in_packets"] or ""),
                str(iface["out_packets"] or ""), str(iface["in_errors"] or ""), str(iface["out_errors"] or ""),
                str(iface["in_discards"] or ""), str(iface["out_discards"] or ""),
            ])
        interface_table = Table(interface_data, repeatRows=1, colWidths=[30, 80, 45, 45, 50, 55, 55, 55, 55, 55, 50, 50, 50, 50])
        interface_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), brand_green),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, line_green),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, soft_green]),
            ("FONTSIZE", (0, 0), (-1, -1), 6),
        ]))
        elements.append(interface_table)
        elements.append(Spacer(1, 8))
        points = [m for m in detail["metrics"] if m["equipment_id"] == d["equipment_id"]]
        last_cpu = points[-1]["cpu_usage"] if points else None
        last_ram = None
        if points and points[-1]["ram_total_kb"]:
            last_ram = (points[-1]["ram_used_kb"] or 0) / points[-1]["ram_total_kb"] * 100
        cpu_label = f"CPU (%) - dernière valeur: {last_cpu:.1f}%" if last_cpu is not None else "CPU (%) - dernière valeur: N/A"
        ram_label = f"RAM (%) - dernière valeur: {last_ram:.1f}%" if last_ram is not None else "RAM (%) - dernière valeur: N/A"
        elements.append(Paragraph(cpu_label, heading_style))
        chart = Drawing(500, 160)
        chart.add(String(2, 140, "100%", fontSize=8, fillColor=colors.grey))
        chart.add(String(2, 15, "0%", fontSize=8, fillColor=colors.grey))
        chart.add(Line(28, 20, 28, 145, strokeColor=colors.lightgrey))
        chart.add(Line(28, 20, 495, 20, strokeColor=colors.lightgrey))
        if points:
            x_step = 465 / max(len(points) - 1, 1)
            cpu_line = []
            for index, point in enumerate(points):
                x = 30 + index * x_step
                cpu_line.extend([x, 20 + min(max(point["cpu_usage"] or 0, 0), 100) * 1.25])
            chart.add(PolyLine(cpu_line, strokeColor=brand_green, strokeWidth=2))
        elements.append(chart)
        elements.append(Paragraph(ram_label, heading_style))
        ram_chart = Drawing(500, 160)
        ram_chart.add(String(2, 140, "100%", fontSize=8, fillColor=colors.grey))
        ram_chart.add(String(2, 15, "0%", fontSize=8, fillColor=colors.grey))
        ram_chart.add(Line(28, 20, 28, 145, strokeColor=colors.lightgrey))
        ram_chart.add(Line(28, 20, 495, 20, strokeColor=colors.lightgrey))
        if points:
            x_step = 465 / max(len(points) - 1, 1)
            ram_line = []
            for index, point in enumerate(points):
                x = 30 + index * x_step
                ram_percent = 0
                if point["ram_total_kb"]:
                    ram_percent = (point["ram_used_kb"] or 0) / point["ram_total_kb"] * 100
                ram_line.extend([x, 20 + min(max(ram_percent, 0), 100) * 1.25])
            ram_chart.add(PolyLine(ram_line, strokeColor=brand_red, strokeWidth=2))
        elements.append(ram_chart)
    doc.build(elements, onFirstPage=draw_page, onLaterPages=draw_page)
    buffer.seek(0)

    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{snapshot_filename(detail["label"], "pdf")}"'}
    )
