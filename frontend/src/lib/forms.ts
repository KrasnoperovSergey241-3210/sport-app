import type { ProfilePayload } from '../api/client'
import { ageOnDate, answerKey, type SettingsConfig } from './scoring'

export type Season = NonNullable<ProfilePayload['season_period']>
export const seasons: Record<Season, string> = {
  rest: 'Отдых', preparation: 'Подготовка к сезону', camp: 'Сборы', competition: 'Период соревнований',
}

export const steps = [
  { title: 'Тренировочный режим', short: 'Нагрузка', note: 'Подтвердите текущий период сезона и объём тренировок.' },
  { title: 'Переносимость нагрузки', short: 'Переносимость', note: 'Оцените, как вы переносите тренировки.' },
  { title: 'Сердце и сосуды', short: 'Сердце', note: 'Отметьте симптомы, которые у вас были.' },
  { title: 'Недавние заболевания', short: 'Заболевания', note: 'Укажите, болели ли вы за последний месяц.' },
  { title: 'Сон и самочувствие', short: 'Самочувствие', note: 'Вспомните, что изменилось по сравнению с вашим обычным состоянием.' },
  { title: 'Настроение и мотивация', short: 'Настроение', note: 'Отметьте изменения в настроении и отношении к тренировкам.' },
  { title: 'Давление и пульс', short: 'Давление', note: 'Если вы измерили давление и пульс в покое, запишите значения.' },
  { title: 'Вариабельность ритма сердца', short: 'ВРС', note: 'Если вы пользуетесь устройством для измерения ВРС, добавьте его показания.' },
]

export const questions: Record<number, { id: string; text: string }[]> = {
  2: [
    { id: '2.2', text: 'Заметили ли вы снижение работоспособности на тренировках?' },
    { id: '2.3', text: 'Держится ли мышечная боль дольше обычного?' },
    { id: '2.4', text: 'Чувствуете ли вы усталость, которая сохраняется после отдыха?' },
  ],
  3: [
    { id: '3.1', text: 'Ощущали ли вы перебои в работе сердца?' },
    { id: '3.2', text: 'Ощущали ли вы учащённое сердцебиение?' },
    { id: '3.3', text: 'Были ли у вас обморок или головокружение?' },
    { id: '3.4', text: 'Повышалось ли ваше давление в покое выше {bp} мм рт. ст.?' },
    { id: '3.5', text: 'Возникала ли у вас боль в груди?' },
  ],
  4: [{ id: '4.1', text: 'Болели ли вы за последний месяц?' }],
  5: [
    { id: '5.1', text: 'Утренний пульс стал выше обычного?' },
    { id: '5.2', text: 'Ухудшился ли ваш сон?' },
    { id: '5.3', text: 'Изменились ли ваш аппетит или вес?' },
    { id: '5.4', text: 'Замечали ли вы, что стали хуже переносить жару или холод?' },
  ],
  6: [
    { id: '6.1', text: 'Снизилась ли у вас мотивация к тренировкам?' },
    { id: '6.2', text: 'Стали ли вы чаще испытывать раздражение или тревогу?' },
    { id: '6.3', text: 'Испытывали ли вы апатию или подавленность?' },
  ],
}

export const symptoms = { fever: 'Температура', throat: 'Боль в горле', runny_nose: 'Насморк', cough: 'Кашель', other: 'Другое' }
export const syncopeDetails = { syncope: 'Обморок', dizziness: 'Головокружение' }
export const hrvMetrics = { rmssd: 'RMSSD', sdnn: 'SDNN', unknown: 'Показатель неизвестен' }
export const hrvConditions = { morning: 'Утром', night: 'Ночью', other: 'Другое' }
export const illnessFrequency = { none: 'Ни разу', once: 'Один раз', twice_plus: 'Два раза или больше' }

export interface RestqAnswers {
  timing: 'before' | 'after'
  answers: Record<string, number>
}

export interface Answers {
  [key: string]: unknown
  [key: `comment_${number}`]: string | undefined
  season_period?: Season
  trainings_per_week?: number | string
  hours_per_week?: number | string
  tolerance?: number
  q3_3_detail: string[]
  q4_2: string[]
  q4_2_other?: string
  q4_3?: number | string
  q4_4?: string
  morning_pulse_today?: number | string
  morning_pulse_usual?: number | string
  bp: { measured?: boolean; sbp?: number | string; dbp?: number | string; pulse?: number | string }
  hrv: { has_device?: boolean; value?: number | string; metric?: string; device?: string; date?: string; conditions?: string }
  restq?: RestqAnswers | null
}

export function initialAnswers(profile: ProfilePayload, previous?: Partial<Answers>): Answers {
  return {
    season_period: profile.season_period || undefined,
    trainings_per_week: profile.trainings_per_week ?? undefined,
    hours_per_week: profile.hours_per_week ?? undefined,
    ...previous,
    q3_3_detail: previous?.q3_3_detail ?? [], q4_2: previous?.q4_2 ?? [],
    bp: previous?.bp ?? {}, hrv: previous?.hrv ?? {},
  }
}

