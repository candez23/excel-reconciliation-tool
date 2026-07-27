"""Lectura local y validada de archivos CSV y Excel."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

import pandas as pd


EXTENSIONES_PERMITIDAS = {".csv", ".xlsx", ".xls"}
CODIFICACIONES_CSV = ("utf-8-sig", "utf-8", "cp1252", "latin-1")


class ErrorLecturaArchivo(ValueError):
    """Error comprensible al leer un archivo de entrada."""


@dataclass(frozen=True)
class ArchivoCargado:
    """Archivo tabular ya validado, con sus valores originales."""

    nombre: str
    datos: pd.DataFrame

    @property
    def filas(self) -> int:
        return len(self.datos)

    @property
    def columnas(self) -> int:
        return len(self.datos.columns)


def _obtener_contenido(archivo: bytes | bytearray | BinaryIO) -> bytes:
    if isinstance(archivo, (bytes, bytearray)):
        return bytes(archivo)

    if not hasattr(archivo, "read"):
        raise ErrorLecturaArchivo("El archivo no se pudo leer como contenido binario.")

    posicion = archivo.tell() if hasattr(archivo, "tell") else None
    contenido = archivo.read()
    if posicion is not None and hasattr(archivo, "seek"):
        archivo.seek(posicion)

    if not isinstance(contenido, bytes):
        raise ErrorLecturaArchivo("El archivo debe abrirse en modo binario.")
    return contenido


def _leer_csv(contenido: bytes, nombre: str) -> pd.DataFrame:
    errores: list[str] = []
    for codificacion in CODIFICACIONES_CSV:
        try:
            return pd.read_csv(
                BytesIO(contenido),
                sep=None,
                engine="python",
                encoding=codificacion,
                dtype=object,
                keep_default_na=False,
            )
        except (UnicodeDecodeError, pd.errors.ParserError) as exc:
            errores.append(f"{codificacion}: {exc}")

    detalle = errores[-1] if errores else "formato CSV no reconocido"
    raise ErrorLecturaArchivo(
        f'No se pudo leer "{nombre}" como CSV. Motivo: {detalle}'
    )


def _leer_excel(contenido: bytes, nombre: str, extension: str) -> pd.DataFrame:
    motor = "openpyxl" if extension == ".xlsx" else "xlrd"
    try:
        return pd.read_excel(
            BytesIO(contenido),
            sheet_name=0,
            dtype=object,
            keep_default_na=False,
            engine=motor,
        )
    except ImportError as exc:
        dependencia = "openpyxl" if extension == ".xlsx" else "xlrd"
        raise ErrorLecturaArchivo(
            f'No se pudo leer "{nombre}". Falta la dependencia gratuita '
            f'"{dependencia}". Instala requirements.txt y vuelve a intentarlo.'
        ) from exc
    except Exception as exc:
        raise ErrorLecturaArchivo(
            f'No se pudo leer "{nombre}" como Excel. Motivo: {exc}'
        ) from exc


def _validar_tabla(datos: pd.DataFrame, nombre: str) -> pd.DataFrame:
    if datos.empty and len(datos.columns) == 0:
        raise ErrorLecturaArchivo(
            f'El archivo "{nombre}" no contiene encabezados ni datos.'
        )
    if len(datos.columns) == 0:
        raise ErrorLecturaArchivo(f'El archivo "{nombre}" no contiene columnas.')

    columnas = [str(columna) for columna in datos.columns]
    vacias = [
        posicion + 1
        for posicion, columna in enumerate(columnas)
        if not columna.strip() or columna.lower().startswith("unnamed:")
    ]
    if vacias:
        posiciones = ", ".join(map(str, vacias))
        raise ErrorLecturaArchivo(
            f'El archivo "{nombre}" tiene encabezados vacíos en las columnas '
            f"{posiciones}. Asigna un nombre a cada columna."
        )

    duplicadas = pd.Index(columnas)[pd.Index(columnas).duplicated()].unique().tolist()
    if duplicadas:
        detalle = ", ".join(f'"{columna}"' for columna in duplicadas)
        raise ErrorLecturaArchivo(
            f'El archivo "{nombre}" contiene encabezados repetidos: {detalle}. '
            "Cada encabezado debe ser único."
        )

    resultado = datos.copy()
    resultado.columns = columnas
    return resultado.reset_index(drop=True)


def leer_archivo(
    archivo: bytes | bytearray | BinaryIO | str | Path,
    nombre: str | None = None,
) -> ArchivoCargado:
    """Lee la primera hoja de un archivo compatible sin modificar sus valores."""

    if isinstance(archivo, (str, Path)):
        ruta = Path(archivo)
        nombre_archivo = nombre or ruta.name
        contenido = ruta.read_bytes()
    else:
        nombre_archivo = nombre or getattr(archivo, "name", "archivo_sin_nombre")
        contenido = _obtener_contenido(archivo)

    extension = Path(nombre_archivo).suffix.lower()
    if extension not in EXTENSIONES_PERMITIDAS:
        permitidas = ", ".join(sorted(EXTENSIONES_PERMITIDAS))
        raise ErrorLecturaArchivo(
            f'El archivo "{nombre_archivo}" tiene una extensión no compatible. '
            f"Usa uno de estos formatos: {permitidas}."
        )
    if not contenido:
        raise ErrorLecturaArchivo(f'El archivo "{nombre_archivo}" está vacío.')

    try:
        if extension == ".csv":
            datos = _leer_csv(contenido, nombre_archivo)
        else:
            datos = _leer_excel(contenido, nombre_archivo, extension)
    except ErrorLecturaArchivo:
        raise
    except Exception as exc:
        raise ErrorLecturaArchivo(
            f'No se pudo leer "{nombre_archivo}". Motivo: {exc}'
        ) from exc

    return ArchivoCargado(
        nombre=nombre_archivo,
        datos=_validar_tabla(datos, nombre_archivo),
    )
