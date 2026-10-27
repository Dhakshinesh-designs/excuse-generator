import logging
import time

logger = logging.getLogger("myapp.request")


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = time.monotonic()
        try:
            response = self.get_response(request)
        except Exception:
            elapsed_ms = (time.monotonic() - started) * 1000
            logger.exception(
                "Request failed: %s %s (%.1f ms)",
                request.method,
                request.path,
                elapsed_ms,
            )
            raise

        elapsed_ms = (time.monotonic() - started) * 1000
        logger.info(
            "%s %s %s (%.1f ms)",
            request.method,
            request.path,
            response.status_code,
            elapsed_ms,
        )
        return response
