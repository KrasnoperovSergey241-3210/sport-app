"""Загрузка справочника видов спорта «как есть» из .csv или .xlsx (Приложение В).

    python manage.py import_sports                       # встроенный apps/profiles/data/sports.csv
    python manage.py import_sports путь/к/файлу.xlsx
Повторный запуск обновляет записи по номеру (столбец №), ничего не дублируя.
"""
import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.profiles.models import Sport

DEFAULT = Path(__file__).resolve().parents[2] / "data" / "sports.csv"


def read_rows(path: Path):
    if path.suffix.lower() == ".csv":
        with open(path, encoding="utf-8-sig", newline="") as f:
            return list(csv.reader(f))[1:]
    from openpyxl import load_workbook

    ws = load_workbook(path, read_only=True, data_only=True).active
    return [[("" if c is None else str(c)) for c in row] for row in ws.iter_rows(min_row=2, values_only=True)]


class Command(BaseCommand):
    help = "Загрузить справочник видов спорта"

    def add_arguments(self, parser):
        parser.add_argument("path", nargs="?", default=str(DEFAULT))

    def handle(self, *args, **opts):
        path = Path(opts["path"])
        if not path.exists():
            raise CommandError(f"Файл не найден: {path}")
        created = updated = 0
        for row in read_rows(path):
            if len(row) < 6 or not str(row[1]).strip():
                continue
            no = int(float(row[0])) if str(row[0]).strip() else None
            vals = dict(
                name=" ".join(str(row[1]).split()),
                type_esc=str(row[2]).strip(),
                intensity_esc=str(row[3]).strip(),
                static_mitchell=str(row[4]).strip(),
                dynamic_mitchell=str(row[5]).strip(),
            )
            _, was_created = Sport.objects.update_or_create(ext_no=no, defaults=vals)
            created += was_created
            updated += not was_created
        self.stdout.write(self.style.SUCCESS(f"Видов спорта: создано {created}, обновлено {updated}"))
