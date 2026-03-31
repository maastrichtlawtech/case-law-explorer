"""LIDO SQLite monthly processing."""

from .dag import dag as lido_sqlite_monthly_dag

__all__ = ['lido_sqlite_monthly_dag']
