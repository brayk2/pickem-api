import time

from peewee import PostgresqlDatabase
from src.config import request_context
from src.config.logger import Logger
from src.config.settings import Settings
from src.integrations.secret_service import SecretService

logger = Logger()

# A connection idle longer than this is checked with `SELECT 1` before reuse.
# Lambda freezes the container between requests, and while it is frozen Neon
# can drop the connection (compute suspend, pooler idle timeout) without the
# client knowing -- the next query then fails with "SSL connection has been
# closed unexpectedly".
_PING_AFTER_IDLE_S = 10


class LambdaPostgresqlDatabase(PostgresqlDatabase):
    """
    One connection per Lambda container, reused across requests and verified
    after idling.

    No client-side pool: a container serves one request at a time, and Neon's
    pooler endpoint already pools on the server side. peewee's pool only
    notices connections *it* closed, so it kept handing out dead ones.

    Also times every query into the request context for the request log line.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_used = 0.0

    def _connect(self):
        started = time.perf_counter()
        conn = super()._connect()
        elapsed_ms = (time.perf_counter() - started) * 1000
        ctx = request_context.current()
        if ctx is not None:
            ctx.db_connect_ms += elapsed_ms
        logger.info(
            "opened database connection",
            extra={"fields": {"db_connect_ms": round(elapsed_ms, 1)}},
        )
        return conn

    def execute_sql(self, sql, params=None, commit=None):
        started = time.perf_counter()
        try:
            return super().execute_sql(sql, params)
        finally:
            self._last_used = time.monotonic()
            ctx = request_context.current()
            if ctx is not None:
                ctx.db_ms += (time.perf_counter() - started) * 1000
                ctx.db_queries += 1

    def discard_if_dead(self) -> None:
        """Close a reused connection that is broken, so the next query reconnects."""
        if self.is_closed():
            return

        if not self.is_connection_usable():
            self.discard("connection closed or left in a failed transaction")
            return

        if time.monotonic() - self._last_used < _PING_AFTER_IDLE_S:
            return

        try:
            self._state.conn.cursor().execute("SELECT 1")
            self._last_used = time.monotonic()
        except Exception as exc:
            self.discard(f"ping failed: {exc}".strip())

    def discard(self, reason: str) -> None:
        """Drop the current connection without a clean close; the next query reconnects."""
        logger.warning(
            "discarding database connection", extra={"fields": {"reason": reason}}
        )
        try:
            self._state.conn.close()
        except Exception:
            pass
        self._state.reset()


def get_database() -> PostgresqlDatabase:
    settings = Settings()
    secret_service = SecretService()

    logger.info(f"db name = {settings.db_name}")
    secret = secret_service.get_secret("dev/db")

    return LambdaPostgresqlDatabase(
        settings.db_name,
        # Every thread shares the one connection. A container handles one
        # request at a time, and FastAPI runs sync dependencies on a worker
        # thread, which would otherwise open a second connection and leak it.
        thread_safe=False,
        host=settings.db_host,
        user=secret.get("username"),
        password=secret.get("password"),
        sslmode="require",
        connect_timeout=5,
    )
