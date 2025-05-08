# Prometheus Integration in Langflow

This document explains how Prometheus monitoring is integrated into Langflow, including the metrics server implementation, configuration options, and available metrics.

## Overview

Langflow includes a comprehensive metrics collection system built on [OpenTelemetry](https://opentelemetry.io/) and [Prometheus](https://prometheus.io/). This integration allows you to monitor various aspects of your Langflow deployment, including application performance and usage statistics.

The metrics system is designed to be flexible, supporting two deployment modes:
- **Inline mode**: Metrics are exposed on the main FastAPI application
- **Separate mode**: Metrics are served on a dedicated port by a separate server

## Configuration Options

### Environment Variables

The Prometheus integration can be configured using the following environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `LANGFLOW_PROMETHEUS_ENABLED` | Enable/disable Prometheus metrics | `false` |
| `LANGFLOW_PROMETHEUS_PORT` | Port for the Prometheus metrics server (separate mode) | `9090` |
| `LANGFLOW_METRICS_PORT_MODE` | Mode for serving metrics (`inline` or `separate`) | `inline` |
| `LANGFLOW_METRICS_HOST` | Host address for the metrics server (separate mode) | `0.0.0.0` |
| `LANGFLOW_METRICS_LOG_LEVEL` | Log level for the metrics server | `warning` |

### Configuration in Settings

These settings are defined in the `Settings` class in `services/settings/base.py`:

```python
prometheus_enabled: bool = False
"""If set to True, Langflow will expose Prometheus metrics."""
prometheus_port: int = 9090
"""The port on which Langflow will expose Prometheus metrics. 9090 is the default port."""
```

## Implementation Details

### Metrics Server

The metrics server is implemented in the `TelemetryService` class in `services/telemetry/service.py`. Key components:

1. **Metrics Server Initialization**:
   ```python
   if (self.settings_service.settings.prometheus_enabled
       and os.getenv("LANGFLOW_METRICS_PORT_MODE") == "separate"
       and not self._metrics_server_started):
       # Start metrics server
       self.start_metrics_server()
   ```

2. **Metrics Server Implementation**:
   ```python
   def start_metrics_server(self) -> None:
       """Start Prometheus metrics server on a separate port if configured."""
       port = self.settings_service.settings.prometheus_port
       host = os.getenv("LANGFLOW_METRICS_HOST", "0.0.0.0")
       log_level = os.getenv("LANGFLOW_METRICS_LOG_LEVEL", "warning")

       metrics_app = make_asgi_app()

       def run_metrics_server():
           logger.info(f"Starting Prometheus metrics server at http://{host}:{port}/metrics")
           uvicorn.run(
               metrics_app,
               host=host,
               port=port,
               log_level=log_level,
               access_log=False,
               timeout_keep_alive=5,
           )

       self._metrics_thread = threading.Thread(
           target=run_metrics_server,
           name="PrometheusMetricsServer",
           daemon=True,
       )
       self._metrics_thread.start()
       self._metrics_server_started = True
   ```

### Metrics Definition

Metrics are defined in the `OpenTelemetry` class in `services/telemetry/opentelemetry.py`. The class implements a thread-safe singleton pattern to manage metrics and provides methods for incrementing counters, updating gauges, and observing histograms.

Key metrics defined:
- `file_uploads`: Tracks the uploaded file size in bytes
- `num_files_uploaded`: Counts the number of files uploaded
- `fastapi_version`: Reports the FastAPI version as a gauge
- `langflow_version`: Reports the Langflow version as a gauge

### FastAPI Integration

The metrics are integrated with the FastAPI application in `main.py`:

```python
# Initialize configuration
if settings.prometheus_enabled:
    if metrics_mode == "inline":
        from prometheus_client import make_asgi_app
        logger.debug("Mounting Prometheus /metrics endpoint on main FastAPI app")
        app.mount("/metrics", make_asgi_app())
    elif metrics_mode == "separate":
        logger.debug("Prometheus metrics will be served on a separate port by the TelemetryService")
    else:
        logger.warning(f"Unknown LANGFLOW_METRICS_PORT_MODE='{metrics_mode}', defaulting to 'inline'")
        from prometheus_client import make_asgi_app
        app.mount("/metrics", make_asgi_app())

# Instrument the FastAPI application
FastAPIInstrumentor.instrument_app(app, excluded_urls="health,health_check")
```

## Docker Deployment

When deploying with Docker Compose, Prometheus is configured as a separate service. The configuration file is located at `deploy/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: prometheus
    static_configs:
      - targets: ["prometheus:9090"]
  - job_name: flower
    static_configs:
      - targets: ["flower:5555"]
```

The Docker Compose configuration in `deploy/docker-compose.yml` includes:

```yaml
prometheus:
  image: prom/prometheus:v2.37.9
  env_file:
    - .env
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml
  command:
    - "--config.file=/etc/prometheus/prometheus.yml"
  deploy:
    labels:
      - traefik.enable=true
      - traefik.constraint-label-stack=${TRAEFIK_TAG?Variable not set}
      - traefik.http.routers.${STACK_NAME?Variable not set}-prometheus-http.rule=PathPrefix(`/metrics`)
      - traefik.http.services.${STACK_NAME?Variable not set}-prometheus.loadbalancer.server.port=9090
```

A Grafana service is also included for visualizing the metrics.

## Available Metrics

### System Metrics

- **FastAPI Version**: Gauge showing the FastAPI version used by Langflow
  ```
  # HELP fastapi_version The FastAPI version.
  # TYPE fastapi_version gauge
  fastapi_version{version="0.115.11"} 1.0
  ```

- **Langflow Version**: Gauge showing the version of Langflow being run
  ```
  # HELP langflow_version The Langflow app version.
  # TYPE langflow_version gauge
  langflow_version{version="1.2.0"} 1.0
  ```

- **Python Information**: Details about the Python environment
  ```
  # HELP python_info Python platform information
  # TYPE python_info gauge
  python_info{implementation="CPython",major="3",minor="12",patchlevel="9",version="3.12.9"} 1.0
  ```

- **Target Information**: Metadata about the service and telemetry SDK
  ```
  # HELP target_info Target metadata
  # TYPE target_info gauge
  target_info{service_name="langflow",telemetry_sdk_language="python",telemetry_sdk_name="opentelemetry",telemetry_sdk_version="1.31.0"} 1.0
  ```

### Usage Metrics

- **File Uploads**: Tracks the size of uploaded files in bytes
- **Number of Files Uploaded**: Counts the total number of file uploads

### Python Runtime Metrics

- **Garbage Collection Statistics**:
  ```
  # HELP python_gc_objects_collected_total Objects collected during gc
  # TYPE python_gc_objects_collected_total counter
  python_gc_objects_collected_total{generation="0"} 210266.0
  python_gc_objects_collected_total{generation="1"} 82767.0
  python_gc_objects_collected_total{generation="2"} 37889.0

  # HELP python_gc_objects_uncollectable_total Uncollectable objects found during GC
  # TYPE python_gc_objects_uncollectable_total counter
  python_gc_objects_uncollectable_total{generation="0"} 0.0
  python_gc_objects_uncollectable_total{generation="1"} 0.0
  python_gc_objects_uncollectable_total{generation="2"} 0.0

  # HELP python_gc_collections_total Number of times this generation was collected
  # TYPE python_gc_collections_total counter
  python_gc_collections_total{generation="0"} 5836.0
  python_gc_collections_total{generation="1"} 530.0
  python_gc_collections_total{generation="2"} 19.0
  ```

### FastAPI/HTTP Metrics

The FastAPI instrumentation automatically adds:

- **Active Requests**: Current number of active HTTP requests
  ```
  # HELP http_server_active_requests Number of active HTTP server requests.
  # TYPE http_server_active_requests gauge
  http_server_active_requests{http_flavor="1.1",http_host="127.0.0.1:7860",http_method="POST",http_scheme="http",http_server_name="127.0.0.1:7860"} 0.0
  ```

- **Request Duration**: Histogram of HTTP request durations in milliseconds
  ```
  # HELP http_server_duration_milliseconds Measures the duration of inbound HTTP requests.
  # TYPE http_server_duration_milliseconds histogram
  ```

- **Request Size**: Histogram of HTTP request sizes in bytes
  ```
  # HELP http_server_request_size_bytes Measures the size of HTTP request messages (compressed).
  # TYPE http_server_request_size_bytes histogram
  ```

- **Response Size**: Histogram of HTTP response sizes in bytes
  ```
  # HELP http_server_response_size_bytes measures the size of HTTP response messages (compressed).
  # TYPE http_server_response_size_bytes histogram
  ```

## Accessing Metrics

### Direct Access

In inline mode, metrics are accessible at:
```
http://your-langflow-instance/metrics
```

In separate mode, metrics are accessible at:
```
http://your-langflow-instance:9090/metrics
```

## Best Practices

1. **Production Deployments**: For production deployments, it's recommended to use the separate mode to isolate the metrics server from the main application.

2. **Security**: In production environments, consider configuring authentication for accessing metrics and using a reverse proxy to control access.

3. **Custom Metrics**: To add custom metrics, you can extend the `OpenTelemetry` class in your own extensions.

4. **Resource Usage**: Monitoring can add some overhead. If you're running in a resource-constrained environment, be mindful of the additional memory and CPU usage.
