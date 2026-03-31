"""Cellar ETL pipeline."""

from .dag import dag as cellar_dag

__all__ = ['cellar_dag']
