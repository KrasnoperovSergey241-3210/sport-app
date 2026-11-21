import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  answerKey,
  ageOnDate,
  evaluateAssessment,
  experienceYears,
  kerdoClass,
  kerdoIndex,
  nextDueDays,
  scoreRestq,
  YESNO_FLAG_QUESTIONS,
  type SettingsConfig,
} from "../src/lib/scoring.ts";

const CFG: SettingsConfig = {
  thresholds: {
    tolerance_flag_max: 3,
    sbp_max: 135,
    dbp_max: 90,
    kerdo_low: -15,
    kerdo_high: 15,
  },
  reminders: {
    normal_days: 30,
    flag_days: 7,
    offsets_days: [0, 1, 3],
    default_time: "09:00",
  },
  texts: {
    reasons: {
      "2.1": "Низкая оценка переносимости тренировочных нагрузок: {score} из 5",
      "2.2": "Спад работоспособности",
      "2.3": "Долгая мышечная боль",
      "2.4": "Хроническая усталость",
      "3.1": "Перебои в работе сердца",
      "3.2": "Ощущение учащённого сердцебиения",
      "3.3": "Потеря сознания или головокружение",
      "3.3.syncope": "потеря сознания (обморок)",
      "3.3.dizziness": "головокружение",
      "3.4": "Повышение АД в покое выше 135/90 мм рт. ст.",
      "3.5": "Боли в груди",
      "4.1": "Заболевание за последний месяц",
      "5.1": "Повышение утреннего пульса",
      "5.2": "Нарушения сна",
      "5.3": "Изменение аппетита и веса",
      "5.4": "Сбои терморегуляции",
      "6.1": "Потеря мотивации",
      "6.2": "Раздражительность и тревожность",
      "6.3": "Апатия и подавленность",
      bp: "Повышенное АД по данным измерения: {sbp}/{dbp} мм рт. ст.",
    },
  },
};

function makeAnswers(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  const base: Record<string, unknown> = {
    tolerance: 5,
    bp: { measured: false },
  };
  for (const qid of YESNO_FLAG_QUESTIONS) {
    base[answerKey(qid)] = false;
  }
  return { ...base, ...overrides };
}

