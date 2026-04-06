from django.conf import settings
from django.db import models
from django.utils import timezone


class ShopClosedDate(models.Model):
    """Days the clinic is closed — clients cannot book; staff may reject existing pending requests."""

    date = models.DateField(unique=True)
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Closed {self.date}"


class Service(models.Model):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveIntegerField(default=30)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Pet(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pets"
    )
    name = models.CharField(max_length=120)

    PET_SPECIES_CHOICES = [
        ("cat", "Cat"),
        ("dog", "Dog"),
        ("mouse", "Mouse"),
        ("hamster", "Hamster"),
        ("rabbit", "Rabbit"),
        ("bird", "Bird"),
    ]

    species = models.CharField(max_length=20, choices=PET_SPECIES_CHOICES)
    breed = models.CharField(max_length=120, blank=True)
    birth_date = models.DateField(blank=True, null=True)
    medical_history = models.TextField(blank=True)
    vaccination_next_due = models.DateField(
        blank=True, null=True, help_text="Used for vaccination reminder emails."
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.species})"


class Appointment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="appointments"
    )
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name="appointments")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="appointments")
    appointment_date = models.DateField()
    appointment_time = models.TimeField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    is_emergency = models.BooleanField(
        default=False,
        help_text="Emergency bookings appear first in the staff queue.",
    )
    notes = models.TextField(blank=True)
    is_over_capacity = models.BooleanField(
        default=False,
        help_text="True if the slot was already full when the client submitted (needs admin decision).",
    )
    rejection_reason = models.TextField(
        blank=True,
        help_text="Shown to the client when staff rejects this booking.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_emergency", "appointment_date", "appointment_time"]
        indexes = [
            models.Index(fields=["appointment_date", "appointment_time", "status"]),
        ]

    def __str__(self):
        return f"{self.pet.name} — {self.service.name} @ {self.appointment_date}"


class Transaction(models.Model):
    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        REFUNDED = "refunded", "Refunded"

    appointment = models.OneToOneField(
        Appointment, on_delete=models.CASCADE, related_name="transaction"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Txn #{self.pk} — {self.amount} ({self.payment_status})"


class Notification(models.Model):
    class Kind(models.TextChoices):
        APPOINTMENT = "appointment", "Appointment"
        FOLLOWUP = "followup", "Follow-up"
        VACCINATION = "vaccination", "Vaccination"
        SYSTEM = "system", "System"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    kind = models.CharField(max_length=32, choices=Kind.choices, default=Kind.SYSTEM)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
