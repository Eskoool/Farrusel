"""Genera el Excel maestro: Fase 1 (huecos) x Fase 3 (movimientos), con un
sistema de colores unico para identificar alertas.

Reutiliza `maestro_huecos.construir()` en vez de repetir el cruce.

Sistema de colores (aplicado columna a columna, no celda a celda suelta):
  ROJO  -- error a corregir, requiere accion fisica en la maquina:
           stock_supera_capacidad, capacidad_sin_limite (placeholder
           999999999: nadie ha configurado una capacidad real), y los huecos
           cuyo articulo esta "sin consumo" con accion "valorar retirar".
  AMBAR -- conocido / a revisar, no bloqueante: en_proceso_de_baja, los
           huecos "sin consumo" ya en BAJA (accion "agotar sin reponer"), y
           los articulos en ambos kardex con consumo (k1_vs_k2 no resuelto:
           limitacion de la fuente, no del hueco).
  GRIS  -- informativo, sin accion: bloqueado (posicion fija).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from maestro_huecos import ACCION_AGOTAR, ACCION_RETIRAR, SALIDAS, construir

ANCHO_POR_DEFECTO = 14
ANCHOS = {
    "fecha_descarga": 14, "almacen": 10, "ubicacion": 18, "codigo": 11,
    "descripcion": 44, "stock": 8, "capacidad": 11, "tipo_hueco": 40,
    "bloqueado": 10, "lote": 10, "fecha_lote": 12, "en_proceso_de_baja": 16,
    "capacidad_sin_limite": 18, "stock_supera_capacidad": 19,
    "alerta_capacidad": 60,
    "formato_codigo": 15, "articulo_n_huecos": 12,
    "articulo_tiene_consumo_periodo": 14, "articulo_periodo_dias": 12,
    "articulo_cantidad_periodo": 14, "articulo_n_movimientos_periodo": 15,
    "articulo_tasa_diaria_periodo": 12, "articulo_tasa_7d_periodo": 11,
    "articulo_tasa_30d_periodo": 11, "articulo_ultimo_movimiento": 18,
    "articulo_en_ambos_kardex": 15, "articulo_k1_vs_k2": 44,
    "articulo_sin_consumo_accion": 46, "n_alertas": 10,
}


def main() -> int:
    r = construir()
    m = r.maestro
    f3 = r.f3
    SALIDAS.mkdir(exist_ok=True)
    fecha_corte = pd.to_datetime(m["fecha_descarga"].iloc[0])
    destino = SALIDAS / f"kardex_maestro_huecos_{fecha_corte:%Y%m%d}.xlsx"

    n_alerta_capacidad = int(m["capacidad_sin_limite"].sum())
    n_alerta_stock = int(m["stock_supera_capacidad"].sum())
    n_retirar = int((m["articulo_sin_consumo_accion"] == ACCION_RETIRAR).sum())
    n_agotar = int((m["articulo_sin_consumo_accion"] == ACCION_AGOTAR).sum())

    resumen = pd.DataFrame([
        ("Fecha de corte (Fase 1)", str(fecha_corte.date())),
        ("Periodo de movimientos (Fase 3)", f"{f3.desde} .. {f3.hasta} ({f3.dias_periodo} dias)"),
        ("Huecos totales", len(m)),
        ("  con consumo en el periodo", int(m["articulo_tiene_consumo_periodo"].sum())),
        ("  sin consumo en el periodo", int((~m["articulo_tiene_consumo_periodo"]).sum())),
        ("Codigos distintos", int(m["codigo"].nunique())),
        ("", ""),
        ("--- ALERTAS ROJAS (error a corregir) ---", ""),
        ("Huecos con stock por encima de su capacidad", n_alerta_stock),
        ("Huecos con capacidad sin configurar (placeholder 999999999)", n_alerta_capacidad),
        ("Huecos de articulos 'sin consumo' -> valorar retirar", n_retirar),
        ("--- ALERTAS AMBAR (conocido / a revisar) ---", ""),
        ("Huecos en proceso de baja", int(m["en_proceso_de_baja"].sum())),
        ("Huecos de articulos 'sin consumo' ya en BAJA (agotar sin reponer)", n_agotar),
        ("Huecos de articulos en ambos kardex con consumo (K1 vs K2 sin resolver)",
         int(m["articulo_k1_vs_k2"].notna().sum())),
        ("", ""),
        ("LEYENDA DE COLORES", ""),
        ("ROJO", "Error a corregir: stock_supera_capacidad, capacidad_sin_limite, "
                 "articulo_sin_consumo_accion = 'valorar retirar e introducir en carrusel' "
                 "-- el texto exacto de que corregir esta en la columna alerta_capacidad "
                 "para las dos primeras"),
        ("AMBAR", "Conocido / a revisar, no bloqueante: en_proceso_de_baja, "
                  "articulo_sin_consumo_accion = 'agotar sin reponer...', "
                  "articulo_k1_vs_k2 (limitacion de la fuente, no del hueco)"),
        ("GRIS", "Informativo, sin accion: bloqueado (posicion fija)"),
        ("", ""),
        ("ACLARACION", "tipo_hueco NO determina capacidad: son dos columnas independientes "
                        "del informe original (Cap. vs Hueco, tools/parser_stock_huecos.py). "
                        "tipo_hueco tiene solo 11 valores, todos modelos fisicos de cajon "
                        "(tamano/LEDs/nº de divisiones), no una cifra de capacidad -- un mismo "
                        "tipo_hueco convive con decenas de capacidades distintas. capacidad es "
                        "un numero configurado hueco a hueco en la maquina; para Fase 4, "
                        "min/max/capacidad deben compararse contra la columna capacidad, "
                        "nunca contra tipo_hueco."),
        ("AVISO", "Las columnas articulo_*_periodo son totales de TODA la farmacia por "
                  "codigo en el periodo analizado, repetidos en cada hueco que ocupa ese "
                  "codigo (ver articulo_n_huecos) -- NO sumar estas columnas entre filas de "
                  "este fichero o se cuenta el consumo 2x/3x. Para el total real por codigo, "
                  "una fila por codigo, usar salidas/fase3_movimientos.csv."),
        ("AVISO", "Este informe de movimientos es de toda la farmacia, SIN desglose por "
                  "almacen. articulo_k1_vs_k2 deja constancia de que NO se puede saber si "
                  "el consumo de un articulo duplicado en ambos kardex vino de KARDEX1, de "
                  "KARDEX2 o de ambos -- eso sigue sin resolverse y hace falta un informe de "
                  "movimientos con desglose por almacen."),
        ("AVISO", "articulo_tasa_7d_periodo / articulo_tasa_30d_periodo son una "
                  "extrapolacion lineal desde el total del periodo, no una media "
                  "semanal/mensual observada."),
        ("REFERENCIA", "Ver tambien kardex_inventario_huecos_*.xlsx (Fase 1) y "
                        "kardex_movimientos_*.xlsx (Fase 3) para el detalle completo de cada "
                        "analisis por separado; este fichero los integra a nivel de hueco."),
    ], columns=["Campo", "Valor"])

    with pd.ExcelWriter(destino, engine="xlsxwriter",
                        datetime_format="yyyy-mm-dd",
                        date_format="yyyy-mm-dd") as xl:
        libro = xl.book
        cab = libro.add_format({"bold": True, "bg_color": "#1F3864",
                                "font_color": "white", "border": 1,
                                "align": "center", "valign": "vcenter",
                                "text_wrap": True})
        rojo = libro.add_format({"bg_color": "#FFC7CE", "font_color": "#9C0006"})
        ambar = libro.add_format({"bg_color": "#FFEB9C", "font_color": "#9C6500"})
        gris = libro.add_format({"bg_color": "#F2F2F2", "font_color": "#7F7F7F"})
        envolver = libro.add_format({"text_wrap": True, "valign": "top"})

        # ---- maestro_huecos ------------------------------------------
        m.to_excel(xl, sheet_name="maestro_huecos", index=False)
        hoja = xl.sheets["maestro_huecos"]
        for i, col in enumerate(m.columns):
            hoja.write(0, i, col, cab)
            hoja.set_column(i, i, ANCHOS.get(col, ANCHO_POR_DEFECTO))
        hoja.autofilter(0, 0, len(m), len(m.columns) - 1)
        hoja.freeze_panes(1, 5)

        def col(nombre: str) -> int:
            return m.columns.get_loc(nombre)

        # Rojo
        for nombre in ("stock_supera_capacidad", "capacidad_sin_limite"):
            c = col(nombre)
            hoja.conditional_format(1, c, len(m), c, {
                "type": "cell", "criteria": "==", "value": True, "format": rojo})
        c = col("articulo_sin_consumo_accion")
        hoja.conditional_format(1, c, len(m), c, {
            "type": "text", "criteria": "containing", "value": "valorar retirar",
            "format": rojo})
        c = col("alerta_capacidad")
        hoja.conditional_format(1, c, len(m), c, {"type": "no_blanks", "format": rojo})

        # Ambar
        c = col("en_proceso_de_baja")
        hoja.conditional_format(1, c, len(m), c, {
            "type": "cell", "criteria": "==", "value": True, "format": ambar})
        hoja.conditional_format(1, col("articulo_sin_consumo_accion"), len(m),
                                col("articulo_sin_consumo_accion"), {
            "type": "text", "criteria": "containing", "value": "agotar sin reponer",
            "format": ambar})
        c = col("articulo_k1_vs_k2")
        hoja.conditional_format(1, c, len(m), c, {"type": "no_blanks", "format": ambar})

        # Gris
        c = col("bloqueado")
        hoja.conditional_format(1, c, len(m), c, {
            "type": "cell", "criteria": "==", "value": True, "format": gris})

        # ---- hojas de trazabilidad de Fase 3 ---------------------------
        for nombre, df in (
            ("sin_consumo", f3.sin_consumo),
            ("en_ambos_kardex", f3.con_consumo_ambos),
            ("movimiento_sin_kardex", f3.sin_kardex),
        ):
            df.to_excel(xl, sheet_name=nombre, index=False)
            hoja = xl.sheets[nombre]
            for i, c2 in enumerate(df.columns):
                hoja.write(0, i, c2, cab)
                hoja.set_column(i, i, ANCHOS.get(c2, ANCHO_POR_DEFECTO))
            hoja.autofilter(0, 0, len(df), len(df.columns) - 1)
            hoja.freeze_panes(1, 2)

        # ---- resumen -------------------------------------------------
        resumen.to_excel(xl, sheet_name="resumen", index=False)
        hoja = xl.sheets["resumen"]
        for i, c2 in enumerate(resumen.columns):
            hoja.write(0, i, c2, cab)
        hoja.set_column(0, 0, 46)
        hoja.set_column(1, 1, 95, envolver)

    print(f"Generado: {destino}")
    print(f"  maestro_huecos          {len(m):,} filas x {len(m.columns)} columnas")
    print(f"  sin_consumo             {len(f3.sin_consumo):,} filas")
    print(f"  en_ambos_kardex         {len(f3.con_consumo_ambos):,} filas")
    print(f"  movimiento_sin_kardex   {len(f3.sin_kardex):,} filas")
    print(f"  resumen                 {len(resumen):,} filas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
