from django.conf import settings
from django.db import models


class AttendanceRecord(models.Model):
    class Status(models.TextChoices):
        WFH = "WFH", "Work From Home"
        WFO = "WFO", "Work From Office"
        LEAVE = "Leave", "Leave"
        HOLIDAY = "Holiday", "Holiday"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "date"], name="one_status_per_user_per_day")
        ]
        ordering = ["date"]

    def __str__(self):
        return f"{self.user} — {self.date} — {self.status}"
