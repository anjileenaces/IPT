from django.contrib import admin

from clinic.models import Appointment, Notification, Pet, Service, ShopClosedDate, Transaction


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "duration_minutes", "base_price")
    search_fields = ("name",)


class TransactionInline(admin.StackedInline):
    model = Transaction
    extra = 0


@admin.register(ShopClosedDate)
class ShopClosedDateAdmin(admin.ModelAdmin):
    list_display = ("date", "reason", "created_at")
    date_hierarchy = "date"


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "pet",
        "service",
        "appointment_date",
        "appointment_time",
        "status",
        "is_emergency",
        "is_over_capacity",
    )
    list_filter = ("status", "is_emergency", "is_over_capacity", "appointment_date")
    search_fields = ("user__username", "pet__name", "service__name")
    inlines = [TransactionInline]
    date_hierarchy = "appointment_date"


@admin.register(Pet)
class PetAdmin(admin.ModelAdmin):
    list_display = ("name", "species", "breed", "owner")
    search_fields = ("name", "owner__username")
    list_filter = ("species",)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "appointment", "amount", "payment_status", "created_at", "paid_at")
    list_filter = ("payment_status",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "kind", "read", "created_at")
    list_filter = ("kind", "read")
