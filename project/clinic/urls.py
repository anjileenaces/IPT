from django.urls import path

from clinic import views

app_name = "clinic"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("book/", views.book_appointment, name="book"),
    path("api/booking-availability/", views.booking_availability_api, name="booking_availability_api"),
    path("api/my-visits/", views.my_visits_chart_api, name="my_visits_chart_api"),
    path("notifications/", views.notifications_list, name="notifications"),
    path("notifications/<int:pk>/read/", views.notification_mark_read, name="notification_read"),
    path("profile/", views.profile_edit, name="profile"),
    path("pets/", views.PetListView.as_view(), name="pets"),
    path("pets/add/", views.PetCreateView.as_view(), name="pet_add"),
    path("pets/<int:pk>/edit/", views.PetUpdateView.as_view(), name="pet_edit"),
    path("pets/<int:pk>/delete/", views.PetDeleteView.as_view(), name="pet_delete"),
    path("staff/", views.StaffDashboardView.as_view(), name="staff_dashboard"),
    path("staff/appointments/<int:pk>/action/", views.staff_appointment_action, name="staff_appointment_action"),
    path("staff/staff-accounts/add/", views.superuser_create_staff, name="staff_create_staff"),
    path("staff/shop-closed/", views.superuser_shop_closed, name="staff_shop_closed"),
    path("staff/users/", views.StaffUserListView.as_view(), name="staff_users"),
    path("staff/reports/", views.StaffReportsView.as_view(), name="staff_reports"),
    path("staff/transactions/<int:pk>/", views.staff_transaction_update, name="staff_transaction_update"),
]
  