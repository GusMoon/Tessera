"""Servidor Backend FastAPI para el proyecto TESSERA (Hito 1 · Rol A).

Endpoints:
- POST /api/fuentes/subir: Subida y procesamiento automático de archivos (CSV, XLSX, PDF).
- GET  /api/fuentes: Listado de fuentes registradas y conteos (leídas, guardadas, rechazadas, omitidas).
- GET  /api/fuentes/rechazos: Listado de todas las filas defectuosas rechazadas y sus motivos.
- GET  /api/fuentes/{fuente_id}/rechazos: Rechazos específicos de una fuente.
- POST /api/fuentes/cargar-dataset-sintetico: Carga en lote del dataset sintético para demostración.
- GET  /api/health: Estado de salud del servicio.
"""

import sys
import os
from pathlib import Path
from typing import List, Optional

# Asegurar que el directorio raíz del proyecto esté en sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from db.database import get_connection, init_db
from ingest.servicio import procesar_archivo

app = FastAPI(
    title="TESSERA API",
    description="Backend local de cotizaciones con IA · Hito 1: Ingesta de datos",
    version="0.1.0"
)

# Habilitar CORS para el frontend en Vite (localhost:5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Modelos Pydantic
class FuenteResumen(BaseModel):
    id: int
    nombre: str
    tipo: str
    estado: str
    leidas: int
    guardadas: int
    rechazadas: int
    omitidas: int
    motivo: Optional[str] = None
    fecha_carga: str


class RechazoItem(BaseModel):
    id: int
    fuente_id: Optional[int] = None
    archivo: str
    fila_numero: Optional[int] = None
    campo: Optional[str] = None
    valor_crudo: Optional[str] = None
    motivo: str
    fecha: str


class RespuestaCarga(BaseModel):
    ok: bool
    mensaje: str
    fuente: Optional[FuenteResumen] = None


@app.on_event("startup")
def startup_event():
    """Verifica e inicializa la base de datos al arrancar si no existe."""
    init_db(reset=False)


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "app": "TESSERA API",
        "hito": "Hito 1 · Datos e Ingesta",
        "modo": "Local $0 MXN"
    }


@app.get("/api/fuentes", response_model=List[FuenteResumen])
def listar_fuentes():
    """Devuelve todas las fuentes procesadas con sus conteos de filas."""
    conn = get_connection()
    try:
        cur = conn.execute(
            """SELECT 
                   id, nombre, tipo, estado, 
                   filas_leidas as leidas, 
                   filas_guardadas as guardadas, 
                   filas_rechazadas as rechazadas, 
                   filas_omitidas as omitidas, 
                   motivo, fecha_carga
               FROM fuentes 
               ORDER BY id DESC"""
        )
        filas = cur.fetchall()
        return [FuenteResumen(**dict(f)) for f in filas]
    finally:
        conn.close()


@app.post("/api/fuentes/subir", response_model=RespuestaCarga)
async def subir_fuente(file: UploadFile = File(...)):
    """
    Sube y procesa inmediatamente un archivo (CSV, XLSX o PDF).
    Valida, guarda válidas en SQLite y registra rechazos con motivo legible.
    """
    nombre = file.filename
    if not nombre:
        raise HTTPException(status_code=400, detail="Nombre de archivo no válido")

    try:
        contenido = await file.read()
        res = procesar_archivo(contenido, nombre)
        
        # Consultar la fuente creada para responder con formato homogéneo
        conn = get_connection()
        try:
            cur = conn.execute(
                """SELECT 
                       id, nombre, tipo, estado, 
                       filas_leidas as leidas, 
                       filas_guardadas as guardadas, 
                       filas_rechazadas as rechazadas, 
                       filas_omitidas as omitidas, 
                       motivo, fecha_carga
                   FROM fuentes WHERE id = ?""",
                (res["fuente_id"],)
            )
            fila = cur.fetchone()
            fuente_obj = FuenteResumen(**dict(fila)) if fila else None
        finally:
            conn.close()

        return RespuestaCarga(
            ok=True,
            mensaje=f"Archivo '{nombre}' procesado: {res['guardadas']} guardadas, {res['rechazadas']} rechazadas.",
            fuente=fuente_obj
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar archivo: {str(e)}")


@app.get("/api/fuentes/rechazos", response_model=List[RechazoItem])
def listar_rechazos(archivo: Optional[str] = Query(None)):
    """Lista todas las filas defectuosas rechazadas y sus motivos legibles."""
    conn = get_connection()
    try:
        if archivo:
            cur = conn.execute(
                """SELECT id, fuente_id, archivo, fila_numero, campo, valor_crudo, motivo, fecha
                   FROM rechazos WHERE archivo = ? ORDER BY id ASC""",
                (archivo,)
            )
        else:
            cur = conn.execute(
                """SELECT id, fuente_id, archivo, fila_numero, campo, valor_crudo, motivo, fecha
                   FROM rechazos ORDER BY id ASC"""
            )
        return [RechazoItem(**dict(r)) for r in cur.fetchall()]
    finally:
        conn.close()


@app.get("/api/fuentes/{fuente_id}/rechazos", response_model=List[RechazoItem])
def listar_rechazos_fuente(fuente_id: int):
    """Lista los rechazos asociados a una fuente específica."""
    conn = get_connection()
    try:
        cur = conn.execute(
            """SELECT id, fuente_id, archivo, fila_numero, campo, valor_crudo, motivo, fecha
               FROM rechazos WHERE fuente_id = ? ORDER BY id ASC""",
            (fuente_id,)
        )
        return [RechazoItem(**dict(r)) for r in cur.fetchall()]
    finally:
        conn.close()


@app.post("/api/fuentes/cargar-dataset-sintetico")
def cargar_dataset_sintetico():
    """
    Carga automáticamente todo el dataset sintético (CSV, XLSX y los 10 PDFs)
    desde el disco para demostración instantánea sin intervención manual.
    """
    dir_synthetic = ROOT_DIR / "data" / "synthetic"
    ruta_csv = dir_synthetic / "catalogo_materiales.csv"
    ruta_xlsx = dir_synthetic / "historial_cotizaciones.xlsx"
    dir_fichas = dir_synthetic / "fichas_tecnicas"

    if not ruta_csv.exists() or not ruta_xlsx.exists():
        raise HTTPException(
            status_code=404, 
            detail="Dataset sintético no generado. Ejecute primero data/synthetic/generar_datos.py"
        )

    archivos = [ruta_csv, ruta_xlsx]
    archivos.extend(sorted(list(dir_fichas.glob("*.pdf"))))

    conn = get_connection()
    procesados = []
    try:
        for arch in archivos:
            res = procesar_archivo(arch, arch.name, conn=conn)
            procesados.append(res)
    finally:
        conn.close()

    total_guardadas = sum(p["guardadas"] for p in procesados)
    total_rechazadas = sum(p["rechazadas"] for p in procesados)

    return {
        "ok": True,
        "mensaje": f"Dataset sintético cargado: {len(procesados)} archivos procesados ({total_guardadas} guardadas, {total_rechazadas} rechazadas).",
        "archivos_procesados": len(procesados),
        "total_guardadas": total_guardadas,
        "total_rechazadas": total_rechazadas
    }


@app.post("/api/fuentes/limpiar")
def limpiar_base():
    """Vacía todas las tablas de ingesta en la base de datos SQLite sin tocar el código."""
    init_db(reset=True)
    return {"ok": True, "mensaje": "Base de datos vaciada con éxito. Pantalla lista para demostración."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)