export function dateKey(date = new Date()): string {
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

export function formatDate(value: string, year = false): string {
  const date = new Date(value.length === 10 ? `${value}T12:00:00` : value)
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', ...(year ? { year: 'numeric' } : {}) }).format(date)
}

export function profileIdentity(firstName?: string, lastName?: string) {
  const names = [firstName?.trim(), lastName?.trim()].filter((name): name is string => Boolean(name))
  return {
    name: names.join(' '),
    initials: names.map((name) => Array.from(name)[0]).join('').toLocaleUpperCase('ru-RU'),
  }
}

export function numberIn(value: unknown, low: number, high: number, step?: number): boolean {
  if ((typeof value !== 'number' && typeof value !== 'string') || value === '') return false
  const number = Number(value)
  return Number.isFinite(number) && number >= low && number <= high && (step === undefined || Number.isInteger(number / step))
}

export function validateLoad(season: Season | '', trainings: unknown, hours: unknown): string {
  if (!season || !(season in seasons)) return 'Выберите период сезона.'
  if (!numberIn(trainings, 0, 21, 1)) return 'Укажите от 0 до 21 тренировки в неделю.'
  if (!numberIn(hours, 0, 60, .5)) return 'Укажите от 0 до 60 часов с шагом 0,5.'
  return ''
}

export function validateProfile(profile: ProfilePayload): string {
  if (!profile.first_name?.trim() || !profile.last_name?.trim()) return 'Введите имя и фамилию.'
  if (!profile.sex) return 'Укажите пол.'
  if (!profile.birth_date || ageOnDate(profile.birth_date, dateKey()) < 18) return 'Укажите дату рождения. Приложение доступно с 18 лет.'
  if (!profile.sport && !profile.sport_custom?.trim()) return 'Выберите вид спорта или впишите свой.'
  const maxAge = Math.min(ageOnDate(profile.birth_date, dateKey()), 100)
  if (!numberIn(profile.start_age_any, 0, maxAge, 1) || !numberIn(profile.start_age_sport, Number(profile.start_age_any), maxAge, 1)) {
    return 'Проверьте возраст начала занятий. Начало занятий выбранным видом спорта должно быть не раньше начала занятий спортом.'
  }
  return validateLoad(profile.season_period ?? '', profile.trainings_per_week, profile.hours_per_week)
}

export function validateStep(step: number, a: Answers): string {
  if (step === 1) return validateLoad(a.season_period ?? '', a.trainings_per_week, a.hours_per_week)
  if (step === 2 && !numberIn(a.tolerance, 1, 5, 1)) return 'Выберите оценку от 1 до 5.'
  if (questions[step]?.some(({ id }) => typeof a[answerKey(id)] !== 'boolean')) return 'Ответьте на все вопросы раздела.'
  if (step === 3 && a.q3_3 && !a.q3_3_detail.length) return 'Уточните, был ли обморок, головокружение или оба симптома.'
  if (step === 4) {
    if (a.q4_1 && !a.q4_2.length) return 'Выберите хотя бы один симптом.'
    if (a.q4_2.includes('other') && a.q4_1 && !a.q4_2_other?.trim()) return 'Опишите другой симптом.'
    if (a.q4_1 && !numberIn(a.q4_3, 1, 4, 1)) return 'Укажите, сколько недель назад вы болели.'
    if (!a.q4_4) return 'Укажите частоту заболеваний.'
  }
  if (step === 5) {
    for (const value of [a.morning_pulse_today, a.morning_pulse_usual]) {
      if (value !== undefined && value !== '' && !numberIn(value, 30, 200, 1)) return 'Допустимое значение пульса — от 30 до 200 уд/мин.'
    }
  }
  if (step === 7) {
    if (a.bp.measured === undefined) return 'Укажите, измеряли ли вы давление и пульс.'
    if (a.bp.measured) {
      if (!numberIn(a.bp.sbp, 60, 250, 1) || !numberIn(a.bp.dbp, 40, 150, 1) || !numberIn(a.bp.pulse, 30, 200, 1)) return 'Проверьте значения давления и пульса.'
      if (Number(a.bp.sbp) <= Number(a.bp.dbp)) return 'Верхнее давление должно быть выше нижнего.'
    }
  }
  if (step === 8) {
    if (a.hrv.has_device === undefined) return 'Укажите, есть ли данные ВРС.'
    if (a.hrv.has_device && (!numberIn(a.hrv.value, 5, 300) || !a.hrv.metric || !a.hrv.conditions)) return 'Введите ВРС от 5 до 300 мс, выберите показатель и условия измерения.'
  }
  return ''
}

export function needsRestq(answers: Answers, settings: SettingsConfig): boolean {
  return answers.tolerance !== undefined && answers.tolerance <= settings.thresholds.tolerance_flag_max && !answers.restq
}

export function submissionAnswers(a: Answers): Record<string, unknown> {
  const result: Record<string, unknown> = { ...a, trainings_per_week: Number(a.trainings_per_week), hours_per_week: Number(a.hours_per_week) }
  if (!a.q3_3) delete result.q3_3_detail
  if (!a.q4_1) {
    delete result.q4_2
    delete result.q4_3
  }
  if (!a.q4_1 || !a.q4_2.includes('other')) delete result.q4_2_other
  for (const key of ['morning_pulse_today', 'morning_pulse_usual']) {
    result[key] = a[key] === '' || a[key] === undefined ? null : Number(a[key])
  }
  result.bp = a.bp.measured ? { measured: true, sbp: Number(a.bp.sbp), dbp: Number(a.bp.dbp), pulse: Number(a.bp.pulse) } : { measured: false }
  result.hrv = a.hrv.has_device
    ? { has_device: true, value: Number(a.hrv.value), metric: a.hrv.metric, conditions: a.hrv.conditions, device: a.hrv.device, date: a.hrv.date || undefined }
    : { has_device: false }
  return result
}
