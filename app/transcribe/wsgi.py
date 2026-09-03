"""The WSGI entry point gunicorn serves.

Browser pages poll every few seconds and there are no server-sent events, so a
plain WSGI server with sync workers is enough.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "transcribe.settings")

application = get_wsgi_application()
