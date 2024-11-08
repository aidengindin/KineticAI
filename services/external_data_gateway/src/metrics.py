from prometheus_client import Counter, Histogram, Gauge

SYNC_REQUESTS_TOTAL = Counter(
    "sync_requests_total",
    "Total number of sync requests",
    ["user_id", "status"]
)

ACTIVITY_PROCESSING_TIME = Histogram(
    "activity_processing_seconds",
    "Time spent processing activities",
    ["operation"]
)

ACTIVE_SYNCS = Gauge(
    "active_syncs",
    "Number of active sync operations"
)
