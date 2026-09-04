"""Vuelca las primeras filas de una hoja sin interpretar nada.

Los informes de maquina traen titulo, metadatos y a veces varias tablas en
la misma hoja. Antes de decidir donde esta la cabecera hay que verlo crudo.

    python tools/explorar_hoja.py datos/fichero.xls --hoja 0 --filas 40
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from kardex_io import leer_bytes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("fichero")
    ap.add_argument("--hoja", default="0")
    ap.add_argument("--filas", type=int, default=40)
    ap.add_argument("--desde", type=int, default=0)
    ap.add_argument("--ancho", type=int, default=22, help="Ancho por celda")
    args = ap.parse_args()

    ruta = Path(args.fichero)
    hoja: object = int(args.hoja) if args.hoja.isdigit() else args.hoja

    df = pd.read_excel(io.BytesIO(leer_bytes(ruta)), sheet_name=hoja,
                       header=None, dtype=str)
    print(f"Hoja {hoja!r}: {len(df)} filas x {len(df.columns)} columnas\n")

    # Solo las columnas con algun dato: los informes vienen llenos de
    # columnas de relleno que solo estorban al leer.
    utiles = [c for c in df.columns if df[c].notna().any()]
    print(f"Columnas con datos: {utiles}\n")

    cab = "fila | " + " | ".join(f"[{c}]".center(args.ancho) for c in utiles)
    print(cab)
    print("-" * len(cab))

    fin = min(args.desde + args.filas, len(df))
    for i in range(args.desde, fin):
        celdas = []
        for c in utiles:
            v = df.iloc[i][c]
            s = "" if pd.isna(v) else str(v).strip()
            celdas.append(s[:args.ancho].ljust(args.ancho))
        if any(c.strip() for c in celdas):
            print(f"{i:>4} | " + " | ".join(celdas))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
