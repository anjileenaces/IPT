from django.core.mail import send_mail
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from clinic.models import Appointment, Notification


@receiver(post_save, sender=Appointment)
def appointment_created_notify(sender, instance, created, **kwargs):
    if not created:
        return
    note = ""
    if instance.is_over_capacity:
        note = (
            " This time slot was already full — staff will approve or decline based on availability."
        )
    Notification.objects.create(
        user=instance.user,
        kind=Notification.Kind.APPOINTMENT,
        title="Appointment submitted",
        body=f"Your booking for {instance.pet.name} on {instance.appointment_date} "
        f"at {instance.appointment_time} is pending staff approval.{note}",
    )
    subject = "PawCare — Booking received"
    oc_line = ""
    if instance.is_over_capacity:
        oc_line = "The slot was already busy; staff will confirm or suggest another time.\n"
    message = (
        f"Hello {instance.user.get_full_name() or instance.user.username},\n\n"
        f"We received your appointment request for {instance.pet.name} "
        f"({instance.service.name}) on {instance.appointment_date} at {instance.appointment_time}.\n"
        f"Emergency priority: {'Yes' if instance.is_emergency else 'No'}\n"
        f"{oc_line}\n"
        "You will receive another message when staff approves or rejects it.\n\n"
        "— PawCare Clinic"
    )
    if instance.user.email:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [instance.user.email])
