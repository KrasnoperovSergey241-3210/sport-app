"""Роутер БД: приложение `pii` (ФИО, контакты) живёт в отдельной базе `pii`.

Между базами нет внешних ключей: связь медицинских данных с ПДн — только через
внутренний код пользователя (UUID, поле `code`). См. ТЗ, раздел 7 «Разделение данных».
"""

PII_APPS = {"pii"}


class PiiRouter:
    def db_for_read(self, model, **hints):
        return "pii" if model._meta.app_label in PII_APPS else None

    db_for_write = db_for_read

    def allow_relation(self, obj1, obj2, **hints):
        return (obj1._meta.app_label in PII_APPS) == (obj2._meta.app_label in PII_APPS)

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in PII_APPS:
            return db == "pii"
        return db == "default"
