"""
Oracle stub — read-only, used ONLY for pulling training data.

MAWRID never writes to Oracle.
This module is NOT called anywhere in the live pipeline.

To enable: install cx-Oracle + Oracle Instant Client, then uncomment.
"""

from __future__ import annotations
from config.settings import get_settings


class OracleStubConnection:
    """Placeholder so imports don't break before cx_Oracle is installed."""

    def execute(self, query: str, params: dict | None = None):
        raise NotImplementedError(
            "Oracle connection not configured. "
            "Install cx-Oracle and set ORACLE_DSN / ORACLE_USER / ORACLE_PASSWORD."
        )

    def fetchall(self):
        return []

    def close(self):
        pass


def get_training_connection() -> OracleStubConnection:
    """
    Return a read-only Oracle connection for training data extraction.
    Replace with real cx_Oracle.connect() when the Oracle client is available.
    """
    settings = get_settings()
    if not settings.oracle_dsn:
        return OracleStubConnection()

    # Uncomment when cx_Oracle is installed:
    # import cx_Oracle
    # return cx_Oracle.connect(
    #     user=settings.oracle_user,
    #     password=settings.oracle_password,
    #     dsn=settings.oracle_dsn,
    # )
    return OracleStubConnection()
