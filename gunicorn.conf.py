# Gunicorn configuration file for BLU Suite EMS
import multiprocessing
import os

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes
workers = min(multiprocessing.cpu_count() * 2 + 1, 4)  # Cap at 4 for 2 GB RAM
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
preload_app = True
timeout = 120
keepalive = 2

# Logging
accesslog = "/opt/blusuite/logs/access.log"
errorlog = "/opt/blusuite/logs/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'blu_suite_ems'

# Server mechanics
daemon = False
pidfile = '/tmp/gunicorn.pid'
user = None
group = None
tmp_upload_dir = None

# SSL (if needed)
keyfile = None
certfile = None

# Security
limit_request_line = 4096       # Must not be 0 (disables request-line length check)
limit_request_fields = 100
limit_request_field_size = 8190


def post_fork(server, worker):
    """Warm up DB connection after worker fork to avoid cold-start 502s"""
    try:
        from django.db import connection
        connection.ensure_connection()
    except Exception:
        pass
