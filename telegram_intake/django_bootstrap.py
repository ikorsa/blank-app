from __future__ import annotations

import os


def ensure_django() -> None:
    if getattr(ensure_django, "_ready", False):
        return
    import anamnes_storage  # noqa: F401

    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "anamnes_site.settings")
    django.setup()
    ensure_django._ready = True  # type: ignore[attr-defined]
