// Reproduit côté frontend la logique de alerts.py, uniquement pour savoir
// quelle carte métrique surligner en rouge — la détection/persistance
// faisant foi reste côté backend (table alert_events).

function metricValue(diagnostic, metric) {
  if (metric === 'cpu_usage') return diagnostic?.cpu_usage ?? null
  if (metric === 'temperature_c') return diagnostic?.temperature_c ?? null
  if (metric === 'ram_percent') {
    if (!diagnostic?.ram_total_kb) return null
    return ((diagnostic.ram_used_kb ?? 0) / diagnostic.ram_total_kb) * 100
  }
  return null
}

/**
 * thresholds: liste brute de GET /thresholds
 * Retourne { cpu_usage: bool, ram_percent: bool, temperature_c: bool }
 */
export function computeBreaches(thresholds, equipmentId, diagnostic) {
  const result = { cpu_usage: false, ram_percent: false, temperature_c: false }
  if (!diagnostic) return result

  const applicable = {}
  for (const t of thresholds) {
    if (!t.enabled) continue
    // un seuil spécifique à l'équipement prime sur le seuil global pour cette métrique
    if (t.equipment_id === equipmentId) applicable[t.metric] = t
    else if (t.equipment_id === null && !(t.metric in applicable)) applicable[t.metric] = t
  }

  for (const metric of Object.keys(result)) {
    const t = applicable[metric]
    if (!t) continue
    const value = metricValue(diagnostic, metric)
    if (value == null) continue
    result[metric] = t.operator === 'gt' ? value > t.threshold_value : value < t.threshold_value
  }
  return result
}
