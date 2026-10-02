from django.contrib import admin

from .models import AttendanceRecord


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "status", "updated_at")
    list_filter = ("status", "user")
    date_hierarchy = "date"
    search_fields = ("user__username",)
