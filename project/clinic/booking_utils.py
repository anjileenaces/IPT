"""Availability, smart slot hints, and time grid for booking."""

from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.db.models import Count
from django.db.models.functions import ExtractHour

from clinic.models import Appointment


def is_shop_closed(on_date) -> bool:
    from clinic.models import ShopClosedDate

    return ShopClosedDate.objects.filter(date=on_date).exists()


def work_times(step_minutes: int = 30):
    """Generate opening time slots (default 09:00–17:00, 30-min steps)."""
    start = time(9, 0)
    end = time(17, 0)
    slots = []
    t = datetime.combine(date.today(), start)
    end_dt = datetime.combine(date.today(), end)
    while t < end_dt:
        slots.append(t.time())
        t += timedelta(minutes=step_minutes)
    return slots


def slot_booking_count(on_date, at_time) -> int:
    active = [Appointment.Status.PENDING, Appointment.Status.APPROVED]
    return Appointment.objects.filter(
        appointment_date=on_date,
        appointment_time=at_time,
        status__in=active,
    ).count()


def slot_available(on_date, at_time) -> bool:
    cap = getattr(settings, "APPOINTMENT_SLOT_CAPACITY", 2)
    return slot_booking_count(on_date, at_time) < cap


def busy_by_hour(on_date):
    """Return list of {hour, count} for chart / smart recommendations."""
    active = [Appointment.Status.PENDING, Appointment.Status.APPROVED]
    qs = (
        Appointment.objects.filter(appointment_date=on_date, status__in=active)
        .annotate(hour=ExtractHour("appointment_time"))
        .values("hour")
        .annotate(c=Count("id"))
        .order_by("hour")
    )
    return list(qs)


def recommended_times(on_date, top_n: int = 3):
    """Least busy hours on a given day (smart recommendation)."""
    counts = {h: 0 for h in range(9, 17)}
    for row in busy_by_hour(on_date):
        hr = row.get("hour")
        if hr is not None and hr in counts:
            counts[hr] = row["c"]
    ranked = sorted(counts.items(), key=lambda x: x[1])
    return [f"{h:02d}:00 – suggested (lighter load)" for h, _ in ranked[:top_n]]
