import copy
import json

from django import forms
from django.contrib import admin, messages
from django.db import transaction
from django.utils.html import format_html

from .models import AuditLog, SettingsVersion
from .settings_service import get_active_settings, validate_settings


class SettingsVersionForm(forms.ModelForm):
    data = forms.CharField(
        required=False,
        label="Настройки (JSON)",
        widget=forms.Textarea(attrs={"rows": 40, "cols": 120, "style": "font-family:monospace"}),
    )

    class Meta:
        model = SettingsVersion
        fields = ["comment", "approved_by", "data"]

    def clean_data(self):
        raw = self.cleaned_data.get("data")
        if not raw and self.instance.pk:  # просмотр старой версии: содержимое не меняется
            return self.instance.data
        try:
            data = json.loads(raw or "")
            validate_settings(data)
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            raise forms.ValidationError(f"Некорректные настройки: {e}")
        return data


@admin.register(SettingsVersion)
class SettingsVersionAdmin(admin.ModelAdmin):
    """Новая версия = «Добавить»; форма заполнена действующими значениями. Старые версии не редактируются."""

    form = SettingsVersionForm
    list_display = ("version", "is_active", "created_at", "created_by", "approved_by", "comment")
    actions = ["make_active"]

    def get_changeform_initial_data(self, request):
        return {"data": json.dumps(copy.deepcopy(get_active_settings().data), ensure_ascii=False, indent=2)}

    def get_fields(self, request, obj=None):
        if obj is None:
            return ["comment", "approved_by", "data"]
        return ["version", "is_active", "created_at", "created_by", "approved_by", "comment", "data_pretty"]

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return []
        return ["version", "is_active", "created_at", "created_by", "approved_by", "comment", "data_pretty"]

    @admin.display(description="Настройки (JSON)")
    def data_pretty(self, obj):
        return format_html("<pre>{}</pre>", json.dumps(obj.data, ensure_ascii=False, indent=2))

    def has_delete_permission(self, request, obj=None):
        return False

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        if change:
            return
        last = SettingsVersion.objects.order_by("-version").first()
        obj.version = (last.version + 1) if last else 1
        obj.created_by = request.user
        obj.is_active = True
        SettingsVersion.objects.filter(is_active=True).update(is_active=False)
        obj.save()

    @admin.action(description="Сделать выбранную версию действующей (откат)")
    def make_active(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Выберите одну версию", messages.ERROR)
            return
        with transaction.atomic():
            SettingsVersion.objects.filter(is_active=True).update(is_active=False)
            queryset.update(is_active=True)
        self.message_user(request, "Версия активирована")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("ts", "actor_role", "actor_code", "action", "object_type", "object_id", "ip")
    list_filter = ("action", "actor_role")
    date_hierarchy = "ts"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
