"""Replica en Python la logica exacta del parser TypeScript de Lovable
(src/lib/kardex/stock-huecos.ts) y la compara con el parser de referencia.

Sirve para responder a una pregunta concreta: si el usuario sube el fichero
desde la app, ¿entran en Supabase exactamente los mismos datos que cargue yo?

Se replica el ORDEN de comprobaciones tal cual esta en el TS, porque ahi esta
el riesgo: comprueba "es cabecera" antes que "es fila de datos", asi que
cualquier fila de datos cuyo texto contenga HOSPITAL o INFORME DE STOCK se
contaria como cabecera y desapareceria sin aviso.
"""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from kardex_io import leer_bytes
from parser_stock_huecos import parsear

RUTA = Path(__file__).parent.parent / "datos" / "Informe_StockHuecos.xls"

COL = {"ubicacion": 1, "codigo": 2, "descripcion": 4, "stock": 6,
       "capacidad": 9, "bloqueo": 10, "tipo_hueco": 12, "lote": 14,
       "fecha_lote": 18}

RE_ARMARIO = re.compile(r"^(KARDEX\d+)\((\d+)\)$")
RE_UBICACION = re.compile(r"^\d{3}(?:-\d{2}){4}$")
RE_CODIGO = re.compile(r"^[A-Z]{0,2}\d{4,8}$")
SIN_LIMITE = 1_000_000


def celda(fila, i):
    if i >= len(fila):
        return ""
    v = fila[i]
    return "" if pd.isna(v) else str(v).strip()


def no_vacias(fila):
    return [("" if pd.isna(c) else str(c).strip()) for c in fila
            if not pd.isna(c) and str(c).strip() != ""]


def parsear_como_lovable(ruta: Path):
    xls = pd.ExcelFile(io.BytesIO(leer_bytes(ruta)))
    total = datos = cabecera = vacias = 0
    descartadas, filas = [], []
    tragadas_por_cabecera = []

    for hoja in xls.sheet_names:
        grid = pd.read_excel(xls, sheet_name=hoja, header=None, dtype=str)
        armario = None
        for idx in range(len(grid)):
            fila = list(grid.iloc[idx])
            total += 1
            celdas = no_vacias(fila)

            if not celdas:
                vacias += 1
                continue

            if len(celdas) == 1:
                m = RE_ARMARIO.match(celdas[0])
                if m:
                    armario = m.group(1)
                    cabecera += 1
                    continue

            unido = " ".join(celdas).upper()
            col1 = celda(fila, COL["ubicacion"])
            cod = celda(fila, COL["codigo"])
            es_cabecera = ("INFORME DE STOCK" in unido
                           or "HOSPITAL" in unido
                           or celdas[0].startswith("Armarios")
                           or col1 in ("Ubicación", "Ubicacion"))

            if es_cabecera:
                cabecera += 1
                # Aqui esta el riesgo: si ademas parecia fila de datos, se
                # ha perdido un medicamento sin que nadie se entere.
                if RE_UBICACION.match(col1) and RE_CODIGO.match(cod):
                    tragadas_por_cabecera.append(
                        (hoja, idx, col1, cod, celda(fila, COL["descripcion"])))
                continue

            if RE_UBICACION.match(col1) and RE_CODIGO.match(cod):
                if not armario:
                    descartadas.append((hoja, idx, "sin armario"))
                    continue
                cap = celda(fila, COL["capacidad"])
                cap_n = float(cap.replace(".", "").replace(",", ".")) if cap else None
                sin_lim = cap_n is not None and cap_n >= SIN_LIMITE
                stk = celda(fila, COL["stock"])
                stk_n = float(stk.replace(".", "").replace(",", ".")) if stk else None
                desc = celda(fila, COL["descripcion"])
                filas.append({
                    "almacen": armario, "ubicacion": col1, "codigo": cod,
                    "descripcion": desc, "stock": stk_n,
                    "capacidad": None if sin_lim else cap_n,
                    "capacidad_sin_limite": sin_lim,
                    "en_proceso_de_baja": bool(re.match(r"^\s*baja\b", desc, re.I)),
                    "stock_supera_capacidad": (
                        not sin_lim and cap_n is not None and stk_n is not None
                        and stk_n > cap_n),
                })
                datos += 1
                continue

            descartadas.append((hoja, idx, f"ubicacion={col1!r} codigo={cod!r}"))

    return (pd.DataFrame(filas),
            {"total": total, "datos": datos, "cabecera": cabecera,
             "vacias": vacias, "descartadas": len(descartadas)},
            descartadas, tragadas_por_cabecera)


def main() -> int:
    lov, cuentas, descartadas, tragadas = parsear_como_lovable(RUTA)
    ref, _, _ = parsear(RUTA)

    fallos = []

    def check(cond, msg):
        print(f"  {'OK  ' if cond else 'FALLO'}  {msg}")
        if not cond:
            fallos.append(msg)

    print("\n1. Riesgo de filas tragadas por el orden de comprobaciones")
    check(len(tragadas) == 0,
          f"filas de datos clasificadas como cabecera: {len(tragadas)}")
    for h, i, u, c, d in tragadas[:10]:
        print(f"        {h} fila {i}: {u} {c} {d[:40]}")

    print("\n2. Cuentas de reparto")
    print(f"     {cuentas}")
    check(cuentas["total"] == cuentas["datos"] + cuentas["cabecera"]
          + cuentas["vacias"] + cuentas["descartadas"], "el reparto suma el total")
    check(cuentas["descartadas"] == 0,
          f"cero filas descartadas (hay {cuentas['descartadas']})")

    print("\n3. Paridad con el parser de referencia")
    check(len(lov) == len(ref), f"filas de datos: Lovable {len(lov)} vs referencia {len(ref)}")
    check(len(lov) == 1742, f"total esperado 1742 (obtenido {len(lov)})")

    por_arm_l = dict(lov["almacen"].value_counts())
    print(f"     por armario: {por_arm_l}")
    check(por_arm_l.get("KARDEX1") == 894, "KARDEX1 = 894 huecos")
    check(por_arm_l.get("KARDEX2") == 848, "KARDEX2 = 848 huecos")
    check(lov["codigo"].nunique() == 828,
          f"828 articulos distintos (obtenido {lov['codigo'].nunique()})")
    check(int(lov["en_proceso_de_baja"].sum()) == 22,
          f"22 en proceso de baja (obtenido {int(lov['en_proceso_de_baja'].sum())})")
    check(int(lov["capacidad_sin_limite"].sum()) == 24,
          f"24 con capacidad sin limite (obtenido {int(lov['capacidad_sin_limite'].sum())})")
    check(int(lov["stock_supera_capacidad"].sum()) == 43,
          f"43 con stock > capacidad (obtenido {int(lov['stock_supera_capacidad'].sum())})")

    print("\n4. Comparacion fila a fila (clave armario+ubicacion)")
    a = lov.set_index(["almacen", "ubicacion"]).sort_index()
    b = ref.rename(columns={"armario": "almacen"}).set_index(
        ["almacen", "ubicacion"]).sort_index()
    check(set(a.index) == set(b.index), "mismo conjunto de huecos")
    comunes = a.index.intersection(b.index)
    difs = [k for k in comunes if a.loc[k, "codigo"] != b.loc[k, "codigo"]]
    check(not difs, f"mismo codigo en cada hueco ({len(difs)} discrepancias)")

    print("\n" + "=" * 62)
    if fallos:
        print(f"{len(fallos)} FALLOS:")
        for f in fallos:
            print(f"  - {f}")
        return 1
    print("El parser de Lovable produce exactamente los mismos datos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
