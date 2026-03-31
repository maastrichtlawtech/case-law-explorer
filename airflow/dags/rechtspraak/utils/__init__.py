"""Rechtspraak ETL pipeline."""

from .dag import dag as rechtspraak_dag

__all__ = ['rechtspraak_dag']
