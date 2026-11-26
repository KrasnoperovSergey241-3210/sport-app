import { ref, toRaw } from 'vue'
import { ApiError, SportApiClient, type AssessmentCompleteRequest, type ProfilePayload, type SportItem, type TokenStorage } from '../api/client'
import { evaluateAssessment, kerdoClass, kerdoIndex, nextDueDays, type SettingsConfig } from './scoring'
import { dateKey, type Answers, type Season } from './forms'

export interface PublicSettings extends SettingsConfig {
  drafts: { ttl_hours: number }
  texts: SettingsConfig['texts'] & {
    about: string; age_restriction: string; urgent: string; flag: string; ok: string; flag_reasons_title: string; disclaimer: string
    kerdo: Record<string, { title: string; text: string }>
  }
}

export interface Result {
  id?: string
  red_flag: boolean
  urgent: boolean
  filled_at: string
  result: {
    urgent_message: string | null
    summary: string
    reasons_title: string | null
    reasons: string[]
    blood_pressure: { sbp: number; dbp: number; pulse: number } | null
    kerdo: { value: number; title: string; text: string } | null
    disclaimer: string
    next_due_date: string
  }
}

interface Home {
  first_name: string
  season_period?: Season
  last_assessment: { id: string; filled_at: string; red_flag: boolean; urgent: boolean } | null
  next_assessment: { date: string; days_left: number; overdue: boolean } | null
  tolerance_6m: { date: string; tolerance: number }[]
}

export interface Draft {
  step: number
  client_uuid: string
  started_at: string
  answers: Partial<Answers>
  updatedAt: number
  expiresAt: number
  dirty: boolean
}

const key = 'sport-pulse:'
function read<T>(name: string): T | null {
  try { return JSON.parse(sessionStorage.getItem(key + name) || 'null') as T | null }
  catch { return null }
}

function store(name: string, value: unknown): boolean {
  try {
    if (value === null) sessionStorage.removeItem(key + name)
    else sessionStorage.setItem(key + name, JSON.stringify(value))
    return true
  } catch { return false }
}

function snapshot<T>(value: T): T {
  return JSON.parse(JSON.stringify(toRaw(value))) as T
}

export function messageFor(error: unknown): string {
  if (error instanceof ApiError && error.status < 500) {
    const collect = (value: unknown): string[] => {
      if (typeof value === 'string') return [value]
      if (value && typeof value === 'object') return Object.values(value).flatMap(collect)
      return []
    }
    const detail = collect(error.errors).join(' ')
    return detail || (/[а-яё]/i.test(error.message) ? error.message : 'Проверьте данные и повторите попытку.')
  }
  return 'Сервер недоступен. Проверьте подключение и попробуйте ещё раз.'
}

function transient(error: unknown): boolean {
  return error instanceof TypeError || (error instanceof ApiError && [502, 503, 504].includes(error.status))
}

export function localResult(payload: AssessmentCompleteRequest, cfg: PublicSettings): Result {
  const evaluation = evaluateAssessment(payload.answers, cfg)
  const bp = payload.answers.bp as { measured?: boolean; sbp: number; dbp: number; pulse: number } | undefined
  const pressure = bp?.measured ? { sbp: bp.sbp, dbp: bp.dbp, pulse: bp.pulse } : null
  const kerdo = pressure ? kerdoIndex(pressure.dbp, pressure.pulse) : null
  const classification = kerdo === null ? null : kerdoClass(kerdo, cfg.thresholds.kerdo_low, cfg.thresholds.kerdo_high)
  const date = new Date(payload.filled_at || Date.now())
  date.setDate(date.getDate() + nextDueDays(evaluation.redFlag, evaluation.urgent, cfg))
  return {
    red_flag: evaluation.redFlag, urgent: evaluation.urgent, filled_at: payload.filled_at || new Date().toISOString(),
    result: {
      urgent_message: evaluation.urgent ? cfg.texts.urgent : null,
      summary: evaluation.redFlag ? cfg.texts.flag : cfg.texts.ok,
      reasons_title: evaluation.reasons.length ? cfg.texts.flag_reasons_title : null,
      reasons: evaluation.reasons.map(({ text }) => text),
      blood_pressure: pressure,
      kerdo: kerdo !== null && classification ? { value: kerdo, ...cfg.texts.kerdo[classification] } : null,
      disclaimer: cfg.texts.disclaimer, next_due_date: dateKey(date),
    },
  }
}

