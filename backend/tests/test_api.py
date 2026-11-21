import uuid
from datetime import date, timedelta

import pytest
from django.core.exceptions import PermissionDenied
from django.db import connections
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.assessments.models import SelfAssessment
from apps.assessments.scoring import YESNO_FLAG_QUESTIONS, answer_key
from apps.pii.models import Identity
from apps.profiles.models import Sport

pytestmark = pytest.mark.django_db(databases=["default", "pii"], transaction=True)
PASSWORD = "Str0ng-pass-123"


@pytest.fixture
def athlete():
    c = APIClient()
    email = f"a{uuid.uuid4().hex[:8]}@example.com"
    r = c.post("/api/auth/register/start/", {"contact": email, "birth_date": "1998-05-10", "consent": True}, format="json")
    r = c.post("/api/auth/register/verify/", {"contact": email, "code": r.data["debug_code"], "password": PASSWORD}, format="json")
    assert r.status_code == 201, r.data
    c.credentials(HTTP_AUTHORIZATION="Bearer " + r.data["access"])
    c.email = email
    sport = Sport.objects.create(name="Плавание", type_esc="выносливость", intensity_esc="высокой интенсивности",
                                 static_mitchell="низкая", dynamic_mitchell="высокая")
    r = c.put("/api/profile/", {
        "last_name": "Иванов", "first_name": "Иван", "sex": "male", "sport": sport.id,
        "start_age_any": 8, "start_age_sport": 10, "trainings_per_week": 6, "hours_per_week": "12.5",
    }, format="json")
    assert r.status_code == 200, r.data
    return c


def answers(**over):
    a = {
        "season_period": "preparation", "trainings_per_week": 6, "hours_per_week": 12.5, "tolerance": 5,
        "q4_4": "none", "bp": {"measured": True, "sbp": 118, "dbp": 74, "pulse": 64}, "hrv": {"has_device": False},
    }
    for q in YESNO_FLAG_QUESTIONS:
        a[answer_key(q)] = False
    a.update(over)
    return a


def post_assessment(c, **over):
    return c.post("/api/assessments/", {"client_uuid": str(uuid.uuid4()), "answers": answers(**over)}, format="json")


def test_s14_under_18_rejected():
    c = APIClient()
    young = (date.today() - timedelta(days=365 * 17)).isoformat()
    r = c.post("/api/auth/register/start/", {"contact": "kid@example.com", "birth_date": young, "consent": True}, format="json")
    assert r.status_code == 400 and r.data["code"] == "age_restriction"
    assert r.data["detail"] == "Приложение предназначено для спортсменов 18 лет и старше"


def test_consent_required():
    r = APIClient().post("/api/auth/register/start/", {"contact": "x@example.com", "birth_date": "1990-01-01", "consent": False}, format="json")
    assert r.status_code == 400


def test_pii_is_in_separate_database(athlete):
    assert Identity.objects.using("pii").count() == 1
    assert "pii_identity" not in connections["default"].introspection.table_names()
    assert not any(f.name in ("email", "phone", "first_name", "last_name") for f in User._meta.get_fields())


def test_login_wrong_password_and_lockout(athlete):
    c = APIClient()
    for _ in range(5):
        r = c.post("/api/auth/login/", {"contact": athlete.email, "password": "wrong-pass"}, format="json")
        assert r.status_code == 401
    r = c.post("/api/auth/login/", {"contact": athlete.email, "password": PASSWORD}, format="json")
    assert r.status_code == 429


def test_s1_ok_assessment_30_days(athlete):
    r = post_assessment(athlete)
    assert r.status_code == 201, r.data
    assert r.data["kerdo_index"] == -15.6 and r.data["kerdo_class"] == "vagotonia"
    assert r.data["red_flag"] is False and r.data["restq"] is None
    assert r.data["result"]["kerdo"]["title"] == "Ваготония"
    assert date.fromisoformat(r.data["next_due_date"]) - date.today() in (timedelta(days=30), timedelta(days=29), timedelta(days=31))


