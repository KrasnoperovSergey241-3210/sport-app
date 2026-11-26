<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import Icon from './Icon.vue'
import type { ProfilePayload, SportItem } from './api/client'
import { dateKey, numberIn, profileIdentity, seasons, validateProfile } from './lib/forms'
import { ageOnDate, experienceYears } from './lib/scoring'

const props = defineProps<{ profile: ProfilePayload; sports: SportItem[]; busy: boolean; error: string; offline: boolean }>()
const emit = defineEmits<{ save: [data: ProfilePayload] }>()
const data = reactive({ ...props.profile })
const identity = computed(() => profileIdentity(data.first_name, data.last_name))
const sport = ref(props.profile.sport ? String(props.profile.sport) : props.profile.sport_custom ? 'other' : '')
const validation = ref('')
const age = computed(() => data.birth_date ? ageOnDate(data.birth_date, dateKey()) : null)
const total = computed(() => age.value !== null && numberIn(data.start_age_any, 0, age.value, 1) ? experienceYears(age.value, Number(data.start_age_any)) : null)
const experience = computed(() => age.value !== null && numberIn(data.start_age_sport, 0, age.value, 1) ? experienceYears(age.value, Number(data.start_age_sport)) : null)

function submit() {
  const payload: ProfilePayload = {
    first_name: data.first_name?.trim(), last_name: data.last_name?.trim(), middle_name: data.middle_name?.trim() ?? '',
    sex: data.sex, birth_date: data.birth_date, sport: sport.value && sport.value !== 'other' ? Number(sport.value) : null,
    sport_custom: sport.value === 'other' ? data.sport_custom?.trim() : '', season_period: data.season_period,
    start_age_any: data.start_age_any, start_age_sport: data.start_age_sport, trainings_per_week: data.trainings_per_week, hours_per_week: data.hours_per_week,
  }
  validation.value = validateProfile(payload)
  if (!validation.value) emit('save', payload)
}
</script>

<template>
  <section class="profile-view">
    <header class="profile-banner">
      <div class="profile-banner-content">
        <span class="profile-emblem" :class="{ 'profile-emblem-named': identity.initials }" aria-hidden="true">
          <span v-if="identity.initials">{{ identity.initials }}</span>
          <Icon v-else name="user" :size="27" />
        </span>
        <div class="profile-banner-copy">
          <Transition name="profile-name" mode="out-in">
            <h1 :key="identity.name ? 'named' : 'empty'">{{ identity.name || 'Заполните профиль' }}</h1>
          </Transition>
          <p>Личные данные, спортивный стаж и тренировочный режим</p>
        </div>
      </div>
    </header>
    <form class="surface form-panel form-stack" @submit.prevent="submit">
      <h2>Личные данные</h2>
      <div class="field-grid three">
        <label>Фамилия<input v-model.trim="data.last_name" autocomplete="family-name" maxlength="100" required /></label>
        <label>Имя<input v-model.trim="data.first_name" autocomplete="given-name" maxlength="100" required /></label>
        <label>Отчество <span class="optional">необязательно</span><input v-model.trim="data.middle_name" autocomplete="additional-name" maxlength="100" /></label>
      </div>
      <div class="field-grid">
        <label>Дата рождения<input v-model="data.birth_date" type="date" min="1900-01-01" :max="dateKey()" autocomplete="bday" required /></label>
        <label>Пол<select v-model="data.sex" required><option disabled value="">Выберите пол</option><option value="female">Женский</option><option value="male">Мужской</option></select></label>
      </div>
      <hr />
      <h2>Тренировки</h2>
      <div class="field-grid">
        <label>Вид спорта<select v-model="sport" required><option disabled value="">Выберите вид спорта</option><option v-if="data.sport && !sports.some(item => item.id === data.sport)" :value="String(data.sport)">{{ data.sport_name }}</option><option v-for="item in sports" :key="item.id" :value="String(item.id)">{{ item.name }}</option><option value="other">Другой вид спорта</option></select></label>
        <label>Период сезона<select v-model="data.season_period" required><option disabled value="">Выберите период</option><option v-for="(label, value) in seasons" :key="value" :value="value">{{ label }}</option></select></label>
      </div>
      <label v-if="sport === 'other'">Название вида спорта<input v-model.trim="data.sport_custom" maxlength="200" required /></label>
      <div class="field-grid">
        <label>Возраст начала занятий спортом<input v-model.number="data.start_age_any" type="number" min="0" :max="Math.min(age ?? 100, 100)" required /></label>
        <label>Возраст начала занятий этим видом спорта<input v-model.number="data.start_age_sport" type="number" min="0" :max="Math.min(age ?? 100, 100)" required /></label>
        <label>Тренировок в неделю<input v-model.number="data.trainings_per_week" type="number" min="0" max="21" required /></label>
        <label>Часов в неделю<input v-model.number="data.hours_per_week" type="number" min="0" max="60" step="0.5" required /></label>
      </div>
      <div v-if="age !== null && age >= 18" class="profile-facts"><span>Возраст <strong>{{ age }}</strong></span><span>Общий стаж, лет <strong>{{ total !== null && total >= 0 ? total : '—' }}</strong></span><span>Стаж в этом виде спорта, лет <strong>{{ experience !== null && experience >= 0 ? experience : '—' }}</strong></span></div>
      <p v-if="offline" class="inline-note">Для сохранения профиля понадобится подключение к сети.</p>
      <p v-if="validation || error" class="error" role="alert">{{ validation || error }}</p>
      <div class="form-actions"><button class="button primary" :disabled="busy || offline">{{ busy ? 'Сохраняем…' : 'Сохранить профиль' }}</button></div>
    </form>
  </section>
</template>
