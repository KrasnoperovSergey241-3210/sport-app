<script setup lang="ts">
import { computed, ref } from 'vue'
import Icon from './Icon.vue'
import { formatDate } from './lib/forms'

const props = defineProps<{ entries: { date: string; tolerance: number }[] }>()
const hovered = ref<number | null>(null)
const groups = computed(() => {
  const now = new Date()
  return Array.from({ length: 6 }, (_, index) => new Date(now.getFullYear(), now.getMonth() + index - 5, 1))
})
const width = 820
const height = 130
const left = 32
const right = 800
const y = (value: number) => 13 + (5 - value) * 25
const points = computed(() => {
  const first = +groups.value[0]
  const now = new Date()
  const end = +new Date(now.getFullYear(), now.getMonth() + 1, 1)
  return props.entries.map((entry) => ({ ...entry, time: Date.parse(entry.date.length === 10 ? `${entry.date}T12:00:00` : entry.date) }))
    .filter(({ time, tolerance }) => time >= first && time < end && tolerance >= 1 && tolerance <= 5)
    .sort((a, b) => a.time - b.time)
    .map((entry) => ({ ...entry, x: left + (entry.time - first) / (end - first) * (right - left), y: y(entry.tolerance) }))
})
const line = computed(() => points.value.map((p, index) => `${index ? 'L' : 'M'}${p.x} ${p.y}`).join(' '))
const area = computed(() => points.value.length > 1 ? `${line.value} L${points.value.at(-1)!.x} ${y(1)} H${points.value[0].x} Z` : '')
const selected = computed(() => hovered.value === null ? null : points.value[hovered.value])
</script>

<template>
  <section class="surface chart-card">
    <div class="chart-header"><div class="chart-heading"><span class="icon-tile purple"><Icon name="trend" :size="21" /></span><div><h2>Переносимость нагрузки</h2><p>Оценки по шкале от 1 до 5</p></div></div><span class="period-tag">6 месяцев</span></div>
    <div v-if="points.length" class="chart" @mouseleave="hovered = null">
      <svg :viewBox="`0 0 ${width} ${height}`" preserveAspectRatio="none" role="group" aria-label="График переносимости нагрузки">
        <defs><linearGradient id="chart-fill" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#8257f1" stop-opacity=".20" /><stop offset="1" stop-color="#8257f1" stop-opacity=".02" /></linearGradient></defs>
        <g v-for="n in [5, 4, 3, 2, 1]" :key="n"><line :x1="left" :x2="right" :y1="y(n)" :y2="y(n)" stroke="#e8e5f0" stroke-dasharray="4 4" /><text x="7" :y="y(n) + 4" class="chart-axis">{{ n }}</text></g>
        <path :d="area" fill="url(#chart-fill)" /><path :d="line" fill="none" stroke="#7048e8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke" />
        <circle v-for="(p, index) in points" :key="`${p.date}-${index}`" :cx="p.x" :cy="p.y" :r="hovered === index ? 6 : 4" fill="white" stroke="#7048e8" stroke-width="2" vector-effect="non-scaling-stroke" tabindex="0" :aria-label="`${formatDate(p.date)} — ${p.tolerance} из 5`" @mouseenter="hovered = index" @focus="hovered = index" @blur="hovered = null"><title>{{ formatDate(p.date) }} — {{ p.tolerance }} из 5</title></circle>
      </svg>
      <div class="chart-months"><span v-for="month in groups" :key="+month">{{ month.toLocaleDateString('ru-RU', { month: 'short' }).replace('.', '') }}</span></div>
      <div v-if="selected" class="chart-tooltip" :style="{ left: `${Math.min(88, Math.max(13, selected.x / width * 100))}%` }">{{ formatDate(selected.date) }} · {{ selected.tolerance }} из 5</div>
    </div>
    <p v-else class="empty-chart">График появится после первой завершённой самооценки.</p>
  </section>
</template>
