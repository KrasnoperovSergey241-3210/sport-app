from datetime import date


def age_on(birth: date, on: date) -> int:
    """Полных лет на дату `on` (ТЗ п. 6.3)."""
    return on.year - birth.year - ((on.month, on.day) < (birth.month, birth.day))


def jsonable(obj):
    """Привести данные (Decimal, date, OrderedDict) к виду, пригодному для JSONField."""
    import json
    from datetime import date as _date
    from datetime import datetime as _dt
    from decimal import Decimal

    def default(o):
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, (_date, _dt)):
            return o.isoformat()
        raise TypeError(f"Нельзя сериализовать {type(o)}")

    return json.loads(json.dumps(obj, default=default))
