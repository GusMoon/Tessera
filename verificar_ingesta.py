"""Script de verificación automática de ingesta para Tessera (Hito 1).

Compara:
- Conteos de archivos leídos.
- Filas guardadas en SQLite vs manifiesto.
- Filas defectuosas plantadas (8) rechazadas con motivo exacto vs manifiesto.
- Tiempo total de ingesta (< 60 segundos).

Imprime reporte claro en consola con veredicto APROBADO o FALLIDO.
"""

import sys
import os
import json
import time
from pathlib import Path

# Agregar directorio actual al path para importar módulos locales
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from db.database import init_db, get_connection
from ingest.servicio import procesar_archivo


def ejecutar_verificacion():
    print("=" * 70)
    print(" VERIFICADOR DE INGESTA AUTOMÁTICA · PROYECTO TESSERA (HITO 1)")
    print("=" * 70)

    # 1. Cargar manifiesto
    ruta_manifiesto = ROOT_DIR / "data" / "synthetic" / "manifiesto.json"
    if not ruta_manifiesto.exists():
        print(f"[ERROR] No se encontró el manifiesto en {ruta_manifiesto}")
        print("Ejecuta primero: python data/synthetic/generar_datos.py")
        sys.exit(1)

    with open(ruta_manifiesto, "r", encoding="utf-8") as f:
        manifiesto = json.load(f)

    resumen_esperado = manifiesto["resumen"]
    rechazos_esperados = manifiesto["rechazos_plantados"]

    # 2. Inicializar base de datos limpia
    print("\n[1/4] Inicializando base de datos SQLite limpia...")
    init_db(reset=True)
    print("      Base de datos reseteada con éxito.")

    # 3. Archivos a procesar
    dir_synthetic = ROOT_DIR / "data" / "synthetic"
    ruta_csv = dir_synthetic / "catalogo_materiales.csv"
    ruta_xlsx = dir_synthetic / "historial_cotizaciones.xlsx"
    ruta_tarifario = dir_synthetic / "tarifario_servicios.csv"
    dir_fichas = dir_synthetic / "fichas_tecnicas"

    archivos_a_procesar = [ruta_csv, ruta_xlsx]
    esperado_tarifario = resumen_esperado.get("tarifario_servicios")
    if esperado_tarifario and ruta_tarifario.exists():
        archivos_a_procesar.append(ruta_tarifario)
    archivos_pdf = sorted(list(dir_fichas.glob("*.pdf")))
    archivos_a_procesar.extend(archivos_pdf)

    print(f"\n[2/4] Iniciando ingesta de {len(archivos_a_procesar)} archivos:")
    print(f"      - 1 CSV Catálogo ({resumen_esperado['catalogo_csv']['total_filas']} filas)")
    print(f"      - 1 XLSX Historial ({resumen_esperado['historial_xlsx']['total_filas']} filas)")
    print(f"      - {len(archivos_pdf)} Fichas técnicas en PDF")
    if esperado_tarifario:
        print(f"      - 1 CSV Tarifario de servicios ({esperado_tarifario['total_filas']} filas)")

    # Iniciar cronómetro
    t_inicio = time.perf_counter()

    conn = get_connection()
    resultados_ingesta = []
    try:
        for arch in archivos_a_procesar:
            res = procesar_archivo(arch, arch.name, conn=conn)
            resultados_ingesta.append(res)
    finally:
        conn.close()

    t_fin = time.perf_counter()
    duracion_segundos = t_fin - t_inicio
    print(f"      Ingesta completada en {duracion_segundos:.3f} segundos.")

    # 4. Consultar SQLite para verificar datos reales almacenados
    print("\n[3/4] Validando datos almacenados en SQLite contra manifiesto...")
    conn = get_connection()
    try:
        # Conteos en tablas de datos
        total_catalogo = conn.execute("SELECT COUNT(*) as c FROM catalogo").fetchone()["c"]
        total_cotizaciones = conn.execute("SELECT COUNT(*) as c FROM cotizaciones_historicas").fetchone()["c"]
        total_partidas = conn.execute("SELECT COUNT(*) as c FROM partidas_historicas").fetchone()["c"]
        total_fichas = conn.execute("SELECT COUNT(*) as c FROM fichas_tecnicas").fetchone()["c"]
        total_servicios = conn.execute("SELECT COUNT(*) as c FROM servicios").fetchone()["c"]
        total_rechazos = conn.execute("SELECT COUNT(*) as c FROM rechazos").fetchone()["c"]

        # Filas con precios desactualizados (> 6 meses)
        catalogo_desactualizado = conn.execute("SELECT COUNT(*) as c FROM catalogo WHERE desactualizado = 1").fetchone()["c"]
        # Partidas duplicadas detectadas
        partidas_duplicadas = conn.execute("SELECT COUNT(*) as c FROM partidas_historicas WHERE duplicada = 1").fetchone()["c"]

        # Filas de rechazos registradas
        cur_rechazos = conn.execute("SELECT archivo, fila_numero, campo, valor_crudo, motivo FROM rechazos ORDER BY id ASC")
        rechazos_obtenidos = [dict(r) for r in cur_rechazos.fetchall()]

        # Totales en la tabla fuentes
        resumen_fuentes = conn.execute(
            """SELECT 
                   SUM(filas_leidas) as leidas, 
                   SUM(filas_guardadas) as guardadas, 
                   SUM(filas_rechazadas) as rechazadas 
               FROM fuentes"""
        ).fetchone()

    finally:
        conn.close()

    # 5. Evaluación de criterios binarios de éxito
    print("\n" + "=" * 70)
    print(" TABLA COMPARATIVA: ESPERADO vs OBTENIDO")
    print("=" * 70)
    
    val_csv_esperado = resumen_esperado["catalogo_csv"]["filas_validas"]
    val_xlsx_esperado = resumen_esperado["historial_xlsx"]["filas_validas"]
    val_pdf_esperado = resumen_esperado["fichas_pdf"]["validos"]
    rechazos_esperados_n = resumen_esperado["totales_combinados"]["total_filas_defectuosas"]

    print(f" {'Métrica / Colección':<35} | {'Esperado':<12} | {'Obtenido':<12} | {'Estado'}")
    print("-" * 70)
    
    ok_csv = (total_catalogo == val_csv_esperado)
    print(f" {'Catálogo CSV (filas válidas)':<35} | {val_csv_esperado:<12} | {total_catalogo:<12} | {'✓ CORRECTO' if ok_csv else '✗ ERROR'}")

    ok_xlsx = (total_partidas == val_xlsx_esperado)
    print(f" {'Historial XLSX (partidas válidas)':<35} | {val_xlsx_esperado:<12} | {total_partidas:<12} | {'✓ CORRECTO' if ok_xlsx else '✗ ERROR'}")

    ok_pdf = (total_fichas == val_pdf_esperado)
    print(f" {'Fichas Técnicas PDF (guardadas)':<35} | {val_pdf_esperado:<12} | {total_fichas:<12} | {'✓ CORRECTO' if ok_pdf else '✗ ERROR'}")

    ok_rechazos = (total_rechazos == rechazos_esperados_n)
    print(f" {'Filas defectuosas rechazadas':<35} | {rechazos_esperados_n:<12} | {total_rechazos:<12} | {'✓ CORRECTO' if ok_rechazos else '✗ ERROR'}")

    ok_servicios = True
    if esperado_tarifario:
        val_srv_esperado = esperado_tarifario["filas_validas"]
        ok_servicios = (total_servicios == val_srv_esperado)
        print(f" {'Tarifario de servicios (guardados)':<35} | {val_srv_esperado:<12} | {total_servicios:<12} | {'✓ CORRECTO' if ok_servicios else '✗ ERROR'}")

    ok_tiempo = (duracion_segundos < 60.0)
    print(f" {'Tiempo de ingesta total':<35} | {'< 60.00 s':<12} | {f'{duracion_segundos:.3f} s':<12} | {'✓ CORRECTO' if ok_tiempo else '✗ ERROR'}")

    print(f" {'Precios > 6 meses detectados':<35} | {'> 0 marcados':<12} | {f'{catalogo_desactualizado} marcados':<12} | {'✓ CORRECTO' if catalogo_desactualizado > 0 else '✗ ERROR'}")
    print(f" {'Partidas duplicadas detectadas':<35} | {'> 0 marcadas':<12} | {f'{partidas_duplicadas} marcadas':<12} | {'✓ CORRECTO' if partidas_duplicadas > 0 else '✗ ERROR'}")

    print("\n[4/4] Verificando detalle de los 8 rechazos plantados:")
    print("-" * 70)
    
    coincidencias_rechazos = 0
    for idx, r_esp in enumerate(rechazos_esperados, start=1):
        encontrado = False
        for r_obt in rechazos_obtenidos:
            if (r_obt["archivo"] == r_esp["archivo"] and 
                r_obt["campo"] == r_esp["campo"] and 
                r_obt["motivo"] == r_esp["motivo"]):
                encontrado = True
                break
        
        status_str = "✓ DETECTADO" if encontrado else "✗ NO ENCONTRADO"
        if encontrado:
            coincidencias_rechazos += 1
        print(f" #{idx:02d} [{r_esp['archivo']}] Campo: {r_esp['campo']:<15} Motivo: {r_esp['motivo']:<35} -> {status_str}")

    ok_detalle_rechazos = (coincidencias_rechazos == 8)

    # Veredicto final
    todo_aprobado = (ok_csv and ok_xlsx and ok_pdf and ok_servicios and ok_rechazos and ok_tiempo and ok_detalle_rechazos)

    print("\n" + "=" * 70)
    if todo_aprobado:
        print("               >>> RESULTADO: APROBADO <<<")
        print(" Todas las condiciones del Hito 1 se cumplieron al 100 %.")
    else:
        print("               >>> RESULTADO: FALLIDO <<<")
        print(" Algunas comprobaciones no alcanzaron el 100 % de cumplimiento.")
    print("=" * 70 + "\n")

    return 0 if todo_aprobado else 1


if __name__ == "__main__":
    codigo_salida = ejecutar_verificacion()
    sys.exit(codigo_salida)
