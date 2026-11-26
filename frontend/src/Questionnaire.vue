<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Icon from './Icon.vue'
import Choice from './Choice.vue'
import type { ProfilePayload } from './api/client'
import { dateKey, hrvConditions, hrvMetrics, illnessFrequency, initialAnswers, needsRestq, questions, seasons, steps, symptoms, syncopeDetails, validateStep, type Answers, type RestqAnswers } from './lib/forms'
import { answerKey, evaluateAssessment } from './lib/scoring'
import type { Draft, PublicSettings } from './lib/session'

const props = defineProps<{ profile: ProfilePayload; draft: Draft | null; settings: PublicSettings; status: string; busy: boolean; failure: string }>()
const emit = defineEmits<{ save: [answers: Answers, step: number]; complete: [answers: Answers]; close: [] }>()
const step = ref(props.draft?.step ?? 1)
const answers = ref(initialAnswers(props.profile, props.draft?.answers))
const error = ref('')
const heading = ref<HTMLElement>()
let edited = false
let applyingDraft = false
const section = computed(() => steps[step.value - 1])
const blocked = computed(() => needsRestq(answers.value, props.settings))
const urgent = computed(() => evaluateAssessment(answers.value, props.settings).urgent)
const hints: Record<string, string> = {
  '2.2': 'Сравните текущую работоспособность с привычной при сопоставимой нагрузке.',
  '3.3': 'При ответе «Да» отметьте каждый симптом, который был.',
  '3.4': 'Учитывайте измерения в состоянии покоя.',
  '5.1': 'Сравните значения утреннего пульса в похожих условиях.',
}

function save() {
  if (applyingDraft) return
  edited = true
  emit('save', answers.value, step.value)
}
watch([answers, step], save, { deep: true, flush: 'sync' })
watch(() => props.draft?.client_uuid, () => {
  if (edited || !props.draft) return
  applyingDraft = true
  step.value = props.draft.step
  answers.value = initialAnswers(props.profile, props.draft.answers)
  applyingDraft = false
})

function show(index: number) {
  step.value = index
  window.scrollTo(0, 0)
}

function goBack() {
  error.value = ''
  if (step.value > 1) void show(step.value - 1)
  else { save(); emit('close') }
}

function goNext() {
  error.value = validateStep(step.value, answers.value)
  if (error.value) return
  if (step.value < steps.length) { void show(step.value + 1); return }
  const invalid = steps.findIndex((_, index) => validateStep(index + 1, answers.value))
  if (invalid !== -1) {
    error.value = validateStep(invalid + 1, answers.value)
    void show(invalid + 1)
  } else {
    save()
    emit('complete', answers.value)
  }
}

function setRestq(value: RestqAnswers) { answers.value.restq = value }
</script>

