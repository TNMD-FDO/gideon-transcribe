"""The service's own version, reported in every result and on the status page.

The service is versioned separately from the app that consumes it, because
another Consumer may hold a token for it and never install the app at all. The
API is versioned by path instead, so a breaking change becomes /v2/ rather than
a surprise.
"""

SERVICE_VERSION = "0.2.0"
API_VERSION = "v1"
