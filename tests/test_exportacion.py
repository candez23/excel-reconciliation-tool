from io import BytesIO

import pandas as pd
from openpyxl import load_workbook

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
    for nombre in NOMBRES_HOJAS:
        hoja = libro[nombre]
        assert hoja.freeze_panes == "A2"
        assert hoja.sheet_view.showGridLines is False
        assert hoja["A1"].font.bold is True
        assert hoja["A1"].fill.fgColor.rgb.endswith("1D3448")
    assert libro["Resumen"].max_row > 2
    assert libro["Diferencias"].max_row == 2


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
