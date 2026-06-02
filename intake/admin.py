from django.contrib import admin

from .models import Doctor, Draft, Submission, SubmissionFile

admin.site.register(Doctor)
admin.site.register(Draft)
admin.site.register(Submission)
admin.site.register(SubmissionFile)
