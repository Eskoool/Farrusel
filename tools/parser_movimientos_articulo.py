"""Parser del INFORME DE MOVIMIENTOS DE ARTICULOS.

A diferencia del informe de stock por hueco (una fila = una ubicacion fisica),
aqui una fila = un articulo con sus totales agregados sobre un periodo: numero
de movimientos, fecha del ultimo movimiento y cantidad total movida. El
periodo analizado (Desde/Hasta) viene en la cabecera, no en cada fila.

El fichero trae dos secciones bajo el mismo formato, cada una con su propio
bloque de cabecera repetido: "Articulos Internos" y "Articulos Externos". No
hay pie de pagina ni fila de totales.

Columnas (indice 0-based en la hoja):
    0   Codigo         V28149 / DM000041 / NOGUIA / PAC
    2   Descripcion    GABAPENTINA 100 mg cap
    4   N. Movimientos numero de movimientos en el periodo
    6   Ultimo mov.    fecha y hora del ultimo movimiento (DD/MM/AAAA HH:MM:SS)
   10   Cantidad       unidades movidas en total durante el periodo

Ademas de los codigos de Kardex ya conocidos (ver parser_stock_huecos.py) este
informe trae apuntes del sistema de dispensacion que no son articulos de
Kardex: "DM" + 6 digitos, "NOGUIA" (no guia farmacoterapeutica) y "PAC"
(medicamento que aporta el paciente). Se reconocen y se marcan como
`tipo_codigo="bookkeeping"` en vez de descartarse: son datos reales, solo que
no representan un hueco fisico que gestionar.
"""

from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from kardex_io import leer_bytes
from parser_stock_huecos import RE_BAJA, RE_CODIGO, formato_codigo

COLUMNAS = {
    0: "codigo",
    2: "descripcion",
    4: "n_movimientos",
    6: "ultimo_movimiento",
    10: "cantidad",
}

RE_MARCADOR_SECCION = re.compile(r"^Articulos (Internos|Externos)$", re.I)
# Apuntes del sistema de dispensacion, no articulos reales del Kardex.
RE_BOOKKEEPING_DM = re.compile(r"^DM\d{6}$")
CODIGOS_BOOKKEEPING_TEXTO = {"NOGUIA", "PAC"}

RE_DESDE = re.compile(r"Desde:\s*\|?\s*(\d{2}/\d{2}/\d{4})", re.I)
RE_HASTA = re.compile(r"Hasta:\s*\|?\s*(\d{2}/\d{2}/\d{4})", re.I)


def _texto(v) -> str:
    return "" if pd.isna(v) else str(v).strip()


