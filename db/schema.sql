-- Esquema SQLite para Tessera (Hito 1: Entrada y Datos)
-- Compatible con SQLite 3.x, sin extensiones externas ni licencias restrictivas.

PRAGMA foreign_keys = ON;

-- 1. Registro de fuentes cargadas (archivos procesados)
CREATE TABLE IF NOT EXISTS fuentes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT UNIQUE NOT NULL,
    tipo TEXT NOT NULL,                   -- 'CSV', 'Excel', 'PDF'
    hash_archivo TEXT,
    tamano_bytes INTEGER DEFAULT 0,
    estado TEXT NOT NULL DEFAULT 'Procesando', -- 'Listo', 'Procesando', 'Error', 'Omitido'
    filas_leidas INTEGER DEFAULT 0,
    filas_guardadas INTEGER DEFAULT 0,
    filas_rechazadas INTEGER DEFAULT 0,
    filas_omitidas INTEGER DEFAULT 0,
    motivo TEXT,
    fecha_carga TEXT NOT NULL
);

-- 2. Catálogo maestro de materiales y artículos
CREATE TABLE IF NOT EXISTS catalogo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fuente_id INTEGER,
    sku TEXT NOT NULL,
    descripcion TEXT NOT NULL,
    categoria TEXT,
    unidad TEXT NOT NULL,
    precio_unitario REAL NOT NULL,
    moneda TEXT DEFAULT 'MXN',
    fecha_precio TEXT,
    desactualizado INTEGER DEFAULT 0,    -- 1 si precio tiene > 6 meses
    antiguedad_meses INTEGER DEFAULT 0,
    notas TEXT,
    archivo_origen TEXT,
    creado_en TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (fuente_id) REFERENCES fuentes(id) ON DELETE CASCADE
);

-- 3. Cotizaciones históricas (cabeceras)
CREATE TABLE IF NOT EXISTS cotizaciones_historicas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fuente_id INTEGER,
    folio TEXT NOT NULL,
    cliente TEXT NOT NULL,
    fecha TEXT NOT NULL,
    desactualizado INTEGER DEFAULT 0,    -- 1 si cotización > 6 meses
    archivo_origen TEXT,
    creado_en TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (fuente_id) REFERENCES fuentes(id) ON DELETE CASCADE
);

-- 4. Partidas de cotizaciones históricas
CREATE TABLE IF NOT EXISTS partidas_historicas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cotizacion_id INTEGER,
    folio TEXT NOT NULL,
    partida_num INTEGER,
    concepto TEXT NOT NULL,
    cantidad REAL NOT NULL,
    unidad TEXT NOT NULL,
    precio_unitario REAL NOT NULL,
    subtotal REAL NOT NULL,
    duplicada INTEGER DEFAULT 0,         -- 1 si partida repetida en mismo folio
    notas TEXT,
    archivo_origen TEXT,
    creado_en TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (cotizacion_id) REFERENCES cotizaciones_historicas(id) ON DELETE CASCADE
);

-- 5. Fichas técnicas extraídas de PDFs
CREATE TABLE IF NOT EXISTS fichas_tecnicas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fuente_id INTEGER,
    codigo TEXT,
    titulo TEXT NOT NULL,
    fabricante TEXT,
    contenido_texto TEXT NOT NULL,
    num_paginas INTEGER DEFAULT 1,
    archivo_origen TEXT NOT NULL,
    fecha_carga TEXT NOT NULL,
    FOREIGN KEY (fuente_id) REFERENCES fuentes(id) ON DELETE CASCADE
);

-- 6. Tabla de rechazos (filas inválidas con motivo legible)
CREATE TABLE IF NOT EXISTS rechazos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fuente_id INTEGER,
    archivo TEXT NOT NULL,
    fila_numero INTEGER,
    campo TEXT,
    valor_crudo TEXT,
    motivo TEXT NOT NULL,
    fecha TEXT NOT NULL,
    FOREIGN KEY (fuente_id) REFERENCES fuentes(id) ON DELETE CASCADE
);

-- Índices para búsqueda rápida
CREATE INDEX IF NOT EXISTS idx_catalogo_sku ON catalogo(sku);
CREATE INDEX IF NOT EXISTS idx_catalogo_desactualizado ON catalogo(desactualizado);
CREATE INDEX IF NOT EXISTS idx_partidas_folio ON partidas_historicas(folio);
CREATE INDEX IF NOT EXISTS idx_rechazos_archivo ON rechazos(archivo);
