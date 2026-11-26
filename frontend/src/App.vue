<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import Icon from './Icon.vue'
import AuthForm from './AuthForm.vue'
import ProfileForm from './ProfileForm.vue'
import Questionnaire from './Questionnaire.vue'
import TrendChart from './TrendChart.vue'
import AssessmentResult from './AssessmentResult.vue'
import { formatDate, needsRestq, profileIdentity, seasons, submissionAnswers, type Answers } from './lib/forms'
import { localResult, messageFor, useSession, type Result } from './lib/session'
import type { ProfilePayload } from './api/client'

type Page = 'welcome' | 'register' | 'login' | 'home' | 'profile' | 'assessment' | 'result'
const session = useSession()
const { api, user, profile, home, sports, settings, draft, pending, lastResult, online, status, syncError, accountReady } = session
const signedIn = computed(() => Boolean(user.value))
const pages: Page[] = ['welcome', 'register', 'login', 'home', 'profile', 'assessment', 'result']
const pageFromHash = () => pages.find((value) => location.hash === `#${value}`)
const page = ref<Page>(pageFromHash() || (signedIn.value ? 'home' : 'welcome'))
const busy = ref(false)
const error = ref('')
const result = ref<Result | null>(null)
const preliminary = ref(false)
const main = ref<HTMLElement>()
const showLogout = ref(false)
const effectivePage = computed<Page>(() => {
  if (!signedIn.value && ['home', 'profile', 'assessment', 'result'].includes(page.value)) return 'welcome'
  if (signedIn.value && ['welcome', 'login', 'register'].includes(page.value)) return 'home'
  if (page.value === 'assessment' && !profile.value.is_complete && accountReady.value) return 'profile'
  if (page.value === 'assessment' && !settings.value) return 'home'
  if (page.value === 'result' && !(result.value || lastResult.value)) return 'home'
  return page.value
})
const dateLabel = new Intl.DateTimeFormat('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' }).format(new Date()).replace(/^./u, (letter) => letter.toLocaleUpperCase('ru-RU'))
const season = computed(() => home.value?.season_period || profile.value.season_period)
const avatarInitials = computed(() => profileIdentity(
  profile.value.first_name?.trim() || home.value?.first_name,
  profile.value.last_name,
).initials)
const latest = computed(() => home.value?.last_assessment)
const navItems = [{ id: 'home' as const, label: 'Главная', icon: 'home' }, { id: 'assessment' as const, label: 'Самооценка', icon: 'clipboard' }, { id: 'profile' as const, label: 'Мой профиль', icon: 'user' }]

function go(next: Page) {
  page.value = next
  const hash = `#${next}`
  if (location.hash !== hash) history.pushState(null, '', hash)
  error.value = ''
}

window.addEventListener('popstate', () => { page.value = pageFromHash() || (signedIn.value ? 'home' : 'welcome'); error.value = '' })
watch(effectivePage, async () => { await nextTick(); main.value?.focus(); window.scrollTo(0, 0) })
watch(user, (current, previous) => {
  if (!current && previous) { result.value = null; preliminary.value = false; go('login') }
})
watch(lastResult, (current) => { if (current && !preliminary.value) result.value = current })

async function authenticated(code: string) {
  busy.value = true
  try {
    await session.enterAccount(code)
    go(profile.value.is_complete || !accountReady.value ? 'home' : 'profile')
  } finally { busy.value = false }
}

async function saveProfile(data: ProfilePayload) {
  busy.value = true
  error.value = ''
  try { await session.saveProfile(data); go('home') }
  catch (failure) { error.value = messageFor(failure) }
  finally { busy.value = false }
}

async function openAssessment() {
  if (pending.value) {
    if (session.resumePending()) { result.value = null; preliminary.value = false; go('assessment'); return }
    if (lastResult.value) { result.value = lastResult.value; preliminary.value = false; go('result'); return }
    error.value = 'Запись ждёт отправки на сервер.'
    return
  }
  if (!profile.value.is_complete) { go('profile'); return }
  if (!settings.value && online.value) {
    busy.value = true
    try { await session.refreshSettings() }
    catch (failure) { error.value = messageFor(failure); return }
    finally { busy.value = false }
  }
  if (!settings.value) { error.value = 'Для начала анкеты нужно загрузить настройки с сервера.'; return }
  if (draft.value && draft.value.expiresAt <= Date.now()) session.expireDraft()
  go('assessment')
}

