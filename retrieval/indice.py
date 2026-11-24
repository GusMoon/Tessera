"""Índice híbrido: BM25 (FTS5 de SQLite) + vectores (FAISS), fusionados con RRF.

Regla 6 de CLAUDE.md: los permisos del usuario, el tipo de fuente y la fecha se resuelven con SQL **antes** de
buscar; tanto FTS5 como FAISS solo ven los fragmentos permitidos. Nunca se busca primero y se filtra después.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

import faiss
import numpy as np

from retrieval.embeddings import Embedder, normalizar_texto
from retrieval.permisos import permisos_de

K_RRF = 60  # constante clásica de Reciprocal Rank Fusion
PALABRAS_VACIAS = frozenset("de del la las el los un una unos unas y e o en a al con para por que se su sus lo".split())


@dataclass(frozen=True)
class Fragmento:
    id: int
    fuente_id: int
    tipo: str
    ref: str
    titulo: str
    texto: str
    permiso: str
    fecha: str | None


@dataclass
class Resultado:
    fragmento: Fragmento | None
    puntaje: float  # RRF
    rangos: dict[str, int] = field(default_factory=dict)  # 'bm25' y/o 'vector' (1 = mejor)


def tokens_busqueda(texto: str) -> list[str]:
    """Palabras significativas de una consulta (sin acentos ni palabras vacías), en orden y sin repetir."""
    vistos: list[str] = []
    for t in re.findall(r"[a-z0-9]+", normalizar_texto(texto)):
        if t not in PALABRAS_VACIAS and t not in vistos:
            vistos.append(t)
    return vistos


class Indice:
    def __init__(self, embedder: Embedder, ids: np.ndarray, vectores: np.ndarray):
        self.embedder = embedder
        self.ids = ids.astype(np.int64)
        self.vectores = vectores.astype(np.float32)
        self._faiss = faiss.IndexIDMap(faiss.IndexFlatIP(embedder.dimension))
        if len(self.ids):
            self._faiss.add_with_ids(self.vectores, self.ids)

    # ------------------------------------------------------------------ construcción y persistencia
    @classmethod
    def construir(cls, conn: sqlite3.Connection, embedder: Embedder) -> "Indice":
        filas = conn.execute("SELECT id, texto FROM fragmentos ORDER BY id").fetchall()
        ids = np.array([f["id"] for f in filas], dtype=np.int64)
        vectores = embedder.codificar([f["texto"] for f in filas], "passage")
        return cls(embedder, ids, vectores)

    def guardar(self, carpeta: Path) -> None:
        carpeta.mkdir(parents=True, exist_ok=True)
        np.save(carpeta / "ids.npy", self.ids)
        np.save(carpeta / "vectores.npy", self.vectores)
        (carpeta / "meta.json").write_text(
            json.dumps({"embedder": self.embedder.nombre, "dimension": self.embedder.dimension, "fragmentos": int(len(self.ids))}),
            encoding="utf-8",
        )

    @classmethod
    def cargar(cls, carpeta: Path, embedder: Embedder, conn: sqlite3.Connection) -> "Indice | None":
        """Devuelve el índice guardado o None si no existe o ya no corresponde a la base (otro embedder, otros ids)."""
        try:
            meta = json.loads((carpeta / "meta.json").read_text(encoding="utf-8"))
            ids = np.load(carpeta / "ids.npy")
            vectores = np.load(carpeta / "vectores.npy")
        except (OSError, ValueError):
            return None
        if meta.get("embedder") != embedder.nombre or meta.get("dimension") != embedder.dimension:
            return None
        en_base = [f[0] for f in conn.execute("SELECT id FROM fragmentos ORDER BY id")]
        if en_base != ids.tolist():
            return None
        return cls(embedder, ids, vectores)

    # ------------------------------------------------------------------ búsqueda
    def codificar_consultas(self, consultas: list[str]) -> np.ndarray:
        return self.embedder.codificar(consultas, "query")

    def buscar(
        self,
        conn: sqlite3.Connection,
        consulta: str,
        usuario_id: str,
        k: int = 5,
        tipos: tuple[str, ...] | None = None,
        desde: str | None = None,
        vector: np.ndarray | None = None,
    ) -> list[Resultado]:
        """Top-`k` fragmentos que `usuario_id` puede abrir. `desde` (ISO) descarta datos más viejos; los fragmentos
        sin fecha se conservan. `vector` permite reutilizar la consulta ya codificada (por lote)."""
        permisos = sorted(permisos_de(usuario_id, conn))
        sql = f"SELECT id FROM fragmentos WHERE permiso IN ({','.join('?' * len(permisos))})"
        parametros: list = list(permisos)
        if tipos:
            sql += f" AND tipo IN ({','.join('?' * len(tipos))})"
            parametros += list(tipos)
        if desde:
            sql += " AND (fecha IS NULL OR fecha >= ?)"
            parametros.append(desde)
        permitidos = [f[0] for f in conn.execute(sql, parametros)]
        if not permitidos:
            return []

        n = max(k * 4, 20)
        fusion: dict[int, Resultado] = {}
        for nombre, lista in (
            ("bm25", self._bm25(conn, consulta, permitidos, n)),
            ("vector", self._vectorial(consulta, permitidos, n, vector)),
        ):
            for pos, fid in enumerate(lista, start=1):
                r = fusion.setdefault(fid, Resultado(fragmento=None, puntaje=0.0))
                r.puntaje += 1.0 / (K_RRF + pos)
                r.rangos[nombre] = pos
        mejores = sorted(fusion.items(), key=lambda kv: (-kv[1].puntaje, kv[0]))[:k]
        detalle = self._fragmentos(conn, [fid for fid, _ in mejores])
        for fid, r in mejores:
            r.fragmento = detalle[fid]
        return [r for _, r in mejores]

    def _bm25(self, conn: sqlite3.Connection, consulta: str, permitidos: list[int], n: int) -> list[int]:
        tokens = tokens_busqueda(consulta)
        if not tokens:
            return []
        expresion = " OR ".join(f'"{t}"' for t in tokens)
        filas = conn.execute(
            """SELECT rowid FROM fragmentos_fts
               WHERE fragmentos_fts MATCH ? AND rowid IN (SELECT value FROM json_each(?))
               ORDER BY bm25(fragmentos_fts) LIMIT ?""",
            (expresion, json.dumps(permitidos), n),
        ).fetchall()
        return [f[0] for f in filas]

    def _vectorial(self, consulta: str, permitidos: list[int], n: int, vector: np.ndarray | None) -> list[int]:
        if not len(self.ids):
            return []
        q = vector if vector is not None else self.codificar_consultas([consulta])
        q = np.asarray(q, dtype=np.float32).reshape(1, -1)
        parametros = faiss.SearchParameters()
        parametros.sel = faiss.IDSelectorBatch(np.asarray(permitidos, dtype=np.int64))
        _, ids = self._faiss.search(q, min(n, len(permitidos)), params=parametros)
        return [int(i) for i in ids[0] if i != -1]

    @staticmethod
    def _fragmentos(conn: sqlite3.Connection, ids: list[int]) -> dict[int, Fragmento]:
        filas = conn.execute(
            "SELECT id, fuente_id, tipo, ref, titulo, texto, permiso, fecha FROM fragmentos WHERE id IN (SELECT value FROM json_each(?))",
            (json.dumps(ids),),
        ).fetchall()
        return {f["id"]: Fragmento(**{c: f[c] for c in f.keys()}) for f in filas}
