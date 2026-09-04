"""Parser del INFORME DE STOCK DE ARMARIO POR HUECO.

El informe es una salida paginada para imprimir: cada ~48 filas repite el
bloque de cabecera completo (hospital, fecha, titulo, "Armarios:", el armario
y la fila de nombres de columna). En el fichero del 19/08/2026 son 30 bloques
en KARDEX1 y 29 en KARDEX2. Parsearlo sin filtrar mete esas cabeceras como si
fueran medicamentos.

Una fila de datos es una UBICACION FISICA, no un articulo: un mismo codigo
aparece tantas veces como huecos ocupa. Esa multiplicidad es justo la
informacion que necesita el analisis de espacio.

Columnas (indice 0-based en la hoja):
    1  Ubicacion    001-01-01-42-01
    2  Cod.         V10918
    4  Descripcion  ABACAVIR 300 mg comp
    6  Stock        unidades actuales en ese hueco
    9  Cap.         capacidad maxima que admite el hueco
   10  Bloq.        "Sin bloquear" / bloqueado = posicion fija
   12  Hueco        tipo de hueco asignado
   14  Lote         (vacio en este informe)
   18  Fecha        (vacio en este informe)
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from kardex_io import leer_bytes

COLUMNAS = {
    1: "ubicacion",
    2: "codigo",
    4: "descripcion",
    6: "stock",
    9: "capacidad",
    10: "bloqueo",
    12: "tipo_hueco",
    14: "lote",
    18: "fecha_lote",
}

RE_UBICACION = re.compile(r"^\d{3}(?:-\d{2}){4}$")
# El catalogo real es mas variado de lo que sugeria el brief: ademas de
# V12345 / T12345 aparecen V + 7 digitos (V0715227, BECOZYME C FTE) y codigos
# puramente numericos de 6 digitos (676262, RILUZOL 50 mg), que parecen
# Codigo Nacional. Se acepta el rango amplio y se informa del reparto por
# formato: descartar filas validas por un patron estrecho seria peor que
# admitir alguna rara y verla en el informe.
RE_CODIGO = re.compile(r"^[A-Z]{0,2}\d{4,8}$")
RE_ARMARIO = re.compile(r"^(KARDEX\d+)\((\d+)\)$")
# Marcados como baja en el maestro pero todavia ocupando hueco.
RE_BAJA = re.compile(r"^\s*baja\b", re.I)


def formato_codigo(cod: str) -> str:
    """Clasifica el codigo por su forma, para detectar familias anomalas."""
    m = re.match(r"^([A-Z]*)(\d+)$", cod)
    if not m:
        return "otro"
    prefijo, digitos = m.group(1), m.group(2)
    return f"{prefijo or '(sin letra)'}+{len(digitos)} digitos"


@dataclass
class ResultadoParseo:
    df: pd.DataFrame
    filas_hoja: int = 0
    filas_datos: int = 0
    filas_cabecera: int = 0
    filas_vacias: int = 0
    filas_descartadas: list[tuple[int, str]] = field(default_factory=list)
    armarios: dict[str, int] = field(default_factory=dict)

    @property
    def cuadra(self) -> bool:
        """Toda fila de la hoja tiene que estar contabilizada en alguna categoria.

        Solo vale como comprobacion porque `filas_hoja` se fija ANTES de
        recorrer nada, desde len(df). Si se contara sumando dentro del mismo
        bucle que reparte las categorias, el resultado seria cierto siempre
        por construccion y no detectaria nada.
        """
        return (self.filas_datos + self.filas_cabecera + self.filas_vacias
                + len(self.filas_descartadas)) == self.filas_hoja


def _texto(v) -> str:
    return "" if pd.isna(v) else str(v).strip()


def parsear_hoja(df: pd.DataFrame) -> ResultadoParseo:
    res = ResultadoParseo(df=pd.DataFrame(), filas_hoja=len(df))
    armario_actual: str | None = None
    filas: list[dict] = []

    for i in range(len(df)):
        celdas = {c: _texto(df.iloc[i][c]) if c in df.columns else ""
                  for c in COLUMNAS}
        crudo = [_texto(v) for v in df.iloc[i]]
        no_vacias = [v for v in crudo if v]

        if not no_vacias:
            res.filas_vacias += 1
            continue

        # Marca de armario: "KARDEX1(1)"
        m = RE_ARMARIO.match(no_vacias[0]) if len(no_vacias) == 1 else None
        if m:
            armario_actual = m.group(1)
            res.armarios[armario_actual] = res.armarios.get(armario_actual, 0)
            res.filas_cabecera += 1
            continue

        # Bloque de cabecera de pagina: titulo, hospital, "Armarios:", nombres
        # de columna. Se reconocen por su contenido, no por su posicion, para
        # que el parser no dependa de que la paginacion no cambie nunca.
        texto_fila = " ".join(no_vacias)
        if (celdas[1] == "Ubicación" or celdas[1] == "Ubicacion"
                or "INFORME DE STOCK" in texto_fila
                or "HOSPITAL" in texto_fila
                or texto_fila.startswith("Armarios")):
            res.filas_cabecera += 1
            continue

        # A partir de aqui deberia ser una fila de datos. Si no lo parece, se
        # aparta y se cuenta: nunca se descarta nada en silencio.
        if not RE_UBICACION.match(celdas[1]):
            res.filas_descartadas.append((i, f"ubicacion no valida: {celdas[1]!r} | {texto_fila[:60]}"))
            continue
        if not RE_CODIGO.match(celdas[2]):
            res.filas_descartadas.append((i, f"codigo no valido: {celdas[2]!r}"))
            continue

        fila = {nombre: celdas[c] for c, nombre in COLUMNAS.items()}
        fila["armario"] = armario_actual
        fila["fila_origen"] = i
        fila["formato_codigo"] = formato_codigo(celdas[2])
        fila["dado_de_baja"] = bool(RE_BAJA.match(celdas[4]))
        filas.append(fila)
        res.filas_datos += 1
        if armario_actual:
            res.armarios[armario_actual] += 1

    res.df = pd.DataFrame(filas)
    return res


RE_FECHA_INFORME = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")


def fecha_del_informe(df: pd.DataFrame) -> str | None:
    """Extrae la fecha de emision de la cabecera del informe.

    Se lee del fichero en vez de teclearla: la fecha de descarga identifica
    el corte, y un corte mal fechado hace inservible la comparacion entre
    revisiones, que es el objetivo del proyecto.

    Solo acepta DD/MM/YYYY porque es lo que emite este informe; si algun dia
    cambia el formato, devuelve None y obliga a mirarlo en vez de adivinar.
    """
    for i in range(min(30, len(df))):
        for v in df.iloc[i]:
            if pd.isna(v):
                continue
            m = RE_FECHA_INFORME.match(str(v).strip())
            if m:
                dia, mes, anio = m.groups()
                if 1 <= int(mes) <= 12 and 1 <= int(dia) <= 31:
                    return f"{anio}-{mes}-{dia}"
    return None


def parsear(ruta: Path) -> tuple[pd.DataFrame, list[ResultadoParseo], str | None]:
    xls = pd.ExcelFile(io.BytesIO(leer_bytes(ruta)))
    partes, resultados, fechas = [], [], set()
    for hoja in xls.sheet_names:
        hoja_df = pd.read_excel(xls, sheet_name=hoja, header=None, dtype=str)
        f = fecha_del_informe(hoja_df)
        if f:
            fechas.add(f)
        r = parsear_hoja(hoja_df)
        r.df["hoja"] = hoja
        resultados.append(r)
        partes.append(r.df)
    if len(fechas) > 1:
        raise ValueError(f"Las hojas traen fechas distintas: {sorted(fechas)}. "
                         "No se puede tratar como un unico corte.")
    fecha = fechas.pop() if fechas else None
    df = pd.concat(partes, ignore_index=True)
    df["fecha_descarga"] = fecha
    return df, resultados, fecha
