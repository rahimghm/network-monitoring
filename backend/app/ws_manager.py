"""
Un flux de diagnostic partagé par toutes les connexions WebSocket :
- "start"   {equipment_ids: [...], interval_seconds: 5}
- "pause"   suspend l'envoi de mises à jour sans fermer la connexion
- "resume"  reprend
- "stop"    arrête définitivement les tâches de cette session
- "snapshot" {label}  fige les derniers diagnostics connus dans /snapshots

Chaque équipement sélectionné tourne dans sa propre tâche asyncio, qui
appelle collect_diagnostics (bloquant) via asyncio.to_thread pour ne pas
geler la boucle d'événements pendant l'attente réseau SNMP.
"""
import asyncio
from fastapi import WebSocket

from .database import get_db, get_cursor
from .snmp_poller import collect_diagnostics
from .alerts import evaluate_thresholds
from .polling_control import pause_automatic_polling, resume_automatic_polling


def _save_diagnostic(equipment_id: int, data: dict) -> tuple:
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
        for mac in data["mac_table"]:
            cur.execute(
                """INSERT INTO mac_table_entries
                   (diagnostic_id, mac_address, bridge_port, if_index, if_descr, status)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (diagnostic_id, mac["mac_address"], mac["bridge_port"], mac["if_index"],
                 mac["if_descr"], mac["status"])
            )
        conn.commit()
    return diagnostic_id, collected_at


class MonitoringHub:
    def __init__(self):
        self.subscribers: set[WebSocket] = set()
        self.tasks: dict[int, asyncio.Task] = {}
        self.paused = False
        self.running = False
        self.last_diagnostic_id: dict[int, int] = {}   # equipment_id -> dernier diagnostic_id connu
        self.last_payload: dict[int, dict] = {}         # equipment_id -> dernier payload envoyé

    async def subscribe(self, websocket: WebSocket):
        self.subscribers.add(websocket)
        for payload in self.last_payload.values():
            await websocket.send_json(payload)

    def unsubscribe(self, websocket: WebSocket):
        self.subscribers.discard(websocket)

    async def broadcast(self, payload: dict):
        disconnected = []
        for websocket in self.subscribers:
            try:
                await websocket.send_json(payload)
            except Exception:
                disconnected.append(websocket)
        for websocket in disconnected:
            self.unsubscribe(websocket)

    async def _poll_loop(self, equipment_id: int, hostname: str, community: str, interval: float):
        while True:
            if not self.paused:
                try:
                    data = await asyncio.to_thread(collect_diagnostics, hostname, community)
                    if not self.running or self.paused:
                        continue
                    diagnostic_id, collected_at = await asyncio.to_thread(
                        _save_diagnostic, equipment_id, data
                    )
                    self.last_diagnostic_id[equipment_id] = diagnostic_id

                    alerts = await asyncio.to_thread(
                        evaluate_thresholds, equipment_id, diagnostic_id, data
                    )

                    payload = {
                        "type": "update",
                        "equipment_id": equipment_id,
                        "data": {**data, "id": diagnostic_id,
                                 "collected_at": collected_at.isoformat()},
                    }
                    self.last_payload[equipment_id] = payload
                    await self.broadcast(payload)

                    for alert in alerts:
                        await self.broadcast({
                            "type": "alert",
                            "equipment_id": equipment_id,
                            **alert,
                        })
                except Exception as e:
                    await self.broadcast({
                        "type": "update",
                        "equipment_id": equipment_id,
                        "data": {"is_up": False, "error_message": str(e), "interfaces": []},
                    })
            await asyncio.sleep(interval)

    async def start(self, equipment_ids: list, interval_seconds: float = 5):
        self.running = True
        self.paused = False
        resume_automatic_polling()
        with get_cursor() as cur:
            cur.execute(
                "SELECT id, hostname, community FROM equipments WHERE id = ANY(%s)",
                (equipment_ids,)
            )
            equipments = cur.fetchall()

        for eq in equipments:
            if eq["id"] in self.tasks:
                continue  # déjà en cours de polling
            self.tasks[eq["id"]] = asyncio.create_task(
                self._poll_loop(eq["id"], eq["hostname"], eq["community"], interval_seconds)
            )

    def pause(self):
        self.paused = True
        pause_automatic_polling()

    def resume(self):
        self.paused = False
        resume_automatic_polling()

    async def stop(self):
        self.running = False
        pause_automatic_polling()
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        self.tasks.clear()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def snapshot(self, label: str, created_by: int = None) -> int:
        """Fige les derniers diagnostics connus de la session dans un snapshot persistant."""
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO snapshots (label, created_by) VALUES (%s, %s) RETURNING id",
                (label, created_by)
            )
            snapshot_id = cur.fetchone()[0]
            for equipment_id, diagnostic_id in self.last_diagnostic_id.items():
                cur.execute(
                    """INSERT INTO snapshot_items (snapshot_id, equipment_id, diagnostic_id)
                       VALUES (%s,%s,%s)""",
                    (snapshot_id, equipment_id, diagnostic_id)
                )
            conn.commit()
        return snapshot_id


monitoring_hub = MonitoringHub()
