"""Genera el Excel de explotacion de Fase 3: movimientos cruzados con el
inventario de huecos del Kardex.

Reutiliza `fase3_movimientos.construir()` en vez de repetir el cruce: el
riesgo de que un cambio en la logica de negocio se actualice en un sitio y no
en el otro es mayor que el beneficio de mantener este fichero totalmente
independiente.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from fase3_movimientos import SALIDAS, construir

ANCHO_POR_DEFECTO = 14
ANCHOS = {
    "codigo": 11, "descripcion": 46, "tipo_codigo": 13, "formato_codigo": 16,
    "seccion": 16, "n_filas_origen": 10, "n_movimientos": 12, "cantidad": 11,
    "ultimo_movimiento": 18, "dias_periodo": 11, "tasa_diaria": 11, "tasa_7d": 10,
    "tasa_30d": 10, "armarios": 16, "huecos_total": 11, "stock_total": 11,
    "en_ambos_kardex": 15, "dado_de_baja": 13, "accion": 46, "k1_vs_k2": 44,
}


def _formatear_hoja(libro, hoja, df: pd.DataFrame, cab, congelar: int = 1) -> None:
    for i, col in enumerate(df.columns):
        hoja.write(0, i, col, cab)
        hoja.set_column(i, i, ANCHOS.get(col, ANCHO_POR_DEFECTO))
    hoja.autofilter(0, 0, len(df), len(df.columns) - 1)
    hoja.freeze_panes(1, congelar)


def main() -> int:
    r = construir()
    SALIDAS.mkdir(exist_ok=True)
    destino = SALIDAS / f"kardex_movimientos_{r.hasta:%Y%m%d}.xlsx"

    resumen = pd.DataFrame([
        ("Periodo analizado (Desde)", str(r.desde)),
        ("Periodo analizado (Hasta)", str(r.hasta)),
        ("Dias del periodo (convencion inclusiva)", r.dias_periodo),
        ("Filas del informe fuente", sum(res.filas_hoja for res in r.resultados)),
        ("  de las cuales datos", sum(res.filas_datos for res in r.resultados)),
        ("  de las cuales cabecera/marcadores", sum(res.filas_cabecera for res in r.resultados)),
        ("  de las cuales vacias", sum(res.filas_vacias for res in r.resultados)),
        ("  de las cuales descartadas", sum(len(res.filas_descartadas) for res in r.resultados)),
        ("Codigos distintos con movimiento", len(r.agregado)),
        ("  tipo kardex", int((r.agregado["tipo_codigo"] == "kardex").sum())),
        ("  tipo bookkeeping (DM/NOGUIA/PAC)", int((r.agregado["tipo_codigo"] == "bookkeeping").sum())),
        ("Codigos en Kardex CON consumo", int((r.cruce["_merge"] == "both").sum())),
        ("Codigos en Kardex SIN consumo", len(r.sin_consumo)),
        ("  de los cuales nuevos a valorar", int((~r.sin_consumo["dado_de_baja"]).sum())),
        ("  de los cuales ya en BAJA (consistente)", int(r.sin_consumo["dado_de_baja"].sum())),
        ("Movimiento sin Kardex (no ubicado en huecos)", len(r.sin_kardex)),
        ("En ambos kardex CON consumo (K1 vs K2 sin resolver)", len(r.con_consumo_ambos)),
        ("", ""),
        ("AVISO", "Este informe de movimientos es de toda la farmacia, SIN desglose "
                  "por almacen. Puede decir que un articulo no se ha movido en todo "
                  "el periodo, pero NUNCA que no se ha movido en KARDEX1 pero si en "
                  "KARDEX2 (o al reves). Esa distincion -- el disparador real de una "
                  "consolidacion entre los dos kardex -- sigue sin resolverse y hace "
                  "falta un informe de movimientos con desglose por almacen."),
        ("AVISO", "tasa_7d y tasa_30d son una extrapolacion lineal desde el total "
                  "del periodo, no una media semanal/mensual observada."),
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

        # ---- movimientos_articulo -------------------------------------
        agregado = r.agregado
        agregado.to_excel(xl, sheet_name="movimientos_articulo", index=False)
        hoja = xl.sheets["movimientos_articulo"]
        _formatear_hoja(libro, hoja, agregado, cab, congelar=2)
        c_tipo = agregado.columns.get_loc("tipo_codigo")
        c_filas = agregado.columns.get_loc("n_filas_origen")
        hoja.conditional_format(1, c_tipo, len(agregado), c_tipo, {
            "type": "cell", "criteria": "==", "value": '"bookkeeping"', "format": gris})
        hoja.conditional_format(1, c_filas, len(agregado), c_filas, {
            "type": "cell", "criteria": ">", "value": 1, "format": ambar})

        # ---- sin_consumo -------------------------------------------------
        sin_consumo = r.sin_consumo
        sin_consumo.to_excel(xl, sheet_name="sin_consumo", index=False)
        hoja = xl.sheets["sin_consumo"]
        _formatear_hoja(libro, hoja, sin_consumo, cab, congelar=2)
        c_accion = sin_consumo.columns.get_loc("accion")
        c_baja = sin_consumo.columns.get_loc("dado_de_baja")
        hoja.conditional_format(1, c_accion, len(sin_consumo), c_accion, {
            "type": "text", "criteria": "containing", "value": "valorar retirar",
            "format": rojo})
        hoja.conditional_format(1, c_baja, len(sin_consumo), c_baja, {
            "type": "cell", "criteria": "==", "value": True, "format": ambar})

        # ---- con_consumo_ambos -------------------------------------------
        ambos = r.con_consumo_ambos
        ambos.to_excel(xl, sheet_name="en_ambos_kardex", index=False)
        hoja = xl.sheets["en_ambos_kardex"]
        _formatear_hoja(libro, hoja, ambos, cab, congelar=2)
        c_k1k2 = ambos.columns.get_loc("k1_vs_k2")
        hoja.set_column(c_k1k2, c_k1k2, ANCHOS.get("k1_vs_k2", ANCHO_POR_DEFECTO), ambar)

        # ---- movimiento_sin_kardex -----------------------------------
        sin_kardex = r.sin_kardex
        sin_kardex.to_excel(xl, sheet_name="movimiento_sin_kardex", index=False)
        hoja = xl.sheets["movimiento_sin_kardex"]
        _formatear_hoja(libro, hoja, sin_kardex, cab, congelar=2)
        c_tipo2 = sin_kardex.columns.get_loc("tipo_codigo")
        hoja.conditional_format(1, c_tipo2, len(sin_kardex), c_tipo2, {
            "type": "cell", "criteria": "==", "value": '"bookkeeping"', "format": gris})

        # ---- resumen -------------------------------------------------
        resumen.to_excel(xl, sheet_name="resumen", index=False)
        hoja = xl.sheets["resumen"]
        for i, col in enumerate(resumen.columns):
            hoja.write(0, i, col, cab)
        hoja.set_column(0, 0, 40)
        hoja.set_column(1, 1, 90, envolver)

    print(f"Generado: {destino}")
    print(f"  movimientos_articulo   {len(agregado):,} filas")
    print(f"  sin_consumo            {len(sin_consumo):,} filas")
    print(f"  en_ambos_kardex        {len(ambos):,} filas")
    print(f"  movimiento_sin_kardex  {len(sin_kardex):,} filas")
    print(f"  resumen                {len(resumen):,} filas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
