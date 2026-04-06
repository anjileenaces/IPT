from datetime import date, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.mail import send_mail
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from accounts.forms import ProfileForm, StaffCreateForm

from clinic.booking_utils import (
    busy_by_hour,
    recommended_times,
    slot_available,
    slot_booking_count,
    work_times,
)
from clinic.forms import AppointmentForm, PetForm, ShopClosedDateForm
from clinic.models import Appointment, Notification, Pet, Service, ShopClosedDate, Transaction


def landing(request):
    q = (request.GET.get("q") or "").strip()
    services = Service.objects.all()
    if q:
        services = services.filter(Q(name__icontains=q) | Q(description__icontains=q))
    return render(
        request,
        "clinic/landing.html",
        {"services": services, "search_q": q},
    )


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "clinic/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.localdate()
        upcoming = (
            Appointment.objects.filter(user=user, appointment_date__gte=today)
            .exclude(status=Appointment.Status.CANCELLED)
            .exclude(status=Appointment.Status.REJECTED)
            .select_related("pet", "service")[:10]
        )
        ctx["upcoming_appointments"] = upcoming
        ctx["pets"] = Pet.objects.filter(owner=user)[:6]
        ctx["notifications"] = Notification.objects.filter(user=user)[:8]

        # Visit history chart (completed appointments by month, last 6 months)
        six_mo = today.replace(day=1) - timedelta(days=180)
        visits = (
            Appointment.objects.filter(
                user=user,
                status=Appointment.Status.COMPLETED,
                appointment_date__gte=six_mo,
            )
            .annotate(m=TruncMonth("appointment_date"))
            .values("m")
            .annotate(c=Count("id"))
            .order_by("m")
        )
        ctx["chart_labels"] = [v["m"].strftime("%b %Y") if v["m"] else "" for v in visits]
        ctx["chart_values"] = [v["c"] for v in visits]
        return ctx


@login_required
def notifications_list(request):
    items = Notification.objects.filter(user=request.user)
    status_filter = request.GET.get("status")
    if status_filter == "unread":
        items = items.filter(read=False)
    elif status_filter == "read":
        items = items.filter(read=True)
    sort = request.GET.get("sort", "newest")
    if sort == "oldest":
        items = items.order_by("created_at")
    else:
        items = items.order_by("-created_at")
    return render(
        request,
        "clinic/notifications.html",
        {"notifications": items, "status_filter": status_filter, "sort": sort},
    )


@login_required
def notification_mark_read(request, pk):
    n = get_object_or_404(Notification, pk=pk, user=request.user)
    n.read = True
    n.save(update_fields=["read"])
    messages.success(request, "Marked as read.")
    return redirect("clinic:notifications")


@login_required
def profile_edit(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("clinic:profile")
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "clinic/profile.html", {"form": form})


class PetListView(LoginRequiredMixin, ListView):
    model = Pet
    template_name = "clinic/pet_list.html"
    context_object_name = "pets"

    def get_queryset(self):
        qs = Pet.objects.filter(owner=self.request.user)
        q = (self.request.GET.get("q") or "").strip()
        species = (self.request.GET.get("species") or "").strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(breed__icontains=q))
        if species:
            qs = qs.filter(species__iexact=species)
        sort = self.request.GET.get("sort", "name")
        if sort == "species":
            qs = qs.order_by("species", "name")
        else:
            qs = qs.order_by("name")
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["search_q"] = self.request.GET.get("q", "")
        ctx["species_filter"] = self.request.GET.get("species", "")
        ctx["sort"] = self.request.GET.get("sort", "name")
        return ctx


class PetCreateView(LoginRequiredMixin, CreateView):
    model = Pet
    form_class = PetForm
    template_name = "clinic/pet_form.html"
    success_url = reverse_lazy("clinic:pets")

    def form_valid(self, form):
        form.instance.owner = self.request.user
        messages.success(self.request, "Pet record created.")
        return super().form_valid(form)


