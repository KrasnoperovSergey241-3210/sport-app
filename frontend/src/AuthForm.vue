<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import type { SportApiClient } from './api/client'
import { dateKey } from './lib/forms'
import { ageOnDate } from './lib/scoring'
import { messageFor } from './lib/session'

const props = defineProps<{ api: SportApiClient; registration: boolean }>()
const emit = defineEmits<{ authenticated: [code: string] }>()
const mode = ref<'register' | 'password' | 'code' | 'reset'>(props.registration ? 'register' : 'password')
const contact = ref('')
const birth = ref('')
const consent = ref(false)
const code = ref('')
const password = ref('')
const stage = ref(false)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const seconds = ref(0)
let timer: number | undefined
const title = computed(() => ({ register: 'Создать аккаунт', password: 'Вход в аккаунт', code: 'Вход по коду', reset: 'Восстановление доступа' })[mode.value])
const hint = computed(() => {
  if (mode.value === 'register') return 'Укажите электронную почту и придумайте пароль.'
  return stage.value ? `Введите код, отправленный на ${contact.value}.` : 'Укажите электронную почту или номер телефона.'
})
const button = computed(() => {
  if (mode.value === 'register') return 'Зарегистрироваться'
  if (mode.value === 'password') return 'Войти'
  if (!stage.value) return 'Получить код'
  return mode.value === 'reset' ? 'Сохранить пароль' : 'Войти'
})

function changeMode(next: typeof mode.value) {
  if (busy.value) return
  mode.value = next
  stage.value = false
  code.value = ''
  password.value = ''
  error.value = ''
  notice.value = ''
  seconds.value = 0
  clearInterval(timer)
}

async function sendCode(value: string) {
  const response = mode.value === 'reset' ? await props.api.passwordResetStart(value) : await props.api.loginOtpStart(value)
  stage.value = true
  notice.value = response.debug_code && import.meta.env.DEV ? `Код для локальной проверки: ${response.debug_code}` : response.detail
  seconds.value = response.resend_in
  clearInterval(timer)
  timer = window.setInterval(() => { if (--seconds.value <= 0) clearInterval(timer) }, 1000)
}

async function submit(resend = false) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    const value = contact.value.trim()
    if (mode.value === 'register') {
      if (!birth.value || ageOnDate(birth.value, dateKey()) < 18 || !consent.value) {
        error.value = 'Для регистрации подтвердите согласие и укажите дату рождения. Приложение доступно с 18 лет.'
        return
      }
      const data = await props.api.register({ email: value, password: password.value, birth_date: birth.value, consent: consent.value })
      emit('authenticated', data.user_code)
    } else if (mode.value === 'password') {
      emit('authenticated', (await props.api.login({ contact: value, password: password.value })).user_code)
    } else if (!stage.value || resend) {
      await sendCode(value)
    } else if (mode.value === 'reset') {
      const response = await props.api.passwordResetConfirm({ contact: value, code: code.value, new_password: password.value })
      busy.value = false
      changeMode('password')
      notice.value = response.detail
    } else {
      const data = await props.api.loginOtpVerify({ contact: value, code: code.value })
      emit('authenticated', data.user_code)
    }
  } catch (failure) { error.value = messageFor(failure) }
  finally { busy.value = false }
}

onUnmounted(() => clearInterval(timer))
</script>

<template>
  <div class="auth-form surface">
    <h1>{{ title }}</h1>
    <p class="muted">{{ hint }}</p>
    <form class="form-stack" @submit.prevent="submit()">
      <label v-if="mode === 'register'">Электронная почта<input v-model.trim="contact" type="email" autocomplete="username" placeholder="name@mail.ru" maxlength="254" required /></label>
      <label v-else-if="!stage">Почта или телефон<input v-model.trim="contact" autocomplete="username" placeholder="name@mail.ru или +7…" maxlength="254" required /></label>
      <label v-if="stage">Одноразовый код<input v-model.trim="code" inputmode="numeric" autocomplete="one-time-code" maxlength="10" required /></label>
      <label v-if="mode === 'register' || mode === 'password' || (mode === 'reset' && stage)">
        {{ mode === 'reset' ? 'Новый пароль' : 'Пароль' }}
        <input v-model="password" type="password" :autocomplete="mode === 'password' ? 'current-password' : 'new-password'" :minlength="mode === 'password' ? undefined : 8" maxlength="128" required />
      </label>
      <template v-if="mode === 'register'">
        <label>Дата рождения <input v-model="birth" type="date" autocomplete="bday" min="1900-01-01" :max="dateKey()" required /></label>
        <label class="check-label"><input v-model="consent" type="checkbox" required /> Я даю согласие на обработку персональных данных для регистрации и ведения самооценок.</label>
      </template>
      <p v-if="notice" class="inline-note" role="status">{{ notice }}</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <button class="button primary" :disabled="busy">{{ busy ? 'Подождите…' : button }}</button>
    </form>
    <div v-if="stage" class="form-links">
      <button type="button" class="text-button" :disabled="busy || seconds > 0" @click="submit(true)">{{ seconds > 0 ? `Повторить через ${seconds} с` : 'Отправить код ещё раз' }}</button>
      <button type="button" class="text-button" @click="changeMode(mode)">Изменить контакт</button>
    </div>
    <div v-else class="form-links">
      <button v-if="mode !== 'password'" class="text-button" @click="changeMode('password')">Войти с паролем</button>
      <button v-if="mode === 'password'" class="text-button" @click="changeMode('code')">Войти по коду</button>
      <button v-if="mode === 'password'" class="text-button" @click="changeMode('reset')">Забыли пароль?</button>
      <button v-if="mode !== 'register'" class="text-button" @click="changeMode('register')">Создать аккаунт</button>
    </div>
  </div>
</template>