<template>
  <div class="assessment-layout">
    <div class="page-heading"><span class="icon-tile purple"><Icon name="clipboard" /></span><div><h1>Самооценка</h1><p>Ответьте на вопросы о нагрузке и самочувствии.</p></div></div>
    <div class="wizard-grid">
      <aside class="surface wizard-steps" aria-label="Разделы анкеты">
        <p class="small-caption">Разделы анкеты</p>
        <ol><li v-for="(item, index) in steps" :key="item.short" :aria-current="step === index + 1 ? 'step' : undefined" :class="{ current: step === index + 1, done: step > index + 1 }"><span><Icon v-if="step > index + 1" name="check" :size="14" /><template v-else>{{ index + 1 }}</template></span>{{ item.short }}</li></ol>
      </aside>
      <section class="surface wizard-panel">
        <header class="wizard-progress">
          <div><strong>Шаг {{ step }} из {{ steps.length }}</strong><span>{{ Math.round(step / steps.length * 100) }}%</span></div>
          <progress :value="step" :max="steps.length" aria-label="Прогресс анкеты" />
        </header>
        <form class="form-stack" novalidate @submit.prevent="goNext">
          <Transition name="slide" mode="out-in" @after-enter="heading?.focus()">
            <div :key="step" class="step-content form-stack">
              <div><h2 ref="heading" tabindex="-1">{{ section.title }}</h2><p class="muted">{{ section.note }}</p></div>
              <div v-if="step === 1" class="form-stack">
                <label>Период сезона<select v-model="answers.season_period" required><option disabled value="">Выберите период</option><option v-for="(label, value) in seasons" :key="value" :value="value">{{ label }}</option></select></label>
                <div class="field-grid"><label>Тренировок в неделю<input v-model.number="answers.trainings_per_week" type="number" min="0" max="21" /></label><label>Часов в неделю<input v-model.number="answers.hours_per_week" type="number" min="0" max="60" step="0.5" /></label></div>
              </div>
              <fieldset v-if="step === 2" class="rating">
                <legend>Как вы оцениваете переносимость тренировочной нагрузки?</legend>
                <div class="rating-row"><label v-for="n in 5" :key="n" class="option"><input v-model="answers.tolerance" type="radio" name="tolerance" :value="n" /><span>{{ n }}</span></label></div>
                <div class="rating-scale"><span>1 — очень плохо</span><span>5 — очень хорошо</span></div>
              </fieldset>
              <template v-for="question in questions[step] || []" :key="question.id">
                <Choice v-model="answers[answerKey(question.id)]" :name="question.id" :question="question.text.replace('{bp}', `${settings.thresholds.sbp_max}/${settings.thresholds.dbp_max}`)" :help="hints[question.id]" />
                <fieldset v-if="question.id === '3.3' && answers.q3_3" class="follow-up">
                  <legend>Что именно вы почувствовали?</legend>
                  <label v-for="(label, key) in syncopeDetails" :key="key" class="check-label"><input v-model="answers.q3_3_detail" type="checkbox" :value="key" />{{ label }}</label>
                </fieldset>
              </template>
              <div v-if="step === 3 && urgent" class="urgent-banner" role="alert"><Icon name="alert" :size="24" /><div><strong>Срочная медицинская помощь</strong><p>{{ settings.texts.urgent }}</p></div></div>
              <template v-if="step === 4">
                <fieldset v-if="answers.q4_1" class="follow-up">
                  <legend>Что вас беспокоило?</legend>
                  <label v-for="(label, key) in symptoms" :key="key" class="check-label"><input v-model="answers.q4_2" type="checkbox" :value="key" />{{ label }}</label>
                  <label v-if="answers.q4_2.includes('other')">Другой симптом<input v-model.trim="answers.q4_2_other" maxlength="200" /></label>
                  <label>Сколько недель назад вы болели?<input v-model.number="answers.q4_3" type="number" min="1" max="4" /></label>
                </fieldset>
                <label>Сколько раз вы болели за последний месяц?<select v-model="answers.q4_4"><option disabled value="">Выберите вариант</option><option v-for="(label, key) in illnessFrequency" :key="key" :value="key">{{ label }}</option></select></label>
              </template>
              <div v-if="step === 5" class="field-grid">
                <label>Пульс этим утром, уд/мин <span class="optional">необязательно</span><input v-model.number="answers.morning_pulse_today" type="number" min="30" max="200" /></label>
                <label>Обычный утренний пульс, уд/мин <span class="optional">необязательно</span><input v-model.number="answers.morning_pulse_usual" type="number" min="30" max="200" /></label>
              </div>
              <template v-if="step === 7">
                <Choice v-model="answers.bp.measured" name="bp" question="Вы измерили давление и пульс?" no-label="Нет измерения" />
                <div v-if="answers.bp.measured" class="field-grid three">
                  <label>Верхнее, мм рт. ст.<input v-model.number="answers.bp.sbp" type="number" min="60" max="250" /></label>
                  <label>Нижнее, мм рт. ст.<input v-model.number="answers.bp.dbp" type="number" min="40" max="150" /></label>
                  <label>Пульс, уд/мин<input v-model.number="answers.bp.pulse" type="number" min="30" max="200" /></label>
                </div>
              </template>
              <template v-if="step === 8">
                <Choice v-model="answers.hrv.has_device" name="hrv" question="Есть ли у вас данные ВРС?" help="Вариабельность ритма сердца — изменение интервалов между ударами сердца. Если измерения нет, выберите «Нет»." />
                <div v-if="answers.hrv.has_device" class="field-grid">
                  <label>ВРС, мс<input v-model.number="answers.hrv.value" type="number" min="5" max="300" step="any" /></label>
                  <label>Показатель<select v-model="answers.hrv.metric"><option disabled value="">Выберите показатель</option><option v-for="(label, key) in hrvMetrics" :key="key" :value="key">{{ label }}</option></select></label>
                  <label>Условия измерения<select v-model="answers.hrv.conditions"><option disabled value="">Выберите условия</option><option v-for="(label, key) in hrvConditions" :key="key" :value="key">{{ label }}</option></select></label>
                  <label>Устройство <span class="optional">необязательно</span><input v-model.trim="answers.hrv.device" maxlength="100" /></label>
                  <label>Дата измерения <span class="optional">необязательно</span><input v-model="answers.hrv.date" type="date" :max="dateKey()" /></label>
                </div>
                <slot v-if="blocked" name="restq" :current="answers.restq" :save="setRestq">
                  <p class="inline-note">При такой оценке переносимости для завершения самооценки требуется RESTQ-Sport. Сейчас можно посмотреть предварительный результат.</p>
                </slot>
              </template>
              <label v-if="step >= 2 && step <= 6">Комментарий <span class="optional">необязательно</span><textarea v-model="answers[`comment_${step}`]" rows="3" maxlength="2000" placeholder="Добавьте детали, если хотите" /></label>
            </div>
          </Transition>
          <p v-if="error || failure" class="error" role="alert">{{ error || failure }}</p>
          <div class="wizard-actions"><button type="button" class="button secondary" :disabled="busy" @click="goBack">Назад</button><button class="button primary" :disabled="busy">{{ busy ? 'Сохраняем…' : step < steps.length ? 'Далее' : blocked ? 'Предварительный результат' : 'Завершить самооценку' }}</button></div>
        </form>
        <div class="draft-status"><span aria-live="polite">{{ status || `Срок хранения черновика — ${settings.drafts.ttl_hours} ч.` }}</span><button class="text-button" :disabled="busy" @click="save(); emit('close')">Сохранить и выйти</button></div>
      </section>
    </div>
  </div>
</template>
