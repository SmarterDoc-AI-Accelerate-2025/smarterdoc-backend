import logging
import sys

LOG_LEVEL = logging.INFO
LOG_FORMAT = "[%(levelname)s] [%(asctime)s] [%(name)s] [%(funcName)s:%(lineno)d] - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# --- 1. Create Logger Instance ---
# Use the root logger or a named logger for the application
# We use the root logger here for simplicity in a hackathon setting.
app_logger = logging.getLogger()
app_logger.setLevel(LOG_LEVEL)

# Prevent log messages from propagating to the root logger handlers multiple times
if not app_logger.handlers:
    # --- 2. Create Handler (to direct logs to the console/stdout) ---
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(LOG_LEVEL)

    # --- 3. Create Formatter ---
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    handler.setFormatter(formatter)

    # --- 4. Add Handler to Logger ---
    app_logger.addHandler(handler)

# --- 5. Export the Logger Object ---
# This is the object your other files (gemini_client.py, indexer.py) import
logger = app_logger
