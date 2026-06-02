from django.contrib import admin

from .models import Doctor, Draft, Submission, SubmissionFile


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ("slug", "name", "specialty", "email", "is_active")
    search_fields = ("slug", "name")


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("id", "doctor", "status", "created_at")
    list_filter = ("status", "doctor")
    search_fields = ("id",)
    readonly_fields = ("created_at", "viewed_at")


admin.site.register(Draft)
admin.site.register(SubmissionFile)
