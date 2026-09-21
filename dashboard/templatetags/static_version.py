"""Content-versioned static URL helpers.

Why this exists
---------------
Django's ``runserver`` serves files under ``STATICFILES_DIRS`` via
``django.contrib.staticfiles.handlers.StaticFilesHandler``, which emits
``Last-Modified`` but no ``Cache-Control``/``ETag``. Per RFC 9111 section 4.2.2
browsers then apply *heuristic* freshness (Chrome uses roughly
``(Date - Last-Modified) / 10``), which means a rebuilt ``static/css/output.css``
can silently stay stale across ordinary navigations -- the classic "Ctrl+F5
fixes it" symptom for Tailwind workflows.

The ``versioned_static`` tag below appends a short ``?v=<token>`` query string
derived from the file's mtime+size while ``DEBUG=True``. Because the URL
changes whenever the file changes on disk, the browser treats every rebuild as
a fresh resource -- no hard refresh needed. In production, ``staticfiles_storage
.url()`` already returns the whitenoise/compressed path and we do NOT append a
token, so the behaviour is unchanged from ``{% static %}``.
"""
from __future__ import annotations

import os

from django import template
from django.conf import settings
from django.contrib.staticfiles.finders import find as staticfiles_find
from django.contrib.staticfiles.storage import staticfiles_storage

register = template.Library()


def _version_token(relative_path: str) -> str:
    """Return a short cache-busting token for ``relative_path``.

    Intentionally **not** memoised: in DEBUG we want the token to change the
    instant ``static/css/output.css`` is rewritten by ``tailwind:watch``, so a
    fresh ``os.stat`` on every render is required. ``os.stat`` costs only a few
    microseconds and only runs when ``DEBUG=True`` -- production short-circuits
    at the very first line and hits no filesystem at all.

    The token combines ``mtime`` and ``size`` so it flips whenever the file is
    rewritten (``touch`` changes mtime; a rebuild also changes size).
    """
    if not settings.DEBUG:
        return ""
    # ``staticfiles_storage.path()`` resolves against ``STATIC_ROOT`` -- that is
    # the *collected* copy, which only ``collectstatic`` refreshes. During dev,
    # ``runserver`` actually serves from ``STATICFILES_DIRS`` via the finders,
    # so we must look the file up through the finders to read the same mtime
    # the browser will receive. ``finders.find()`` returns the absolute path of
    # the first matching source file (or None).
    absolute = staticfiles_find(relative_path)
    if not absolute:
        # Fall back to the collected copy so a ``{% versioned_static %}`` never
        # blows up on files that only exist after ``collectstatic``.
        try:
            absolute = staticfiles_storage.path(relative_path)
        except (NotImplementedError, ValueError):
            return ""
    try:
        stat = os.stat(absolute)
    except OSError:
        return ""
    return f"{int(stat.st_mtime):x}-{stat.st_size:x}"


@register.simple_tag
def versioned_static(relative_path: str) -> str:
    """Like ``{% static %}`` but appends ``?v=<mtime+size>`` in DEBUG.

    Usage::

        {% load static_version %}
        <link rel="stylesheet" href="{% versioned_static 'css/output.css' %}">
    """
    url = staticfiles_storage.url(relative_path)
    token = _version_token(relative_path)
    if not token:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}v={token}"
