from django.contrib import admin

from .models import Sport


@admin.register(Sport)
class SportAdmin(admin.ModelAdmin):
    """Справочник видов спорта (Приложение В). Профили спортсменов администратору не видны."""

    list_display = ("ext_no", "name", "type_esc", "intensity_esc", "static_mitchell", "dynamic_mitchell", "is_active")
    list_filter = ("type_esc", "intensity_esc", "is_active")
    search_fields = ("name",)
    list_editable = ("is_active",)
