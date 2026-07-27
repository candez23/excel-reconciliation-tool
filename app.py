"""Interfaz Streamlit del Conciliador de Excel y CSV."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys

import pandas as pd
import streamlit as st


RAIZ = Path(__file__).resolve().parent
RUTA_SRC = RAIZ / "src"
if str(RUTA_SRC) not in sys.path:
    sys.path.insert(0, str(RUTA_SRC))

from conciliador_excel import (  # noqa: E402
    ErrorConciliacion,
    ErrorLecturaArchivo,
    conciliar_archivos,
    exportar_excel,
    leer_archivo,
)
from conciliador_excel.reconciliacion import normalizar_clave  # noqa: E402


st.set_page_config(
    page_title="Conciliador de Excel y CSV | KNDEZ DATA TOOLS",
    page_icon="⇄",
    layout="wide",
    initial_sidebar_state="collapsed",
)


ESTILOS = """
<style>
.kndez-brand {
    color: #77b8dc;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.14em;
    margin: 0 0 0.35rem 0;
}
.kndez-title {
    color: #f2f6f8;
    font-size: clamp(2rem, 4vw, 3.15rem);
    font-weight: 650;
    letter-spacing: -0.035em;
    line-height: 1.08;
    margin: 0;
}
.kndez-subtitle {
    color: #aebdca;
    font-size: 1.02rem;
    line-height: 1.6;
    margin: 0.8rem 0 1.4rem 0;
    max-width: 52rem;
}
.kndez-rule {
    border-top: 1px solid #304657;
    margin: 0 0 1.5rem 0;
}
.kndez-note {
    color: #91a4b3;
    font-size: 0.86rem;
    line-height: 1.5;
}
.kndez-footer {
    border-top: 1px solid #304657;
    color: #8296a6;
    font-size: 0.8rem;
    margin-top: 2.4rem;
    padding-top: 1rem;
}
@media (max-width: 700px) {
    .kndez-subtitle {
        font-size: 0.94rem;
    }
}
</style>
"""
st.markdown(ESTILOS, unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def _cargar_archivo(contenido: bytes, nombre: str):
    return leer_archivo(contenido, nombre)


@st.cache_data(show_spinner=False)
def _crear_excel(resultado) -> bytes:
    return exportar_excel(resultado)


def _detectar_columna_importe(columnas: list[str]) -> str | None:
    palabras = ("importe", "monto", "total", "valor", "amount")
    for columna in columnas:
        normalizada = normalizar_clave(columna) or ""
        if any(palabra in normalizada for palabra in palabras):
            return columna
    return None


def _detectar_columna_clave(columnas: list[str]) -> str | None:
    prioridades = ("clave", "referencia", "folio", "codigo", "id", "identificador")
    normalizadas = {
        columna: (normalizar_clave(columna) or "").split() for columna in columnas
    }
    for palabra in prioridades:
        for columna, tokens in normalizadas.items():
            if palabra in tokens:
                return columna
    return None


def _firma_configuracion(
    contenido_a: bytes,
    contenido_b: bytes,
    clave_a: str,
    clave_b: str,
    importe_a: str | None,
    importe_b: str | None,
    tolerancia: float,
) -> str:
    huella = hashlib.sha256()
    huella.update(contenido_a)
    huella.update(contenido_b)
    for valor in (clave_a, clave_b, importe_a, importe_b, str(tolerancia)):
        huella.update(str(valor).encode("utf-8"))
    return huella.hexdigest()


def _mostrar_ficha_archivo(etiqueta: str, archivo) -> None:
    st.markdown(f"**{etiqueta}: {archivo.nombre}**")
    metrica_filas, metrica_columnas = st.columns(2)
    metrica_filas.metric("Filas", f"{archivo.filas:,}")
    metrica_columnas.metric("Columnas", archivo.columnas)


def _mostrar_tabla(tabla: pd.DataFrame, vacio: str) -> None:
    if tabla.empty:
        st.info(vacio)
        return
    tabla_visible = tabla.copy()
    for columna in tabla_visible.columns:
        tipos = {
            type(valor)
            for valor in tabla_visible[columna]
            if not pd.isna(valor)
        }
        if len(tipos) > 1:
            tabla_visible[columna] = tabla_visible[columna].map(
                lambda valor: "" if pd.isna(valor) else str(valor)
            )
    st.caption(f"{len(tabla):,} registro(s)")
    st.dataframe(
        tabla_visible,
        width="stretch",
        hide_index=True,
        height=min(520, 74 + 35 * min(len(tabla), 12)),
    )


def _mostrar_resultado(resultado) -> None:
    metricas = resultado.metricas
    st.subheader("Resultado de la conciliación")

    fila_uno = st.columns(3)
    fila_uno[0].metric("Coincidencias", int(metricas["Coincidencias"]))
    fila_uno[1].metric("Solo en A", int(metricas["Solo en A"]))
    fila_uno[2].metric("Solo en B", int(metricas["Solo en B"]))
    fila_dos = st.columns(3)
    fila_dos[0].metric(
        "Diferencias de importe", int(metricas["Diferencias de importe"])
    )
    fila_dos[1].metric(
        "Claves duplicadas",
        int(metricas["Claves duplicadas en A"])
        + int(metricas["Claves duplicadas en B"]),
    )
    fila_dos[2].metric(
        "Filas afectadas por duplicados",
        int(metricas["Filas afectadas por duplicados"]),
    )

    if int(metricas["Filas afectadas por duplicados"]):
        st.warning(
            "Las claves duplicadas son ambiguas. Sus filas relacionadas se "
            "separaron en “Duplicados” y no se emparejaron automáticamente."
        )
    if int(metricas["Filas sin clave en A"]) or int(
        metricas["Filas sin clave en B"]
    ):
        st.info(
            "Las filas sin clave se conservaron como registros exclusivos del "
            "archivo donde aparecen."
        )

    pestañas = st.tabs(
        [
            "Resumen",
            "Coincidencias",
            "Solo en A",
            "Solo en B",
            "Diferencias",
            "Duplicados",
        ]
    )
    with pestañas[0]:
        _mostrar_tabla(resultado.resumen, "No hay métricas disponibles.")
    with pestañas[1]:
        _mostrar_tabla(
            resultado.coincidencias,
            "No se encontraron registros coincidentes.",
        )
    with pestañas[2]:
        _mostrar_tabla(
            resultado.solo_en_a,
            "No hay registros exclusivos del archivo A.",
        )
    with pestañas[3]:
        _mostrar_tabla(
            resultado.solo_en_b,
            "No hay registros exclusivos del archivo B.",
        )
    with pestañas[4]:
        _mostrar_tabla(
            resultado.diferencias,
            "No se detectaron diferencias de importe.",
        )
    with pestañas[5]:
        _mostrar_tabla(
            resultado.duplicados,
            "No se detectaron claves duplicadas.",
        )

    excel = _crear_excel(resultado)
    st.download_button(
        "Descargar conciliación en Excel",
        data=excel,
        file_name="conciliacion_KNDEZ_DATA_TOOLS.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        width="stretch",
    )
    st.caption(
        "El libro incluye: Resumen, Coincidencias, Solo_en_A, Solo_en_B, "
        "Diferencias y Duplicados."
    )


st.markdown('<p class="kndez-brand">KNDEZ DATA TOOLS</p>', unsafe_allow_html=True)
st.markdown(
    '<h1 class="kndez-title">Conciliador de Excel y CSV</h1>',
    unsafe_allow_html=True,
)
st.markdown(
    """
    <p class="kndez-subtitle">
    Compara dos archivos, identifica coincidencias y excepciones, y genera un
    reporte de conciliación listo para revisar. El procesamiento es temporal y
    ocurre localmente durante esta sesión.
    </p>
    <div class="kndez-rule"></div>
    """,
    unsafe_allow_html=True,
)

st.subheader("1. Carga los dos archivos")
columna_a, columna_b = st.columns(2, gap="large")
with columna_a:
    carga_a = st.file_uploader(
        "Archivo A",
        type=["csv", "xlsx", "xls"],
        key="archivo_a",
        help="Formatos compatibles: CSV, XLSX y XLS.",
    )
with columna_b:
    carga_b = st.file_uploader(
        "Archivo B",
        type=["csv", "xlsx", "xls"],
        key="archivo_b",
        help="Formatos compatibles: CSV, XLSX y XLS.",
    )

archivo_a = None
archivo_b = None
contenido_a = carga_a.getvalue() if carga_a is not None else None
contenido_b = carga_b.getvalue() if carga_b is not None else None

if carga_a is not None:
    try:
        archivo_a = _cargar_archivo(contenido_a, carga_a.name)
    except ErrorLecturaArchivo as exc:
        st.error(str(exc))
if carga_b is not None:
    try:
        archivo_b = _cargar_archivo(contenido_b, carga_b.name)
    except ErrorLecturaArchivo as exc:
        st.error(str(exc))

if archivo_a is not None and archivo_b is not None:
    ficha_a, ficha_b = st.columns(2, gap="large")
    with ficha_a:
        _mostrar_ficha_archivo("Archivo A", archivo_a)
    with ficha_b:
        _mostrar_ficha_archivo("Archivo B", archivo_b)

    st.subheader("2. Configura la comparación")
    config_a, config_b = st.columns(2, gap="large")
    columnas_a = list(archivo_a.datos.columns)
    columnas_b = list(archivo_b.datos.columns)
    opcion_sin_importe = "— No comparar importes —"

    with config_a:
        clave_sugerida_a = _detectar_columna_clave(columnas_a)
        clave_a = st.selectbox(
            "Columna clave del archivo A",
            columnas_a,
            index=(
                columnas_a.index(clave_sugerida_a)
                if clave_sugerida_a is not None
                else 0
            ),
            key="clave_a",
        )
        importe_sugerido_a = _detectar_columna_importe(columnas_a)
        indice_importe_a = (
            columnas_a.index(importe_sugerido_a) + 1
            if importe_sugerido_a is not None
            else 0
        )
        seleccion_importe_a = st.selectbox(
            "Columna de importe del archivo A (opcional)",
            [opcion_sin_importe, *columnas_a],
            index=indice_importe_a,
            key="importe_a",
        )

    with config_b:
        clave_sugerida_b = _detectar_columna_clave(columnas_b)
        clave_b = st.selectbox(
            "Columna clave del archivo B",
            columnas_b,
            index=(
                columnas_b.index(clave_sugerida_b)
                if clave_sugerida_b is not None
                else 0
            ),
            key="clave_b",
        )
        importe_sugerido_b = _detectar_columna_importe(columnas_b)
        indice_importe_b = (
            columnas_b.index(importe_sugerido_b) + 1
            if importe_sugerido_b is not None
            else 0
        )
        seleccion_importe_b = st.selectbox(
            "Columna de importe del archivo B (opcional)",
            [opcion_sin_importe, *columnas_b],
            index=indice_importe_b,
            key="importe_b",
        )

    importe_a = (
        None if seleccion_importe_a == opcion_sin_importe else seleccion_importe_a
    )
    importe_b = (
        None if seleccion_importe_b == opcion_sin_importe else seleccion_importe_b
    )
    comparar_importes = importe_a is not None and importe_b is not None
    tolerancia = st.number_input(
        "Tolerancia numérica",
        min_value=0.0,
        value=0.0,
        step=0.01,
        format="%.2f",
        disabled=not comparar_importes,
        help=(
            "Una diferencia menor o igual a esta cantidad se considera "
            "coincidencia."
        ),
    )
    st.markdown(
        """
        <p class="kndez-note">
        Las claves se comparan ignorando espacios exteriores, diferencias entre
        mayúsculas y minúsculas y acentos. Los valores originales no se
        reemplazan en las tablas ni en el reporte.
        </p>
        """,
        unsafe_allow_html=True,
    )

    firma_actual = _firma_configuracion(
        contenido_a,
        contenido_b,
        clave_a,
        clave_b,
        importe_a,
        importe_b,
        tolerancia,
    )
    if st.button(
        "Conciliar archivos",
        type="primary",
        width="stretch",
    ):
        try:
            with st.spinner("Conciliando los archivos…"):
                resultado = conciliar_archivos(
                    archivo_a.datos,
                    archivo_b.datos,
                    columna_clave_a=clave_a,
                    columna_clave_b=clave_b,
                    columna_importe_a=importe_a,
                    columna_importe_b=importe_b,
                    tolerancia=tolerancia,
                    nombre_a=archivo_a.nombre,
                    nombre_b=archivo_b.nombre,
                )
            st.session_state["resultado"] = resultado
            st.session_state["firma_resultado"] = firma_actual
        except ErrorConciliacion as exc:
            st.error(str(exc))
            st.session_state.pop("resultado", None)
            st.session_state.pop("firma_resultado", None)

    if st.session_state.get("firma_resultado") == firma_actual:
        _mostrar_resultado(st.session_state["resultado"])
    elif "resultado" in st.session_state:
        st.info(
            "La configuración cambió. Pulsa “Conciliar archivos” para actualizar "
            "el resultado."
        )
else:
    st.info(
        "Carga el archivo A y el archivo B para habilitar la configuración de "
        "la conciliación."
    )

with st.expander("Probar con archivos ficticios de demostración"):
    st.write(
        "Estos CSV contienen operaciones y entidades completamente ficticias. "
        "Descarga ambos y cárgalos arriba."
    )
    demo_a = (RAIZ / "datos_demo" / "demostracion_archivo_A.csv").read_bytes()
    demo_b = (RAIZ / "datos_demo" / "demostracion_archivo_B.csv").read_bytes()
    descarga_a, descarga_b = st.columns(2)
    descarga_a.download_button(
        "Descargar demostración A",
        demo_a,
        "demostracion_archivo_A.csv",
        "text/csv",
        width="stretch",
    )
    descarga_b.download_button(
        "Descargar demostración B",
        demo_b,
        "demostracion_archivo_B.csv",
        "text/csv",
        width="stretch",
    )

st.markdown(
    """
    <p class="kndez-footer">
    KNDEZ DATA TOOLS · Procesamiento temporal y local · No se envían archivos
    a servicios externos
    </p>
    """,
    unsafe_allow_html=True,
)
