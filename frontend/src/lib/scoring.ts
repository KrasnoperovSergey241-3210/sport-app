export type KerdoClass = "balance" | "sympathicotonia" | "vagotonia";

export interface BloodPressureInput {
  measured: boolean;
  sbp?: number;
  dbp?: number;
  pulse?: number;
}

export interface ReasonItem {
  code: string;
  text: string;
}

export interface EvaluationResult {
  redFlag: boolean;
  urgent: boolean;
  reasons: ReasonItem[];
}

export interface RestqScaleResult {
  scaleNo: number;
  name: string;
  block: "OS" | "OV" | "SS" | "SV";
  kind: "stress" | "recovery";
  sum: number;
  mean: number;
}

export interface RestqScoreResult {
  scales: Record<string, { sum: number; mean: number }>;
  scaleList: RestqScaleResult[];
  blocks: {
    OS: number;
    OV: number;
    SS: number;
    SV: number;
  };
  totalStress: number;
  totalRecovery: number;
  balance: number;
}

export interface SettingsConfig {
  thresholds: {
    tolerance_flag_max: number;
    sbp_max: number;
    dbp_max: number;
    kerdo_low: number;
    kerdo_high: number;
  };
  reminders: {
    normal_days: number;
    flag_days: number;
    offsets_days: number[];
    default_time: string;
  };
  texts: {
    reasons: Record<string, string>;
  };
}

export const YESNO_FLAG_QUESTIONS = [
  "2.2", "2.3", "2.4",
  "3.1", "3.2", "3.3", "3.4", "3.5",
  "4.1",
  "5.1", "5.2", "5.3", "5.4",
  "6.1", "6.2", "6.3",
] as const;

export function answerKey(qid: string): string {
  return "q" + qid.replace(".", "_");
}

function roundHalfUp(num: number, decimals: number): number {
  const factor = Math.pow(10, decimals);
  const sign = num < 0 ? -1 : 1;
  return sign * (Math.floor(Math.abs(num) * factor + 0.5) / factor);
}

function mean(values: number[]): number {
  if (!values.length) return 0;
  return values.reduce((acc, v) => acc + v, 0) / values.length;
}

export function kerdoIndex(dbp: number, pulse: number): number {
  if (pulse === 0) {
    throw new Error("ЧСС не может быть равна 0");
  }
  const raw = (1 - dbp / pulse) * 100;
  return roundHalfUp(raw, 1);
}

export function kerdoClass(value: number, low = -15, high = 15): KerdoClass {
  if (value > high) return "sympathicotonia";
  if (value < low) return "vagotonia";
  return "balance";
}

export function evaluateAssessment(
  answers: Record<string, unknown>,
  cfg: SettingsConfig
): EvaluationResult {
  const th = cfg.thresholds;
  const rs = cfg.texts.reasons;
  const reasons: ReasonItem[] = [];

  const tolerance = Number(answers["tolerance"]);
  if (tolerance <= th.tolerance_flag_max) {
    const tpl = rs["2.1"] ?? "Низкая оценка переносимости тренировочных нагрузок: {score} из 5";
    reasons.push({ code: "2.1", text: tpl.replace("{score}", String(tolerance)) });
  }

  for (const qid of YESNO_FLAG_QUESTIONS) {
    if (answers[answerKey(qid)] === true) {
      let text = rs[qid] ?? qid;
      if (qid === "3.3") {
        const rawDetails = Array.isArray(answers["q3_3_detail"])
          ? (answers["q3_3_detail"] as string[])
          : [];
        const details = rawDetails.map((d) => rs[`3.3.${d}`]).filter(Boolean);
        if (details.length > 0) {
          text = `${text}: ${details.join(", ")}`;
        }
      }
      reasons.push({ code: qid, text });
    }
  }

  const bp = (answers["bp"] as BloodPressureInput | undefined) ?? { measured: false };
  if (
    bp.measured &&
    bp.sbp !== undefined &&
    bp.dbp !== undefined &&
    (bp.sbp > th.sbp_max || bp.dbp > th.dbp_max)
  ) {
    const bpTpl =
      rs["bp"] ?? "Повышенное АД по данным измерения: {sbp}/{dbp} мм рт. ст.";
    reasons.push({
      code: "bp",
      text: bpTpl.replace("{sbp}", String(bp.sbp)).replace("{dbp}", String(bp.dbp)),
    });
  }

  const q33Detail = Array.isArray(answers["q3_3_detail"])
    ? (answers["q3_3_detail"] as string[])
    : [];
  const urgent = Boolean(
    answers["q3_5"] === true || (answers["q3_3"] === true && q33Detail.includes("syncope"))
  );

  return {
    redFlag: reasons.length > 0,
    urgent,
    reasons,
  };
}

export function nextDueDays(
  redFlag: boolean,
  urgent: boolean,
  cfg: SettingsConfig
): number {
  return redFlag || urgent ? cfg.reminders.flag_days : cfg.reminders.normal_days;
}

export const RESTQ_SCALES: Record<
  number,
  { name: string; block: "OS" | "OV" | "SS" | "SV"; kind: "stress" | "recovery"; items: readonly number[] }
