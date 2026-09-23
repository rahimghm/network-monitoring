import io
from datetime import datetime
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from apscheduler.schedulers.background import BackgroundScheduler

from .config import POLL_INTERVAL_SECONDS
from .database import get_cursor, get_db
from .schemas import (
    EquipmentCreate, EquipmentOut, DiagnosticOut, MetricPointOut,
    UserCreate, UserOut, TokenOut,
    ThresholdCreate, ThresholdOut,
    SnapshotOut, SnapshotDetailOut,
)
from .snmp_poller import collect_diagnostics
from .alerts import evaluate_thresholds
from .ws_manager import DiagnosisSession
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
                    speed_bps, in_octets, out_octets)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (diagnostic_id, iface["if_index"], iface["if_descr"],
                 iface["oper_status"], iface["admin_status"], iface["speed_bps"],
                 iface["in_octets"], iface["out_octets"])
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


app = FastAPI(title="Network Monitoring API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/config")
def get_config():
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
        return cur.fetchone()


@app.post("/auth/login", response_model=TokenOut)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM users WHERE username = %s", (form_data.username,))
        user = cur.fetchone()
    if user is None or not authmod.verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Identifiants invalides")

    token = authmod.create_access_token({"sub": user["username"], "role": user["role"]})
    return {"access_token": token, "role": user["role"], "username": user["username"]}


@app.get("/auth/me", response_model=UserOut)
def me(user: dict = Depends(authmod.get_current_user)):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM users WHERE id = %s", (user["id"],))
        return cur.fetchone()


@app.get("/users", response_model=List[UserOut])
def list_users(user: dict = Depends(authmod.require_role("admin"))):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM users ORDER BY created_at")
        return cur.fetchall()


@app.post("/users", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate, user: dict = Depends(authmod.require_role("admin"))):
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
        return cur.fetchone()


# ============ Équipements ============
# Admin + Technician gèrent (create/delete) ; Supervisor a un accès en lecture
# seule appliqué côté routeur Vue (les GET restent ouverts à tout utilisateur connecté).

@app.get("/equipments", response_model=List[EquipmentOut])
def list_equipments():
    with get_cursor() as cur:
        cur.execute("SELECT * FROM equipments ORDER BY created_at DESC")
        return cur.fetchall()