def test_s3_restq_required_and_scored(athlete):
    r = post_assessment(athlete, tolerance=3)
    assert r.status_code == 400 and "restq" in r.data["errors"]
    restq = {"timing": "before", "answers": {str(i): 2 for i in range(1, 78)}}
    r = post_assessment(athlete, tolerance=3, restq=restq)
    assert r.status_code == 201, r.data
    assert r.data["red_flag"] is True and r.data["restq"]["total_stress"] == 2.0
    assert len(r.data["restq"]["scales"]) == 19


def test_s9_urgent_message(athlete):
    r = post_assessment(athlete, q3_5=True)
    assert r.status_code == 201 and r.data["urgent"] is True
    assert r.data["result"]["urgent_message"].startswith("Боль в груди")


def test_idempotent_sync(athlete):
    cu = str(uuid.uuid4())
    body = {"client_uuid": cu, "answers": answers()}
    assert athlete.post("/api/assessments/", body, format="json").status_code == 201
    assert athlete.post("/api/assessments/", body, format="json").status_code == 200
    assert SelfAssessment.objects.count() == 1


def test_completed_record_is_immutable(athlete):
    post_assessment(athlete)
    rec = SelfAssessment.objects.get()
    rec.tolerance = 1
    with pytest.raises(PermissionDenied):
        rec.save()
    assert athlete.put(f"/api/assessments/{rec.id}/", {}, format="json").status_code == 405


def test_draft_roundtrip(athlete):
    assert athlete.get("/api/assessments/draft/").status_code == 404
    assert athlete.put("/api/assessments/draft/", {"data": {"tolerance": 4, "step": 2}}, format="json").status_code == 200
    assert athlete.get("/api/assessments/draft/").data["data"]["tolerance"] == 4
    assert athlete.put("/api/assessments/draft/", {"data": {"hack": 1}}, format="json").status_code == 400
    post_assessment(athlete)
    assert athlete.get("/api/assessments/draft/").status_code == 404


def test_profile_history_and_export(athlete):
    athlete.put("/api/profile/season/", {"season_period": "competition"}, format="json")
    hist = athlete.get("/api/profile/history/").data
    assert any(h["field"] == "season_period" and h["new_value"] == "competition" for h in hist)
    post_assessment(athlete)
    ex = athlete.get("/api/export/data/").data
    assert "first_name" not in ex["profile"] and len(ex["assessments"]) == 1
    assert ex["profile"]["sport"]["type_esc"] == "выносливость"
    assert athlete.get("/api/export/data/?include_name=1").data["profile"]["first_name"] == "Иван"


def test_users_see_only_own_records(athlete):
    post_assessment(athlete)
    other = APIClient()
    email = "other@example.com"
    r = other.post("/api/auth/register/start/", {"contact": email, "birth_date": "1990-01-01", "consent": True}, format="json")
    r = other.post("/api/auth/register/verify/", {"contact": email, "code": r.data["debug_code"], "password": PASSWORD}, format="json")
    other.credentials(HTTP_AUTHORIZATION="Bearer " + r.data["access"])
    rec = SelfAssessment.objects.get()
    assert other.get(f"/api/assessments/{rec.id}/").status_code == 404
    assert other.get("/api/assessments/").data == []


def test_admin_has_no_access_to_athlete_data():
    admin = User.objects.create_superuser("admin1", PASSWORD)
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION="Bearer " + str(RefreshToken.for_user(admin).access_token))
    assert c.get("/api/profile/").status_code == 403
    assert c.get("/api/assessments/").status_code == 403


def test_s19_delete_account(athlete):
    post_assessment(athlete)
    assert athlete.delete("/api/account/", {"password": "wrong"}, format="json").status_code == 403
    assert athlete.delete("/api/account/", {"password": PASSWORD}, format="json").status_code == 204
    assert User.objects.count() == 0 and SelfAssessment.objects.count() == 0
    assert Identity.objects.using("pii").count() == 0
    r = APIClient().post("/api/auth/login/", {"contact": athlete.email, "password": PASSWORD}, format="json")
    assert r.status_code == 401


def test_s16_early_assessment_reschedules(athlete):
    post_assessment(athlete, q6_1=True)
    sch = athlete.get("/api/reminders/settings/").data
    first_due = sch["due_date"]
    post_assessment(athlete)
    assert athlete.get("/api/reminders/settings/").data["due_date"] != first_due