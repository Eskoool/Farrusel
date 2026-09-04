"""Fase 1: censo del Kardex a partir del informe de stock por hueco.

Responde a lo que hace falta antes de proponer nada:
  - cuantos articulos y cuantos huecos hay en cada armario
  - que articulos estan en los dos kardex a la vez (candidatos a consolidar)
  - cuanto espacio esta ocupado, bloqueado o vacio
  - que anomalias trae el dato

No propone cambios todavia: sin los minimos y maximos parametrizados de la
maquina (Fase 2) no hay contra que comparar.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from kardex_io import analizar_numeros, detectar_convencion
from parser_stock_huecos import parsear

RUTA = Path(__file__).parent.parent / "datos" / "Informe_StockHuecos.xls"
SALIDAS = Path(__file__).parent.parent / "salidas"
ANCHO = 78


def titulo(t: str) -> None:
    print("\n" + "=" * ANCHO)
    print(t)
    print("=" * ANCHO)


def num(serie: pd.Series) -> pd.Series:
    conv, _ = detectar_convencion(serie)
    from kardex_io import _a_numero
    return serie.map(lambda v: (_a_numero(str(v), conv)[0] if str(v).strip() else None))


def main() -> int:
    df, resultados, fecha_corte = parsear(RUTA)

    titulo("CUADRE DEL PARSEO")
    total_hoja = total_datos = total_cab = total_vac = total_desc = 0
    for r in resultados:
        estado = "CUADRA" if r.cuadra else "NO CUADRA"
        print(f"{r.df['hoja'].iloc[0] if len(r.df) else '?':<16} "
              f"{r.filas_hoja:>5} filas = {r.filas_datos:>4} datos + "
              f"{r.filas_cabecera:>3} cabecera + {r.filas_vacias:>3} vacias + "
              f"{len(r.filas_descartadas):>2} descartadas   [{estado}]")
        print(f"{'':16} armarios: {r.armarios}")
        for i, motivo in r.filas_descartadas[:10]:
            print(f"{'':16}   descartada fila {i}: {motivo}")
        total_hoja += r.filas_hoja
        total_datos += r.filas_datos
        total_cab += r.filas_cabecera
        total_vac += r.filas_vacias
        total_desc += len(r.filas_descartadas)
    print(f"\nTOTAL: {total_hoja} filas de fichero -> {total_datos} filas de datos")
    if total_desc:
        print(f"ATENCION: {total_desc} filas descartadas, revisar arriba")

    # ---------------------------------------------------------------- limpieza
    df["stock_n"] = num(df["stock"])
    df["capacidad_n"] = num(df["capacidad"])
    df["bloqueado"] = ~df["bloqueo"].str.strip().str.lower().eq("sin bloquear")
    df["ocupado"] = df["stock_n"].fillna(0) > 0

    titulo("CENSO POR ARMARIO")
    print(f"{'Armario':<12} {'Huecos':>8} {'Articulos':>10} {'Ocupados':>9} "
          f"{'Vacios':>8} {'Bloqueados':>11}")
    print("-" * 62)
    for arm, g in df.groupby("armario"):
        print(f"{arm:<12} {len(g):>8,} {g['codigo'].nunique():>10,} "
              f"{int(g['ocupado'].sum()):>9,} {int((~g['ocupado']).sum()):>8,} "
              f"{int(g['bloqueado'].sum()):>11,}")
    print("-" * 62)
    print(f"{'TOTAL':<12} {len(df):>8,} {df['codigo'].nunique():>10,} "
          f"{int(df['ocupado'].sum()):>9,} {int((~df['ocupado']).sum()):>8,} "
          f"{int(df['bloqueado'].sum()):>11,}")

    titulo("HUECOS POR ARTICULO (seccion 4.3 del brief)")
    huecos = (df.groupby(["armario", "codigo"])
                .agg(huecos=("ubicacion", "count"),
                     stock=("stock_n", "sum"),
                     capacidad=("capacidad_n", "sum"),
                     descripcion=("descripcion", "first"))
                .reset_index())
    for arm, g in huecos.groupby("armario"):
        rep = g["huecos"].value_counts().sort_index()
        print(f"\n{arm}:")
        for n, cuantos in rep.items():
            etiqueta = ("Normal" if n == 1 else "Medio" if n <= 5 else "ALTO")
            print(f"   {n} hueco/s: {cuantos:>4} articulos   [{etiqueta}]")
        altos = g[g["huecos"] > 5].sort_values("huecos", ascending=False)
        if len(altos):
            print(f"   Articulos con mas de 5 huecos ({len(altos)}):")
            for _, r in altos.head(10).iterrows():
                print(f"      {r['codigo']}  {r['huecos']:>2} huecos  "
                      f"{str(r['descripcion'])[:44]}")

    titulo("FORMATOS DE CODIGO")
    for fmt, n in df["formato_codigo"].value_counts().items():
        raros = ""
        if n <= 5:
            ejemplos = df[df["formato_codigo"] == fmt]["codigo"].unique()[:5]
            raros = f"   -> {', '.join(ejemplos)}"
        print(f"   {n:>5}  {fmt}{raros}")
    print("\nLos formatos minoritarios conviene confirmarlos con el maestro: "
          "un codigo de 7 digitos donde el resto tiene 5 puede ser un error "
          "de grabacion o un Codigo Nacional colado.")

    titulo("ARTICULOS DADOS DE BAJA QUE SIGUEN OCUPANDO HUECO")
    bajas = df[df["dado_de_baja"]]
    print(f"Huecos ocupados por articulos marcados 'baja': {len(bajas)} "
          f"({bajas['codigo'].nunique()} articulos distintos)")
    if len(bajas):
        print(f"Stock inmovilizado en esos huecos: "
              f"{bajas['stock_n'].sum():,.0f} unidades\n")
        print(f"{'Armario':<9} {'Ubicacion':<17} {'Codigo':<9} {'Stock':>6}  Descripcion")
        print("-" * 78)
        for _, r in bajas.sort_values(["armario", "codigo"]).head(30).iterrows():
            print(f"{r['armario']:<9} {r['ubicacion']:<17} {r['codigo']:<9} "
                  f"{r['stock_n']:>6.0f}  {str(r['descripcion'])[:32]}")
        if len(bajas) > 30:
            print(f"... y {len(bajas) - 30} mas")
        bajas.to_csv(SALIDAS / "fase1_articulos_de_baja.csv", sep=";",
                     index=False, encoding="utf-8-sig")

    titulo("ARTICULOS EN LOS DOS KARDEX (candidatos a consolidacion)")
    por_arm = df.groupby("codigo")["armario"].nunique()
    en_ambos = sorted(por_arm[por_arm > 1].index)
    print(f"Articulos presentes en K1 y K2: {len(en_ambos)} "
          f"de {df['codigo'].nunique()} distintos")
    if en_ambos:
        detalle = (df[df["codigo"].isin(en_ambos)]
                   .groupby(["codigo", "armario"])
                   .agg(huecos=("ubicacion", "count"), stock=("stock_n", "sum"))
                   .reset_index()
                   .pivot(index="codigo", columns="armario",
                          values=["huecos", "stock"]))
        detalle.columns = [f"{a}_{b}" for a, b in detalle.columns]
        descs = df.groupby("codigo")["descripcion"].first()
        detalle["descripcion"] = descs
        print(f"\n{'Codigo':<9} {'H_K1':>5} {'H_K2':>5} {'S_K1':>7} {'S_K2':>7}  Descripcion")
        print("-" * 78)
        for cod, r in detalle.head(25).iterrows():
            print(f"{cod:<9} {r.get('huecos_KARDEX1', 0):>5.0f} "
                  f"{r.get('huecos_KARDEX2', 0):>5.0f} "
                  f"{r.get('stock_KARDEX1', 0):>7.0f} "
                  f"{r.get('stock_KARDEX2', 0):>7.0f}  "
                  f"{str(r['descripcion'])[:36]}")
        if len(detalle) > 25:
            print(f"... y {len(detalle) - 25} mas (fichero completo en salidas/)")
        detalle.to_csv(SALIDAS / "fase1_articulos_en_ambos_kardex.csv",
                       sep=";", encoding="utf-8-sig")

    titulo("OCUPACION DEL ESPACIO")
    # El brief (4.3) avisaba de un placeholder de "sin limite" en capacidad.
    # Aqui aparece como 999.999.999. Sumarlo como si fuera capacidad real
    # convierte el % de llenado en 0,0% y lo hace inservible.
    UMBRAL_SIN_LIMITE = 1_000_000
    df["cap_sin_limite"] = df["capacidad_n"] >= UMBRAL_SIN_LIMITE
    n_sin_limite = int(df["cap_sin_limite"].sum())
    print(f"Huecos con capacidad 'sin limite' (>= {UMBRAL_SIN_LIMITE:,}): "
          f"{n_sin_limite} de {len(df):,}")
    if n_sin_limite:
        print("Valores usados como placeholder: "
              f"{sorted(df.loc[df['cap_sin_limite'], 'capacidad_n'].unique())}")
        print("Se excluyen del calculo de llenado: no son capacidad real.\n")
    real = df[~df["cap_sin_limite"]]
    for arm, g in real.groupby("armario"):
        cap, stk = g["capacidad_n"].sum(), g["stock_n"].sum()
        excl = int(df[(df["armario"] == arm) & df["cap_sin_limite"]].shape[0])
        print(f"{arm}: stock {stk:,.0f} uds sobre capacidad {cap:,.0f} uds "
              f"-> {100 * stk / cap if cap else 0:.1f}% de llenado fisico "
              f"({len(g):,} huecos; {excl} excluidos por capacidad sin limite)")

    sobre = real[real["stock_n"] > real["capacidad_n"]]
    print(f"\nHuecos con stock por encima de su capacidad: {len(sobre)}")
    for _, r in sobre.head(10).iterrows():
        print(f"   {r['armario']} {r['ubicacion']} {r['codigo']}  "
              f"stock {r['stock_n']:.0f} > cap {r['capacidad_n']:.0f}  "
              f"{str(r['descripcion'])[:34]}")

    titulo("TIPOS DE HUECO")
    for arm, g in df.groupby("armario"):
        print(f"\n{arm}:")
        for tipo, n in g["tipo_hueco"].value_counts().items():
            print(f"   {n:>4}  {tipo}")

    titulo("BLOQUEOS (posicion fija)")
    for valor, n in df["bloqueo"].value_counts().items():
        print(f"   {n:>5}  {valor}")

    titulo("PUERTAS DE VALIDACION")
    for col in ("stock", "capacidad"):
        d = analizar_numeros(df[col], col)
        print(f"\n[{col}] {d.veredicto}")
        print(f"   convencion: {d.convencion or 'sin resolver'} - {d.motivo_convencion}")
        print(f"   rango {d.minimo:,.0f}..{d.maximo:,.0f}  mediana {d.mediana:,.0f}  "
              f"media {d.media:,.1f}  negativos {d.negativas}")
    dup = df[df.duplicated(subset=["armario", "ubicacion"], keep=False)]
    print(f"\n[ubicacion] duplicadas dentro del mismo armario: {len(dup)}")
    for _, r in dup.head(6).iterrows():
        print(f"   {r['armario']} {r['ubicacion']} -> {r['codigo']}")
    sin_desc = df[df["descripcion"].str.strip() == ""]
    print(f"[descripcion] vacias: {len(sin_desc)}")

    SALIDAS.mkdir(exist_ok=True)
    df.to_csv(SALIDAS / "fase1_huecos.csv", sep=";", index=False,
              encoding="utf-8-sig")
    huecos.to_csv(SALIDAS / "fase1_articulos.csv", sep=";", index=False,
                  encoding="utf-8-sig")
    titulo("SALIDAS")
    print(f"  salidas/fase1_huecos.csv      {len(df):,} filas (una por hueco)")
    print(f"  salidas/fase1_articulos.csv   {len(huecos):,} filas (articulo x armario)")
    if en_ambos:
        print(f"  salidas/fase1_articulos_en_ambos_kardex.csv   {len(en_ambos):,} filas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