@app.post("/equipments", response_model=EquipmentOut, status_code=201)
def create_equipment(eq: EquipmentCreate,
                      user: dict = Depends(authmod.require_role("admin", "technician"))):
    with get_cursor() as cur:
        try:
            cur.execute(
                """INSERT INTO equipments (name, hostname, community)
                   VALUES (%s, %s, %s) RETURNING *""",
                (eq.name, eq.hostname, eq.community)
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Erreur création: {e}")
        return cur.fetchone()


@app.delete("/equipments/{equipment_id}", status_code=204)
def delete_equipment(equipment_id: int,
                      user: dict = Depends(authmod.require_role("admin", "technician"))):
    with get_cursor() as cur:
        cur.execute("DELETE FROM equipments WHERE id = %s", (equipment_id,))
    return None


# ============ Diagnostic ponctuel + historique ============

@app.post("/equipments/{equipment_id}/diagnose", response_model=DiagnosticOut)
def diagnose_equipment(equipment_id: int,
                        user: dict = Depends(authmod.require_role("admin", "technician"))):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM equipments WHERE id = %s", (equipment_id,))
        equipment = cur.fetchone()
    if equipment is None:
        raise HTTPException(status_code=404, detail="Équipement introuvable")
    return run_diagnostic(equipment_id, equipment["hostname"], equipment["community"])


@app.get("/equipments/{equipment_id}/diagnostics", response_model=List[DiagnosticOut])
def get_equipment_history(equipment_id: int, limit: int = 20):
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
def get_metrics_timeseries(equipment_id: int, limit: int = 50):
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
        payload = authmod.decode_token(token)
    except HTTPException:
        await websocket.close(code=4401)
        return
    if payload.get("role") not in ("admin", "technician"):
        await websocket.close(code=4403)
        return

    await websocket.accept()
    session = DiagnosisSession(websocket)
    try:
        while True:
            msg = await websocket.receive_json()
            action = msg.get("action")

            if action == "start":
                await session.start(
                    msg.get("equipment_ids", []),
                    msg.get("interval_seconds", 5)
                )
                await websocket.send_json({"type": "status", "status": "started"})

            elif action == "pause":
                session.pause()
                await websocket.send_json({"type": "status", "status": "paused"})

            elif action == "resume":
                session.resume()
                await websocket.send_json({"type": "status", "status": "resumed"})

            elif action == "stop":
                await session.stop()
                await websocket.send_json({"type": "status", "status": "stopped"})

            elif action == "snapshot":
                with get_cursor() as cur:
                    cur.execute("SELECT id FROM users WHERE username = %s", (payload.get("sub"),))
                    user_row = cur.fetchone()
                snapshot_id = session.snapshot(
                    msg.get("label", f"Snapshot {datetime.utcnow().isoformat()}"),
                    created_by=user_row["id"] if user_row else None
                )
                await websocket.send_json({"type": "snapshot_saved", "snapshot_id": snapshot_id})

    except WebSocketDisconnect:
        await session.stop()


# ============ Feature 4 — Alertes / seuils ============

@app.get("/thresholds", response_model=List[ThresholdOut])
def list_thresholds(user: dict = Depends(authmod.get_current_user)):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM alert_thresholds ORDER BY equipment_id NULLS FIRST, metric")
        return cur.fetchall()


@app.post("/thresholds", response_model=ThresholdOut, status_code=201)
def create_threshold(payload: ThresholdCreate,
                      user: dict = Depends(authmod.require_role("admin"))):
    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO alert_thresholds (equipment_id, metric, operator, threshold_value, enabled)
               VALUES (%s,%s,%s,%s,%s) RETURNING *""",
            (payload.equipment_id, payload.metric, payload.operator,
             payload.threshold_value, payload.enabled)
        )
        return cur.fetchone()


@app.delete("/thresholds/{threshold_id}", status_code=204)
def delete_threshold(threshold_id: int, user: dict = Depends(authmod.require_role("admin"))):
    with get_cursor() as cur:
        cur.execute("DELETE FROM alert_thresholds WHERE id = %s", (threshold_id,))
    return None


# ============ Feature 3 — History page (snapshots) ============

@app.get("/snapshots", response_model=List[SnapshotOut])
def list_snapshots(
    equipment_id: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    user: dict = Depends(authmod.get_current_user),
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
def get_snapshot(snapshot_id: int, user: dict = Depends(authmod.get_current_user)):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM snapshots WHERE id = %s", (snapshot_id,))
        snapshot = cur.fetchone()
        if snapshot is None:
            raise HTTPException(status_code=404, detail="Snapshot introuvable")

        cur.execute(
            """SELECT d.* FROM snapshot_items si
               JOIN diagnostics d ON d.id = si.diagnostic_id
               WHERE si.snapshot_id = %s""",
            (snapshot_id,)
        )
        diagnostics = cur.fetchall()
        for d in diagnostics:
            cur.execute("SELECT * FROM interface_metrics WHERE diagnostic_id = %s", (d["id"],))
            d["interfaces"] = cur.fetchall()

    return {**snapshot, "diagnostics": diagnostics}


@app.get("/snapshots/{snapshot_id}/export/xlsx")
def export_snapshot_xlsx(snapshot_id: int, user: dict = Depends(authmod.get_current_user)):
    from openpyxl import Workbook

    detail = get_snapshot(snapshot_id, user)
    wb = Workbook()
    ws = wb.active
    ws.title = "Snapshot"
    ws.append(["Équipement ID", "Statut", "CPU %", "RAM utilisée (kB)", "RAM totale (kB)",
               "Température °C", "Relevé le"])
    for d in detail["diagnostics"]:
        ws.append([
            d["equipment_id"], "UP" if d["is_up"] else "DOWN", d["cpu_usage"],
            d["ram_used_kb"], d["ram_total_kb"], d["temperature_c"],
            d["collected_at"].strftime("%Y-%m-%d %H:%M:%S"),
        ])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="snapshot_{snapshot_id}.xlsx"'}
    )


@app.get("/snapshots/{snapshot_id}/export/pdf")
def export_snapshot_pdf(snapshot_id: int, user: dict = Depends(authmod.get_current_user)):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    detail = get_snapshot(snapshot_id, user)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()

    elements = [Paragraph(f"Snapshot : {detail['label']}", styles["Title"]), Spacer(1, 12)]

    data = [["Équipement", "Statut", "CPU %", "RAM (kB)", "Temp °C", "Relevé le"]]
    for d in detail["diagnostics"]:
        data.append([
            str(d["equipment_id"]), "UP" if d["is_up"] else "DOWN",
            str(d["cpu_usage"]), f"{d['ram_used_kb']}/{d['ram_total_kb']}",
            str(d["temperature_c"]), d["collected_at"].strftime("%Y-%m-%d %H:%M:%S"),
        ])

    table = Table(data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3b6fed")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)

    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="snapshot_{snapshot_id}.pdf"'}
    )