class PetUpdateView(LoginRequiredMixin, UpdateView):
    model = Pet
    form_class = PetForm
    template_name = "clinic/pet_form.html"
    success_url = reverse_lazy("clinic:pets")

    def get_queryset(self):
        return Pet.objects.filter(owner=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Pet record updated.")
        return super().form_valid(form)


class PetDeleteView(LoginRequiredMixin, DeleteView):
    model = Pet
    template_name = "clinic/pet_confirm_delete.html"
    success_url = reverse_lazy("clinic:pets")

    def get_queryset(self):
        return Pet.objects.filter(owner=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Pet record deleted.")
        return super().delete(request, *args, **kwargs)


@login_required
def book_appointment(request):
    # Staff/admin can monitor client bookings, but clients only can create new bookings.
    if request.user.is_staff:
        messages.error(request, "Staff cannot book appointments. Use the staff dashboard to monitor requests.")
        return redirect("clinic:staff_dashboard")

    if request.method == "POST":
        form = AppointmentForm(request.POST, user=request.user)
        if form.is_valid():
            appt = form.save(commit=False)
            appt.user = request.user
            appt.save()
            if appt.is_over_capacity:
                messages.warning(
                    request,
                    "This time slot was already full. Your request is pending — staff will approve or decline.",
                )
            else:
                messages.success(
                    request,
                    "Booking submitted. Check your email — staff will approve or decline shortly.",
                )
            return redirect("clinic:dashboard")
    else:
        form = AppointmentForm(user=request.user)

    preview_date = request.GET.get("date")
    try:
        d = date.fromisoformat(preview_date) if preview_date else timezone.localdate()
    except ValueError:
        d = timezone.localdate()

    slots = work_times()
    slot_status = [(t, slot_available(d, t), slot_booking_count(d, t)) for t in slots]

    return render(
        request,
        "clinic/book.html",
        {
            "form": form,
            "preview_date": d.isoformat(),
            "slot_status": slot_status,
            "smart_hints": recommended_times(d),
            "busy_hours": busy_by_hour(d),
        },
    )


@login_required
def booking_availability_api(request):
    """JSON for calendar / slot picker."""
    # Prevent staff/admin from using the client booking calendar.
    if request.user.is_staff:
        return JsonResponse({"error": "forbidden"}, status=403)

    ds = request.GET.get("date")
    try:
        d = date.fromisoformat(ds) if ds else timezone.localdate()
    except ValueError:
        return JsonResponse({"error": "invalid date"}, status=400)
    slots = work_times()
    data = [
        {
            "time": t.strftime("%H:%M"),
            "available": slot_available(d, t),
            "booked": slot_booking_count(d, t),
        }
        for t in slots
    ]
    closed = ShopClosedDate.objects.filter(date=d).exists()
    return JsonResponse(
        {
            "date": d.isoformat(),
            "closed": closed,
            "slots": data,
            "hints": recommended_times(d),
        }
    )


def staff_required(user):
    return user.is_authenticated and user.is_staff


class StaffDashboardView(UserPassesTestMixin, TemplateView):
    template_name = "clinic/staff/dashboard.html"
    raise_exception = True

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()
        q = (self.request.GET.get("q") or "").strip()
        status = self.request.GET.get("status") or ""
        emergency_only = self.request.GET.get("emergency") == "1"
        sort = self.request.GET.get("sort", "date")

        appts = Appointment.objects.select_related("user", "pet", "service")
        if q:
            appts = appts.filter(
                Q(user__username__icontains=q)
                | Q(pet__name__icontains=q)
                | Q(service__name__icontains=q)
            )
        if status:
            appts = appts.filter(status=status)
        if emergency_only:
            appts = appts.filter(is_emergency=True)
        if sort == "created":
            appts = appts.order_by("-created_at")
        else:
            appts = appts.order_by("-is_emergency", "appointment_date", "appointment_time")

        ctx["appointments"] = appts[:200]
        ctx["search_q"] = q
        ctx["status_filter"] = status
        ctx["emergency_only"] = emergency_only
        ctx["sort"] = sort
        ctx["pending_count"] = Appointment.objects.filter(status=Appointment.Status.PENDING).count()
        ctx["closed_dates"] = set(ShopClosedDate.objects.values_list("date", flat=True))

        # Staff chart: appointments per day (last 14 days)
        start = today - timedelta(days=14)
        daily = (
            Appointment.objects.filter(appointment_date__gte=start)
            .annotate(day=TruncDate("appointment_date"))
            .values("day")
            .annotate(c=Count("id"))
            .order_by("day")
        )
        ctx["staff_chart_labels"] = [str(x["day"]) for x in daily]
        ctx["staff_chart_values"] = [x["c"] for x in daily]
        return ctx


@login_required
@require_POST
def staff_appointment_action(request, pk):
    if not request.user.is_staff:
        messages.error(request, "Access denied.")
        return redirect("clinic:dashboard")
    appt = get_object_or_404(Appointment, pk=pk)
    action = request.POST.get("action")
    if action == "approve":
        if ShopClosedDate.objects.filter(date=appt.appointment_date).exists():
            messages.error(
                request,
                "This date is marked closed. Remove it from Closed dates or reject the booking.",
            )
            return redirect("clinic:staff_dashboard")
        cap = getattr(settings, "APPOINTMENT_SLOT_CAPACITY", 2)
        approved = Appointment.objects.filter(
            appointment_date=appt.appointment_date,
            appointment_time=appt.appointment_time,
            status=Appointment.Status.APPROVED,
        ).count()
        if approved >= cap:
            messages.error(
                request,
                "This time slot already has the maximum approved bookings. Reject this request or adjust approved visits first.",
            )
            return redirect("clinic:staff_dashboard")
        appt.status = Appointment.Status.APPROVED
        appt.rejection_reason = ""
        appt.save(update_fields=["status", "rejection_reason", "updated_at"])
        txn, created = Transaction.objects.get_or_create(
            appointment=appt,
            defaults={"amount": appt.service.base_price},
        )
        if created:
            Notification.objects.create(
                user=appt.user,
                kind=Notification.Kind.APPOINTMENT,
                title="Appointment approved",
                body=f"{appt.pet.name}'s visit on {appt.appointment_date} was approved. "
                f"Amount due: {txn.amount}.",
            )
            if appt.user.email:
                send_mail(
                    "PawCare — Appointment approved",
                    f"Your appointment for {appt.pet.name} is approved.\n"
                    f"Date: {appt.appointment_date} Time: {appt.appointment_time}\n"
                    f"Service: {appt.service.name}\nAmount due: {txn.amount}\n",
                    settings.DEFAULT_FROM_EMAIL,
                    [appt.user.email],
                )
        messages.success(request, "Booking approved and bill created.")
    elif action == "reject":
        reason = (request.POST.get("rejection_reason") or "").strip()
        appt.status = Appointment.Status.REJECTED
        appt.rejection_reason = reason
        appt.save(update_fields=["status", "rejection_reason", "updated_at"])
        extra = f" Reason: {reason}" if reason else ""
        Notification.objects.create(
            user=appt.user,
            kind=Notification.Kind.APPOINTMENT,
            title="Appointment not approved",
            body=f"Your request for {appt.pet.name} on {appt.appointment_date} was not approved.{extra}",
        )
        if appt.user.email:
            send_mail(
                "PawCare — Booking update",
                f"Your appointment request for {appt.pet.name} on {appt.appointment_date} was not approved.{extra}\n",
                settings.DEFAULT_FROM_EMAIL,
                [appt.user.email],
                fail_silently=True,
            )
        messages.warning(request, "Booking rejected.")
    elif action == "complete":
        appt.status = Appointment.Status.COMPLETED
        appt.save(update_fields=["status", "updated_at"])
        messages.success(request, "Marked as completed.")
    return redirect("clinic:staff_dashboard")


@login_required
def superuser_create_staff(request):
    if not request.user.is_superuser:
        messages.error(request, "Only the main administrator can create staff accounts.")
        return redirect("clinic:staff_dashboard")
    if request.method == "POST":
        form = StaffCreateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Staff account created. They can log in with the username and password you set.",
            )
            return redirect("clinic:staff_users")
    else:
        form = StaffCreateForm()
    return render(request, "clinic/staff/create_staff.html", {"form": form})


@login_required
def superuser_shop_closed(request):
    if not request.user.is_superuser:
        messages.error(request, "Only administrators can manage closed dates.")
        return redirect("clinic:staff_dashboard")
    if request.method == "POST":
        if request.POST.get("delete_id"):
            pk = request.POST.get("delete_id")
            ShopClosedDate.objects.filter(pk=pk).delete()
            messages.success(request, "Closed date removed.")
            return redirect("clinic:staff_shop_closed")
        form = ShopClosedDateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Date marked as closed.")
            return redirect("clinic:staff_shop_closed")
    else:
        form = ShopClosedDateForm()
    closed_dates = ShopClosedDate.objects.all()[:500]
    return render(
        request,
        "clinic/staff/shop_closed.html",
        {"form": form, "closed_dates": closed_dates},
    )


class StaffUserListView(UserPassesTestMixin, ListView):
    template_name = "clinic/staff/users.html"
    context_object_name = "users"
    raise_exception = True

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        qs = User.objects.all().order_by("-date_joined")
        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(username__icontains=q) | Q(email__icontains=q))
        return qs[:500]


