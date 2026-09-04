"""Radiografia de la estructura de un informe multi-seccion.

Localiza cabeceras repetidas, marcas de armario y filas de relleno, para
saber que hay que descartar antes de parsear. Un informe con subtotales o
con varias secciones parseado a lo bruto mete basura en la tabla sin avisar.
"""

from __future__ import annotations

import argparse
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from kardex_io import leer_bytes

RE_ARMARIO = re.compile(r"(KARDEX|CARR|ALMAC|ARMARIO)\s*\w*\s*\(?\d*\)?", re.I)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("fichero")
    args = ap.parse_args()

    ruta = Path(args.fichero)
    xls = pd.ExcelFile(io.BytesIO(leer_bytes(ruta)))

    for hoja in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=hoja, header=None, dtype=str)
        print("=" * 72)
        print(f"HOJA {hoja!r}: {len(df)} filas x {len(df.columns)} columnas")
        print("=" * 72)

        # Cada fila, reducida a su texto, para buscar patrones.
        textos = []
        for i in range(len(df)):
            vals = [str(v).strip() for v in df.iloc[i] if pd.notna(v) and str(v).strip()]
            textos.append(" | ".join(vals))

        cabeceras = [i for i, t in enumerate(textos)
                     if "Ubicaci" in t and "Cod" in t and "Stock" in t]
        armarios = [(i, t) for i, t in enumerate(textos) if RE_ARMARIO.search(t)]
        vacias = sum(1 for t in textos if not t)

        print(f"Filas vacias        : {vacias}")
        print(f"Filas de cabecera   : {cabeceras}")
        print(f"Marcas de armario   : {[(i, t[:45]) for i, t in armarios]}")

        # Todo lo que no es dato ni cabecera ni armario: posibles totales,
        # notas al pie o secciones que habria que descartar.
        conocidas = set(cabeceras) | {i for i, _ in armarios}
        sospechosas = [
            (i, t[:70]) for i, t in enumerate(textos)
            if t and i not in conocidas and len(t.split("|")) <= 3
        ]
        print(f"Filas no tabulares  : {len(sospechosas)}")
        for i, t in sospechosas[:20]:
            print(f"   {i:>5} | {t}")
        if len(sospechosas) > 20:
            print(f"   ... y {len(sospechosas) - 20} mas")

        if cabeceras:
            ini = cabeceras[0]
            datos = [i for i in range(ini + 1, len(df))
                     if textos[i] and len(textos[i].split("|")) > 3]
            print(f"Filas de datos      : {len(datos)} "
                  f"(de la {min(datos)} a la {max(datos)})" if datos else "sin datos")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
