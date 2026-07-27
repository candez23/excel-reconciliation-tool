from decimal import Decimal

import pandas as pd
import pytest

from conciliador_excel.reconciliacion import (
    ErrorConciliacion,
    conciliar_archivos,
    convertir_importe,
)


def test_concilia_coincidencias_exclusivos_y_diferencias_con_tolerancia():
    datos_a = pd.DataFrame(
        {
            "ID Operación": ["Uno", "Dos", "Tres", "Solo A"],
            "Importe MXN": ["100.00", "200.00", "300.00", "50.00"],
            "Descripción": ["Árbol", "Lago", "Brisa", "Nube"],
        }
    )
    datos_b = pd.DataFrame(
        {
            "monto": ["100.10", "200.50", "305.00", "60.00"],
            "REFERENCIA": [" uno ", "DÓS", "tres", "Solo B"],
        }
    )
    copia_a = datos_a.copy(deep=True)
    copia_b = datos_b.copy(deep=True)

    resultado = conciliar_archivos(
        datos_a,
        datos_b,
        "ID Operación",
        "REFERENCIA",
        "Importe MXN",
        "monto",
        tolerancia=0.50,
    )

    assert len(resultado.coincidencias) == 2
    assert len(resultado.solo_en_a) == 1
    assert len(resultado.solo_en_b) == 1
    assert len(resultado.diferencias) == 1
    assert resultado.diferencias.iloc[0]["A | ID Operación"] == "Tres"
    assert resultado.diferencias.iloc[0]["Diferencia absoluta"] == 5.0
    pd.testing.assert_frame_equal(datos_a, copia_a)
    pd.testing.assert_frame_equal(datos_b, copia_b)


def test_duplicados_y_filas_relacionadas_se_separan_sin_producto_cartesiano():
    datos_a = pd.DataFrame(
        {
            "clave": ["K-1", "k-1", "K-2"],
            "importe": [10, 10, 20],
        }
    )
    datos_b = pd.DataFrame(
        {
            "ref": ["K-1", "K-2"],
            "monto": [10, 20],
        }
    )

    resultado = conciliar_archivos(
        datos_a,
        datos_b,
        "clave",
        "ref",
        "importe",
        "monto",
    )

    assert len(resultado.coincidencias) == 1
    assert resultado.coincidencias.iloc[0]["A | clave"] == "K-2"
    assert len(resultado.duplicados) == 3
    assert set(resultado.duplicados["Origen"]) == {"A", "B"}
    assert set(resultado.duplicados["Motivo"]) == {
        "Clave relacionada con duplicado; se separa para revisión"
    }
    assert resultado.metricas["Claves duplicadas en A"] == 1
    assert resultado.metricas["Claves duplicadas en B"] == 0


def test_filas_sin_clave_se_conservan_como_exclusivas():
    datos_a = pd.DataFrame({"clave": [pd.NA, "A"], "valor": [1, 2]})
    datos_b = pd.DataFrame({"clave": [None, "a"], "valor": [3, 2]})

    resultado = conciliar_archivos(datos_a, datos_b, "clave", "clave")

    assert len(resultado.coincidencias) == 1
    assert len(resultado.solo_en_a) == 1
    assert len(resultado.solo_en_b) == 1
    assert resultado.metricas["Filas sin clave en A"] == 1
    assert resultado.metricas["Filas sin clave en B"] == 1


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("$1,234.56", Decimal("1234.56")),
        ("1.234,56 €", Decimal("1234.56")),
        ("(250.40)", Decimal("-250.40")),
        ("8,450", Decimal("8450")),
        ("texto", None),
        ("", None),
    ],
)
def test_conversion_de_importes_frecuentes(valor, esperado):
    assert convertir_importe(valor) == esperado


def test_importe_invalido_se_reporta_como_diferencia_comprensible():
    datos_a = pd.DataFrame({"clave": ["A-1"], "importe": ["sin dato"]})
    datos_b = pd.DataFrame({"ref": ["A-1"], "monto": [100]})

    resultado = conciliar_archivos(
        datos_a,
        datos_b,
        "clave",
        "ref",
        "importe",
        "monto",
    )

    assert resultado.coincidencias.empty
    assert len(resultado.diferencias) == 1
    assert 'A: "importe"' in resultado.diferencias.iloc[0]["Motivo"]


def test_exige_importes_en_ambos_archivos_o_en_ninguno():
    datos_a = pd.DataFrame({"clave": ["A"], "importe": [1]})
    datos_b = pd.DataFrame({"clave": ["A"], "monto": [1]})

    with pytest.raises(ErrorConciliacion, match="ambos archivos"):
        conciliar_archivos(
            datos_a,
            datos_b,
            "clave",
            "clave",
            columna_importe_a="importe",
        )


def test_rechaza_tolerancia_negativa():
    datos = pd.DataFrame({"clave": ["A"]})
    with pytest.raises(ErrorConciliacion, match="mayor o igual"):
        conciliar_archivos(datos, datos, "clave", "clave", tolerancia=-0.01)
