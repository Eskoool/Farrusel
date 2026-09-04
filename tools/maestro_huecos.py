"""Fichero maestro: integra Fase 1 (un hueco fisico por fila: ubicacion,
capacidad, tipo_hueco, stock...) con Fase 3 (consumo por articulo en el
periodo, cruzado contra el inventario).

El grano es el de Fase 1 -- un hueco por fila -- porque es el unico que
conserva `ubicacion`, y porque `capacidad` es un dato por hueco (dos huecos
del mismo articulo pueden tener capacidades distintas). Los datos de Fase 3
son por codigo y de toda la farmacia (sin desglose por hueco, limitacion ya
documentada en MEMORIA.md): se difunden a cada hueco de ese codigo con el
prefijo `articulo_` y el sufijo `_periodo`, mas una columna
`articulo_n_huecos` con la multiplicidad -- para que nadie sume esas columnas
entre filas de este fichero por error (contaria el mismo consumo 2x/3x).

IMPORTANTE (aviso pedido explicitamente): `tipo_hueco` NO determina
`capacidad`. Son dos columnas independientes del informe original (columnas
"Cap." y "Hueco" -- ver parser_stock_huecos.py). `tipo_hueco` solo tiene 11
valores, todos modelos fisicos de cajon (tamano/LEDs/nº de divisiones), no una
cifra de capacidad: un mismo tipo_hueco convive con decenas de capacidades
muy distintas. Para Fase 4, min/max deben compararse contra `capacidad`,
nunca contra `tipo_hueco`.

Sistema de alertas: `capacidad_sin_limite` (el placeholder 999999999) se trata
aqui como ERROR A CORREGIR, no como dato neutro -- sin una capacidad real
configurada no se puede validar min/max contra ella en Fase 4. `n_alertas`
cuenta las alertas rojas de cada hueco (stock_supera_capacidad +
capacidad_sin_limite + "valorar retirar"). `alerta_capacidad` trae el texto
explicativo de que corregir para `capacidad_sin_limite` y
`stock_supera_capacidad` -- antes solo eran un True/False con color, sin decir
que accion tomar.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from exportar_explotacion import construir as construir_huecos
from fase3_movimientos import Fase3Resultado, construir as construir_fase3

SALIDAS = Path(__file__).parent.parent / "salidas"
ANCHO = 78

ACCION_RETIRAR = "valorar retirar e introducir en carrusel"
ACCION_AGOTAR = "agotar sin reponer (ya en proceso de baja, sin accion nueva)"

COLUMNAS_MAESTRO = [
    "fecha_descarga", "almacen", "ubicacion", "codigo", "descripcion",
    "stock", "capacidad", "tipo_hueco", "bloqueado", "lote", "fecha_lote",
    "en_proceso_de_baja", "capacidad_sin_limite", "stock_supera_capacidad",
    "alerta_capacidad",
    "formato_codigo",
    "articulo_n_huecos", "articulo_tiene_consumo_periodo",
    "articulo_periodo_dias", "articulo_cantidad_periodo",
    "articulo_n_movimientos_periodo", "articulo_tasa_diaria_periodo",
    "articulo_tasa_7d_periodo", "articulo_tasa_30d_periodo",
    "articulo_ultimo_movimiento", "articulo_en_ambos_kardex",
    "articulo_k1_vs_k2", "articulo_sin_consumo_accion",
    "n_alertas",
]


def titulo(t: str) -> None:
    print("\n" + "=" * ANCHO)
    print(t)
    print("=" * ANCHO)


@dataclass
class MaestroResultado:
    maestro: pd.DataFrame
    f3: Fase3Resultado


def construir() -> MaestroResultado:
    hueco = construir_huecos()
    f3 = construir_fase3()
    cruce = f3.cruce

    n_huecos_por_codigo = hueco.groupby("codigo")["codigo"].transform("size")

    articulo = pd.DataFrame({"codigo": cruce["codigo"]})
    articulo["articulo_tiene_consumo_periodo"] = cruce["_merge"] == "both"
    articulo["articulo_periodo_dias"] = f3.dias_periodo
    articulo["articulo_cantidad_periodo"] = cruce["cantidad"].fillna(0.0)
    articulo["articulo_n_movimientos_periodo"] = cruce["n_movimientos"].fillna(0.0)
    articulo["articulo_tasa_diaria_periodo"] = cruce["tasa_diaria"].fillna(0.0)
    articulo["articulo_tasa_7d_periodo"] = cruce["tasa_7d"].fillna(0.0)
    articulo["articulo_tasa_30d_periodo"] = cruce["tasa_30d"].fillna(0.0)
    # Sin movimiento no es "0 dias desde el ultimo": es que no hay ninguno.
    articulo["articulo_ultimo_movimiento"] = cruce["ultimo_movimiento"]
    articulo["articulo_en_ambos_kardex"] = cruce["en_ambos_kardex"]

    sin_consumo = cruce["_merge"] == "left_only"
    articulo["articulo_sin_consumo_accion"] = None
    articulo.loc[sin_consumo & cruce["dado_de_baja"], "articulo_sin_consumo_accion"] = ACCION_AGOTAR
    articulo.loc[sin_consumo & ~cruce["dado_de_baja"], "articulo_sin_consumo_accion"] = ACCION_RETIRAR

    con_consumo_ambos = (cruce["_merge"] == "both") & cruce["en_ambos_kardex"]
    articulo["articulo_k1_vs_k2"] = None
    articulo.loc[con_consumo_ambos, "articulo_k1_vs_k2"] = (
        "no resuelto - fuente sin desglose por almacen")

    maestro = hueco.merge(articulo, on="codigo", how="left", validate="m:1")
    maestro["articulo_n_huecos"] = n_huecos_por_codigo

    # Texto explicativo de la alerta de capacidad -- antes solo habia un
    # True/False y un color, sin decir que hacer. capacidad_sin_limite y
    # stock_supera_capacidad son mutuamente excluyentes (exportar_explotacion
    # pone capacidad a None cuando hay placeholder, y stock_supera_capacidad
    # exige capacidad no nula), asi que no hay conflicto entre los dos textos.
    maestro["alerta_capacidad"] = None
    m_sin_limite = maestro["capacidad_sin_limite"]
    maestro.loc[m_sin_limite, "alerta_capacidad"] = (
        "Corregir: capacidad no configurada en la maquina (placeholder "
        "999999999) -- configurar una capacidad real antes de fijar min/max."
    )
    m_supera = maestro["stock_supera_capacidad"]
    maestro.loc[m_supera, "alerta_capacidad"] = maestro.loc[m_supera].apply(
        lambda r: (f"Corregir: stock ({r['stock']:.0f}) supera la capacidad "
                   f"configurada ({r['capacidad']:.0f}) -- revisar si es una "
                   "unidad de medida distinta (envases vs aplicaciones) o "
                   "reubicar el exceso."),
        axis=1,
    )

    maestro["n_alertas"] = (
        maestro["stock_supera_capacidad"].astype(int)
        + maestro["capacidad_sin_limite"].astype(int)
        + (maestro["articulo_sin_consumo_accion"] == ACCION_RETIRAR).astype(int)
    )

    maestro = maestro[COLUMNAS_MAESTRO].sort_values(["almacen", "ubicacion"]).reset_index(drop=True)
    return MaestroResultado(maestro=maestro, f3=f3)


def main() -> int:
    r = construir()
    m = r.maestro

    titulo("CUADRE MAESTRO DE HUECOS")
    con_consumo = int(m["articulo_tiene_consumo_periodo"].sum())
    sin_consumo = int((~m["articulo_tiene_consumo_periodo"]).sum())
    print(f"Huecos totales (Fase 1)         : {len(m):,}")
    print(f"  con consumo en el periodo     : {con_consumo:,}")
    print(f"  sin consumo en el periodo     : {sin_consumo:,}  "
          f"({m.loc[~m['articulo_tiene_consumo_periodo'], 'codigo'].nunique()} codigos)")
    print(f"Codigos distintos               : {m['codigo'].nunique():,}")

    titulo("ALERTAS (sistema de colores: rojo = error a corregir)")
    print(f"stock_supera_capacidad          : {int(m['stock_supera_capacidad'].sum()):,}")
    print(f"capacidad_sin_limite (a corregir): {int(m['capacidad_sin_limite'].sum()):,}")
    print(f"articulo_sin_consumo_accion=retirar: "
          f"{int((m['articulo_sin_consumo_accion'] == ACCION_RETIRAR).sum()):,}")
    print(f"huecos con alguna alerta roja (n_alertas>0): {int((m['n_alertas'] > 0).sum()):,}")

    titulo("AVISO")
    print("tipo_hueco NO determina capacidad -- son columnas independientes del")
    print("informe original. Ver docstring de este fichero / MEMORIA.md.")
    print("Las columnas articulo_*_periodo son totales de TODA la farmacia por")
    print("codigo, repetidos en cada hueco que ocupa (ver articulo_n_huecos):")
    print("NO sumar entre filas de este fichero.")

    SALIDAS.mkdir(exist_ok=True)
    m.to_csv(SALIDAS / "maestro_huecos.csv", sep=";", index=False, encoding="utf-8-sig")

    titulo("SALIDAS")
    print(f"  salidas/maestro_huecos.csv   {len(m):,} filas x {len(m.columns)} columnas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
