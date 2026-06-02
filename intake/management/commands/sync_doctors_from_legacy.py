from __future__ import annotations

from django.core.management.base import BaseCommand

from intake.models import Doctor


class Command(BaseCommand):
    help = "Sync doctors from legacy anamnes_storage source (JSON/PostgreSQL)."

    def handle(self, *args, **options):
        from anamnes_storage import load_doctors

        doctors = load_doctors(include_inactive=True)
        created = 0
        updated = 0

        for item in doctors:
            slug = str(item.get("id") or "").strip().lower()
            if not slug:
                continue
            defaults = {
                "name": str(item.get("name") or slug),
                "specialty": str(item.get("specialty") or "Эндокринолог"),
                "is_active": str(item.get("is_active", "true")).lower() not in {"false", "0", "no"},
            }
            _, was_created = Doctor.objects.update_or_create(slug=slug, defaults=defaults)
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"Doctors synced: created={created}, updated={updated}"))
