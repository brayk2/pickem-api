import bcrypt

from src.config.logger import Logger

logger = Logger()


class PasswordManager:
    @staticmethod
    def hash_password(password: str):
        logger.info("hashing password")
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    @staticmethod
    def verify_password(password: str, hashed_password: str):
        logger.info("verifying password")
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
