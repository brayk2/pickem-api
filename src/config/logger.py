import os
from src.util.injection import dependency
import logging


@dependency
class Logger(logging.Logger):
    def __init__(self, name: str = __name__):
        """
        Initialize the custom logger with a configuration.
        """

        log_level = os.getenv("LOG_LEVEL", logging.INFO)
        super().__init__(name=name, level=log_level)

        # Set the logging level from the config or default to DEBUG
        self.setLevel(level=log_level)

        # Create a console handler (you could add more handlers as needed)
        ch = logging.StreamHandler()
        ch.setLevel(log_level)

        # Create a formatter from config or use default
        formatter = logging.Formatter(
            "%(asctime)s - [%(levelname)s] - %(module)s.%(funcName)s:\t%(message)s"
        )
        ch.setFormatter(formatter)

        # Add the handler to the logger
        self.addHandler(ch)