async function finish(answers: Answers) {
  const cfg = settings.value
  if (!cfg || busy.value) return
  error.value = ''
  const payload = submissionAnswers(answers)
  if (needsRestq(answers, cfg)) {
    preliminary.value = true
    result.value = localResult({ client_uuid: draft.value!.client_uuid, answers: payload }, cfg)
    go('result')
    return
  }
  busy.value = true
  try {
    preliminary.value = false
    result.value = (await session.complete(payload)).result
    go('result')
  } catch (failure) { error.value = messageFor(failure) }
  finally { busy.value = false }
}

async function openResult() {
  if (!latest.value || busy.value) return
  busy.value = true
  error.value = ''
  try {
    preliminary.value = false
    if (!online.value) {
      if (!lastResult.value || lastResult.value.id !== latest.value.id) { error.value = 'Для просмотра записи понадобится подключение к сети.'; return }
      result.value = lastResult.value
    } else {
      result.value = await api.getAssessmentDetail(latest.value.id) as unknown as Result
    }
    go('result')
  } catch (failure) { error.value = messageFor(failure) }
  finally { busy.value = false }
}

async function exit() {
  if (pending.value && !showLogout.value) { showLogout.value = true; return }
  showLogout.value = false
  busy.value = true
  try {
    await session.logout()
    result.value = null
    preliminary.value = false
    go('welcome')
  } finally { busy.value = false }
}
</script>

