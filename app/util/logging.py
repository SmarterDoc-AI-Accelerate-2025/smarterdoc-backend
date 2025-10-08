# app/util/logging.py

import logging
import sys

# Define configuration constants outside the function
LOG_LEVEL = logging.INFO
LOG_FORMAT = "[%(levelname)s] [%(asctime)s] [%(name)s] [%(funcName)s:%(lineno)d] - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Global logger object, defined only after setup runs
logger = None


def setup_logging():
    """
    Sets up the application logger and makes the configured logger available 
    for the entire application.
    """
    global logger

    # 1. Create Logger Instance
    app_logger = logging.getLogger()
    app_logger.setLevel(LOG_LEVEL)

    # 2. Prevent setting up multiple times
    if app_logger.handlers:
        logger = app_logger
        return

    # 3. Create Handler (to direct logs to the console/stdout)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(LOG_LEVEL)

    # 4. Create Formatter
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    handler.setFormatter(formatter)

    # 5. Add Handler and Export
    app_logger.addHandler(handler)
    logger = app_logger  # Export the configured logger object


# Call setup immediately when the module is imported
# This ensures the logger object is ready for use by other modules
setup_logging()
