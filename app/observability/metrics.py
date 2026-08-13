from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS = Counter("platform_http_requests_total", "HTTP requests", ["method", "path", "status"])
HTTP_DURATION = Histogram("platform_http_request_duration_seconds", "HTTP request duration", ["method", "path"])
PROVISIONING_DURATION = Histogram("platform_provisioning_duration_seconds", "Provisioning duration", ["action"])
PROVISIONING_RESULTS = Counter("platform_provisioning_results_total", "Provisioning results", ["action", "result"])
RUNNING_ENVIRONMENTS = Gauge("platform_running_environments", "Number of running student environments")
