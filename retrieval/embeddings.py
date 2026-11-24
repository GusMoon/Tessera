"""Embeddings para la búsqueda semántica.

- `EmbedderE5`: `intfloat/multilingual-e5-small` (MIT) con sentence-transformers. Es el que se mide en el Hito 2.
- `EmbedderHash`: n-gramas de caracteres con hashing en NumPy. Determinista, sin descargas ni red. Solo para
  pruebas unitarias y como respaldo; entiende poco de sinónimos. Todo reporte debe declarar cuál se usó.

Elección con la variable `TESSERA_EMBEDDER` (`e5` por defecto, o `hash`).
"""

from __future__ import annotations

import os
import re
import unicodedata
import zlib
from typing import Protocol

import numpy as np

MODELO_E5 = "intfloat/multilingual-e5-small"


def normalizar_texto(texto: str) -> str:
    """Minúsculas y sin acentos, para comparar y tokenizar de forma estable."""
    sin_acentos = "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", sin_acentos).strip()


class Embedder(Protocol):
    nombre: str
    dimension: int

    def codificar(self, textos: list[str], tipo: str = "passage") -> np.ndarray:
        """Vectores float32 normalizados (filas). `tipo` es 'query' o 'passage' (e5 los trata distinto)."""
        ...


class EmbedderHash:
    nombre = "hash-ngramas"

    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def _vector(self, texto: str) -> np.ndarray:
        v = np.zeros(self.dimension, dtype=np.float32)
        t = normalizar_texto(texto)
        rasgos = [f"w:{p}" for p in re.findall(r"[a-z0-9/.]+", t)]
        relleno = f" {t} "
        for n in (3, 4):
            rasgos += [f"c{n}:{relleno[i:i + n]}" for i in range(len(relleno) - n + 1)]
        for r in rasgos:
            h = zlib.crc32(r.encode("utf-8"))
            v[h % self.dimension] += 1.0 if (h >> 16) & 1 else -1.0
        norma = np.linalg.norm(v)
        return v / norma if norma else v

    def codificar(self, textos: list[str], tipo: str = "passage") -> np.ndarray:
        if not textos:
            return np.zeros((0, self.dimension), dtype=np.float32)
        return np.vstack([self._vector(t) for t in textos]).astype(np.float32)


class EmbedderE5:
    nombre = MODELO_E5

    def __init__(self, modelo: str = MODELO_E5):
        from sentence_transformers import SentenceTransformer  # import perezoso: torch tarda en cargar

        self._modelo = SentenceTransformer(modelo, device="cpu")
        self.dimension = int(self._modelo.get_sentence_embedding_dimension())

    def codificar(self, textos: list[str], tipo: str = "passage") -> np.ndarray:
        if not textos:
            return np.zeros((0, self.dimension), dtype=np.float32)
        prefijo = "query: " if tipo == "query" else "passage: "
        vectores = self._modelo.encode([prefijo + t for t in textos], normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vectores, dtype=np.float32)


def crear_embedder(nombre: str | None = None) -> Embedder:
    """`e5` (defecto) o `hash`. Lee `TESSERA_EMBEDDER` si no se indica."""
    elegido = (nombre or os.environ.get("TESSERA_EMBEDDER") or "e5").strip().lower()
    if elegido == "hash":
        return EmbedderHash()
    if elegido == "e5":
        return EmbedderE5()
    raise ValueError(f"TESSERA_EMBEDDER no válido: {elegido!r}. Valores: e5, hash.")