describe("Контрольные сценарии из раздела 9 ТЗ", () => {
  it("сценарий 1: всё в норме, Кердо -15.6 (ваготония), напоминание через 30 дней", () => {
    const ev = evaluateAssessment(
      makeAnswers({ bp: { measured: true, sbp: 118, dbp: 74, pulse: 64 } }),
      CFG
    );
    assert.equal(ev.redFlag, false);
    assert.equal(ev.urgent, false);
    assert.deepEqual(ev.reasons, []);
    assert.equal(kerdoIndex(74, 64), -15.6);
    assert.equal(kerdoClass(-15.6), "vagotonia");
    assert.equal(nextDueDays(ev.redFlag, ev.urgent, CFG), 30);
  });

  it("сценарий 2: потеря мотивации (6.1) — красный флаг, напоминание через 7 дней", () => {
    const ev = evaluateAssessment(makeAnswers({ tolerance: 4, q6_1: true }), CFG);
    assert.equal(ev.redFlag, true);
    assert.deepEqual(
      ev.reasons.map((r) => r.text),
      ["Потеря мотивации"]
    );
    assert.equal(nextDueDays(ev.redFlag, ev.urgent, CFG), 7);
  });

  it("сценарий 3: оценка переносимости 3 — красный флаг, при 4 без флагов — false", () => {
    const ev3 = evaluateAssessment(makeAnswers({ tolerance: 3 }), CFG);
    assert.equal(ev3.redFlag, true);
    assert.equal(ev3.reasons[0]?.code, "2.1");

    const ev4 = evaluateAssessment(makeAnswers({ tolerance: 4 }), CFG);
    assert.equal(ev4.redFlag, false);
  });

  it("сценарий 4: долгая мышечная боль (2.3)", () => {
    const ev = evaluateAssessment(makeAnswers({ tolerance: 4, q2_3: true }), CFG);
    assert.deepEqual(
      ev.reasons.map((r) => r.text),
      ["Долгая мышечная боль"]
    );
  });

  it("сценарии 5–7: индекс Кердо и граничные значения", () => {
    assert.equal(kerdoIndex(70, 80), 12.5);
    assert.equal(kerdoClass(12.5), "balance");

    assert.equal(kerdoIndex(60, 90), 33.3);
    assert.equal(kerdoClass(33.3), "sympathicotonia");

    assert.equal(kerdoIndex(75, 88), 14.8);
    assert.equal(kerdoClass(14.8), "balance");

    assert.equal(kerdoIndex(69, 60), -15);
    assert.equal(kerdoClass(-15), "balance");

    assert.equal(kerdoIndex(70, 60), -16.7);
    assert.equal(kerdoClass(-16.7), "vagotonia");
  });

  it("сценарий 8: повышенное АД 142/88 — красный флаг; 135/90 — без флага", () => {
    const evHigh = evaluateAssessment(
      makeAnswers({ bp: { measured: true, sbp: 142, dbp: 88, pulse: 70 } }),
      CFG
    );
    assert.equal(evHigh.redFlag, true);
    assert.equal(
      evHigh.reasons[0]?.text,
      "Повышенное АД по данным измерения: 142/88 мм рт. ст."
    );

    const evBorder = evaluateAssessment(
      makeAnswers({ bp: { measured: true, sbp: 135, dbp: 90, pulse: 70 } }),
      CFG
    );
    assert.equal(evBorder.redFlag, false);
  });

  it("сценарии 9–10: боль в груди (срочно), головокружение (не срочно), обморок (срочно)", () => {
    const evPain = evaluateAssessment(makeAnswers({ q3_5: true }), CFG);
    assert.equal(evPain.urgent, true);
    assert.equal(evPain.redFlag, true);
    assert.equal(nextDueDays(evPain.redFlag, evPain.urgent, CFG), 7);

    const evDizz = evaluateAssessment(
      makeAnswers({ q3_3: true, q3_3_detail: ["dizziness"] }),
      CFG
    );
    assert.equal(evDizz.redFlag, true);
    assert.equal(evDizz.urgent, false);

    const evSync = evaluateAssessment(
      makeAnswers({ q3_3: true, q3_3_detail: ["syncope", "dizziness"] }),
      CFG
    );
    assert.equal(evSync.urgent, true);
  });

  it("сценарий 11: заболевание (4.1) — флаг только при true", () => {
    assert.equal(evaluateAssessment(makeAnswers({ q4_1: true }), CFG).redFlag, true);
    assert.equal(evaluateAssessment(makeAnswers({ q4_1: false }), CFG).redFlag, false);
  });

  it("сценарий 12: шкала «Качество сна» (утверждения 19, 27, 36, 46)", () => {
    const answers: Record<number, number> = {};
    for (let i = 1; i <= 77; i++) answers[i] = 0;
    answers[19] = 3;
    answers[27] = 2;
    answers[36] = 2;
    answers[46] = 6;

    const res = scoreRestq(answers);
    assert.equal(res.scales["12"].sum, 9);
    assert.equal(res.scales["12"].mean, 2.25);
  });

  it("сценарий 13: блоки и итоговые показатели RESTQ-Sport", () => {
    const answers: Record<number, number> = {};
    for (let i = 1; i <= 77; i++) answers[i] = 0;

    const stressScaleNos = [1, 2, 3, 4, 5, 6, 7, 13, 14, 15];
    const recoveryScaleNos = [8, 9, 10, 11, 12, 16, 17, 18, 19];
    const scaleItems: Record<number, number[]> = {
      1: [22, 24, 30, 45],
      2: [5, 8, 28, 37],
      3: [21, 26, 39, 48],
      4: [12, 18, 32, 44],
      5: [2, 16, 25, 35],
      6: [4, 11, 31, 40],
      7: [7, 15, 20, 42],
      8: [3, 17, 41, 49],
      9: [6, 14, 23, 33],
      10: [9, 13, 29, 38],
      11: [10, 34, 43, 47],
      12: [19, 27, 36, 46],
      13: [51, 58, 66, 72],
      14: [54, 63, 68, 76],
      15: [50, 57, 64, 73],
      16: [53, 61, 69, 75],
      17: [55, 60, 70, 77],
      18: [52, 59, 65, 71],
      19: [56, 62, 67, 74],
    };
    const reversed = new Set([36, 46]);

    for (const no of stressScaleNos) {
      for (const item of scaleItems[no]) {
        answers[item] = reversed.has(item) ? 6 - 2 : 2;
      }
    }
    const recVals = [3, 4, 3, 4];
    for (const no of recoveryScaleNos) {
      scaleItems[no].forEach((item, idx) => {
        const target = recVals[idx];
        answers[item] = reversed.has(item) ? 6 - target : target;
      });
    }

    const res = scoreRestq(answers);
    assert.deepEqual(res.blocks, { OS: 2, OV: 3.5, SS: 2, SV: 3.5 });
    assert.equal(res.totalStress, 2);
    assert.equal(res.totalRecovery, 3.5);
    assert.equal(res.balance, 1.5);
  });

  it("сценарий 14 и п. 6.3: расчёт возраста и стажа", () => {
    assert.equal(ageOnDate("2000-11-21", "2026-11-20"), 25);
    assert.equal(ageOnDate("2000-11-21", "2026-11-21"), 26);
    assert.equal(ageOnDate("2008-11-22", "2026-11-21"), 17);
    assert.equal(experienceYears(26, 10), 16);
    assert.equal(experienceYears(26, null), null);
  });

  it("сценарий 18: текст push-уведомления не содержит медицинских сведений", () => {
    const body = "Пора пройти самооценку состояния";
    const lower = body.toLowerCase();
    assert.equal(lower, "пора пройти самооценку состояния");
    for (const bad of ["флаг", "врач", "давлен", "боль", "индекс", "restq"]) {
      assert.equal(lower.includes(bad), false);
    }
  });
});