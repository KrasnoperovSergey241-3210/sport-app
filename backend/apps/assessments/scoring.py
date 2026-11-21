"""Расчёты по ТЗ (раздел 5.5, 6.1–6.3). Чистый Python без Django.

Тот же алгоритм и те же тестовые значения (tests/test_scoring.py, сценарии из раздела 9 ТЗ)
должны быть в клиентском TypeScript-модуле Марвата: клиент считает офлайн, сервер перепроверяет.
Округление — «half up» (0,5 -> вверх по модулю), на Decimal, без ошибок float.
"""
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

Q1 = Decimal("0.1")
Q2 = Decimal("0.01")


def rnd(x: Decimal, q: Decimal) -> Decimal:
    return x.quantize(q, rounding=ROUND_HALF_UP)


# ---------- 6.1 Индекс Кердо ----------
def kerdo_index(dbp: int, pulse: int) -> Decimal:
    """ВИ = (1 − ДАД / ЧСС) × 100, один знак после запятой."""
    return rnd((Decimal(1) - Decimal(dbp) / Decimal(pulse)) * 100, Q1)


def kerdo_class(value: Decimal, low=-15, high=15) -> str:
    """По округлённому значению; ровно −15,0 и +15,0 — равновесие."""
    if value > Decimal(str(high)):
        return "sympathicotonia"
    if value < Decimal(str(low)):
        return "vagotonia"
    return "balance"


# ---------- 5.5 Красные флаги ----------
YESNO_FLAG_QUESTIONS = [
    "2.2", "2.3", "2.4",
    "3.1", "3.2", "3.3", "3.4", "3.5",
    "4.1",
    "5.1", "5.2", "5.3", "5.4",
    "6.1", "6.2", "6.3",
]


def answer_key(qid: str) -> str:
    return "q" + qid.replace(".", "_")


@dataclass
class Evaluation:
    red_flag: bool = False
    urgent: bool = False
    reasons: list = field(default_factory=list)  # [{"code": "6.1", "text": "Потеря мотивации"}]


def evaluate(answers: dict, cfg: dict) -> Evaluation:
    """Красные флаги и срочное сообщение. `cfg` — действующая версия настроек (JSON)."""
    th, rs = cfg["thresholds"], cfg["texts"]["reasons"]
    ev = Evaluation()

    if answers["tolerance"] <= th["tolerance_flag_max"]:
        ev.reasons.append({"code": "2.1", "text": rs["2.1"].format(score=answers["tolerance"])})

    for qid in YESNO_FLAG_QUESTIONS:
        if answers.get(answer_key(qid)) is True:
            text = rs[qid]
            if qid == "3.3":
                det = [rs["3.3." + d] for d in answers.get("q3_3_detail", [])]
                if det:
                    text = f"{text}: {', '.join(det)}"
            ev.reasons.append({"code": qid, "text": text})

    bp = answers.get("bp") or {}
    if bp.get("measured") and (bp["sbp"] > th["sbp_max"] or bp["dbp"] > th["dbp_max"]):
        ev.reasons.append({"code": "bp", "text": rs["bp"].format(sbp=bp["sbp"], dbp=bp["dbp"])})

    ev.red_flag = bool(ev.reasons)
    ev.urgent = bool(answers.get("q3_5") is True or (answers.get("q3_3") is True and "syncope" in answers.get("q3_3_detail", [])))
    return ev


def next_due_days(red_flag: bool, urgent: bool, cfg: dict) -> int:
    r = cfg["reminders"]
    return r["flag_days"] if (red_flag or urgent) else r["normal_days"]


# ---------- 6.2 RESTQ-Sport 76 ----------
RESTQ_SCALES = {
    1: ("Общий стресс", "OS", (22, 24, 30, 45)),
    2: ("Эмоциональный стресс", "OS", (5, 8, 28, 37)),
    3: ("Социальный стресс", "OS", (21, 26, 39, 48)),
    4: ("Конфликты/давление", "OS", (12, 18, 32, 44)),
    5: ("Общая усталость", "OS", (2, 16, 25, 35)),
    6: ("Нехватка энергии", "OS", (4, 11, 31, 40)),
    7: ("Соматические жалобы", "OS", (7, 15, 20, 42)),
    8: ("Успех", "OV", (3, 17, 41, 49)),
    9: ("Социальное восстановление", "OV", (6, 14, 23, 33)),
    10: ("Физическое восстановление", "SV", (9, 13, 29, 38)),
    11: ("Общее самочувствие", "OV", (10, 34, 43, 47)),
    12: ("Качество сна", "OV", (19, 27, 36, 46)),
    13: ("Качество перерывов", "SS", (51, 58, 66, 72)),
    14: ("Эмоциональное выгорание", "SS", (54, 63, 68, 76)),
    15: ("Подверженность травме", "SS", (50, 57, 64, 73)),
    16: ("Спортивная форма", "SV", (53, 61, 69, 75)),
    17: ("Личные достижения", "SV", (55, 60, 70, 77)),
    18: ("Самоэффективность", "SV", (52, 59, 65, 71)),
    19: ("Саморегуляция", "SV", (56, 62, 67, 74)),
}
REVERSED = {36, 46}
BLOCKS = {
    "OS": [1, 2, 3, 4, 5, 6, 7],
    "OV": [8, 9, 11, 12],
    "SS": [13, 14, 15],
    "SV": [10, 16, 17, 18, 19],
}
STRESS_SCALES = [1, 2, 3, 4, 5, 6, 7, 13, 14, 15]
RECOVERY_SCALES = [8, 9, 10, 11, 12, 16, 17, 18, 19]
RESTQ_ITEMS = 77


def _mean(values) -> Decimal:
    return sum(values, Decimal(0)) / Decimal(len(values))


def restq_score(answers: dict) -> dict:
    """answers: {номер утверждения 1..77: балл 0..6} (ключи int или str). Утверждение 1 не оценивается."""
    a = {int(k): int(v) for k, v in answers.items()}
    if sorted(a) != list(range(1, RESTQ_ITEMS + 1)) or any(not 0 <= v <= 6 for v in a.values()):
        raise ValueError("Нужны ответы 0–6 на все 77 утверждений")
    a = {n: (6 - v if n in REVERSED else v) for n, v in a.items()}

    sums, means = {}, {}
    for no, (_, _, items) in RESTQ_SCALES.items():
        sums[no] = sum(a[i] for i in items)
        means[no] = Decimal(sums[no]) / Decimal(4)

    blocks = {b: _mean([means[s] for s in scales]) for b, scales in BLOCKS.items()}
    stress = _mean([means[s] for s in STRESS_SCALES])
    recovery = _mean([means[s] for s in RECOVERY_SCALES])
    balance = recovery - stress

    return {
        "scales": {str(no): {"sum": sums[no], "mean": float(rnd(means[no], Q2))} for no in RESTQ_SCALES},
        "blocks": {b: float(rnd(v, Q2)) for b, v in blocks.items()},
        "total_stress": float(rnd(stress, Q2)),
        "total_recovery": float(rnd(recovery, Q2)),
        "balance": float(rnd(balance, Q2)),
    }
