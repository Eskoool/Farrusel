"""Comprueba que las puertas cazan las corrupciones reales de Farrusel.

Cada caso reproduce una patologia observada en produccion. Si alguna vez
un cambio hace pasar estos tests en verde por el motivo equivocado, se
habra roto la unica red que separa este proyecto del anterior.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from kardex_io import (
    _a_numero,
    analizar_fechas,
    analizar_numeros,
    detectar_convencion,
)
from parser_movimientos_articulo import RE_BAJA, parsear_hoja, periodo_del_informe

HOY = date(2026, 8, 19)
fallos: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(f"  {'OK  ' if cond else 'FALLO'}  {msg}")
    if not cond:
        fallos.append(msg)


print("\n1. La trampa de Farrusel: columna DMY que leida como MDY va al futuro")
# Valores como "12/06/2026" (12 de junio). Ningun componente supera 12, asi
# que no hay prueba directa; pero leerlos como MDY los manda a diciembre.
# Farrusel eligio MDY y se llevo 20.876 fechas futuras sin enterarse.
trampa = [f"{dia:02d}/{mes:02d}/2026" for dia in range(7, 13) for mes in range(1, 7)]
d = analizar_fechas(pd.Series(trampa), "Fecha", hoy=HOY)
check(d.prueba_dmy == 0 and d.prueba_mdy == 0, "no hay prueba directa (todo <= 12)")
check(d.formato == "DMY", f"aun asi resuelve DMY (resolvio {d.formato})")
check(d.resuelto_por == "plausibilidad", f"por descarte (via {d.resuelto_por})")
check(d.futuras_mdy > 0, f"detecta que leerlo MDY daria {d.futuras_mdy} futuras")
check(d.futuras == 0, "con el formato correcto no queda ninguna futura")

print("\n1b. Fichero roto de verdad: futuras se mire como se mire")
d = analizar_fechas(pd.Series(["11/11/2027", "10/10/2028"]), "Fecha", hoy=HOY)
check(d.futuras > 0, f"lo marca igualmente ({d.futuras} futuras)")
check("BLOQUEANTE" in d.veredicto, f"veredicto -> {d.veredicto!r}")

print("\n2. Columna con formatos mezclados (unas filas exigen DMY y otras MDY)")
d = analizar_fechas(pd.Series(["25/03/2026", "03/25/2026", "01/02/2026"]),
                    "Fecha", hoy=HOY)
check(d.contradictorio, "marca la columna como contradictoria")
check("CONTRADICTORIO" in d.veredicto, f"veredicto -> {d.veredicto!r}")

print("\n3. Columna ambigua: ningun valor supera 12, no se puede deducir")
d = analizar_fechas(pd.Series(["01/02/2026", "03/04/2026", "05/06/2026"]),
                    "Fecha", hoy=HOY)
check(d.formato is None, "no inventa un formato")
check("AMBIGUO" in d.veredicto, f"pide decision humana -> {d.veredicto!r}")

print("\n4. Fechas sanas en DMY")
sanas = [(date(2026, 1, 1) + timedelta(days=i)).strftime("%d/%m/%Y")
         for i in range(180)]
d = analizar_fechas(pd.Series(sanas), "Fecha", hoy=HOY)
check(d.formato == "DMY", f"deduce DMY (dedujo {d.formato})")
check(d.futuras == 0, "sin fechas futuras")
check(d.veredicto.startswith("OK"), f"veredicto -> {d.veredicto!r}")

print("\n5. Escala x100 por coma decimal perdida")
# 20.084,00 unidades guardadas como 2008400.
d = analizar_numeros(pd.Series([str(v * 100) for v in range(1, 400)]), "Cantidad")
check(d.pct_multiplos_100 > 50, f"{d.pct_multiplos_100:.0f}% multiplos de 100")
check("ESCALA x100" in d.veredicto, f"veredicto -> {d.veredicto!r}")

print("\n6. Outliers que hacen inutil la suma (el caso PARACETAMOL)")
d = analizar_numeros(pd.Series([str(v) for v in ([32] * 500 + [2003900] * 20)]),
                     "CantidadMovida")
check("OUTLIERS" in d.veredicto, f"veredicto -> {d.veredicto!r}")

print("\n7. Cantidades sanas con decimales europeos")
d = analizar_numeros(pd.Series(["12,5", "3,25", "100,00", "7,75"]), "Cantidad")
check(d.con_decimales == 4, f"conserva los 4 decimales (vio {d.con_decimales})")
check(d.convencion == "europea", f"deduce convencion europea (vio {d.convencion})")
check(d.veredicto == "OK", f"veredicto -> {d.veredicto!r}")

print("\n8. Convencion numerica deducida de la columna, no supuesta")
eu, _ = detectar_convencion(pd.Series(["1.234.567", "890", "12"]))
check(eu == "europea", f"1.234.567 delata millar europeo (vio {eu})")
us, _ = detectar_convencion(pd.Series(["1,234,567", "890", "12"]))
check(us == "americana", f"1,234,567 delata millar americano (vio {us})")
amb, motivo = detectar_convencion(pd.Series(["1.234", "5.678"]))
check(amb is None, f"1.234 aislado sigue siendo irresoluble (vio {amb})")
mix, motivo = detectar_convencion(pd.Series(["1.234,56", "1,234.56"]))
check(mix is None and motivo.startswith("MEZCLA"), f"detecta mezcla -> {motivo}")

print("\n9. Conversion con la convencion ya resuelta")
casos = [
    ("1.234,56",  "europea",   1234.56, "europeo completo"),
    ("1,234.56",  "americana", 1234.56, "americano completo"),
    ("1.234",     "europea",   1234.0,  "millar europeo"),
    ("1,234",     "americana", 1234.0,  "millar americano"),
    ("12,5",      "europea",   12.5,    "decimal europeo corto"),
    ("0,75",      "europea",   0.75,    "decimal europeo < 1"),
    ("-3.200",    "europea",   -3200.0, "negativo con millar"),
    ("2008400",   None,        2008400.0, "entero sin separador"),
    ("1.234",     None,        1234.0,  "sin convencion: lectura conservadora"),
]
for bruto, conv, esperado, etiqueta in casos:
    v, _ = _a_numero(bruto, conv)
    check(v == esperado, f"{etiqueta}: {bruto!r} [{conv}] -> {v} (esperado {esperado})")

print("\n10. Informe de movimientos: dos secciones, cuadre y familias de codigo")
# Reproduce la forma real del fichero a escala reducida: preambulo, marcador
# de seccion, cabecera repetida, un codigo normal de Kardex, un DM+6 digitos
# (que tambien encaja en el patron ancho de RE_CODIGO: hay que comprobar que
# no se cuela como "kardex"), una fila vacia, la segunda seccion con NOGUIA,
# y una fila que hay que descartar (nº movimientos no numerico).
filas_mov = {
    0: ["HOSPITAL DE PRUEBAS", "", "", "", "", "", "", "", "", "", ""],
    1: ["20/08/2026", "INFORME DE MOVIMIENTOS DE ARTICULOS", "", "", "", "", "", "", "", "", ""],
    2: ["", "Grupos:", "", "Desde:", "01/01/2026 00:00", "", "Hasta:", "", "19/08/2026 00:00", "", ""],
    3: ["Articulos Internos", "", "", "", "", "", "", "", "", "", ""],
    4: ["Articulo", "", "", "", "Nº Movimientos", "", "Último movimiento", "", "", "", "Cantidad"],
    5: ["V00001", "-", "PARACETAMOL 1 g comp", "", "10", "", "01/08/2026 10:00:00", "", "", "", "50"],
    6: ["DM000041", "-", "RESTRINGIDO X", "", "3", "", "02/08/2026 11:00:00", "", "", "", "9"],
    7: ["", "", "", "", "", "", "", "", "", "", ""],
    8: ["Articulos Externos", "", "", "", "", "", "", "", "", "", ""],
    9: ["Articulo", "", "", "", "Nº Movimientos", "", "Último movimiento", "", "", "", "Cantidad"],
    10: ["NOGUIA", "-", "NO GUIA FARMACOTERAPEUTICA", "", "5", "", "03/08/2026 09:00:00", "", "", "", "12"],
    11: ["V99999", "-", "CODIGO CON MOVIMIENTOS ROTO", "", "n/a", "", "04/08/2026 12:00:00", "", "", "", "1"],
}
df_mov = pd.DataFrame.from_dict(filas_mov, orient="index")
r = parsear_hoja(df_mov)
check(r.cuadra, f"cuadra: {r.filas_datos} datos + {r.filas_cabecera} cabecera + "
                f"{r.filas_vacias} vacias + {len(r.filas_descartadas)} descartadas "
                f"== {r.filas_hoja} filas_hoja")
check(r.filas_datos == 3, f"3 filas de datos (vio {r.filas_datos})")
check(len(r.filas_descartadas) == 1, f"1 fila descartada (vio {len(r.filas_descartadas)})")
check(r.secciones == {"internos": 2, "externos": 1},
      f"reparto por seccion (vio {r.secciones})")
tipos = dict(zip(r.df["codigo"], r.df["tipo_codigo"]))
check(tipos.get("V00001") == "kardex", f"V00001 -> kardex (vio {tipos.get('V00001')})")
check(tipos.get("DM000041") == "bookkeeping",
      f"DM000041 -> bookkeeping, no kardex (vio {tipos.get('DM000041')})")
check(tipos.get("NOGUIA") == "bookkeeping",
      f"NOGUIA -> bookkeeping (vio {tipos.get('NOGUIA')})")

print("\n11. Codigo duplicado: el parser NO lo fusiona (eso es cosa del analisis)")
filas_dup = {
    0: ["Articulos Internos", "", "", "", "", "", "", "", "", "", ""],
    1: ["V02254", "-", "MESNA 1.000 MG AMPOL", "", "8", "", "18/08/2026 20:52:34", "", "", "", "27"],
    2: ["V02254", "-", "MESNA 1.000 MG AMPOL", "", "1", "", "10/08/2026 08:00:00", "", "", "", "1"],
}
r_dup = parsear_hoja(pd.DataFrame.from_dict(filas_dup, orient="index"))
check(r_dup.filas_datos == 2, f"las dos filas sobreviven por separado (vio {r_dup.filas_datos})")
suma = r_dup.df.groupby("codigo")["cantidad"].apply(lambda s: sum(int(v) for v in s))
check(suma.get("V02254") == 28,
      f"la fusion (suma) es responsabilidad de la capa de analisis, no del parser "
      f"(groupby posterior da {suma.get('V02254')})")

print("\n12. periodo_del_informe: extrae Desde/Hasta, no la fecha de emision")
periodo = periodo_del_informe(df_mov)
check(periodo == (date(2026, 1, 1), date(2026, 8, 19)),
      f"periodo (vio {periodo})")
if periodo:
    dias = (periodo[1] - periodo[0]).days + 1
    check(dias == 231, f"231 dias con convencion inclusiva (vio {dias})")

print("\n13. RE_BAJA se reutiliza igual en el informe de movimientos")
check(bool(RE_BAJA.match("BAJA TRAMADOL/PARACETAMOL 37,5/325")), "BAJA en mayusculas")
check(bool(RE_BAJA.match("baja  ciclobenzaprina 10 mg")), "baja en minusculas, doble espacio")
check(not RE_BAJA.match("ABAJA 500 mg"), "no falso-positivo en 'ABAJA'")

print("\n14. Fechas con hora (nunca probado hasta ahora: HH:MM:SS en analizar_fechas)")
con_hora = [f"{dia:02d}/08/2026 20:52:{sg:02d}" for dia, sg in zip(range(1, 19), range(0, 54, 3))]
d = analizar_fechas(pd.Series(con_hora), "UltimoMovimiento", hoy=HOY)
check(d.formato == "DMY", f"deduce DMY con hora presente (dedujo {d.formato})")
check(d.futuras == 0, "sin fechas futuras")
check(d.veredicto.startswith("OK"), f"veredicto -> {d.veredicto!r}")

print("\n" + "=" * 60)
if fallos:
    print(f"{len(fallos)} FALLOS:")
    for f in fallos:
        print(f"  - {f}")
    raise SystemExit(1)
print("Todas las puertas funcionan.")
