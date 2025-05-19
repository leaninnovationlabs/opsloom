import logging


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure global logging and return a module logger."""
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    return logging.getLogger(__name__)


# Backwards compatibility for existing imports
SetupLogging = setup_logging
