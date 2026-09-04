"""Lectura e inspeccion de ficheros del Kardex.

Regla de oro: este modulo NUNCA modifica el fichero de origen y NUNCA
"arregla" un valor en silencio. Su trabajo es enseniar lo que hay de verdad,
incluidas las anomalias, para que la decision de como interpretarlo sea
explicita y quede escrita.

Las puertas de validacion nacen de dos corrupciones reales encontradas en
Farrusel (el modulo hermano del carrusel):

  - 20.876 filas (10,6%) con fecha futura, por inversion DD/MM <-> MM/DD.
    Causa: el formato de fecha estaba fijado a mano en el parser, sin
    detectarlo ni validarlo.
  - Cantidades a escala x100 por coma decimal perdida, con outliers que
    hacian inutil cualquier suma.

Ninguna de las dos se detecto hasta meses despues.
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import chardet
import pandas as pd

# --------------------------------------------------------------------------
# Lectura cruda
# --------------------------------------------------------------------------

# Suficiente para adivinar la codificacion sin leer ficheros de 200 MB enteros.
_MUESTRA_ENCODING = 256 * 1024


def leer_bytes(ruta: Path) -> bytes:
    """Lee el fichero aunque Excel lo tenga abierto.

    Path.read_bytes() falla con "used by another process" si el fichero esta
    abierto en otra aplicacion. Abrirlo con FileShare.ReadWrite evita tener
    que pedirle a nadie que cierre el Excel antes de trabajar.
    """
    try:
        return ruta.read_bytes()
    except PermissionError:
        import msvcrt
        import os

        fd = os.open(ruta, os.O_RDONLY | os.O_BINARY)
        try:
            with os.fdopen(fd, "rb", closefd=False) as fh:
                return fh.read()
        finally:
            os.close(fd)


def detectar_encoding(ruta: Path) -> tuple[str, float]:
    """Devuelve (encoding, confianza). Prioriza los BOM, que son inequivocos."""
    crudo = leer_bytes(ruta)[:_MUESTRA_ENCODING]
    if crudo.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig", 1.0
    if crudo.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16", 1.0
    res = chardet.detect(crudo)
    enc = (res.get("encoding") or "cp1252").lower()
    conf = float(res.get("confidence") or 0.0)
    # chardet confunde a menudo cp1252 con estos dos en textos en castellano.
    if enc in {"iso-8859-1", "windows-1252", "latin-1", "ascii"}:
        enc = "cp1252"
    return enc, conf


def detectar_delimitador(texto: str) -> str:
    """Adivina el separador contando candidatos en las primeras lineas."""
    muestra = "\n".join(texto.splitlines()[:50])
    try:
        return csv.Sniffer().sniff(muestra, delimiters=";,\t|").delimiter
    except csv.Error:
        pass
    # Plan B: el que mas aparece de forma consistente.
    conteos = {d: muestra.count(d) for d in (";", ",", "\t", "|")}
    mejor = max(conteos, key=lambda d: conteos[d])
    return mejor if conteos[mejor] > 0 else ";"


def cabecera_cruda(ruta: Path, n: int = 15) -> list[str]:
    """Primeras n lineas tal cual, sin interpretar.

    Los informes de maquina suelen traer titulo y metadatos antes de la
    cabecera real; hay que verlo con los ojos antes de parsear nada.
    """
    if ruta.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
        df = pd.read_excel(io.BytesIO(leer_bytes(ruta)), header=None,
                           nrows=n, dtype=str)
        return [" | ".join("" if pd.isna(v) else str(v) for v in fila)
                for fila in df.itertuples(index=False)]
    enc, _ = detectar_encoding(ruta)
    texto = leer_bytes(ruta).decode(enc, errors="replace")
    return texto.splitlines()[:n]


def leer_tabla(ruta: Path, fila_cabecera: int = 0, hoja: Any = 0) -> pd.DataFrame:
    """Lee el fichero como texto puro.

    Todo entra como str a proposito: convertir a numero o fecha aqui seria
    justo el paso donde Farrusel perdio la informacion. Primero se mira,
    luego se decide como convertir.
    """
    if ruta.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
        return pd.read_excel(io.BytesIO(leer_bytes(ruta)), header=fila_cabecera,
                             sheet_name=hoja, dtype=str)
    enc, _ = detectar_encoding(ruta)
    texto = leer_bytes(ruta).decode(enc, errors="replace")
    sep = detectar_delimitador(texto)
    return pd.read_csv(
        io.StringIO(texto),
        sep=sep,
        header=fila_cabecera,
        dtype=str,
        keep_default_na=False,
        na_values=[""],
        engine="python",
        on_bad_lines="warn",
    )


def hojas_excel(ruta: Path) -> list[str]:
    if ruta.suffix.lower() not in {".xlsx", ".xlsm", ".xls"}:
        return []
    return pd.ExcelFile(io.BytesIO(leer_bytes(ruta))).sheet_names


# --------------------------------------------------------------------------
# Puerta 1 y 2: fechas
# --------------------------------------------------------------------------

_RE_FECHA = re.compile(
    r"^\s*(\d{1,4})[/\-.](\d{1,2})[/\-.](\d{1,4})"
    r"(?:[ T]+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([AaPp][Mm])?)?\s*$"
)


@dataclass
class DiagnosticoFecha:
    """Veredicto sobre una columna de fechas.

    `formato` solo se rellena cuando el dato lo demuestra. Si la columna es
    ambigua se queda en None y hay que preguntar: adivinar es exactamente
    como Farrusel acabo con 20.876 fechas futuras.
    """

    columna: str
    total: int = 0
    vacias: int = 0
    no_reconocidas: int = 0
    formato: str | None = None          # "DMY" | "MDY" | "ISO" | None
    prueba_dmy: int = 0                 # filas con 1er componente > 12
    prueba_mdy: int = 0                 # filas con 2o componente > 12
    ambiguas: int = 0                   # ambos componentes <= 12
    contradictorio: bool = False
    ejemplos: list[str] = field(default_factory=list)
    # Puerta 2, solo calculable una vez resuelto el formato
    futuras: int = 0
    fecha_min: str | None = None
    fecha_max: str | None = None
    # Como se llego al formato: por prueba directa o por descarte de futuras
    resuelto_por: str = "prueba"        # "prueba" | "plausibilidad" | "ninguno"
    futuras_dmy: int = 0
    futuras_mdy: int = 0

    @property
    def concluyente(self) -> bool:
        return self.formato is not None and not self.contradictorio

    @property
    def veredicto(self) -> str:
        if self.total == self.vacias:
            return "COLUMNA VACIA"
        if self.no_reconocidas == self.total - self.vacias:
            return "NO ES UNA COLUMNA DE FECHAS"
        if self.contradictorio:
            return "CONTRADICTORIO - hay filas que exigen DMY y otras MDY"
        # Las futuras van antes que la ambiguedad: si las dos lecturas mandan
        # fechas al futuro, el fichero esta mal se interprete como se interprete,
        # y eso hay que decirlo aunque no sepamos el formato.
        if self.futuras:
            return f"BLOQUEANTE - {self.futuras} fechas en el futuro"
        if self.formato is None:
            return ("AMBIGUO - ningun valor supera 12 y ambas lecturas son "
                    "plausibles; hay que preguntar el formato")
        if self.resuelto_por == "plausibilidad":
            return (f"OK - formato {self.formato} (deducido por descarte: leerlo como "
                    f"{'MDY' if self.formato == 'DMY' else 'DMY'} daria "
                    f"{max(self.futuras_dmy, self.futuras_mdy)} fechas futuras). "
                    "CONFIRMAR con el origen.")
        return f"OK - formato {self.formato}"


def _contar_futuras(analizadas: list[tuple[int, int, int]], formato: str,
                    hoy: date) -> int:
    """Cuantas fechas caerian en el futuro leyendo la columna con ese formato."""
    n = 0
    for a, b, anio in analizadas:
        dia, mes = (a, b) if formato == "DMY" else (b, a)
        try:
            if date(anio, mes, dia) > hoy:
                n += 1
        except ValueError:
            continue
    return n


def analizar_fechas(serie: pd.Series, nombre: str,
                    hoy: date | None = None) -> DiagnosticoFecha:
    """Deduce el formato de fecha por evidencia, nunca por convencion.

    Un valor como 25/03/2026 solo puede ser DMY (no hay mes 25). Basta un
    valor asi para fijar el formato de toda la columna. Si aparecen pruebas
    de los dos formatos a la vez, el fichero mezcla criterios y no se puede
    interpretar sin decidirlo a mano.
    """
    hoy = hoy or date.today()
    d = DiagnosticoFecha(columna=nombre, total=len(serie))

    analizadas: list[tuple[int, int, int]] = []   # (a, b, anio)
    iso = 0
    for valor in serie:
        if valor is None or (isinstance(valor, float) and pd.isna(valor)):
            d.vacias += 1
            continue
        s = str(valor).strip()
        if not s:
            d.vacias += 1
            continue
        m = _RE_FECHA.match(s)
        if not m:
            d.no_reconocidas += 1
            if len(d.ejemplos) < 5:
                d.ejemplos.append(s)
            continue
        p1, p2, p3 = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if len(m.group(1)) == 4:            # 2026-03-25 -> ISO, sin ambiguedad
            iso += 1
            analizadas.append((p2, p3, p1))
            continue
        anio = p3 + 2000 if p3 < 100 else p3
        analizadas.append((p1, p2, anio))
        if p1 > 12:
            d.prueba_dmy += 1
        elif p2 > 12:
            d.prueba_mdy += 1
        else:
            d.ambiguas += 1

    if iso and not d.prueba_dmy and not d.prueba_mdy and not d.ambiguas:
        d.formato = "ISO"
    elif d.prueba_dmy and d.prueba_mdy:
        d.contradictorio = True
    elif d.prueba_dmy:
        d.formato = "DMY"
    elif d.prueba_mdy:
        d.formato = "MDY"

    # Ninguna prueba directa: aun queda la plausibilidad. Un informe no puede
    # contener movimientos que todavia no han ocurrido, asi que si una de las
    # dos lecturas manda fechas al futuro y la otra no, queda resuelta.
    # Este es el razonamiento que destapo las 20.876 fechas rotas de Farrusel.
    if d.formato is None and not d.contradictorio and analizadas:
        d.futuras_dmy = _contar_futuras(analizadas, "DMY", hoy)
        d.futuras_mdy = _contar_futuras(analizadas, "MDY", hoy)
        if d.futuras_dmy == 0 and d.futuras_mdy > 0:
            d.formato, d.resuelto_por = "DMY", "plausibilidad"
        elif d.futuras_mdy == 0 and d.futuras_dmy > 0:
            d.formato, d.resuelto_por = "MDY", "plausibilidad"
        else:
            d.resuelto_por = "ninguno"
            # Ambas lecturas dan futuras: el fichero esta mal se mire como se mire.
            if d.futuras_dmy and d.futuras_mdy:
                d.futuras = min(d.futuras_dmy, d.futuras_mdy)

    if d.concluyente and analizadas:
        dias, minimo, maximo = 0, None, None
        for a, b, anio in analizadas:
            dia, mes = (a, b) if d.formato in ("DMY", "ISO") else (b, a)
            if d.formato == "ISO":
                dia, mes = b, a
            try:
                f = date(anio, mes, dia)
            except ValueError:
                d.no_reconocidas += 1
                continue
            dias += 1
            minimo = f if minimo is None or f < minimo else minimo
            maximo = f if maximo is None or f > maximo else maximo
            if f > hoy:
                d.futuras += 1
        if dias:
            d.fecha_min = minimo.isoformat()
            d.fecha_max = maximo.isoformat()
    return d


def histograma_dia_del_mes(serie: pd.Series, formato: str) -> dict[int, int]:
    """Reparto por dia del mes.

    Con las fechas sanas el reparto es casi plano. La inversion DD/MM deja
    una firma inconfundible: los dias 1-6 al doble y un agujero en 7-12.
    """
    cuenta: Counter[int] = Counter()
    for valor in serie.dropna():
        m = _RE_FECHA.match(str(valor).strip())
        if not m:
            continue
        p1, p2 = int(m.group(1)), int(m.group(2))
        if len(m.group(1)) == 4:
            cuenta[int(m.group(3))] += 1
        else:
            cuenta[p1 if formato == "DMY" else p2] += 1
    return dict(sorted(cuenta.items()))


# --------------------------------------------------------------------------
# Puerta 3: escala numerica
# --------------------------------------------------------------------------

_RE_NUM = re.compile(r"^\s*[-+]?[\d.,\s]+\s*$")


@dataclass
class DiagnosticoNumero:
    columna: str
    total: int = 0
    vacias: int = 0
    numericas: int = 0
    con_decimales: int = 0
    multiplos_100: int = 0
    negativas: int = 0
    convencion: str | None = None       # "europea" | "americana" | None
    motivo_convencion: str = ""
    minimo: float | None = None
    maximo: float | None = None
    mediana: float | None = None
    media: float | None = None
    ejemplos: list[str] = field(default_factory=list)

    @property
    def pct_multiplos_100(self) -> float:
        return 100.0 * self.multiplos_100 / self.numericas if self.numericas else 0.0

    @property
    def veredicto(self) -> str:
        if not self.numericas:
            return "NO ES UNA COLUMNA NUMERICA"
        avisos = []
        if self.convencion is None and self.motivo_convencion.startswith("MEZCLA"):
            avisos.append(f"CONVENCION NUMERICA MEZCLADA - {self.motivo_convencion}")
        if self.pct_multiplos_100 > 50 and not self.con_decimales:
            avisos.append(
                f"SOSPECHA DE ESCALA x100 ({self.pct_multiplos_100:.0f}% multiplos de 100, "
                "ningun decimal) - posible coma decimal perdida"
            )
        # Media muy por encima de mediana = cola de outliers que rompe las sumas.
        if (self.mediana is not None and self.media is not None
                and self.mediana != 0 and abs(self.media) > 5 * abs(self.mediana)):
            avisos.append(
                f"OUTLIERS (media {self.media:.1f} vs mediana {self.mediana:.1f}) "
                "- las sumas no seran fiables"
            )
        return " | ".join(avisos) if avisos else "OK"


def detectar_convencion(serie: pd.Series) -> tuple[str | None, str]:
    """Deduce si la columna usa notacion europea o americana.

    Un valor aislado como "1.234" es irresoluble: puede ser mil doscientos
    treinta y cuatro (millar europeo) o uno coma dos tres cuatro (decimal
    americano). Una columna entera, en cambio, casi siempre delata su
    convencion en algun valor. Se busca esa prueba en vez de suponerla.

    Devuelve ("europea" | "americana" | None, explicacion).
    """
    pruebas_eu = pruebas_us = 0
    ejemplo_eu = ejemplo_us = ""
    for bruto in serie.dropna():
        s = str(bruto).strip().replace(" ", "").replace("\xa0", "")
        if not s or not _RE_NUM.match(s):
            continue
        s = s.lstrip("+-")
        n_punto, n_coma = s.count("."), s.count(",")
        if n_punto and n_coma:
            # Con ambos presentes, el ultimo en aparecer es el decimal.
            if s.rfind(",") > s.rfind("."):
                pruebas_eu += 1
                ejemplo_eu = ejemplo_eu or s
            else:
                pruebas_us += 1
                ejemplo_us = ejemplo_us or s
        elif n_coma > 1:                       # 1,234,567 -> coma es millar
            pruebas_us += 1
            ejemplo_us = ejemplo_us or s
        elif n_punto > 1:                      # 1.234.567 -> punto es millar
            pruebas_eu += 1
            ejemplo_eu = ejemplo_eu or s
        elif n_coma == 1 and len(s) - s.rfind(",") - 1 != 3:
            pruebas_eu += 1                    # 12,5 -> coma decimal
            ejemplo_eu = ejemplo_eu or s
        elif n_punto == 1 and len(s) - s.rfind(".") - 1 != 3:
            pruebas_us += 1                    # 12.5 -> punto decimal
            ejemplo_us = ejemplo_us or s
        # Un solo separador con 3 digitos detras no aporta informacion.

    if pruebas_eu and pruebas_us:
        return None, (f"MEZCLA: {pruebas_eu} valores europeos (ej. {ejemplo_eu}) y "
                      f"{pruebas_us} americanos (ej. {ejemplo_us})")
    if pruebas_eu:
        return "europea", f"{pruebas_eu} valores lo demuestran (ej. {ejemplo_eu})"
    if pruebas_us:
        return "americana", f"{pruebas_us} valores lo demuestran (ej. {ejemplo_us})"
    return None, "sin separadores concluyentes (o son todos enteros)"


def _a_numero(s: str, convencion: str | None = None) -> tuple[float | None, bool]:
    """Convierte un valor aplicando la convencion ya deducida de la columna.

    Sin convencion resuelta, un separador unico con 3 digitos detras se trata
    como millar (lectura conservadora: 1.234 -> 1234, no 1.234). La alternativa
    dividiria la cifra por mil sin avisar, que es como Farrusel acabo con
    cantidades a escala equivocada.
    """
    s = s.strip().replace(" ", "").replace("\xa0", "")
    if not s or not _RE_NUM.match(s):
        return None, False
    neg = s.startswith("-")
    s = s.lstrip("+-")

    if "." not in s and "," not in s:
        try:
            return (-float(s) if neg else float(s)), False
        except ValueError:
            return None, False

    dec_car = {"europea": ",", "americana": "."}.get(convencion or "")
    ult_punto, ult_coma = s.rfind("."), s.rfind(",")

    if dec_car and dec_car in s:
        pos = s.rfind(dec_car)
        # Con la convencion clara, 3 digitos detras del separador decimal
        # siguen siendo millares (1.234 en Europa es mil doscientos treinta y cuatro).
        if len(s) - pos - 1 == 3 and s.count(dec_car) == 1 and (
                ult_punto == -1 or ult_coma == -1):
            return (-float(re.sub(r"[.,]", "", s)) if neg
                    else float(re.sub(r"[.,]", "", s))), False
        entero = re.sub(r"[.,]", "", s[:pos])
        try:
            v = float(f"{entero or 0}.{s[pos + 1:]}")
        except ValueError:
            return None, False
        return (-v if neg else v), True

    if ult_punto != -1 and ult_coma != -1:
        pos = max(ult_punto, ult_coma)
        entero = re.sub(r"[.,]", "", s[:pos])
        try:
            v = float(f"{entero or 0}.{s[pos + 1:]}")
        except ValueError:
            return None, False
        return (-v if neg else v), True

    pos = max(ult_punto, ult_coma)
    cola = len(s) - pos - 1
    if cola == 3 and s.count(s[pos]) >= 1:
        limpio, decimales = re.sub(r"[.,]", "", s), False
    else:
        limpio = re.sub(r"[.,]", "", s[:pos]) + "." + s[pos + 1:]
        decimales = True
    try:
        v = float(limpio)
    except ValueError:
        return None, False
    return (-v if neg else v), decimales


def analizar_numeros(serie: pd.Series, nombre: str) -> DiagnosticoNumero:
    convencion, motivo = detectar_convencion(serie)
    d = DiagnosticoNumero(columna=nombre, total=len(serie),
                          convencion=convencion, motivo_convencion=motivo)
    valores: list[float] = []
    for bruto in serie:
        if bruto is None or (isinstance(bruto, float) and pd.isna(bruto)):
            d.vacias += 1
            continue
        s = str(bruto).strip()
        if not s:
            d.vacias += 1
            continue
        v, dec = _a_numero(s, convencion)
        if v is None:
            if len(d.ejemplos) < 5:
                d.ejemplos.append(s)
            continue
        d.numericas += 1
        valores.append(v)
        if dec:
            d.con_decimales += 1
        if v < 0:
            d.negativas += 1
        if v and float(v).is_integer() and int(v) % 100 == 0:
            d.multiplos_100 += 1
    if valores:
        s = pd.Series(valores)
        d.minimo, d.maximo = float(s.min()), float(s.max())
        d.mediana, d.media = float(s.median()), float(s.mean())
    return d


# --------------------------------------------------------------------------
# Perfil de columna
# --------------------------------------------------------------------------

def _normaliza(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").upper().strip()


_PISTAS_FECHA = ("FECHA", "CADUC", "DATE", "ALTA", "BAJA", "HORA")
_PISTAS_NUM = ("CANT", "STOCK", "MIN", "MAX", "EXIST", "CONSUM", "PRECIO",
               "UNID", "UDC", "CAPAC", "IMPORT", "TOTAL", "NUM", "POSIC")


def clasificar(nombre: str, serie: pd.Series) -> str:
    """Decide si tratar la columna como fecha, numero o texto.

    Se mira el nombre y tambien el contenido: un informe puede llamar
    "Alta" a algo que no es una fecha, y al reves.
    """
    n = _normaliza(nombre)
    if any(p in n for p in _PISTAS_FECHA):
        return "fecha"
    muestra = [str(v).strip() for v in serie.dropna().head(200) if str(v).strip()]
    if not muestra:
        return "texto"
    if sum(bool(_RE_FECHA.match(v)) for v in muestra) > 0.7 * len(muestra):
        return "fecha"
    if any(p in n for p in _PISTAS_NUM):
        return "numero"
    if sum(bool(_RE_NUM.match(v)) for v in muestra) > 0.7 * len(muestra):
        return "numero"
    return "texto"


def perfil_texto(serie: pd.Series, nombre: str) -> dict[str, Any]:
    limpia = serie.dropna().astype(str).str.strip()
    limpia = limpia[limpia != ""]
    top = Counter(limpia).most_common(8)
    largos = limpia.str.len()
    return {
        "columna": nombre,
        "total": len(serie),
        "vacias": int(len(serie) - len(limpia)),
        "distintos": int(limpia.nunique()),
        "long_min": int(largos.min()) if len(largos) else 0,
        "long_max": int(largos.max()) if len(largos) else 0,
        "top": top,
    }
