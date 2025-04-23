import logging

def SetupLogging():
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Configure SQLAlchemy logging for PostgreSQL queries
    sqlalchemy_engine_logger = logging.getLogger("sqlalchemy.engine")
    sqlalchemy_engine_logger.setLevel(logging.INFO)
    
    return logging.getLogger(__name__)