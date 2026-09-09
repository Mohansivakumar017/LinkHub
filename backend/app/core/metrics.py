from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

REQUEST_COUNT = Counter(
    "linkhub_http_requests_total",
    "Total number of HTTP requests handled by the API.",
    ("method", "path", "status"),
)
REQUEST_ERRORS = Counter(
    "linkhub_http_errors_total",
    "Total number of HTTP responses with a 5xx status.",
    ("method", "path", "status"),
)
REQUEST_LATENCY = Histogram(
    "linkhub_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ("method", "path"),
)
CACHE_HITS = Counter(
    "linkhub_url_cache_hits_total",
    "Number of URL redirect cache hits.",
)
CACHE_MISSES = Counter(
    "linkhub_url_cache_misses_total",
    "Number of URL redirect cache misses.",
)
CACHE_ERRORS = Counter(
    "linkhub_url_cache_errors_total",
    "Number of URL redirect cache operation errors.",
)


def route_label(request_path: str, route: object | None) -> str:
    """Return a bounded route label instead of a user-controlled URL path."""
    path = getattr(route, "path", None)
    if not isinstance(path, str):
        return "<unmatched>"
    if request_path == path:
        return path
    if request_path.endswith(path):
        return request_path[: -len(path)] + path

    route_parts = path.strip("/").split("/")
    request_parts = request_path.strip("/").split("/")
    if len(request_parts) >= len(route_parts):
        prefix_parts = request_parts[: -len(route_parts)]
        return "/" + "/".join(prefix_parts + route_parts)
    return path


def metrics_payload() -> bytes:
    """Serialize the process metrics in Prometheus exposition format."""
    return generate_latest()


__all__ = [
    "CACHE_ERRORS",
    "CACHE_HITS",
    "CACHE_MISSES",
    "CONTENT_TYPE_LATEST",
    "REQUEST_COUNT",
    "REQUEST_ERRORS",
    "REQUEST_LATENCY",
]
