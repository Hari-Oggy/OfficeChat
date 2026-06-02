# -*- coding: utf-8 -*-
# =============================================================================
# logger.py — Centralized logging utility for Neuro AI
# =============================================================================

import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler

_logger = None

def get_logger():
    """Initialize and return the centralized rotating file logger."""
    global _logger
    if _logger is not None:
        return _logger

    # Find the optimal log directory (same as config.json)
    if os.name == 'nt':
        base_dir = Path(os.environ.get("APPDATA", os.path.expanduser("~")))
    else:
        base_dir = Path(os.path.expanduser("~"))

    log_dir = base_dir / ".neuro_ai" / "logs"
    
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        # Try to restrict directory permissions
        if os.name != 'nt':
            try:
                log_dir.chmod(0o700)
            except Exception:
                pass
    except Exception:
        # Fallback to tmp if we literally cannot write to home directory
        import tempfile
        log_dir = Path(tempfile.gettempdir()) / "neuro_ai_logs"
        log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "neuro_ai.log"

    _logger = logging.getLogger("NeuroAI")
    _logger.setLevel(logging.DEBUG)  # Capture everything; handlers filter it

    # Console Handler (useful if started from terminal)
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)

    # Rotating File Handler (max 2MB per file, keep 3 backups)
    try:
        fh = RotatingFileHandler(str(log_file), maxBytes=2*1024*1024, backupCount=3, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
    except Exception:
        fh = logging.NullHandler()

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
    ch.setFormatter(formatter)
    fh.setFormatter(formatter)

    _logger.addHandler(ch)
    _logger.addHandler(fh)

    _logger.info("Neuro AI Logger Initialized.")
    return _logger

def log_info(msg):
    get_logger().info(msg)

def log_error(msg, exc_info=False):
    get_logger().error(msg, exc_info=exc_info)

def log_warning(msg):
    get_logger().warning(msg)

def log_debug(msg):
    get_logger().debug(msg)
