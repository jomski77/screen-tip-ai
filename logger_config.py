"""
Logger Configuration Module for Screen Tip AI.

Provides proper, production-grade logging with full ISO dates, timestamps, 
module names, source line numbers, log rotation (RotatingFileHandler), 
and dual output to both console (stdout) and persistent log file.
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler

# Log Directory & File Path (~/.screen_tip_ai/screen_tip_ai.log)
LOG_DIR = os.path.expanduser("~/.screen_tip_ai")
LOG_FILE_PATH = os.path.join(LOG_DIR, "screen_tip_ai.log")


def get_logger(name: str = "ScreenTipAI") -> logging.Logger:
    """
    Configure and return a structured logger with full dates, timestamps,
    source line numbers, and rotating log file management.
    
    Args:
        name (str): Name of the logger component.
        
    Returns:
        logging.Logger: Configured logger instance.
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Prevent duplicate handlers if get_logger is called multiple times
    if logger.handlers:
        return logger

    # Proper production log format with date, time, millisecond, level, module, line number
    log_format = "%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)-20s | %(filename)s:%(lineno)-4d | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    formatter = logging.Formatter(fmt=log_format, datefmt=date_format)

    # 1. Console Output Handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    # 2. Persistent Rotating File Handler (5 MB limit, 5 backup files)
    file_handler = RotatingFileHandler(
        LOG_FILE_PATH,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)

    return logger
