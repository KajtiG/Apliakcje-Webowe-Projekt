import os

bind = "0.0.0.0:8000"
workers = int(os.environ.get("WEB_CONCURRENCY", "3"))
timeout = 60

# Logi na stdout/stderr -> Container Apps zbiera je do Log Analytics
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
# Prawdziwy IP klienta z Application Gateway (X-Forwarded-For)
access_log_format = '%({x-forwarded-for}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(a)s" %(L)ss'


def post_fork(server, worker):
    """Application Insights - włączane tylko gdy ustawiono connection string.

    Wywołanie w post_fork (a nie w wsgi.py), bo OpenTelemetry nie lubi forka po inicjalizacji.
    """
    if os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        from azure.monitor.opentelemetry import configure_azure_monitor
        configure_azure_monitor()