> = {
  1: { name: "Общий стресс", block: "OS", kind: "stress", items: [22, 24, 30, 45] },
  2: { name: "Эмоциональный стресс", block: "OS", kind: "stress", items: [5, 8, 28, 37] },
  3: { name: "Социальный стресс", block: "OS", kind: "stress", items: [21, 26, 39, 48] },
  4: { name: "Конфликты/давление", block: "OS", kind: "stress", items: [12, 18, 32, 44] },
  5: { name: "Общая усталость", block: "OS", kind: "stress", items: [2, 16, 25, 35] },
  6: { name: "Нехватка энергии", block: "OS", kind: "stress", items: [4, 11, 31, 40] },
  7: { name: "Соматические жалобы", block: "OS", kind: "stress", items: [7, 15, 20, 42] },
  8: { name: "Успех", block: "OV", kind: "recovery", items: [3, 17, 41, 49] },
  9: { name: "Социальное восстановление", block: "OV", kind: "recovery", items: [6, 14, 23, 33] },
  10: { name: "Физическое восстановление", block: "SV", kind: "recovery", items: [9, 13, 29, 38] },
  11: { name: "Общее самочувствие", block: "OV", kind: "recovery", items: [10, 34, 43, 47] },
  12: { name: "Качество сна", block: "OV", kind: "recovery", items: [19, 27, 36, 46] },
  13: { name: "Качество перерывов", block: "SS", kind: "stress", items: [51, 58, 66, 72] },
  14: { name: "Эмоциональное выгорание", block: "SS", kind: "stress", items: [54, 63, 68, 76] },
  15: { name: "Подверженность травме", block: "SS", kind: "stress", items: [50, 57, 64, 73] },
  16: { name: "Спортивная форма", block: "SV", kind: "recovery", items: [53, 61, 69, 75] },
  17: { name: "Личные достижения", block: "SV", kind: "recovery", items: [55, 60, 70, 77] },
  18: { name: "Самоэффективность", block: "SV", kind: "recovery", items: [52, 59, 65, 71] },
  19: { name: "Саморегуляция", block: "SV", kind: "recovery", items: [56, 62, 67, 74] },
};

const REVERSED_ITEMS = new Set<number>([36, 46]);

const BLOCK_SCALES: Record<"OS" | "OV" | "SS" | "SV", readonly number[]> = {
  OS: [1, 2, 3, 4, 5, 6, 7],
  OV: [8, 9, 11, 12],
  SS: [13, 14, 15],
  SV: [10, 16, 17, 18, 19],
};

const STRESS_SCALES = [1, 2, 3, 4, 5, 6, 7, 13, 14, 15];
const RECOVERY_SCALES = [8, 9, 10, 11, 12, 16, 17, 18, 19];

export function scoreRestq(answers: Record<string | number, number>): RestqScoreResult {
  const normalized: Record<number, number> = {};
  for (let i = 1; i <= 77; i++) {
    const val = answers[i] ?? answers[String(i)];
    if (typeof val !== "number" || !Number.isInteger(val) || val < 0 || val > 6) {
      throw new Error(`Некорректное значение для утверждения ${i}: ожидается целое число 0..6`);
    }
    normalized[i] = REVERSED_ITEMS.has(i) ? 6 - val : val;
  }

  const rawMeans: Record<number, number> = {};
  const scales: Record<string, { sum: number; mean: number }> = {};
  const scaleList: RestqScaleResult[] = [];

  for (let no = 1; no <= 19; no++) {
    const meta = RESTQ_SCALES[no];
    const sum = meta.items.reduce((acc, itemNo) => acc + normalized[itemNo], 0);
    const exactMean = sum / 4;
    const roundedMean = roundHalfUp(exactMean, 2);
    rawMeans[no] = exactMean;
    scales[String(no)] = { sum, mean: roundedMean };
    scaleList.push({
      scaleNo: no,
      name: meta.name,
      block: meta.block,
      kind: meta.kind,
      sum,
      mean: roundedMean,
    });
  }

  const totalStressRaw = mean(STRESS_SCALES.map((no) => rawMeans[no]));
  const totalRecoveryRaw = mean(RECOVERY_SCALES.map((no) => rawMeans[no]));
  const balanceRaw = totalRecoveryRaw - totalStressRaw;

  return {
    scales,
    scaleList,
    blocks: {
      OS: roundHalfUp(mean(BLOCK_SCALES.OS.map((no) => rawMeans[no])), 2),
      OV: roundHalfUp(mean(BLOCK_SCALES.OV.map((no) => rawMeans[no])), 2),
      SS: roundHalfUp(mean(BLOCK_SCALES.SS.map((no) => rawMeans[no])), 2),
      SV: roundHalfUp(mean(BLOCK_SCALES.SV.map((no) => rawMeans[no])), 2),
    },
    totalStress: roundHalfUp(totalStressRaw, 2),
    totalRecovery: roundHalfUp(totalRecoveryRaw, 2),
    balance: roundHalfUp(balanceRaw, 2),
  };
}

export function ageOnDate(birthDateIso: string, onDateIso: string): number {
  const b = new Date(`${birthDateIso}T00:00:00Z`);
  const d = new Date(`${onDateIso}T00:00:00Z`);
  let age = d.getUTCFullYear() - b.getUTCFullYear();
  const monthDiff = d.getUTCMonth() - b.getUTCMonth();
  if (monthDiff < 0 || (monthDiff === 0 && d.getUTCDate() < b.getUTCDate())) {
    age -= 1;
  }
  return age;
}

export function experienceYears(currentAge: number, startAge: number | null | undefined): number | null {
  if (startAge === null || startAge === undefined) return null;
  return currentAge - startAge;
}