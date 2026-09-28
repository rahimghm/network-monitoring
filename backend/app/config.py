import os
from dotenv import load_dotenv

load_dotenv()  # charge automatiquement le fichier .env s'il existe

DB_CONFIG = {
    # Docker Compose injects DB_HOST=db; local development can set DB_HOST=localhost.
    "host": os.getenv("DB_HOST", "db"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("DB_NAME", "monitoring"),
    "user": os.getenv("DB_USER", "monitor_user"),
    "password": os.getenv("DB_PASSWORD", "changeme"),
}

SNMP_TIMEOUT = float(os.getenv("SNMP_TIMEOUT", 3))
SNMP_RETRIES = int(os.getenv("SNMP_RETRIES", 1))
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", 20))
HOSTNAME_CACHE_TTL_SECONDS = int(os.getenv("HOSTNAME_CACHE_TTL_SECONDS", 60))
