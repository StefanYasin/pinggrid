"""
Logging configuration with rotating file handler.
"""

import logging
from logging.handlers import RotatingFileHandler


def get_logger(name, level="INFO", log_file="monitor.log", max_size_mb=5, backup_count=3):
    """Configure and return a logger with rotating file handler."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    if logger.handlers:
        return logger
    
    handler = RotatingFileHandler(
        log_file,
        maxBytes=max_size_mb * 1024 * 1024,
        backupCount=backup_count
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
    logger.addHandler(handler)
    
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s"
    ))
    logger.addHandler(console)
    
    return logger