export function useSession() {
  const auth = read<{ access: string; refresh?: string }>('auth') ?? { access: '' }
  const user = ref(read<string>('user'))
  const profile = ref<ProfilePayload>({})
  const home = ref<Home | null>(null)
  const sports = ref<SportItem[]>([])
  const settings = ref(read<PublicSettings>('settings'))
  const draft = ref<Draft | null>(null)
  const pending = ref<AssessmentCompleteRequest | null>(null)
  const lastResult = ref<Result | null>(null)
  const online = ref(navigator.onLine)
  const status = ref('')
  const syncError = ref('')
  const accountReady = ref(false)
  let draftTimer: number | undefined
  let draftRequest: Promise<void> | undefined
  let completion: Promise<Result | null> | undefined
  let revision = 0

  const tokens: TokenStorage = {
    getAccessToken: () => auth.access || null,
    getRefreshToken: () => auth.refresh || null,
    setTokens(next) {
      auth.access = next.access
      if (next.refresh) auth.refresh = next.refresh
      store('auth', auth)
    },
    clearTokens() {
      auth.access = ''
      delete auth.refresh
      store('auth', null)
    },
  }
  const api = new SportApiClient({
    baseUrl: import.meta.env.VITE_API_BASE_URL || location.origin,
    storage: tokens,
    onUnauthorized: () => { user.value = null; store('user', null); accountReady.value = false },
  })

  function restore() {
    clearTimeout(draftTimer)
    revision++
    const account = user.value
    profile.value = account ? read<ProfilePayload>(`${account}:profile`) ?? {} : {}
    home.value = account ? read<Home>(`${account}:home`) : null
    sports.value = account ? read<SportItem[]>(`${account}:sports`) ?? [] : []
    draft.value = account ? read<Draft>(`${account}:draft`) : null
    if (draft.value && draft.value.expiresAt <= Date.now()) {
      store(`${account}:draft`, null)
      draft.value = null
    }
    pending.value = account ? read<AssessmentCompleteRequest>(`${account}:pending`) : null
    lastResult.value = account ? read<Result>(`${account}:result`) : null
    status.value = draft.value ? 'Черновик сохранён' : ''
    syncError.value = ''
    accountReady.value = Boolean(account && profile.value.birth_date)
  }

  async function refreshHome() {
    const account = user.value
    if (!account || !online.value) return
    const [profileData, homeData] = await Promise.all([api.getProfile(), api.getHome()])
    if (user.value !== account) return
    profile.value = profileData
    home.value = homeData as unknown as Home
    accountReady.value = true
    store(`${account}:profile`, profile.value)
    store(`${account}:home`, home.value)
  }

  async function refreshSettings() {
    if (!online.value) return
    const response = await api.getPublicSettings()
    const data = response.data as unknown as PublicSettings
    store('settings', data)
    settings.value = data
  }

  async function loadAccount() {
    const account = user.value
    if (!account || !online.value) return
    await Promise.allSettled([refreshSettings(), refreshHome(), api.getSports().then((items) => {
      if (user.value !== account) return
      sports.value = items
      store(`${account}:sports`, items)
    })])
    if (user.value === account && !accountReady.value) syncError.value = 'Не удалось открыть профиль. Проверьте соединение.'
    await synchronize()
    const before = revision
    try {
      const remote = await api.getDraft()
      if (user.value !== account || before !== revision || pending.value || draft.value?.dirty) return
      const { step, client_uuid, started_at, ...answers } = remote.data
      const updatedAt = Date.parse(remote.updated_at)
      if (client_uuid && updatedAt >= (draft.value?.updatedAt ?? 0)) {
        draft.value = {
          step: Math.max(1, Math.min(8, Number(step) || 1)), client_uuid: String(client_uuid),
          started_at: String(started_at || remote.updated_at), answers: answers as Partial<Answers>,
          updatedAt, expiresAt: Date.parse(remote.expires_at), dirty: false,
        }
        store(`${account}:draft`, draft.value)
      }
    } catch (error) {
      if (!(error instanceof ApiError && error.status === 404)) return
      if (user.value === account && before === revision && draft.value && !draft.value.dirty) {
        draft.value = null
        store(`${account}:draft`, null)
        status.value = ''
      }
    }
  }

  async function enterAccount(code: string) {
    user.value = code
    store('user', code)
    restore()
    await loadAccount()
  }

  async function saveProfile(data: ProfilePayload) {
    profile.value = await api.updateProfile(data, 'PUT')
    store(`${user.value}:profile`, profile.value)
    await refreshHome().catch(() => {})
  }

  function saveDraft(answers: Answers, step: number): Draft {
    const current = draft.value && draft.value.expiresAt > Date.now() ? draft.value : null
    draft.value = {
      answers: snapshot(answers), step, client_uuid: current?.client_uuid ?? crypto.randomUUID(),
      started_at: current?.started_at ?? new Date().toISOString(), updatedAt: Date.now(),
      expiresAt: Date.now() + (settings.value?.drafts.ttl_hours ?? 72) * 3600000, dirty: true,
    }
    revision++
    const saved = store(`${user.value}:draft`, draft.value)
    status.value = saved ? 'Черновик сохранён на устройстве' : 'Черновик пока хранится только на этом экране'
    clearTimeout(draftTimer)
    if (online.value) draftTimer = window.setTimeout(() => { void syncDraft() }, 650)
    return draft.value
  }

  async function syncDraft() {
    if (draftRequest) return draftRequest
    const draftData = draft.value
    const account = user.value
    if (!draftData?.dirty || !account || !online.value || pending.value || draftData.expiresAt <= Date.now()) return
    const { answers, step, client_uuid, started_at } = draftData
    const rev = revision
    draftRequest = (async () => {
      try {
        const saved = await api.saveDraft({ ...answers, step, client_uuid, started_at })
        if (user.value === account && revision === rev) {
          draft.value = { ...draftData, dirty: false, updatedAt: Date.parse(saved.updated_at), expiresAt: Date.parse(saved.expires_at) }
          store(`${account}:draft`, draft.value)
          status.value = 'Черновик синхронизирован'
        }
      } catch { /* Keep the local draft for the next synchronization. */ }
    })()
    try { await draftRequest } finally { draftRequest = undefined }
    if (user.value === account && revision !== rev) await syncDraft()
  }

  function forgetDraft() {
    clearTimeout(draftTimer)
    revision++
    draft.value = null
    store(`${user.value}:draft`, null)
    status.value = ''
  }

  function recordResult(result: Result) {
    lastResult.value = result
    store(`${user.value}:result`, result)
  }

  async function sendPending(): Promise<Result | null> {
    if (completion) return completion
    const account = user.value
    const request = pending.value
    if (!request || !account || !online.value) return null
    completion = (async () => {
      await draftRequest
      try {
        const result = await api.createAssessment(request) as unknown as Result
        if (user.value === account) {
          pending.value = null
          store(`${account}:pending`, null)
          forgetDraft()
          recordResult(result)
          syncError.value = ''
          await refreshHome().catch(() => {})
        }
        return result
      } catch (error) {
        if (transient(error)) return null
        throw error
      }
    })()
    try { return await completion } finally { completion = undefined }
  }

  async function complete(answers: Record<string, unknown>): Promise<{ result: Result; queued: boolean }> {
    const current = draft.value
    const cfg = settings.value
    if (!current || !cfg) throw new Error('Нет черновика или настроек')
    const payload = pending.value ?? { client_uuid: current.client_uuid, filled_at: new Date().toISOString(), answers: snapshot(answers) }
    const calculated = localResult(payload, cfg)
    const account = user.value
    pending.value = payload
    const saved = store(`${account}:pending`, payload)
    clearTimeout(draftTimer)
    try {
      const result = await sendPending()
      if (result) return { result, queued: false }
      if (!saved) throw new Error('Не удалось сохранить запись на устройстве')
      recordResult(calculated)
      return { result: calculated, queued: true }
    } catch (error) {
      // Keep an unacknowledged request for a later retry using the same UUID.
      if ((error instanceof ApiError && error.status === 400) || !saved) {
        pending.value = null
        store(`${account}:pending`, null)
      }
      throw error
    }
  }

  async function synchronize() {
    if (!user.value || !online.value) return
    try {
      if (pending.value) {
        await refreshSettings().catch(() => {})
        await sendPending()
      } else await syncDraft()
    } catch (error) { syncError.value = messageFor(error) }
  }

  function resumePending() {
    const request = pending.value
    if (!request || !syncError.value || completion) return false
    pending.value = null
    store(`${user.value}:pending`, null)
    lastResult.value = null
    store(`${user.value}:result`, null)
    syncError.value = ''
    return true
  }

  async function logout() {
    const account = user.value
    clearTimeout(draftTimer)
    await draftRequest
    if (online.value && !pending.value) await syncDraft()
    if (online.value) await api.logout().catch(() => {})
    else tokens.clearTokens()
    for (const name of ['profile', 'home', 'sports', 'draft', 'pending', 'result']) store(`${account}:${name}`, null)
    user.value = null
    store('user', null)
    restore()
  }

  restore()
  window.addEventListener('offline', () => { online.value = false })
  window.addEventListener('online', () => {
    online.value = true
    void loadAccount()
  })
  void (user.value ? loadAccount() : refreshSettings().catch(() => {}))
  return { api, user, profile, home, sports, settings, draft, pending, lastResult, online, status, syncError, accountReady, enterAccount, loadAccount, refreshSettings, saveProfile, saveDraft, expireDraft: forgetDraft, complete, synchronize, resumePending, logout }
}
