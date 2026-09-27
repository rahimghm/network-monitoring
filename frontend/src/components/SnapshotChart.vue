<script setup>
import { computed } from 'vue'

const props = defineProps({
  points: { type: Array, default: () => [] },
})

const width = 560
const height = 160
const padding = 28

function buildPath(values) {
  if (!values.length) return ''
  const stepX = (width - padding * 2) / Math.max(values.length - 1, 1)
  return values.map((value, index) => {
    const x = padding + index * stepX
    const y = height - padding - (Math.max(0, Math.min(value || 0, 100)) / 100) * (height - padding * 2)
    return `${index === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`
  }).join(' ')
}

const cpuValues = computed(() => props.points.map(point => point.cpu_usage ?? 0))
const ramValues = computed(() => props.points.map(point => {
  if (!point.ram_total_kb) return 0
  return ((point.ram_used_kb ?? 0) / point.ram_total_kb) * 100
}))
const cpuPath = computed(() => buildPath(cpuValues.value))
const ramPath = computed(() => buildPath(ramValues.value))
const lastCpu = computed(() => {
  const value = cpuValues.value.at(-1)
  return value == null ? 'N/A' : `${value.toFixed(1)}%`
})
const lastRam = computed(() => {
  const value = ramValues.value.at(-1)
  return value == null ? 'N/A' : `${value.toFixed(1)}%`
})
</script>

<template>
  <div class="snapshot-chart">
    <div class="chart-title">Mesures capturées au moment du snapshot</div>
    <p v-if="!points.length" class="empty">Aucun point métrique capturé.</p>
    <template v-else>
      <div class="chart-block">
        <div class="legend"><span><i class="dot cpu"></i>CPU</span><strong>Dernière valeur: {{ lastCpu }} | 0% - 100%</strong></div>
        <svg :viewBox="`0 0 ${width} ${height}`" class="svg-chart" role="img" aria-label="Graphique CPU du snapshot">
          <text x="0" y="15" class="scale">100%</text>
          <text x="5" :y="height - padding + 4" class="scale">0%</text>
          <line :x1="padding" :y1="height - padding" :x2="width - padding" :y2="height - padding" class="axis" />
          <line :x1="padding" :y1="padding" :x2="padding" :y2="height - padding" class="axis" />
          <path :d="cpuPath" class="line cpu" fill="none" />
        </svg>
      </div>
      <div class="chart-block">
        <div class="legend"><span><i class="dot ram"></i>RAM</span><strong>Dernière valeur: {{ lastRam }} | 0% - 100%</strong></div>
        <svg :viewBox="`0 0 ${width} ${height}`" class="svg-chart" role="img" aria-label="Graphique RAM du snapshot">
          <text x="0" y="15" class="scale">100%</text>
          <text x="5" :y="height - padding + 4" class="scale">0%</text>
          <line :x1="padding" :y1="height - padding" :x2="width - padding" :y2="height - padding" class="axis" />
          <line :x1="padding" :y1="padding" :x2="padding" :y2="height - padding" class="axis" />
          <path :d="ramPath" class="line ram" fill="none" />
        </svg>
      </div>
    </template>
  </div>
</template>

<style scoped>
.snapshot-chart { margin-top: 14px; padding: 14px; border: 1px solid #e2e5ea; border-radius: 8px; background: #fafbfc; }
.chart-title { margin-bottom: 8px; color: #1a1d23; font-size: 13px; font-weight: 700; }
.chart-block { padding: 10px; border: 1px solid #e2e5ea; border-radius: 6px; background: #fff; }
.chart-block + .chart-block { margin-top: 10px; }
.legend { display: flex; justify-content: space-between; margin-bottom: 3px; color: #656d79; font-size: 11px; }
.legend span { display: inline-flex; align-items: center; gap: 5px; }
.legend strong { color: #858b95; font-weight: 600; }
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.dot.cpu { background: var(--brand-green); }
.dot.ram { background: #d1453b; }
.svg-chart { display: block; width: 100%; height: 150px; }
.axis { stroke: #dfe3e8; stroke-width: 1; }
.scale { fill: #858b95; font-size: 10px; }
.line { stroke-width: 2; }
.line.cpu { stroke: var(--brand-green); }
.line.ram { stroke: #d1453b; }
.empty { margin: 0; color: #858b95; font-size: 12px; }
</style>
