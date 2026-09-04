"""Convierte el informe paginado en un Excel plano de explotacion.

El informe original es una salida para imprimir: 295 filas de cabecera
repetidas, columnas de relleno, el armario escondido en una marca de seccion
y sin fecha en las filas. Sirve para mirarlo en papel, no para filtrar,
cruzar ni hacer tablas dinamicas.

Esto produce una sola hoja, una fila por hueco, con el almacen y la fecha
del corte en cada fila.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from kardex_io import _a_numero, detectar_convencion
from parser_stock_huecos import parsear

RUTA = Path(__file__).parent.parent / "datos" / "Informe_StockHuecos.xls"
SALIDAS = Path(__file__).parent.parent / "salidas"
UMBRAL_SIN_LIMITE = 1_000_000

# Orden pensado para leer y filtrar: primero el que/donde, luego las cifras,
# y al final las marcas de calidad del dato.
COLUMNAS = [
    "fecha_descarga",
    "almacen",
    "ubicacion",
    "codigo",
    "descripcion",
    "stock",
    "capacidad",
    "tipo_hueco",
    "bloqueado",
    "lote",
    "fecha_lote",
    "en_proceso_de_baja",
    "capacidad_sin_limite",
    "stock_supera_capacidad",
    "formato_codigo",
]


def a_numero(serie: pd.Series) -> pd.Series:
    conv, _ = detectar_convencion(serie)
    return serie.map(lambda v: _a_numero(str(v), conv)[0] if str(v).strip() else None)


def construir() -> pd.DataFrame:
    df, _, fecha = parsear(RUTA)
    if not fecha:
        raise SystemExit("No se ha podido leer la fecha del informe. Revisar cabecera.")

    out = pd.DataFrame()
    out["fecha_descarga"] = pd.to_datetime(df["fecha_descarga"]).dt.date
    out["almacen"] = df["armario"]
    out["ubicacion"] = df["ubicacion"]
    out["codigo"] = df["codigo"]
    out["descripcion"] = df["descripcion"].str.strip()
    out["stock"] = a_numero(df["stock"])
    out["capacidad"] = a_numero(df["capacidad"])
    out["tipo_hueco"] = df["tipo_hueco"]
    # "Sin bloquear" -> False. Bloqueado significa posicion fija.
    out["bloqueado"] = ~df["bloqueo"].str.strip().str.lower().eq("sin bloquear")
    out["lote"] = df["lote"].replace("", None)
    out["fecha_lote"] = df["fecha_lote"].replace("", None)

    # Marcado, no corregido: el 999999999 es un "sin limite", no una capacidad.
    out["capacidad_sin_limite"] = out["capacidad"] >= UMBRAL_SIN_LIMITE
    out.loc[out["capacidad_sin_limite"], "capacidad"] = None

    out["en_proceso_de_baja"] = df["dado_de_baja"]
    out["stock_supera_capacidad"] = (
        out["capacidad"].notna() & (out["stock"] > out["capacidad"])
    )
    out["formato_codigo"] = df["formato_codigo"]

    return out[COLUMNAS].sort_values(["almacen", "ubicacion"]).reset_index(drop=True)


def main() -> int:
    df = construir()
    SALIDAS.mkdir(exist_ok=True)
    fecha = df["fecha_descarga"].iloc[0]
    destino = SALIDAS / f"kardex_inventario_huecos_{fecha:%Y%m%d}.xlsx"

    with pd.ExcelWriter(destino, engine="xlsxwriter",
                        datetime_format="yyyy-mm-dd",
                        date_format="yyyy-mm-dd") as xl:
        df.to_excel(xl, sheet_name="inventario_huecos", index=False)
        libro, hoja = xl.book, xl.sheets["inventario_huecos"]

        cab = libro.add_format({"bold": True, "bg_color": "#1F3864",
                                "font_color": "white", "border": 1,
                                "align": "center", "valign": "vcenter",
                                "text_wrap": True})
        for i, col in enumerate(df.columns):
            hoja.write(0, i, col, cab)
        anchos = {"fecha_descarga": 14, "almacen": 10, "ubicacion": 18,
                  "codigo": 11, "descripcion": 46, "stock": 9, "capacidad": 11,
                  "tipo_hueco": 40, "bloqueado": 11, "lote": 12,
                  "fecha_lote": 12, "en_proceso_de_baja": 18,
                  "capacidad_sin_limite": 20, "stock_supera_capacidad": 21,
                  "formato_codigo": 16}
        for i, col in enumerate(df.columns):
            hoja.set_column(i, i, anchos.get(col, 14))

        # Autofiltro y panel fijo: es un fichero para trabajar, no para leer.
        hoja.autofilter(0, 0, len(df), len(df.columns) - 1)
        hoja.freeze_panes(1, 5)

        rojo = libro.add_format({"bg_color": "#FFC7CE", "font_color": "#9C0006"})
        ambar = libro.add_format({"bg_color": "#FFEB9C", "font_color": "#9C6500"})
        c_baja = df.columns.get_loc("en_proceso_de_baja")
        c_sobre = df.columns.get_loc("stock_supera_capacidad")
        for col, fmt in ((c_baja, ambar), (c_sobre, rojo)):
            hoja.conditional_format(1, col, len(df), col, {
                "type": "cell", "criteria": "==", "value": True, "format": fmt})

    print(f"Generado: {destino}")
    print(f"Filas   : {len(df):,}")
    print(f"Corte   : {fecha}")
    print(f"Almacen : {dict(df['almacen'].value_counts())}")
    print(f"\nMarcas de calidad:")
    print(f"  en_proceso_de_baja     : {int(df['en_proceso_de_baja'].sum())}")
    print(f"  capacidad_sin_limite   : {int(df['capacidad_sin_limite'].sum())}")
    print(f"  stock_supera_capacidad : {int(df['stock_supera_capacidad'].sum())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
