import logging

from logging_config import (
    setup_logging,
    get_logger
)

setup_logging()

logger = get_logger("SECURITY_TEST")

logger.info("Authorization: Bearer abc123secret")
logger.info("API_KEY=my-secret-api-key")
logger.info("access_token=my-access-token")
logger.info("refresh_token=my-refresh-token")
logger.info("password=my-password")
logger.info("client_secret=my-client-secret")