<script setup>
import { ref, watch, onMounted, onUnmounted, computed } from 'vue'
import { getMetricsTimeseries } from '../api.js'

const props = defineProps({
  equipmentId: { type: Number, default: null }
})

const points = ref([])
let intervalId = null

const WIDTH = 560
const HEIGHT = 160
const PADDING = 28

async function refresh() {
  if (!props.equipmentId) return
  try {
    points.value = await getMetricsTimeseries(props.equipmentId, 50)
  } catch (e) {
    // silencieux : le graphique reste juste vide si l'API échoue ponctuellement
  }
}

function buildPath(values, maxValue) {
  if (values.length === 0) return ''
  const stepX = (WIDTH - PADDING * 2) / Math.max(values.length - 1, 1)
  return values
    .map((v, i) => {
      const x = PADDING + i * stepX
      const ratio = maxValue > 0 ? v / maxValue : 0
      const y = HEIGHT - PADDING - ratio * (HEIGHT - PADDING * 2)
      return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`
    })
    .join(' ')
}

const cpuValues = computed(() => points.value.map(p => p.cpu_usage ?? 0))
const ramPercentValues = computed(() =>
  points.value.map(p => {
    if (!p.ram_total_kb) return 0
    return ((p.ram_used_kb ?? 0) / p.ram_total_kb) * 100
  })
)

const cpuPath = computed(() => buildPath(cpuValues.value, 100))
const ramPath = computed(() => buildPath(ramPercentValues.value, 100))

const lastCpu = computed(() => {
  const v = cpuValues.value
  return v.length ? v[v.length - 1].toFixed(1) : '—'
})
const lastRam = computed(() => {
  const v = ramPercentValues.value
  return v.length ? v[v.length - 1].toFixed(1) : '—'
})

watch(() => props.equipmentId, () => {
  points.value = []
  refresh()
})

onMounted(() => {
  refresh()
  // Le backend poll déjà toutes les 20s en arrière-plan ; on rafraîchit
  // l'affichage un peu plus souvent pour que le graphique suive de près.
  intervalId = setInterval(refresh, 5000)
})

onUnmounted(() => {
  if (intervalId) clearInterval(intervalId)
})
</script>

<template>
  <div class="chart-panel" v-if="equipmentId">
    <div class="chart-header">
      <h3>CPU / RAM (temps réel)</h3>
      <span class="hint">actualisé toutes les 5s · relevé auto toutes les 20s</span>
    </div>

    <div v-if="points.length === 0" class="empty">
      Pas encore d'historique — patiente ~20s après le premier diagnostic.
    </div>

    <div v-else class="charts">
      <div class="chart-block">
        <div class="legend"><span class="dot cpu"></span> CPU <strong>{{ lastCpu }}%</strong></div>
        <svg :viewBox="`0 0 ${WIDTH} ${HEIGHT}`" class="svg-chart">
          <line :x1="PADDING" :y1="HEIGHT - PADDING" :x2="WIDTH - PADDING" :y2="HEIGHT - PADDING" class="axis" />
          <path :d="cpuPath" class="line cpu" fill="none" />
        </svg>
      </div>

      <div class="chart-block">
        <div class="legend"><span class="dot ram"></span> RAM <strong>{{ lastRam }}%</strong></div>
        <svg :viewBox="`0 0 ${WIDTH} ${HEIGHT}`" class="svg-chart">
          <line :x1="PADDING" :y1="HEIGHT - PADDING" :x2="WIDTH - PADDING" :y2="HEIGHT - PADDING" class="axis" />
          <path :d="ramPath" class="line ram" fill="none" />
        </svg>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chart-panel {
  margin-top: 20px;
  border-top: 1px solid #e2e5ea;
  padding-top: 16px;
}
.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 10px;
}
.chart-header h3 { margin: 0; font-size: 14px; color: #1a1d23; }
.hint { font-size: 11px; color: #aaa; }
.empty { color: #888; font-size: 13px; padding: 20px 0; text-align: center; }

.charts { display: flex; flex-direction: column; gap: 16px; }
.chart-block { background: #f7f8fa; border-radius: 8px; padding: 10px 12px; }
.legend { font-size: 12px; color: #555; margin-bottom: 4px; display: flex; align-items: center; gap: 6px; }
.legend strong { color: #1a1d23; margin-left: auto; }
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.dot.cpu { background: var(--brand-green); }
.dot.ram { background: #d1453b; }

.svg-chart { width: 100%; height: 120px; display: block; }
.axis { stroke: #e2e5ea; stroke-width: 1; }
.line { stroke-width: 2; }
.line.cpu { stroke: var(--brand-green); }
.line.ram { stroke: #d1453b; }
</style>
