import os
import warnings

from django.apps import AppConfig
from django.conf import settings
from django.core.checks import Warning, register


def _secret_key_from_env() -> str:
    return os.getenv("DJANGO_SECRET_KEY", "").strip()


@register()
def production_safety_check(app_configs, **kwargs):
    errors: list[Warning] = []
    if settings.DEBUG:
        return errors

    secret = _secret_key_from_env()
    if not secret or secret == "dev-secret-key-change-me" or len(secret) < 50:
        errors.append(
            Warning(
                "Set a strong DJANGO_SECRET_KEY (50+ chars) when DJANGO_DEBUG=0.",
                id="intake.W001",
            )
        )
    if "*" in settings.ALLOWED_HOSTS:
        errors.append(
            Warning(
                "Set DJANGO_ALLOWED_HOSTS to your domain(s), not '*', in production.",
                id="intake.W002",
            )
        )
    if settings.ANAMNES_ADMIN_PASSWORD in {"", "admin", "change-me-strong-password"}:
        errors.append(
            Warning(
                "Set a strong ANAMNES_ADMIN_PASSWORD in /etc/anamnes.env.",
                id="intake.W003",
            )
        )
    return errors


class IntakeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "intake"

    def ready(self) -> None:
        if os.getenv("DJANGO_DEBUG", "1") != "0":
            return
        secret = _secret_key_from_env()
        if not secret or secret == "dev-secret-key-change-me":
            warnings.warn(
                "DJANGO_SECRET_KEY is missing or still the dev default while DJANGO_DEBUG=0.",
                stacklevel=1,
            )
