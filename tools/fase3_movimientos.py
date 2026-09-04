"""Fase 3: cruce de movimientos con el inventario de huecos del Kardex (Fase 1).

Responde a una pregunta muy concreta: de los articulos que hoy ocupan hueco en
el Kardex, ¿cuales no han tenido NINGUN movimiento en el periodo del informe?
Esos son candidatos a "valorar retirar e introducir en carrusel" -- salvo que
ya esten marcados BAJA, en cuyo caso la accion ya conocida es agotar sin
reponer, no retirar.

Limitacion que hay que tener siempre presente: el informe de movimientos es de
toda la farmacia, sin desglose por almacen. Puede decir "sin consumo en todo
el periodo" pero NUNCA "sin consumo en KARDEX1 pero si en KARDEX2", que es la
pregunta que de verdad dispara una consolidacion entre los dos kardex (ver
MEMORIA.md, "Pendiente"). Este script no la resuelve y lo deja escrito en el
propio dato, no solo en la documentacion.

`construir()` hace el analisis y devuelve los DataFrames; `main()` solo
imprime y exporta CSV. `tools/exportar_movimientos.py` reutiliza `construir()`
para generar el Excel, en vez de repetir el cruce por su cuenta.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from kardex_io import _a_numero, analizar_fechas, analizar_numeros, detectar_convencion
from parser_movimientos_articulo import ResultadoParseoMovimientos, parsear
from parser_stock_huecos import RE_BAJA

RUTA = Path(__file__).parent.parent / "datos" / "Informe_MovimientosArtículo.xls"
SALIDAS = Path(__file__).parent.parent / "salidas"
ANCHO = 78


def titulo(t: str) -> None:
    print("\n" + "=" * ANCHO)
    print(t)
    print("=" * ANCHO)


def num(serie: pd.Series) -> pd.Series:
    conv, _ = detectar_convencion(serie)
    return serie.map(lambda v: (_a_numero(str(v), conv)[0] if str(v).strip() else None))


@dataclass
class Fase3Resultado:
    resultados: list[ResultadoParseoMovimientos]
    desde: object
    hasta: object
    dias_periodo: int
    agregado: pd.DataFrame       # un codigo por fila, con tasas
    cruce: pd.DataFrame          # outer merge inventario x movimientos
    sin_consumo: pd.DataFrame    # en Kardex, sin movimiento en el periodo
    con_consumo_ambos: pd.DataFrame  # en ambos kardex, con consumo (K1 vs K2 sin resolver)
    sin_kardex: pd.DataFrame     # con movimiento, no en el inventario de huecos


def construir(ruta: Path = RUTA) -> Fase3Resultado:
    df, resultados, periodo = parsear(ruta)
    if not periodo:
        raise SystemExit("No se ha podido leer el periodo (Desde/Hasta) de la cabecera.")
    desde, hasta = periodo
    dias_periodo = (hasta - desde).days + 1

    df["n_movimientos_n"] = num(df["n_movimientos"])
    df["cantidad_n"] = num(df["cantidad"])

    fd = analizar_fechas(df["ultimo_movimiento"], "ultimo_movimiento")
    if not fd.formato:
        raise SystemExit(f"Formato de fecha no resuelto en ultimo_movimiento: {fd.veredicto}")
    df["ultimo_movimiento_dt"] = pd.to_datetime(
        df["ultimo_movimiento"], format="%d/%m/%Y %H:%M:%S", errors="coerce")

    agregado = (
        df.groupby("codigo")
        .agg(
            descripcion=("descripcion", "first"),
            tipo_codigo=("tipo_codigo", "first"),
            formato_codigo=("formato_codigo", "first"),
            seccion=("seccion", lambda s: "+".join(sorted(set(s)))),
            n_filas_origen=("codigo", "count"),
            n_movimientos=("n_movimientos_n", "sum"),
            cantidad=("cantidad_n", "sum"),
            ultimo_movimiento=("ultimo_movimiento_dt", "max"),
        )
        .reset_index()
    )
    agregado["dias_periodo"] = dias_periodo
    agregado["tasa_diaria"] = agregado["cantidad"] / dias_periodo
    agregado["tasa_7d"] = agregado["tasa_diaria"] * 7
    agregado["tasa_30d"] = agregado["tasa_diaria"] * 30

    fase1 = pd.read_csv(SALIDAS / "fase1_articulos.csv", sep=";", encoding="utf-8-sig")
    inv = (
        fase1.groupby("codigo")
        .agg(
            descripcion=("descripcion", "first"),
            armarios=("armario", lambda s: "+".join(sorted(set(s)))),
            huecos_total=("huecos", "sum"),
            stock_total=("stock", "sum"),
        )
        .reset_index()
    )
    inv["dado_de_baja"] = inv["descripcion"].apply(lambda d: bool(RE_BAJA.match(str(d))))

    ruta_ambos = SALIDAS / "fase1_articulos_en_ambos_kardex.csv"
    en_ambos_kardex: set[str] = set()
    if ruta_ambos.exists():
        ambos = pd.read_csv(ruta_ambos, sep=";", encoding="utf-8-sig")
        en_ambos_kardex = set(ambos["codigo"])
    inv["en_ambos_kardex"] = inv["codigo"].isin(en_ambos_kardex)

    cruce = pd.merge(inv, agregado, on="codigo", how="outer",
                     suffixes=("_inventario", "_movimientos"), indicator=True)
    # El outer merge mete NaN en las filas que no existen a un lado, lo que
    # convierte estas columnas booleanas en dtype "object" (bool + NaN
    # mezclados). Sin normalizar, un `~` sobre eso invierte bits en vez de
    # booleanos (~True == -2 en Python) y da recuentos sin sentido.
    cruce["dado_de_baja"] = cruce["dado_de_baja"].fillna(False).astype(bool)
    cruce["en_ambos_kardex"] = cruce["en_ambos_kardex"].fillna(False).astype(bool)

    sin_consumo = cruce[cruce["_merge"] == "left_only"].copy()
    sin_consumo["accion"] = sin_consumo["dado_de_baja"].map({
        True: "agotar sin reponer (ya en proceso de baja, sin accion nueva)",
        False: "valorar retirar e introducir en carrusel",
    })
    sin_consumo = (
        sin_consumo[["codigo", "descripcion_inventario", "armarios", "huecos_total",
                     "stock_total", "en_ambos_kardex", "dado_de_baja", "accion"]]
        .rename(columns={"descripcion_inventario": "descripcion"})
        .sort_values(["dado_de_baja", "codigo"])
        .reset_index(drop=True)
    )

    con_consumo_ambos = cruce[(cruce["_merge"] == "both") & (cruce["en_ambos_kardex"])].copy()
    con_consumo_ambos["k1_vs_k2"] = "no resuelto - fuente sin desglose por almacen"
    con_consumo_ambos = (
        con_consumo_ambos[["codigo", "descripcion_inventario", "armarios", "huecos_total",
                           "stock_total", "cantidad", "tasa_diaria", "k1_vs_k2"]]
        .rename(columns={"descripcion_inventario": "descripcion"})
        .sort_values("codigo")
        .reset_index(drop=True)
    )

    sin_kardex = (
        cruce[cruce["_merge"] == "right_only"]
        [["codigo", "descripcion_movimientos", "tipo_codigo", "n_movimientos", "cantidad"]]
        .rename(columns={"descripcion_movimientos": "descripcion"})
        .sort_values(["tipo_codigo", "codigo"])
        .reset_index(drop=True)
    )

    return Fase3Resultado(
        resultados=resultados, desde=desde, hasta=hasta, dias_periodo=dias_periodo,
        agregado=agregado, cruce=cruce, sin_consumo=sin_consumo,
        con_consumo_ambos=con_consumo_ambos, sin_kardex=sin_kardex,
    )


def main() -> int:
    r = construir()

    titulo("CUADRE DEL PARSEO")
    for res in r.resultados:
        estado = "CUADRA" if res.cuadra else "NO CUADRA"
        print(f"{res.filas_hoja:>5} filas = {res.filas_datos:>4} datos + "
              f"{res.filas_cabecera:>3} cabecera + {res.filas_vacias:>3} vacias + "
              f"{len(res.filas_descartadas):>2} descartadas   [{estado}]")
        print(f"secciones: {res.secciones}")
        for i, motivo in res.filas_descartadas[:10]:
            print(f"   descartada fila {i}: {motivo}")
    print(f"\nPeriodo analizado: {r.desde} .. {r.hasta}  "
          f"({r.dias_periodo} dias, convencion inclusiva)")

    titulo("PUERTAS DE VALIDACION")
    df = pd.concat([res.df for res in r.resultados], ignore_index=True)
    for col in ("n_movimientos", "cantidad"):
        d = analizar_numeros(df[col], col)
        print(f"\n[{col}] {d.veredicto}")
        print(f"   convencion: {d.convencion or 'sin resolver'} - {d.motivo_convencion}")
        print(f"   rango {d.minimo:,.0f}..{d.maximo:,.0f}  mediana {d.mediana:,.0f}  "
              f"media {d.media:,.1f}")
    fd = analizar_fechas(df["ultimo_movimiento"], "ultimo_movimiento")
    print(f"\n[ultimo_movimiento] {fd.veredicto}")
    if fd.fecha_min and fd.fecha_max:
        print(f"   rango {fd.fecha_min} .. {fd.fecha_max}")

    titulo("CODIGO DUPLICADO EN EL FICHERO FUENTE")
    dup = df[df.duplicated("codigo", keep=False)].sort_values("codigo")
    print(f"Codigos con mas de una fila en el informe: {dup['codigo'].nunique()}")
    for cod, g in dup.groupby("codigo"):
        print(f"   {cod}  {g['descripcion'].iloc[0][:40]!r}  "
              f"-> {len(g)} filas, secciones {sorted(g['seccion'].unique())}, "
              f"cantidad por fila {list(g['cantidad'])}")
    print("Se fusionan aqui (suma, en el agregado por codigo), no en el parser: "
          "el parser mantiene fidelidad 1:1 con el fichero fuente para que su "
          "cuadre siga siendo una comprobacion real.")

    titulo("FAMILIAS DE CODIGO")
    for tipo, n in df["tipo_codigo"].value_counts().items():
        print(f"   {n:>4}  {tipo}")
    print(f"\nCodigos distintos con movimiento en el periodo: {len(r.agregado)}")
    print("AVISO: tasa_7d y tasa_30d son una extrapolacion lineal desde el total "
          f"del periodo ({r.dias_periodo} dias) -- NO son una media semanal/mensual "
          "observada. Se calculan como cantidad_total / dias_periodo * 7 (o * 30).")

    titulo("CRUCE CON EL INVENTARIO DE HUECOS DEL KARDEX (FASE 1)")
    print(f"Codigos con movimiento       : {len(r.agregado):>4}")
    print(f"  con consumo (en ambos)     : {(r.cruce['_merge'] == 'both').sum():>4}")
    print(f"  sin consumo en el periodo  : {len(r.sin_consumo):>4}"
          "   <- en Kardex pero sin movimiento")
    print(f"  movimiento sin Kardex      : {len(r.sin_kardex):>4}"
          "   <- se mueve pero no esta en el inventario de huecos")

    titulo("SIN CONSUMO EN EL PERIODO (candidatos a 'valorar retirar')")
    nuevos = int((~r.sin_consumo["dado_de_baja"]).sum())
    print(f"Total: {len(r.sin_consumo)}  ({nuevos} nuevos a valorar, "
          f"{len(r.sin_consumo) - nuevos} ya en BAJA -- consistente, no es hallazgo nuevo)")
    for _, row in r.sin_consumo.iterrows():
        print(f"   {row['codigo']:<9} {row['armarios']:<16} stock {row['stock_total']:>6.0f}  "
              f"ambos_kardex={row['en_ambos_kardex']!s:<5}  {row['accion']:<50}  "
              f"{str(row['descripcion'])[:34]}")

    titulo("CON CONSUMO Y EN AMBOS KARDEX (no resuelve K1 vs K2)")
    print(f"Articulos en ambos kardex con consumo en el periodo: {len(r.con_consumo_ambos)}")
    print("Este informe NO distingue si el consumo vino de KARDEX1, de KARDEX2 o de "
          "ambos: solo dice que se movio en algun punto de la farmacia. Sigue haciendo "
          "falta un informe de movimientos con desglose por almacen para resolver la "
          "consolidacion real.")

    titulo("MOVIMIENTO SIN KARDEX (no estan en el inventario de huecos)")
    bookkeeping = r.sin_kardex[r.sin_kardex["tipo_codigo"] == "bookkeeping"]
    otros = r.sin_kardex[r.sin_kardex["tipo_codigo"] != "bookkeeping"]
    print(f"Total: {len(r.sin_kardex)}  ({len(bookkeeping)} apuntes del dispensador "
          f"DM/NOGUIA/PAC, {len(otros)} articulos V/T/Y no ubicados en KARDEX1/2)")

    SALIDAS.mkdir(exist_ok=True)
    r.agregado.to_csv(SALIDAS / "fase3_movimientos.csv", sep=";", index=False,
                      encoding="utf-8-sig")
    r.sin_consumo.to_csv(SALIDAS / "fase3_sin_consumo.csv", sep=";", index=False,
                         encoding="utf-8-sig")
    r.sin_kardex.to_csv(SALIDAS / "fase3_movimiento_sin_kardex.csv", sep=";", index=False,
                        encoding="utf-8-sig")

    titulo("SALIDAS")
    print(f"  salidas/fase3_movimientos.csv           {len(r.agregado):,} filas (un codigo por fila)")
    print(f"  salidas/fase3_sin_consumo.csv            {len(r.sin_consumo):,} filas")
    print(f"  salidas/fase3_movimiento_sin_kardex.csv  {len(r.sin_kardex):,} filas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
