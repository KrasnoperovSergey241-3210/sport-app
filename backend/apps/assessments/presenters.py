"""Преобразование записей в JSON для клиента. Тексты берутся из версии настроек, по которой запись обработана."""
from .scoring import BLOCKS, RECOVERY_SCALES, RESTQ_SCALES

BLOCK_TITLES = {
    "OS": "Общий стресс",
    "OV": "Общее восстановление",
    "SS": "Спортивный стресс",
    "SV": "Спортивное восстановление",
}


def restq_dict(res, with_answers=False):
    if res is None:
        return None
    scales = [
        {
            "no": no,
            "name": RESTQ_SCALES[no][0],
            "block": RESTQ_SCALES[no][1],
            "kind": "recovery" if no in RECOVERY_SCALES else "stress",
            "sum": res.scales[str(no)]["sum"],
            "mean": res.scales[str(no)]["mean"],
        }
        for no in sorted(RESTQ_SCALES)
    ]
    out = {
        "timing": res.timing,
        "scales": scales,
        "blocks": [{"code": b, "name": BLOCK_TITLES[b], "mean": res.blocks[b]} for b in BLOCKS],
        "total_stress": res.total_stress,
        "total_recovery": res.total_recovery,
        "balance": res.balance,
    }
    if with_answers:
        out["answers"] = res.answers
    return out


def result_dict(rec):
    """Экран результата (ТЗ п. 5.5): все тексты — с сервера."""
    t = rec.settings_version.data["texts"]
    out = {
        "urgent_message": t["urgent"] if rec.urgent else None,
        "summary": t["flag"] if rec.red_flag else t["ok"],
        "reasons_title": t["flag_reasons_title"] if rec.reasons else None,
        "reasons": [r["text"] for r in rec.reasons],
        "blood_pressure": {"sbp": rec.sbp, "dbp": rec.dbp, "pulse": rec.pulse} if rec.bp_measured else None,
        "kerdo": None,
        "restq_hints": t["restq_hints"] if rec.restq_filled else None,
        "disclaimer": t["disclaimer"],
        "next_due_date": rec.next_due_date,
    }
    if rec.kerdo_index is not None:
        k = t["kerdo"][rec.kerdo_class]
        out["kerdo"] = {"value": float(rec.kerdo_index), "class": rec.kerdo_class, "title": k["title"], "text": k["text"]}
    return out


def assessment_dict(rec, full=False):
    res = getattr(rec, "restq", None) if rec.restq_filled else None
    d = {
        "id": str(rec.id),
        "client_uuid": str(rec.client_uuid),
        "filled_at": rec.filled_at,
        "age": rec.age,
        "sport": rec.sport,
        "trainings_per_week": rec.trainings_per_week,
        "hours_per_week": float(rec.hours_per_week),
        "season_period": rec.season_period,
        "tolerance": rec.tolerance,
        "restq_filled": rec.restq_filled,
        "bp_measured": rec.bp_measured,
        "sbp": rec.sbp,
        "dbp": rec.dbp,
        "pulse": rec.pulse,
        "kerdo_index": None if rec.kerdo_index is None else float(rec.kerdo_index),
        "kerdo_class": rec.kerdo_class,
        "hrv": {
            "has_device": rec.hrv_has_device,
            "value": rec.hrv_value,
            "metric": rec.hrv_metric,
            "device": rec.hrv_device,
            "date": rec.hrv_date,
            "conditions": rec.hrv_conditions,
        },
        "red_flag": rec.red_flag,
        "urgent": rec.urgent,
        "reasons": rec.reasons,
        "next_due_date": rec.next_due_date,
        "settings_version": rec.settings_version.version,
        "restq": restq_dict(res, with_answers=full),
    }
    if full:
        d["answers"] = rec.answers
        d["result"] = result_dict(rec)
    return d
