from src.config.logger import Logger
from src.lambdas.utils import connect_db

logger = Logger()


@connect_db
def handle_event(event, context):
    pass
