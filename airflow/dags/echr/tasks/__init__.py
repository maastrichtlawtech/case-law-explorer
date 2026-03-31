"""ECHR ETL pipeline."""

from .dag import dag as echr_dag

__all__ = ['echr_dag']
