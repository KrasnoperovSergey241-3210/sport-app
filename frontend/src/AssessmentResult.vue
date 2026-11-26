<script setup lang="ts">
import { computed } from 'vue'
import Icon from './Icon.vue'
import { formatDate } from './lib/forms'
import type { Result } from './lib/session'

const props = defineProps<{ assessment: Result; preliminary: boolean; pending: boolean }>()
defineEmits<{ home: []; resume: [] }>()
const title = computed(() => props.assessment.urgent ? 'Требуется срочная помощь' : props.assessment.red_flag ? 'Есть признаки, требующие внимания' : 'Тревожных признаков не выявлено')
</script>

<template>
  <div class="result-layout">
    <div class="page-heading"><span class="icon-tile purple"><Icon name="pulse" /></span><div><h1>{{ preliminary ? 'Предварительный результат' : 'Результат самооценки' }}</h1><p>{{ formatDate(assessment.filled_at, true) }}</p></div></div>
    <div v-if="assessment.urgent && assessment.result.urgent_message" class="urgent-banner" role="alert"><Icon name="alert" :size="26" /><div><strong>Срочная медицинская помощь</strong><p>{{ assessment.result.urgent_message }}</p></div></div>
    <section class="surface result-card" :class="{ attention: assessment.red_flag }">
      <span class="icon-tile" :class="assessment.red_flag ? 'peach' : 'mint'"><Icon :name="assessment.red_flag ? 'alert' : 'check'" :size="24" /></span>
      <div><h2>{{ title }}</h2><p>{{ assessment.result.summary }}</p></div>
    </section>
    <section v-if="assessment.result.reasons.length" class="surface form-panel"><h2>{{ assessment.result.reasons_title }}</h2><ul class="reasons"><li v-for="reason in assessment.result.reasons" :key="reason">{{ reason }}</li></ul></section>
    <section v-if="assessment.result.kerdo" class="surface form-panel"><h2>Индекс Кердо <strong class="result-number">{{ new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 1 }).format(assessment.result.kerdo.value) }}</strong></h2><p><strong>{{ assessment.result.kerdo.title }}</strong></p><p class="muted">{{ assessment.result.kerdo.text }}</p><p v-if="assessment.result.blood_pressure" class="muted">Давление {{ assessment.result.blood_pressure.sbp }}/{{ assessment.result.blood_pressure.dbp }} мм рт. ст. · пульс {{ assessment.result.blood_pressure.pulse }} уд/мин</p></section>
    <div v-if="preliminary" class="inline-note"><Icon name="info" /> Для завершения и сохранения результата нужно заполнить RESTQ-Sport.</div>
    <div v-else-if="pending" class="inline-note"><Icon name="sync" /> Запись сохранена в этой вкладке и будет отправлена при восстановлении связи с сервером.</div>
    <p v-else class="due-line"><Icon name="calendar" /> Следующая самооценка {{ formatDate(assessment.result.next_due_date) }}</p>
    <p class="muted">{{ assessment.result.disclaimer }}</p>
    <div class="form-actions"><button v-if="preliminary" class="button secondary" @click="$emit('resume')">Вернуться к анкете</button><button class="button primary" @click="$emit('home')">На главную</button></div>
  </div>
</template>
