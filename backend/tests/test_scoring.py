"""Контрольные сценарии из раздела 9 ТЗ (чистая логика, без БД). Те же значения нужны Марвату и Артему."""
from datetime import date
from decimal import Decimal

import pytest

from apps.assessments import scoring as sc
from apps.core.default_settings import DEFAULT_SETTINGS as CFG
from apps.core.utils import age_on


def answers(**over):
    a = {"tolerance": 5, "bp": {"measured": False}}
    for q in sc.YESNO_FLAG_QUESTIONS:
        a[sc.answer_key(q)] = False
    a.update(over)
    return a


# --- сценарий 1 ---
def test_s1_all_ok():
    a = answers(bp={"measured": True, "sbp": 118, "dbp": 74, "pulse": 64})
    ev = sc.evaluate(a, CFG)
    assert not ev.red_flag and not ev.urgent and ev.reasons == []
    assert sc.kerdo_index(74, 64) == Decimal("-15.6")
    assert sc.kerdo_class(Decimal("-15.6")) == "vagotonia"
    assert sc.next_due_days(ev.red_flag, ev.urgent, CFG) == 30


# --- сценарий 2, 4 ---
def test_s2_motivation_flag_7_days():
    ev = sc.evaluate(answers(tolerance=4, q6_1=True), CFG)
    assert ev.red_flag and [r["text"] for r in ev.reasons] == ["Потеря мотивации"]
    assert sc.next_due_days(True, False, CFG) == 7


def test_s4_muscle_pain():
    ev = sc.evaluate(answers(tolerance=4, q2_3=True), CFG)
    assert [r["text"] for r in ev.reasons] == ["Долгая мышечная боль"]


# --- сценарий 3 ---
def test_s3_tolerance_3_is_flag():
    ev = sc.evaluate(answers(tolerance=3), CFG)
    assert ev.red_flag and ev.reasons[0]["code"] == "2.1"
    assert sc.evaluate(answers(tolerance=4), CFG).red_flag is False


# --- сценарии 5–7: индекс Кердо ---
@pytest.mark.parametrize(
    "dbp,hr,value,cls",
    [
        (70, 80, "12.5", "balance"),  # 5
        (60, 90, "33.3", "sympathicotonia"),  # 6
        (75, 88, "14.8", "balance"),  # 7а
        (69, 60, "-15.0", "balance"),  # 7б (граница)
        (70, 60, "-16.7", "vagotonia"),  # пример из п. 6.1
    ],
)
def test_kerdo(dbp, hr, value, cls):
    v = sc.kerdo_index(dbp, hr)
    assert v == Decimal(value) and sc.kerdo_class(v) == cls


# --- сценарий 8 ---
def test_s8_high_bp():
    ev = sc.evaluate(answers(bp={"measured": True, "sbp": 142, "dbp": 88, "pulse": 70}), CFG)
    assert ev.red_flag and ev.reasons[0]["text"] == "Повышенное АД по данным измерения: 142/88 мм рт. ст."
    assert sc.evaluate(answers(bp={"measured": True, "sbp": 135, "dbp": 90, "pulse": 70}), CFG).red_flag is False


# --- сценарии 9, 10 ---
def test_s9_chest_pain_urgent():
    ev = sc.evaluate(answers(q3_5=True), CFG)
    assert ev.urgent and ev.red_flag
    assert sc.next_due_days(ev.red_flag, ev.urgent, CFG) == 7


def test_s10_dizziness_not_urgent_but_syncope_is():
    ev = sc.evaluate(answers(q3_3=True, q3_3_detail=["dizziness"]), CFG)
    assert ev.red_flag and not ev.urgent
    assert sc.evaluate(answers(q3_3=True, q3_3_detail=["syncope", "dizziness"]), CFG).urgent


# --- сценарий 11 ---
def test_s11_illness_flag_only_while_current():
    assert sc.evaluate(answers(q4_1=True), CFG).red_flag
    assert not sc.evaluate(answers(q4_1=False), CFG).red_flag


# --- сценарий 12: шкала «Качество сна» ---
def test_s12_sleep_scale():
    a = {n: 0 for n in range(1, 78)}
    a.update({19: 3, 27: 2, 36: 2, 46: 6})
    s = sc.restq_score(a)["scales"]["12"]
    assert s["sum"] == 9 and s["mean"] == 2.25


# --- сценарий 13: итоговые показатели ---
def test_s13_totals():
    a = {n: 0 for n in range(1, 78)}
    for no, (_, _, items) in sc.RESTQ_SCALES.items():
        target = 2 if no in sc.STRESS_SCALES else None
        for i in items:
            if target is not None:
                a[i] = 2
            else:
                a[i] = 3 if i not in (36, 46) else 3  # 3 -> 3 при обратном счёте
    # шкалы восстановления: среднее 3,5 — по 3 и 4 поровну (сумма 14)
    for no in sc.RECOVERY_SCALES:
        items = sc.RESTQ_SCALES[no][2]
        vals = [3, 4, 3, 4]
        for i, v in zip(items, vals):
            a[i] = (6 - v) if i in sc.REVERSED else v
    r = sc.restq_score(a)
    assert r["blocks"] == {"OS": 2.0, "OV": 3.5, "SS": 2.0, "SV": 3.5}
    assert (r["total_stress"], r["total_recovery"], r["balance"]) == (2.0, 3.5, 1.5)


def test_restq_validation():
    with pytest.raises(ValueError):
        sc.restq_score({n: 0 for n in range(1, 77)})  # 76 ответов
    with pytest.raises(ValueError):
        sc.restq_score({**{n: 0 for n in range(1, 78)}, 5: 7})


# --- 6.3 возраст ---
def test_age():
    assert age_on(date(2000, 11, 21), date(2026, 11, 20)) == 25
    assert age_on(date(2000, 11, 21), date(2026, 11, 21)) == 26
    assert age_on(date(2008, 11, 22), date(2026, 11, 21)) == 17  # сценарий 14: младше 18


def test_s18_push_text_has_no_medical_info():
    body = CFG["texts"]["push_body"].lower()
    assert body == "пора пройти самооценку состояния"
    assert not any(w in body for w in ("флаг", "врач", "давлен", "боль", "индекс", "restq"))
