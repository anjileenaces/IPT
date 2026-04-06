"""Schedule with Windows Task Scheduler or cron: daily run for reminders."""

from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone

from clinic.models import Appointment, Notification, Pet


class Command(BaseCommand):
    help = "Send appointment, follow-up, and vaccination reminder emails."

    def handle(self, *args, **options):
        today = timezone.localdate()
        tomorrow = today + timedelta(days=1)

        # Appointment reminders (tomorrow, approved)
        appts = Appointment.objects.filter(
            appointment_date=tomorrow,
            status=Appointment.Status.APPROVED,
        ).select_related("user", "pet", "service")
        for a in appts:
            if not a.user.email:
                continue
            send_mail(
                "PawCare — Appointment reminder",
                f"Reminder: {a.pet.name} has an appointment tomorrow ({a.appointment_date}) "
                f"at {a.appointment_time} for {a.service.name}.\n",
                settings.DEFAULT_FROM_EMAIL,
                [a.user.email],
            )
            Notification.objects.create(
                user=a.user,
                kind=Notification.Kind.APPOINTMENT,
                title=f"Reminder: visit tomorrow for {a.pet.name}",
                body=f"{a.service.name} at {a.appointment_time}",
            )

        # Vaccination alerts (due within 7 days)
        soon = today + timedelta(days=7)
        pets = Pet.objects.filter(
            vaccination_next_due__isnull=False,
            vaccination_next_due__lte=soon,
            vaccination_next_due__gte=today,
        ).select_related("owner")
        for p in pets:
            Notification.objects.create(
                user=p.owner,
                kind=Notification.Kind.VACCINATION,
                title=f"Vaccination reminder: {p.name}",
                body=f"Due date: {p.vaccination_next_due}",
            )
            if p.owner.email:
                send_mail(
                    "PawCare — Vaccination due soon",
                    f"{p.name}'s vaccination is due on or before {p.vaccination_next_due}. "
                    "Please book a visit.\n",
                    settings.DEFAULT_FROM_EMAIL,
                    [p.owner.email],
                )

        # Follow-up placeholder: notify users with completed visit in last 3 days
        three_days_ago = today - timedelta(days=3)
        recent = Appointment.objects.filter(
            status=Appointment.Status.COMPLETED,
            appointment_date__gte=three_days_ago,
            appointment_date__lt=today,
        ).select_related("user", "pet")
        for a in recent:
            exists = Notification.objects.filter(
                user=a.user,
                kind=Notification.Kind.FOLLOWUP,
                title__contains=a.pet.name,
                created_at__date=today,
            ).exists()
            if not exists:
                Notification.objects.create(
                    user=a.user,
                    kind=Notification.Kind.FOLLOWUP,
                    title=f"Follow-up: how is {a.pet.name}?",
                    body="We hope the visit went well. Book a follow-up anytime.",
                )

        self.stdout.write(self.style.SUCCESS("Reminder job finished."))
