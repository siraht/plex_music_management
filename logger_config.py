# logger_config.py

import logging
from config import LOG_FILE

def setup_logging():
    """Configures the root logger for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s:%(levelname)s:%(message)s',
        handlers=[
            logging.FileHandler('conversion.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )