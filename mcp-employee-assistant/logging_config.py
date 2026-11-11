import logging
import re
from pathlib import Path
from logging.handlers import RotatingFileHandler


# ==================================================
# 1. PROJECT DIRECTORIES
# ==================================================

BASE_DIR = Path(__file__).resolve().parent

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / "application.log"


# ==================================================
# 2. SENSITIVE DATA MASKING FILTER
# ==================================================

class SensitiveDataFilter(logging.Filter):

    PATTERNS = [
        # Bearer tokens
        (
            re.compile(
                r"(?i)(Bearer\s+)[A-Za-z0-9._~+/=-]+"
            ),
            r"\1[MASKED]"
        ),

        # API keys
        (
            re.compile(
                r"(?i)(api[_-]?key\s*[=:]\s*)[^\s,;]+"
            ),
            r"\1[MASKED]"
        ),

        # Access tokens
        (
            re.compile(
                r"(?i)(access[_-]?token\s*[=:]\s*)[^\s,;]+"
            ),
            r"\1[MASKED]"
        ),

        # Refresh tokens
        (
            re.compile(
                r"(?i)(refresh[_-]?token\s*[=:]\s*)[^\s,;]+"
            ),
            r"\1[MASKED]"
        ),

        # Passwords
        (
            re.compile(
                r"(?i)(password\s*[=:]\s*)[^\s,;]+"
            ),
            r"\1[MASKED]"
        ),

        # Client secrets
        (
            re.compile(
                r"(?i)(client[_-]?secret\s*[=:]\s*)[^\s,;]+"
            ),
            r"\1[MASKED]"
        ),
    ]

    def filter(self, record):

        message = record.getMessage()

        for pattern, replacement in self.PATTERNS:

            message = pattern.sub(
                replacement,
                message
            )

        record.msg = message
        record.args = ()

        return True


# ==================================================
# 3. CENTRALIZED LOGGING CONFIGURATION
# ==================================================

def setup_logging():

    log_format = (
        "%(asctime)s | "
        "%(levelname)s | "
        "%(name)s | "
        "%(message)s"
    )

    formatter = logging.Formatter(log_format)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Rotating file handler
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=5
    )

    file_handler.setFormatter(formatter)

    # Apply sensitive-data masking
    sensitive_filter = SensitiveDataFilter()

    console_handler.addFilter(sensitive_filter)
    file_handler.addFilter(sensitive_filter)

    # Root logger configuration
    root_logger = logging.getLogger()

    root_logger.setLevel(logging.INFO)

    # Avoid duplicate handlers
    if not root_logger.handlers:

        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)


# ==================================================
# 4. GET LOGGER
# ==================================================

def get_logger(name):

    return logging.getLogger(name)