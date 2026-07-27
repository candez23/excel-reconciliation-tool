"""Lógica de conciliación independiente de Streamlit."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import math
import re
import unicodedata

import pandas as pd


class ErrorConciliacion(ValueError):
    """Configuración o datos que impiden una conciliación confiable."""


@dataclass
class ResultadoConciliacion:
    """Tablas y métricas producidas por una conciliación."""

    resumen: pd.DataFrame
    coincidencias: pd.DataFrame
    solo_en_a: pd.DataFrame
    solo_en_b: pd.DataFrame
    diferencias: pd.DataFrame
    duplicados: pd.DataFrame

    @property
    def metricas(self) -> dict[str, int | float | str]:
        return dict(zip(self.resumen["Métrica"], self.resumen["Valor"]))


def normalizar_clave(valor: object) -> str | None:
    """Crea una clave auxiliar; nunca sustituye el valor original."""

    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return None
    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass

    texto = str(valor).strip()
    if not texto:
        return None

    texto = " ".join(texto.split()).casefold()
    texto = "".join(
        caracter
        for caracter in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(caracter)
    )
    return texto


def _decimal_desde_texto(texto: str) -> Decimal | None:
    texto = texto.strip()
    if not texto:
        return None

    negativo_parentesis = texto.startswith("(") and texto.endswith(")")
    texto = texto.strip("()").replace("\u00a0", "").replace(" ", "")
    texto = re.sub(r"[^\d,\.\-+]", "", texto)
    if not texto or texto in {"-", "+", ".", ","}:
        return None

    ultima_coma = texto.rfind(",")
    ultimo_punto = texto.rfind(".")
    if ultima_coma >= 0 and ultimo_punto >= 0:
        separador_decimal = "," if ultima_coma > ultimo_punto else "."
        separador_miles = "." if separador_decimal == "," else ","
        texto = texto.replace(separador_miles, "")
        texto = texto.replace(separador_decimal, ".")
    elif "," in texto:
        partes = texto.split(",")
        if len(partes) == 2 and 1 <= len(partes[1]) <= 2:
            texto = ".".join(partes)
        else:
            texto = "".join(partes)
    elif "." in texto:
        partes = texto.split(".")
        if len(partes) != 2 or len(partes[1]) == 3:
            texto = "".join(partes)

    if negativo_parentesis:
        texto = f"-{texto.lstrip('+-')}"

    try:
        numero = Decimal(texto)
    except InvalidOperation:
        return None
    return numero if numero.is_finite() else None


def convertir_importe(valor: object) -> Decimal | None:
    """Convierte formatos monetarios frecuentes solo para calcular diferencias."""

    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, Decimal):
        return valor if valor.is_finite() else None
    if isinstance(valor, (int, float)):
        try:
            numero = Decimal(str(valor))
        except InvalidOperation:
            return None
        return numero if numero.is_finite() else None
    return _decimal_desde_texto(str(valor))


def _validar_configuracion(
    datos_a: pd.DataFrame,
    datos_b: pd.DataFrame,
    columna_clave_a: str,
    columna_clave_b: str,
    columna_importe_a: str | None,
    columna_importe_b: str | None,
    tolerancia: float | Decimal,
) -> Decimal:
    for etiqueta, datos, columna in (
        ("A", datos_a, columna_clave_a),
        ("B", datos_b, columna_clave_b),
    ):
        if columna not in datos.columns:
            raise ErrorConciliacion(
                f'Archivo {etiqueta}, columna "{columna}": la columna clave no existe.'
            )

    if (columna_importe_a is None) != (columna_importe_b is None):
        raise ErrorConciliacion(
            "Para comparar importes selecciona una columna de importe en ambos "
            "archivos, o deja ambas sin seleccionar."
        )

    for etiqueta, datos, columna in (
        ("A", datos_a, columna_importe_a),
        ("B", datos_b, columna_importe_b),
    ):
        if columna is not None and columna not in datos.columns:
            raise ErrorConciliacion(
                f'Archivo {etiqueta}, columna "{columna}": la columna de importe '
                "no existe."
            )

    try:
        tolerancia_decimal = Decimal(str(tolerancia))
    except InvalidOperation as exc:
        raise ErrorConciliacion("La tolerancia debe ser un número válido.") from exc
    if not tolerancia_decimal.is_finite() or tolerancia_decimal < 0:
        raise ErrorConciliacion("La tolerancia debe ser mayor o igual que cero.")
    return tolerancia_decimal


def _prefijar_fila(
    fila: pd.Series,
    prefijo: str,
) -> dict[str, object]:
    return {f"{prefijo} | {columna}": valor for columna, valor in fila.items()}


def _tabla_vacia_combinada(
    datos_a: pd.DataFrame,
    datos_b: pd.DataFrame,
    con_importes: bool,
) -> pd.DataFrame:
    columnas = ["Fila A", "Fila B"]
    columnas += [f"A | {columna}" for columna in datos_a.columns]
    columnas += [f"B | {columna}" for columna in datos_b.columns]
    if con_importes:
        columnas += [
            "Importe A (numérico)",
            "Importe B (numérico)",
            "Diferencia absoluta",
            "Motivo",
        ]
    return pd.DataFrame(columns=columnas)


def _crear_tabla_duplicados(
    datos_a: pd.DataFrame,
    datos_b: pd.DataFrame,
    claves_a: pd.Series,
    claves_b: pd.Series,
    claves_duplicadas_a: set[str],
    claves_duplicadas_b: set[str],
) -> pd.DataFrame:
    claves_conflictivas = claves_duplicadas_a | claves_duplicadas_b
    registros: list[dict[str, object]] = []

    for origen, datos, claves in (
        ("A", datos_a, claves_a),
        ("B", datos_b, claves_b),
    ):
        for posicion in datos.index[claves.isin(claves_conflictivas)]:
            registro: dict[str, object] = {
                "Origen": origen,
                "Fila de origen": int(posicion) + 2,
                "Motivo": (
                    "Clave relacionada con duplicado; se separa para revisión"
                ),
            }
            registro.update(_prefijar_fila(datos.loc[posicion], origen))
            registros.append(registro)

    columnas = ["Origen", "Fila de origen", "Motivo"]
    columnas += [f"A | {columna}" for columna in datos_a.columns]
    columnas += [f"B | {columna}" for columna in datos_b.columns]
    return pd.DataFrame(registros, columns=columnas)


def conciliar_archivos(
    datos_a: pd.DataFrame,
    datos_b: pd.DataFrame,
    columna_clave_a: str,
    columna_clave_b: str,
    columna_importe_a: str | None = None,
    columna_importe_b: str | None = None,
    tolerancia: float | Decimal = 0,
    nombre_a: str = "Archivo A",
    nombre_b: str = "Archivo B",
) -> ResultadoConciliacion:
    """Concilia dos tablas sin alterar sus filas ni columnas originales."""

    tolerancia_decimal = _validar_configuracion(
        datos_a,
        datos_b,
        columna_clave_a,
        columna_clave_b,
        columna_importe_a,
        columna_importe_b,
        tolerancia,
    )

    a = datos_a.copy(deep=True).reset_index(drop=True)
    b = datos_b.copy(deep=True).reset_index(drop=True)
    claves_a = a[columna_clave_a].map(normalizar_clave)
    claves_b = b[columna_clave_b].map(normalizar_clave)

    conteos_a = claves_a.dropna().value_counts()
    conteos_b = claves_b.dropna().value_counts()
    duplicadas_a = set(conteos_a[conteos_a > 1].index)
    duplicadas_b = set(conteos_b[conteos_b > 1].index)
    conflictivas = duplicadas_a | duplicadas_b

    elegibles_a = {
        clave: posicion
        for posicion, clave in claves_a.items()
        if clave is not None and clave not in conflictivas
    }
    elegibles_b = {
        clave: posicion
        for posicion, clave in claves_b.items()
        if clave is not None and clave not in conflictivas
    }

    claves_comunes = [
        clave for clave in elegibles_a if clave in elegibles_b
    ]
    claves_solo_a = {
        clave for clave in elegibles_a if clave not in elegibles_b
    }
    claves_solo_b = {
        clave for clave in elegibles_b if clave not in elegibles_a
    }

    posiciones_solo_a = [
        posicion
        for posicion, clave in claves_a.items()
        if clave is None or clave in claves_solo_a
    ]
    posiciones_solo_b = [
        posicion
        for posicion, clave in claves_b.items()
        if clave is None or clave in claves_solo_b
    ]
    solo_en_a = a.loc[posiciones_solo_a].copy().reset_index(drop=True)
    solo_en_b = b.loc[posiciones_solo_b].copy().reset_index(drop=True)

    comparar_importes = (
        columna_importe_a is not None and columna_importe_b is not None
    )
    coincidencias_registros: list[dict[str, object]] = []
    diferencias_registros: list[dict[str, object]] = []

    for clave in claves_comunes:
        posicion_a = elegibles_a[clave]
        posicion_b = elegibles_b[clave]
        fila_a = a.loc[posicion_a]
        fila_b = b.loc[posicion_b]
        combinado: dict[str, object] = {
            "Fila A": int(posicion_a) + 2,
            "Fila B": int(posicion_b) + 2,
        }
        combinado.update(_prefijar_fila(fila_a, "A"))
        combinado.update(_prefijar_fila(fila_b, "B"))

        if not comparar_importes:
            coincidencias_registros.append(combinado)
            continue

        importe_a = convertir_importe(fila_a[columna_importe_a])
        importe_b = convertir_importe(fila_b[columna_importe_b])
        detalle = combinado.copy()
        detalle["Importe A (numérico)"] = (
            float(importe_a) if importe_a is not None else None
        )
        detalle["Importe B (numérico)"] = (
            float(importe_b) if importe_b is not None else None
        )

        if importe_a is None or importe_b is None:
            detalle["Diferencia absoluta"] = None
            columnas_invalidas = []
            if importe_a is None:
                columnas_invalidas.append(f'A: "{columna_importe_a}"')
            if importe_b is None:
                columnas_invalidas.append(f'B: "{columna_importe_b}"')
            detalle["Motivo"] = (
                "Importe no numérico o vacío en " + " y ".join(columnas_invalidas)
            )
            diferencias_registros.append(detalle)
            continue

        diferencia = abs(importe_a - importe_b)
        detalle["Diferencia absoluta"] = float(diferencia)
        if diferencia <= tolerancia_decimal:
            detalle["Motivo"] = "Dentro de tolerancia"
            coincidencias_registros.append(detalle)
        else:
            detalle["Motivo"] = (
                f"Supera la tolerancia de {float(tolerancia_decimal):g}"
            )
            diferencias_registros.append(detalle)

    if coincidencias_registros:
        coincidencias = pd.DataFrame(coincidencias_registros)
    else:
        coincidencias = _tabla_vacia_combinada(
            a, b, con_importes=comparar_importes
        )
    if diferencias_registros:
        diferencias = pd.DataFrame(diferencias_registros)
    else:
        diferencias = _tabla_vacia_combinada(a, b, con_importes=True)

    duplicados = _crear_tabla_duplicados(
        a,
        b,
        claves_a,
        claves_b,
        duplicadas_a,
        duplicadas_b,
    )

    filas_sin_clave_a = int(claves_a.isna().sum())
    filas_sin_clave_b = int(claves_b.isna().sum())
    resumen = pd.DataFrame(
        [
            ("Identidad", "KNDEZ DATA TOOLS"),
            ("Aplicación", "Conciliador de Excel y CSV"),
            ("Archivo A", nombre_a),
            ("Filas en A", len(a)),
            ("Columnas en A", len(a.columns)),
            ("Columna clave A", columna_clave_a),
            ("Archivo B", nombre_b),
            ("Filas en B", len(b)),
            ("Columnas en B", len(b.columns)),
            ("Columna clave B", columna_clave_b),
            ("Columna importe A", columna_importe_a or "No seleccionada"),
            ("Columna importe B", columna_importe_b or "No seleccionada"),
            ("Tolerancia", float(tolerancia_decimal)),
            ("Coincidencias", len(coincidencias)),
            ("Solo en A", len(solo_en_a)),
            ("Solo en B", len(solo_en_b)),
            ("Diferencias de importe", len(diferencias)),
            ("Claves duplicadas en A", len(duplicadas_a)),
            ("Claves duplicadas en B", len(duplicadas_b)),
            ("Filas afectadas por duplicados", len(duplicados)),
            ("Filas sin clave en A", filas_sin_clave_a),
            ("Filas sin clave en B", filas_sin_clave_b),
        ],
        columns=["Métrica", "Valor"],
    )

    return ResultadoConciliacion(
        resumen=resumen,
        coincidencias=coincidencias,
        solo_en_a=solo_en_a,
        solo_en_b=solo_en_b,
        diferencias=diferencias,
        duplicados=duplicados,
    )
