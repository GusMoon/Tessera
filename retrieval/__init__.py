"""Recuperación híbrida (BM25 con FTS5 + vectores con FAISS) con filtro previo de permisos y fecha."""

from retrieval.indice import Indice, Resultado
from retrieval.permisos import permisos_de

__all__ = ["Indice", "Resultado", "permisos_de"]
