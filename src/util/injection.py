import functools
from unittest.mock import MagicMock

from src.config.logger import get_logger
from src.util.dependency_cache import DependencyCache

logger = get_logger(__name__)
_attr = "__dependency__"


def dependency(cls):
    logger.info(f"marking class {cls.__name__} as a {_attr}")
    setattr(cls, _attr, True)
    return cls


def validate_init(name: str):
    if name != "__init__":
        raise ValueError("decorator must be applied to __init__ function")


def inject(f):
    @functools.wraps(f)
    def inner(*args, mock: bool = False, **kwargs):
        validate_init(name=f.__name__)

        for attr, annot in f.__annotations__.items():
            if hasattr(annot, _attr):
                if mock:
                    logger.info(f"mocking dependency: {attr}")
                    kwargs[attr] = MagicMock()
                else:
                    kwargs[attr] = kwargs.get(attr, DependencyCache.get(dep=annot))
            else:
                logger.info(f"{annot} is not {_attr}")
        return f(*args, **kwargs)

    return inner
