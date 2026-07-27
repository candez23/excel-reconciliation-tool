from io import BytesIO
from zipfile import ZipFile

import pandas as pd
from openpyxl import load_workbook
from openpyxl.utils.cell import range_boundaries

from conciliador_excel.exportacion import NOMBRES_HOJAS, exportar_excel
from conciliador_excel.reconciliacion import conciliar_archivos


def _resultado_ejemplo():
    datos_a = pd.DataFrame(
        {
            "Clave": ["A-1", "A-2", "A-3", "DUP", "dup"],
            "Importe": [100, 200, 300, 10, 10],
        }
    )
    datos_b = pd.DataFrame(
        {
            "Referencia": ["A-1", "A-2", "A-4", "DUP"],
            "Monto": [100, 205, 400, 10],
        }
    )
    return conciliar_archivos(
        datos_a,
        datos_b,
        "Clave",
        "Referencia",
        "Importe",
        "Monto",
        tolerancia=1,
    )


def test_exporta_las_seis_hojas_con_nombres_exactos_y_formato():
    contenido = exportar_excel(_resultado_ejemplo())
    libro = load_workbook(BytesIO(contenido))

    assert tuple(libro.sheetnames) == NOMBRES_HOJAS
    nombres_tablas = set()
    for nombre in NOMBRES_HOJAS:
        hoja = libro[nombre]
        assert hoja.freeze_panes == "A2"
        assert hoja.sheet_view.showGridLines is False
        assert hoja["A1"].font.bold is True
        assert hoja["A1"].fill.fgColor.rgb.endswith("1D3448")
        assert hoja.auto_filter.ref is None

        assert len(hoja.tables) == 1
        tabla = next(iter(hoja.tables.values()))
        assert tabla.displayName not in nombres_tablas
        nombres_tablas.add(tabla.displayName)
        assert tabla.ref == hoja.dimensions
        assert tabla.autoFilter.ref == tabla.ref

        columna_inicial, fila_inicial, columna_final, fila_final = range_boundaries(
            tabla.ref
        )
        assert fila_inicial == 1
        assert fila_final >= 2
        assert columna_final >= columna_inicial

        encabezados = [columna.name for columna in tabla.tableColumns]
        assert all(encabezado.strip() for encabezado in encabezados)
        assert len(encabezados) == len(set(encabezados))
    assert libro["Resumen"].max_row > 2
    assert libro["Diferencias"].max_row == 2


def test_no_duplica_filtros_de_hoja_y_tabla_en_el_ooxml():
    contenido = exportar_excel(_resultado_ejemplo())

    with ZipFile(BytesIO(contenido)) as archivo:
        hojas_xml = [
            nombre
            for nombre in archivo.namelist()
            if nombre.startswith("xl/worksheets/sheet") and nombre.endswith(".xml")
        ]
        tablas_xml = [
            nombre
            for nombre in archivo.namelist()
            if nombre.startswith("xl/tables/table") and nombre.endswith(".xml")
        ]

        assert len(hojas_xml) == len(NOMBRES_HOJAS)
        assert len(tablas_xml) == len(NOMBRES_HOJAS)
        assert all(b"<autoFilter" not in archivo.read(nombre) for nombre in hojas_xml)
        assert all(b"<autoFilter" in archivo.read(nombre) for nombre in tablas_xml)


def test_valores_que_parecen_formula_se_exportan_como_texto():
    datos_a = pd.DataFrame({"Clave": ["=2+2"], "Valor": ["=CMD()"]})
    datos_b = pd.DataFrame({"Referencia": ["=2+2"], "Dato": ["seguro"]})
    resultado = conciliar_archivos(datos_a, datos_b, "Clave", "Referencia")

    contenido = exportar_excel(resultado)
    libro = load_workbook(BytesIO(contenido), data_only=False)
    hoja = libro["Coincidencias"]
    encabezados = {
        celda.value: celda.column for celda in hoja[1] if celda.value is not None
    }
    celda_clave = hoja.cell(2, encabezados["A | Clave"])
    celda_valor = hoja.cell(2, encabezados["A | Valor"])

    assert celda_clave.value == "=2+2"
    assert celda_clave.data_type == "s"
    assert celda_valor.value == "=CMD()"
    assert celda_valor.data_type == "s"