@login_required
@require_POST
def staff_transaction_update(request, pk):
    if not request.user.is_staff:
        messages.error(request, "Access denied.")
        return redirect("clinic:dashboard")
    txn = get_object_or_404(Transaction, pk=pk)
    if request.method == "POST":
        st = request.POST.get("payment_status")
        if st in dict(Transaction.PaymentStatus.choices):
            txn.payment_status = st
            if st == Transaction.PaymentStatus.PAID:
                txn.paid_at = timezone.now()
            txn.save()
            messages.success(request, "Payment status updated.")
    return redirect("clinic:staff_reports")


class StaffReportsView(UserPassesTestMixin, TemplateView):
    template_name = "clinic/staff/reports.html"
    raise_exception = True

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()
        start_s = self.request.GET.get("from")
        end_s = self.request.GET.get("to")
        try:
            start = date.fromisoformat(start_s) if start_s else today - timedelta(days=30)
        except ValueError:
            start = today - timedelta(days=30)
        try:
            end = date.fromisoformat(end_s) if end_s else today
        except ValueError:
            end = today

        daily_appts = (
            Appointment.objects.filter(appointment_date__range=(start, end))
            .annotate(day=TruncDate("appointment_date"))
            .values("day")
            .annotate(c=Count("id"))
            .order_by("day")
        )
        ctx["report_from"] = start.isoformat()
        ctx["report_to"] = end.isoformat()
        ctx["daily_labels"] = [str(x["day"]) for x in daily_appts]
        ctx["daily_values"] = [x["c"] for x in daily_appts]

        revenue = Transaction.objects.filter(
            payment_status=Transaction.PaymentStatus.PAID,
            paid_at__date__range=(start, end),
        ).aggregate(total=Sum("amount"))
        ctx["revenue_total"] = revenue["total"] or 0

        monthly = (
            Transaction.objects.filter(
                payment_status=Transaction.PaymentStatus.PAID,
                paid_at__isnull=False,
            )
            .annotate(m=TruncMonth("paid_at"))
            .values("m")
            .annotate(total=Sum("amount"))
            .order_by("m")
        )
        ctx["rev_month_labels"] = [x["m"].strftime("%b %Y") if x["m"] else "" for x in monthly]
        ctx["rev_month_values"] = [float(x["total"] or 0) for x in monthly]

        trends = (
            Appointment.objects.filter(status=Appointment.Status.COMPLETED, appointment_date__gte=start)
            .annotate(m=TruncMonth("appointment_date"))
            .values("m")
            .annotate(c=Count("id"))
            .order_by("m")
        )
        ctx["trend_labels"] = [x["m"].strftime("%b %Y") if x["m"] else "" for x in trends]
        ctx["trend_values"] = [x["c"] for x in trends]

        ctx["transactions"] = Transaction.objects.select_related(
            "appointment", "appointment__user", "appointment__pet"
        ).order_by("-created_at")[:100]
        return ctx


@login_required
def my_visits_chart_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({}, status=401)
    today = timezone.localdate()
    six_mo = today.replace(day=1) - timedelta(days=180)
    visits = (
        Appointment.objects.filter(
            user=request.user,
            status=Appointment.Status.COMPLETED,
            appointment_date__gte=six_mo,
        )
        .annotate(m=TruncMonth("appointment_date"))
        .values("m")
        .annotate(c=Count("id"))
        .order_by("m")
    )
    return JsonResponse(
        {
            "labels": [v["m"].strftime("%b %Y") if v["m"] else "" for v in visits],
            "values": [v["c"] for v in visits],
        }
    )
