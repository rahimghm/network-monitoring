"""
Compare les métriques d'un diagnostic aux seuils configurés (globaux ou
spécifiques à l'équipement) et enregistre/retourne les dépassements.
"""
from .database import get_db, get_cursor


def _metric_values(diagnostic: dict) -> dict:
    ram_percent = None
    if diagnostic.get("ram_total_kb"):
        ram_percent = (diagnostic.get("ram_used_kb") or 0) / diagnostic["ram_total_kb"] * 100
    return {
        "cpu_usage": diagnostic.get("cpu_usage"),
        "ram_percent": ram_percent,
        "temperature_c": diagnostic.get("temperature_c"),
    }


def evaluate_thresholds(equipment_id: int, diagnostic_id: int, diagnostic: dict) -> list:
    """
    Retourne la liste des alertes déclenchées (et les enregistre dans
    alert_events). Les seuils spécifiques à l'équipement priment sur les
    seuils globaux (equipment_id IS NULL) pour une même métrique.
    """
    with get_cursor() as cur:
        cur.execute(
            """SELECT * FROM alert_thresholds
               WHERE enabled = true AND (equipment_id = %s OR equipment_id IS NULL)
               ORDER BY equipment_id NULLS LAST""",  # spécifique d'abord
            (equipment_id,)
        )
        thresholds = cur.fetchall()

    values = _metric_values(diagnostic)
    seen_metrics = set()
    triggered = []

    for t in thresholds:
        metric = t["metric"]
        if metric in seen_metrics:
            continue  # un seuil spécifique équipement a déjà été appliqué pour cette métrique
        seen_metrics.add(metric)

        value = values.get(metric)
        if value is None:
            continue

        breached = (value > t["threshold_value"]) if t["operator"] == "gt" else (value < t["threshold_value"])
        if not breached:
            continue

        message = f"{metric} = {value:.1f} {'>' if t['operator'] == 'gt' else '<'} seuil {t['threshold_value']}"
        triggered.append({
            "metric": metric,
            "value": value,
            "threshold_value": t["threshold_value"],
            "message": message,
        })

    if triggered:
        with get_db() as conn:
            cur = conn.cursor()
            for alert in triggered:
                cur.execute(
                    """INSERT INTO alert_events
                       (equipment_id, diagnostic_id, metric, value, threshold_value, message)
                       VALUES (%s,%s,%s,%s,%s,%s)""",
                    (equipment_id, diagnostic_id, alert["metric"], alert["value"],
                     alert["threshold_value"], alert["message"])
                )
            conn.commit()

    return triggered