def _sin_acentos(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def clasificar_tipo_codigo(cod: str) -> str:
    """bookkeeping (apunte del dispensador) / kardex (hueco fisico real) / otro.

    Se comprueba bookkeeping primero: "DM"+6 digitos encaja tambien en el
    patron amplio de RE_CODIGO (0-2 letras + digitos), así que si se mirase
    al reves los 16 apuntes DM se colarian como si fueran codigos de Kardex.
    """
    if RE_BOOKKEEPING_DM.match(cod) or cod in CODIGOS_BOOKKEEPING_TEXTO:
        return "bookkeeping"
    if RE_CODIGO.match(cod):
        return "kardex"
    return "otro"


@dataclass
class ResultadoParseoMovimientos:
    df: pd.DataFrame
    filas_hoja: int = 0
    filas_datos: int = 0
    filas_cabecera: int = 0
    filas_vacias: int = 0
    filas_descartadas: list[tuple[int, str]] = field(default_factory=list)
    secciones: dict[str, int] = field(default_factory=dict)

    @property
    def cuadra(self) -> bool:
        """Ver ResultadoParseo.cuadra en parser_stock_huecos.py: `filas_hoja`
        se fija ANTES de recorrer nada, para que esto sea una comprobacion
        real y no una tautologia."""
        return (self.filas_datos + self.filas_cabecera + self.filas_vacias
                + len(self.filas_descartadas)) == self.filas_hoja


def parsear_hoja(df: pd.DataFrame) -> ResultadoParseoMovimientos:
    res = ResultadoParseoMovimientos(df=pd.DataFrame(), filas_hoja=len(df))
    seccion_actual: str | None = None
    filas: list[dict] = []

    for i in range(len(df)):
        celdas = {c: _texto(df.iloc[i][c]) if c in df.columns else ""
                  for c in COLUMNAS}
        crudo = [_texto(v) for v in df.iloc[i]]
        no_vacias = [v for v in crudo if v]

        if not no_vacias:
            res.filas_vacias += 1
            continue

        # Marca de seccion: "Articulos Internos" / "Articulos Externos", sola
        # en la fila.
        m = RE_MARCADOR_SECCION.match(no_vacias[0]) if len(no_vacias) == 1 else None
        if m:
            seccion_actual = m.group(1).lower()
            res.secciones[seccion_actual] = res.secciones.get(seccion_actual, 0)
            res.filas_cabecera += 1
            continue

        # Bloque de cabecera: titulo, hospital, "Grupos:/Desde:/Hasta:", fila
        # de nombres de columna. Por contenido, nunca por posicion.
        texto_fila = " ".join(no_vacias)
        texto_norm = _sin_acentos(texto_fila).upper()
        col0_norm = _sin_acentos(celdas[0]).strip().upper()
        if (
            (col0_norm == "ARTICULO" and "MOVIMIENTOS" in texto_norm)
            or "HOSPITAL" in texto_norm
            or "INFORME DE MOVIMIENTOS" in texto_norm
            or texto_fila.strip().upper().startswith("GRUPOS")
        ):
            res.filas_cabecera += 1
            continue

        # A partir de aqui deberia ser una fila de datos. El gate es
        # estructural (codigo presente, nº movimientos numerico), no un
        # patron estricto de codigo: eso ya tiro filas validas en Fase 1
        # (NOGUIA/PAC/DM+6 digitos son datos reales, no ruido).
        codigo = celdas[0]
        if not codigo:
            res.filas_descartadas.append((i, f"codigo vacio | {texto_fila[:60]}"))
            continue
        if not re.match(r"^\d+$", celdas[4]):
            res.filas_descartadas.append(
                (i, f"n_movimientos no valido: {celdas[4]!r} | codigo {codigo!r}"))
            continue

        fila = {nombre: celdas[c] for c, nombre in COLUMNAS.items()}
        fila["fila_origen"] = i
        fila["seccion"] = seccion_actual
        fila["tipo_codigo"] = clasificar_tipo_codigo(codigo)
        fila["formato_codigo"] = formato_codigo(codigo)
        fila["dado_de_baja"] = bool(RE_BAJA.match(celdas[2]))
        filas.append(fila)
        res.filas_datos += 1
        if seccion_actual:
            res.secciones[seccion_actual] += 1

    res.df = pd.DataFrame(filas)
    return res


def periodo_del_informe(df: pd.DataFrame) -> tuple[date, date] | None:
    """Extrae el periodo Desde/Hasta de la cabecera del informe.

    No es la fecha de emision (esa es la de la fila del titulo): es el rango
    que de verdad acota los movimientos contados en cada fila, y por tanto lo
    que hace falta para convertir un total en una tasa diaria.
    """
    for i in range(min(10, len(df))):
        celdas = [_texto(v) for v in df.iloc[i]]
        texto_fila = " | ".join(c for c in celdas if c)
        if not texto_fila:
            continue
        m_desde = RE_DESDE.search(texto_fila)
        m_hasta = RE_HASTA.search(texto_fila)
        if m_desde and m_hasta:
            desde = datetime.strptime(m_desde.group(1), "%d/%m/%Y").date()
            hasta = datetime.strptime(m_hasta.group(1), "%d/%m/%Y").date()
            return desde, hasta
    return None


def parsear(
    ruta: Path,
) -> tuple[pd.DataFrame, list[ResultadoParseoMovimientos], tuple[date, date] | None]:
    xls = pd.ExcelFile(io.BytesIO(leer_bytes(ruta)))
    partes, resultados, periodos = [], [], set()
    for hoja in xls.sheet_names:
        hoja_df = pd.read_excel(xls, sheet_name=hoja, header=None, dtype=str)
        periodo = periodo_del_informe(hoja_df)
        if periodo:
            periodos.add(periodo)
        r = parsear_hoja(hoja_df)
        r.df["hoja"] = hoja
        resultados.append(r)
        partes.append(r.df)
    if len(periodos) > 1:
        raise ValueError(f"Las hojas traen periodos distintos: {sorted(periodos)}. "
                         "No se puede tratar como un unico corte.")
    periodo = periodos.pop() if periodos else None
    df = pd.concat(partes, ignore_index=True)
    return df, resultados, periodo