<template>
  <div v-if="!signedIn" class="public-shell">
    <header class="public-header"><a class="brand" href="#welcome" @click.prevent="go('welcome')"><span class="brand-mark"><Icon name="pulse" :size="22" /></span><span>Пульс</span></a><button v-if="effectivePage === 'welcome'" class="button secondary" @click="go('login')">Войти</button><button v-else class="text-button" @click="go('welcome')">На главную</button></header>
    <main ref="main" tabindex="-1" class="public-main">
      <Transition name="page" mode="out-in">
        <section v-if="effectivePage === 'welcome'" key="welcome" class="public-hero hero">
          <div class="hero-content"><span class="hero-tag"><Icon name="pulse" :size="17" /> Дневник спортсмена</span><h1>Самоконтроль<br />спортсмена</h1><p>Оценивайте самочувствие, следите за переносимостью нагрузки и замечайте изменения на протяжении сезона.</p><button class="button light" @click="go('register')">Создать аккаунт</button><p class="age-note">Для спортсменов от 18 лет</p></div>
        </section>
        <AuthForm v-else :key="effectivePage" :api="api" :registration="effectivePage === 'register'" @authenticated="authenticated" />
      </Transition>
    </main>
  </div>
  <div v-else class="app-shell">
    <aside class="sidebar">
      <a class="brand" href="#home" @click.prevent="go('home')"><span class="brand-mark"><Icon name="pulse" :size="22" /></span><span>Пульс<small>Дневник спортсмена</small></span></a>
      <nav aria-label="Основная навигация"><button v-for="item in navItems" :key="item.id" class="nav-item" :class="{ active: effectivePage === item.id || (item.id === 'assessment' && effectivePage === 'result') }" :aria-current="effectivePage === item.id ? 'page' : undefined" :disabled="busy" @click="item.id === 'assessment' ? openAssessment() : go(item.id)"><Icon :name="item.icon" :size="19" /><span>{{ item.label }}</span></button></nav>
      <div class="sidebar-bottom"><button class="nav-item" :disabled="busy" @click="exit"><Icon name="logOut" :size="19" /><span>Выйти</span></button></div>
    </aside>
    <main ref="main" tabindex="-1" class="workspace">
      <header class="topbar">
        <span class="top-date"><Icon name="calendar" :size="17" />{{ dateLabel }}</span>
        <button class="avatar" aria-label="Мой профиль" :disabled="busy" @click="go('profile')">
          <span v-if="avatarInitials" aria-hidden="true">{{ avatarInitials }}</span>
          <Icon v-else name="user" :size="18" />
        </button>
      </header>
      <div v-if="!online" class="inline-note status-note" role="status"><Icon name="wifiOff" /> Офлайн. Данные самооценки сохраняются в этой вкладке.</div>
      <div v-if="pending && online" class="inline-note status-note" role="status"><Icon name="sync" /><span>{{ syncError || 'Запись ожидает отправки.' }}</span><button class="text-button" @click="session.synchronize">Повторить</button><button v-if="syncError" class="text-button" @click="openAssessment">Открыть анкету</button></div>
      <div v-if="!accountReady" class="surface form-panel"><p role="status">{{ syncError || 'Загружаем профиль…' }}</p><button v-if="syncError && online" class="button secondary" @click="session.loadAccount">Повторить</button></div>
      <Transition v-else name="page" mode="out-in">
        <section v-if="effectivePage === 'home'" key="home" class="dashboard">
          <div class="dashboard-heading"><h1>{{ profile.first_name || home?.first_name ? `Привет, ${profile.first_name || home?.first_name}!` : 'Самоконтроль спортсмена' }}</h1><p>Ваше самочувствие и тренировочный сезон</p></div>
          <section class="hero dashboard-hero"><div class="hero-content"><span class="hero-tag"><Icon name="pulse" :size="17" /> Самоконтроль</span><h2>{{ draft ? 'Продолжите самооценку' : 'Проверьте своё самочувствие' }}</h2><p>Ответьте на вопросы о тренировках, восстановлении и самочувствии.</p><button class="button light" :disabled="busy" @click="openAssessment"><Icon name="clipboard" :size="18" />{{ pending ? 'Посмотреть результат' : !profile.is_complete ? 'Заполнить профиль' : draft ? 'Продолжить самооценку' : 'Начать самооценку' }}</button></div></section>
          <p v-if="error" class="error" role="alert">{{ error }}</p>
          <div class="metric-grid">
            <article class="surface metric"><span class="icon-tile purple"><Icon name="flag" :size="20" /></span><div><p>Период сезона</p><h2>{{ season ? seasons[season] : 'Не выбран' }}</h2></div><button class="text-button" @click="go('profile')">Изменить период</button></article>
            <article class="surface metric"><span class="icon-tile mint"><Icon name="clipboard" :size="20" /></span><div><p>Последняя самооценка</p><h2>{{ latest ? formatDate(latest.filled_at) : 'Записей пока нет' }}</h2></div><button v-if="latest" class="text-button" :disabled="busy" @click="openResult">Посмотреть результат</button></article>
            <article class="surface metric"><span class="icon-tile peach"><Icon name="calendar" :size="20" /></span><div><p>Следующая самооценка</p><h2>{{ home?.next_assessment ? formatDate(home.next_assessment.date) : 'Дата появится позже' }}</h2></div><span v-if="home?.next_assessment" class="due-tag" :class="{ overdue: home.next_assessment.overdue }">{{ home.next_assessment.overdue ? 'Срок прошёл' : home.next_assessment.days_left === 0 ? 'Сегодня' : `Осталось дней: ${home.next_assessment.days_left}` }}</span></article>
          </div>
          <TrendChart :entries="home?.tolerance_6m || []" />
        </section>
        <ProfileForm v-else-if="effectivePage === 'profile'" key="profile" :profile="profile" :sports="sports" :busy="busy" :error="error" :offline="!online" @save="saveProfile" />
        <Questionnaire v-else-if="effectivePage === 'assessment' && settings" key="assessment" :profile="profile" :draft="draft" :settings="settings" :status="status" :busy="busy" :failure="error" @save="session.saveDraft" @complete="finish" @close="go('home')" />
        <AssessmentResult v-else-if="effectivePage === 'result' && (result || lastResult)" key="result" :assessment="(result || lastResult)!" :preliminary="preliminary" :pending="Boolean(pending)" @home="go('home')" @resume="openAssessment" />
      </Transition>
      <div v-if="showLogout" class="overlay" @click.self="showLogout = false"><div class="surface form-panel dialog" role="alertdialog" aria-modal="true" aria-label="Выход из аккаунта" @keydown.esc="showLogout = false"><h2>Выйти из аккаунта?</h2><p>Неотправленная самооценка будет удалена из этой вкладки.</p><div class="form-actions"><button class="button secondary" @click="showLogout = false">Остаться</button><button class="button primary" @click="exit">Выйти</button></div></div></div>
    </main>
  </div>
</template>
