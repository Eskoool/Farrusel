"""Carga el corte de inventario de huecos en Supabase.

Usa la API REST con la clave publicable, que es exactamente el camino que
seguira la app: si funciona aqui, funcionara desde Farrusel.

Orden obligatorio: primero `articulo` (el maestro), despues
`inventario_huecos_kardex`, que lo referencia por clave ajena.

Es idempotente: reprocesar el mismo fichero no duplica nada, gracias a la
restriccion unica (fecha_descarga, almacen, ubicacion).
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from exportar_explotacion import construir

URL = "https://sgpbdzphweyeaegzesvb.supabase.co"
# Clave publicable, la misma que lleva el frontend. Es publica por diseno.
KEY = "sb_publishable_Y4M3WKzOScDVTCYrIWDLiQ_u7Kcdvir"
LOTE = 500


def peticion(metodo: str, ruta: str, cuerpo=None, prefer: str | None = None):
    datos = json.dumps(cuerpo, default=str).encode() if cuerpo is not None else None
    req = urllib.request.Request(f"{URL}/rest/v1/{ruta}", data=datos, method=metodo)
    req.add_header("apikey", KEY)
    req.add_header("Authorization", f"Bearer {KEY}")
    req.add_header("Content-Type", "application/json")
    if prefer:
        req.add_header("Prefer", prefer)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            txt = r.read().decode()
            return json.loads(txt) if txt.strip() else None
    except urllib.error.HTTPError as e:
        raise SystemExit(f"\nERROR {e.code} en {metodo} {ruta}\n{e.read().decode()}")


def contar(tabla: str, filtro: str = "") -> int:
    req = urllib.request.Request(
        f"{URL}/rest/v1/{tabla}?select=*{filtro}", method="HEAD")
    req.add_header("apikey", KEY)
    req.add_header("Authorization", f"Bearer {KEY}")
    req.add_header("Prefer", "count=exact")
    with urllib.request.urlopen(req, timeout=60) as r:
        rango = r.headers.get("Content-Range", "*/0")
    return int(rango.split("/")[-1])


def por_lotes(tabla: str, filas: list[dict], on_conflict: str) -> int:
    total = 0
    for i in range(0, len(filas), LOTE):
        trozo = filas[i:i + LOTE]
        peticion("POST", f"{tabla}?on_conflict={on_conflict}", trozo,
                 prefer="resolution=merge-duplicates,return=minimal")
        total += len(trozo)
        print(f"   {tabla}: {total:,}/{len(filas):,}", end="\r")
    print(f"   {tabla}: {total:,}/{len(filas):,}   ")
    return total


def main() -> int:
    df = construir()
    corte = df["fecha_descarga"].iloc[0]
    print(f"Corte {corte} · {len(df):,} huecos\n")

    # ---------------------------------------------------------- maestro
    # Un mismo codigo puede venir con descripciones distintas en K1 y K2
    # (mayusculas, espacios, prefijo BAJA anadido en una sola). Se toma la
    # mas frecuente y se avisa de las discrepancias en vez de elegir a ciegas.
    discrepantes = []
    articulos = []
    for cod, g in df.groupby("codigo"):
        descs = Counter(g["descripcion"])
        if len(descs) > 1:
            discrepantes.append((cod, list(descs)))
        articulos.append({
            "codigo": cod,
            "descripcion": descs.most_common(1)[0][0],
            "ubicaciones": sorted(g["almacen"].unique().tolist()),
            "en_proceso_de_baja": bool(g["en_proceso_de_baja"].any()),
            "formato_codigo": g["formato_codigo"].iloc[0],
        })

    print(f"Maestro: {len(articulos):,} articulos distintos")
    if discrepantes:
        print(f"AVISO: {len(discrepantes)} codigos con descripcion distinta "
              f"entre armarios (se usa la mas frecuente):")
        for cod, ds in discrepantes[:8]:
            print(f"   {cod}: {ds}")
    print("Subiendo articulo...")
    por_lotes("articulo", articulos, "codigo")

    # ------------------------------------------------------- inventario
    filas = []
    for _, r in df.iterrows():
        filas.append({
            "fecha_descarga": str(r["fecha_descarga"]),
            "almacen": r["almacen"],
            "ubicacion": r["ubicacion"],
            "codigo": r["codigo"],
            "descripcion": r["descripcion"],
            "stock": None if pd.isna(r["stock"]) else float(r["stock"]),
            "capacidad": None if pd.isna(r["capacidad"]) else float(r["capacidad"]),
            "tipo_hueco": r["tipo_hueco"],
            "bloqueado": bool(r["bloqueado"]),
            "lote": r["lote"] if pd.notna(r["lote"]) else None,
            "fecha_lote": r["fecha_lote"] if pd.notna(r["fecha_lote"]) else None,
            "en_proceso_de_baja": bool(r["en_proceso_de_baja"]),
            "capacidad_sin_limite": bool(r["capacidad_sin_limite"]),
            "stock_supera_capacidad": bool(r["stock_supera_capacidad"]),
        })
    print("Subiendo inventario_huecos_kardex...")
    por_lotes("inventario_huecos_kardex", filas,
              "fecha_descarga,almacen,ubicacion")

    # ---------------------------------------------------------- cuadre
    print("\nVERIFICACION")
    n_art = contar("articulo")
    n_inv = contar("inventario_huecos_kardex", f"&fecha_descarga=eq.{corte}")
    print(f"  articulo                            : {n_art:,} "
          f"(esperado {len(articulos):,})  "
          f"{'OK' if n_art == len(articulos) else 'NO CUADRA'}")
    print(f"  inventario_huecos_kardex (corte {corte}): {n_inv:,} "
          f"(esperado {len(df):,})  "
          f"{'OK' if n_inv == len(df) else 'NO CUADRA'}")
    return 0 if (n_art == len(articulos) and n_inv == len(df)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
