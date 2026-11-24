-- Esquema SQLite para Tessera (Hito 1: datos · Hito 2: búsqueda y cotizaciones · Hito 3: revisión y aprobación)
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
    fecha_carga TEXT NOT NULL,
    permiso TEXT NOT NULL DEFAULT 'Todos' -- 'Todos' | 'Comercial' | 'Administración' (regla 6: se filtra antes de recuperar)
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


-- ───────────── Hito 2 y 3 ─────────────

-- 7. Tarifario de servicios (flete por zona, instalación por pieza, opcionales premium)
CREATE TABLE IF NOT EXISTS servicios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fuente_id INTEGER,
    codigo TEXT NOT NULL,
    servicio TEXT NOT NULL,
    tipo TEXT NOT NULL,                   -- 'Flete', 'Instalación', 'Opcional'
    unidad TEXT NOT NULL,
    precio_unitario REAL NOT NULL,
    zona TEXT,
    incluir_en TEXT NOT NULL DEFAULT 'todos', -- 'todos' | 'premium'
    fecha_precio TEXT,
    desactualizado INTEGER DEFAULT 0,
    antiguedad_meses INTEGER DEFAULT 0,
    notas TEXT,
    archivo_origen TEXT,
    creado_en TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (fuente_id) REFERENCES fuentes(id) ON DELETE CASCADE
);

-- 8. Usuarios de prueba (prototipo: sin contraseñas; la identidad llega en la cabecera X-Usuario-Id)
CREATE TABLE IF NOT EXISTS usuarios (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    rol TEXT NOT NULL                     -- 'Vendedor' | 'Responsable comercial' | 'Administrador'
);

-- 9. Fragmentos indexables y citables (catálogo, historial, fichas, servicios). Se reconstruyen al indexar.
CREATE TABLE IF NOT EXISTS fragmentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fuente_id INTEGER NOT NULL,
    tipo TEXT NOT NULL,                   -- 'catalogo' | 'historial' | 'ficha' | 'servicio'
    ref TEXT NOT NULL,                    -- clave citable estable, p. ej. 'catalogo:GAB-403020'
    titulo TEXT NOT NULL,
    texto TEXT NOT NULL,
    permiso TEXT NOT NULL DEFAULT 'Todos',
    fecha TEXT,                           -- fecha del dato citado (ISO), para filtrar y mostrar antigüedad
    FOREIGN KEY (fuente_id) REFERENCES fuentes(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_fragmentos_ref ON fragmentos(ref);
CREATE VIRTUAL TABLE IF NOT EXISTS fragmentos_fts USING fts5(
    texto, titulo, tokenize = 'unicode61 remove_diacritics 2'
);                                        -- rowid = fragmentos.id

-- 10. Cotizaciones generadas por el sistema. Los importes se guardan en centavos enteros (nunca flotantes).
CREATE TABLE IF NOT EXISTS cotizaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    folio TEXT UNIQUE NOT NULL,
    cliente TEXT NOT NULL,
    solicitud TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'Borrador', -- 'Borrador' | 'En revisión' | 'Aprobada' | 'Rechazada'
    creada_por TEXT NOT NULL,
    fecha TEXT NOT NULL,                  -- ISO con hora
    escenario_aprobado TEXT,
    motivo_rechazo TEXT,
    contexto_json TEXT NOT NULL DEFAULT '{}', -- avisos, cotizaciones parecidas y origen de la redacción
    FOREIGN KEY (creada_por) REFERENCES usuarios(id)
);

CREATE TABLE IF NOT EXISTS cotizacion_escenarios (
    cotizacion_id INTEGER NOT NULL,
    escenario TEXT NOT NULL,              -- 'economico' | 'recomendado' | 'premium'
    margen_puntos_base INTEGER NOT NULL,  -- margen objetivo sobre el precio de venta (1 800 = 18 %)
    notas TEXT NOT NULL DEFAULT '',
    riesgos_json TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (cotizacion_id, escenario),
    FOREIGN KEY (cotizacion_id) REFERENCES cotizaciones(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cotizacion_partidas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cotizacion_id INTEGER NOT NULL,
    escenario TEXT NOT NULL,
    orden INTEGER NOT NULL,
    tipo TEXT NOT NULL,                   -- 'material' | 'servicio'
    codigo TEXT NOT NULL,
    concepto TEXT NOT NULL,
    unidad TEXT NOT NULL,
    cantidad INTEGER NOT NULL,
    costo_unitario_centavos INTEGER NOT NULL,
    precio_unitario_centavos INTEGER NOT NULL,
    fuente_ref TEXT NOT NULL,             -- regla 2: toda partida lleva su fuente
    fuente_fecha TEXT,
    antiguedad_meses INTEGER NOT NULL DEFAULT 0,
    precio_antiguo INTEGER NOT NULL DEFAULT 0, -- 1 si el precio tiene más de 6 meses
    editada_por TEXT,
    FOREIGN KEY (cotizacion_id) REFERENCES cotizaciones(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_cot_partidas ON cotizacion_partidas(cotizacion_id, escenario);

CREATE TABLE IF NOT EXISTS cotizacion_historial (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cotizacion_id INTEGER NOT NULL,
    fecha TEXT NOT NULL,
    usuario TEXT NOT NULL,
    texto TEXT NOT NULL,
    FOREIGN KEY (cotizacion_id) REFERENCES cotizaciones(id) ON DELETE CASCADE
);

-- 11. Aprobaciones (regla 3: sin una fila aquí no existe ruta de código que genere el PDF final)
CREATE TABLE IF NOT EXISTS aprobaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cotizacion_id INTEGER UNIQUE NOT NULL,
    escenario TEXT NOT NULL,
    aprobado_por TEXT NOT NULL,
    fecha TEXT NOT NULL,
    total_centavos INTEGER NOT NULL,
    FOREIGN KEY (cotizacion_id) REFERENCES cotizaciones(id) ON DELETE CASCADE,
    FOREIGN KEY (aprobado_por) REFERENCES usuarios(id)
);

-- 12. Memoria visible y editable (regla 5): cada hecho con origen y fecha
CREATE TABLE IF NOT EXISTS memoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    texto TEXT NOT NULL,
    origen TEXT NOT NULL,
    fecha TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'Activa', -- 'Activa' | 'Pausada'
    por_confirmar INTEGER NOT NULL DEFAULT 1
);

-- 13. Bitácora de auditoría
CREATE TABLE IF NOT EXISTS bitacora (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL,
    usuario TEXT NOT NULL,
    pregunta TEXT NOT NULL,
    documentos_json TEXT NOT NULL DEFAULT '[]',
    herramientas_json TEXT NOT NULL DEFAULT '[]',
    duracion_ms INTEGER NOT NULL DEFAULT 0,
    cotizacion TEXT,
    aprobado_por TEXT
);
