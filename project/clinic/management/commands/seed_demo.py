from django.core.management.base import BaseCommand

from clinic.models import Service


class Command(BaseCommand):
    help = "Create default clinic services if none exist."

    def handle(self, *args, **options):
        if Service.objects.exists():
            self.stdout.write(self.style.WARNING("Services already exist — skipping."))
            return
        defaults = [
            ("Wellness Exam", "Annual check-up and vitals", 30, "45.00"),
            ("Vaccination", "Core vaccines and records update", 20, "35.00"),
            ("Dental Cleaning", "Dental scale and polish", 60, "120.00"),
            ("Emergency Visit", "Urgent care triage", 45, "95.00"),
            ("Grooming", "Bath, nail trim, basic groom", 45, "55.00"),
        ]
        for name, desc, mins, price in defaults:
            Service.objects.create(
                name=name,
                description=desc,
                duration_minutes=mins,
                base_price=price,
            )
        self.stdout.write(self.style.SUCCESS(f"Created {len(defaults)} services."))
