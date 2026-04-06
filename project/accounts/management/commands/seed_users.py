from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Create default demo accounts: admin (superuser) and Staff (staff). "
        "Django cannot store an empty login password; Staff is created with no usable password "
        "until you set one (Admin → Users → Staff → change password), or: "
        "python manage.py changepassword Staff"
    )

    def handle(self, *args, **options):
        admin, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@local",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        admin.set_password("admin123")
        admin.is_staff = True
        admin.is_superuser = True
        admin.save()
        self.stdout.write(
            self.style.SUCCESS(
                "admin: password set to admin123 (superuser)"
            )
        )

        staff, created = User.objects.get_or_create(
            username="Staff",
            defaults={
                "email": "staff@local",
                "is_staff": True,
                "is_superuser": False,
            },
        )
        staff.is_staff = True
        staff.is_superuser = False
        staff.set_unusable_password()
        staff.save()
        self.stdout.write(
            self.style.WARNING(
                "Staff: no login password (Django cannot use blank passwords). "
                "Set one in Admin or: python manage.py changepassword Staff"
            )
        )
