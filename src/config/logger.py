import logging


def get_logger(name: str = __name__):
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)-15s %(name)-8s %(message)s"
    )
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    return logger
