"""Perfila un fichero del Kardex y aplica las puertas de validacion.

    python tools/inspeccionar.py datos/inventario_k1.csv
    python tools/inspeccionar.py datos/informe.xlsx --hoja "Hoja1" --cabecera 3

No escribe nada ni toca el fichero de origen. Solo mira y cuenta.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from kardex_io import (
    analizar_fechas,
    analizar_numeros,
    cabecera_cruda,
    clasificar,
    detectar_delimitador,
    detectar_encoding,
    histograma_dia_del_mes,
    hojas_excel,
    leer_tabla,
    perfil_texto,
)

ANCHO = 78


def titulo(t: str) -> None:
    print("\n" + "=" * ANCHO)
    print(t)
    print("=" * ANCHO)


def sub(t: str) -> None:
    print("\n" + t)
    print("-" * len(t))


def main() -> int:
    ap = argparse.ArgumentParser(description="Inspector de ficheros del Kardex")
    ap.add_argument("fichero")
    ap.add_argument("--cabecera", type=int, default=0,
                    help="Indice (0-based) de la fila de cabecera")
    ap.add_argument("--hoja", default=None, help="Nombre o indice de hoja (Excel)")
    ap.add_argument("--crudas", type=int, default=15,
                    help="Cuantas lineas crudas mostrar")
    args = ap.parse_args()

    ruta = Path(args.fichero)
    if not ruta.exists():
        print(f"ERROR: no existe {ruta}")
        return 1

    titulo(f"FICHERO: {ruta.name}")
    print(f"Ruta      : {ruta.resolve()}")
    print(f"Tamanio   : {ruta.stat().st_size / 1024:.1f} KB")
    print(f"Extension : {ruta.suffix.lower()}")

    es_excel = ruta.suffix.lower() in {".xlsx", ".xlsm", ".xls"}
    if es_excel:
        hs = hojas_excel(ruta)
        print(f"Hojas     : {hs}")
    else:
        enc, conf = detectar_encoding(ruta)
        texto = ruta.read_text(encoding=enc, errors="replace")
        print(f"Encoding  : {enc} (confianza {conf:.0%})")
        print(f"Separador : {detectar_delimitador(texto)!r}")
        print(f"Lineas    : {texto.count(chr(10)) + 1}")

    # Lo primero es mirar el fichero en bruto: los informes de maquina suelen
    # llevar titulo y metadatos antes de la cabecera real.
    sub(f"PRIMERAS {args.crudas} LINEAS EN BRUTO")
    for i, ln in enumerate(cabecera_cruda(ruta, args.crudas)):
        print(f"{i:>3} | {ln[:200]}")

    hoja = args.hoja
    if hoja is not None and hoja.isdigit():
        hoja = int(hoja)
    df = leer_tabla(ruta, fila_cabecera=args.cabecera,
                    hoja=hoja if hoja is not None else 0)

    titulo("ESTRUCTURA")
    print(f"Filas   : {len(df):,}")
    print(f"Columnas: {len(df.columns)}")
    sub("COLUMNAS")
    for i, c in enumerate(df.columns):
        no_nulos = int(df[c].notna().sum())
        print(f"{i:>3}  {str(c)[:44]:<44}  {clasificar(str(c), df[c]):<7}  "
              f"{no_nulos:>7,} con dato")

    # Duplicados: si hay una columna de codigo, importa saber si el fichero
    # trae una fila por articulo o varias (una por hueco, por ejemplo).
    cols_cod = [c for c in df.columns
                if any(p in str(c).upper() for p in ("COD", "ARTIC", "REFER"))]
    if cols_cod:
        sub("UNICIDAD")
        for c in cols_cod[:3]:
            vals = df[c].dropna().astype(str).str.strip()
            print(f"{c}: {len(vals):,} valores, {vals.nunique():,} distintos"
                  f"{'  -> UNA FILA POR VALOR' if len(vals) == vals.nunique() else '  -> HAY REPETIDOS'}")
            if len(vals) != vals.nunique():
                for v, n in vals.value_counts().head(3).items():
                    print(f"    {v} aparece {n} veces")

    titulo("PUERTAS DE VALIDACION")
    bloqueantes: list[str] = []

    for c in df.columns:
        tipo = clasificar(str(c), df[c])

        if tipo == "fecha":
            d = analizar_fechas(df[c], str(c))
            sub(f"[FECHA] {c}")
            print(f"Veredicto : {d.veredicto}")
            print(f"Valores   : {d.total:,} ({d.vacias:,} vacias, "
                  f"{d.no_reconocidas:,} no reconocidas)")
            print(f"Evidencia : {d.prueba_dmy:,} exigen DMY (1er componente >12) | "
                  f"{d.prueba_mdy:,} exigen MDY (2o >12) | {d.ambiguas:,} ambiguas")
            if d.fecha_min:
                print(f"Rango     : {d.fecha_min} .. {d.fecha_max}")
            if d.ejemplos:
                print(f"No reconocidos: {d.ejemplos}")
            if d.futuras:
                bloqueantes.append(f"{c}: {d.futuras:,} fechas en el futuro")
            if d.contradictorio:
                bloqueantes.append(f"{c}: formato de fecha contradictorio")
            if d.concluyente and d.total - d.vacias > 100:
                h = histograma_dia_del_mes(df[c], d.formato)
                if h:
                    print("Dia del mes (firma de inversion DD/MM: pico en 1-6, "
                          "agujero en 7-12):")
                    med = sorted(h.values())[len(h) // 2] or 1
                    for dia in sorted(h):
                        n = h[dia]
                        barra = "#" * min(40, int(20 * n / med))
                        print(f"  {dia:>2} {n:>7,} {barra}")

        elif tipo == "numero":
            d = analizar_numeros(df[c], str(c))
            if not d.numericas:
                continue
            sub(f"[NUMERO] {c}")
            print(f"Veredicto : {d.veredicto}")
            print(f"Valores   : {d.numericas:,} numericos, {d.vacias:,} vacios, "
                  f"{d.negativas:,} negativos")
            print(f"Rango     : {d.minimo:,.2f} .. {d.maximo:,.2f}   "
                  f"mediana {d.mediana:,.2f}   media {d.media:,.2f}")
            print(f"Convencion: {d.convencion or 'sin resolver'} - {d.motivo_convencion}")
            print(f"Decimales : {d.con_decimales:,} con decimales   "
                  f"multiplos de 100: {d.multiplos_100:,} ({d.pct_multiplos_100:.0f}%)")
            if d.ejemplos:
                print(f"No numericos: {d.ejemplos}")
            if "SOSPECHA" in d.veredicto:
                bloqueantes.append(f"{c}: posible escala x100")

        else:
            p = perfil_texto(df[c], str(c))
            if p["distintos"] == 0:
                continue
            sub(f"[TEXTO] {c}")
            print(f"Distintos : {p['distintos']:,} de {p['total'] - p['vacias']:,} "
                  f"con dato ({p['vacias']:,} vacios)")
            print(f"Longitud  : {p['long_min']}..{p['long_max']}")
            for v, n in p["top"]:
                print(f"    {n:>7,}  {v[:60]}")

    titulo("RESUMEN")
    if bloqueantes:
        print("NO ACEPTAR ESTA CARGA. Incidencias bloqueantes:")
        for b in bloqueantes:
            print(f"  - {b}")
    else:
        print("Sin incidencias bloqueantes en las puertas automaticas.")
        print("Falta la revision humana de convenciones (codigos, almacenes).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
