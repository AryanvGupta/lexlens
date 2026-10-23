"""Prometheus metrics for rag-api, exposed at GET /metrics.

Label values are bounded on purpose: `route` is the matched route template (never the raw
path), `mode` is the search-mode enum, and `outcome` is answered/refused, so a client cannot
create new time series by varying what it sends.
"""

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

HTTP_REQUESTS = Counter(
    "lexlens_http_requests_total",
    "HTTP requests handled by rag-api",
    ["method", "route", "status"],
)
HTTP_SECONDS = Histogram(
    "lexlens_http_request_seconds",
    "HTTP request latency in seconds",
    ["method", "route"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)
SEARCHES = Counter("lexlens_searches_total", "Searches by retrieval mode", ["mode"])
ASKS = Counter(
    "lexlens_asks_total",
    "/ask results: answered with verified citations, or refused",
    ["outcome"],
)


def route_label(request) -> str:
    """Route template such as '/search'; 'unmatched' for 404s so scanners cannot add series."""
    route = request.scope.get("route")
    return getattr(route, "path", None) or "unmatched"


def record_request(request, status: int, seconds: float) -> None:
    route = route_label(request)
    HTTP_REQUESTS.labels(request.method, route, str(status)).inc()
    HTTP_SECONDS.labels(request.method, route).observe(seconds)


def render() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
