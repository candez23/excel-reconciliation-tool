from io import BytesIO

import pandas as pd
import pytest

from conciliador_excel.lectura import ErrorLecturaArchivo, leer_archivo


def test_lee_csv_con_separador_y_encabezados_en_espanol():
    contenido = (
        "  CLAVE ÚNICA  ;Importe Total;Descripción\n"
        "A-1;1250,50;Operación ficticia\n"
    ).encode("utf-8")

    archivo = leer_archivo(contenido, "ejemplo.csv")

    assert archivo.nombre == "ejemplo.csv"
    assert archivo.filas == 1
    assert archivo.columnas == 3
    assert list(archivo.datos.columns) == [
        "  CLAVE ÚNICA  ",
        "Importe Total",
        "Descripción",
    ]
    assert archivo.datos.iloc[0]["Importe Total"] == "1250,50"


def test_lee_xlsx_desde_memoria():
    origen = pd.DataFrame(
        {"Referencia": ["X-1", "X-2"], "Importe": [10.25, 20.50]}
    )
    buffer = BytesIO()
    origen.to_excel(buffer, index=False, engine="openpyxl")

    archivo = leer_archivo(buffer.getvalue(), "entrada.xlsx")

    assert archivo.filas == 2
    assert list(archivo.datos.columns) == ["Referencia", "Importe"]
    assert archivo.datos.iloc[1]["Referencia"] == "X-2"


def test_archivo_xls_se_rutea_al_motor_xlrd(monkeypatch):
    captura = {}

    def lector_simulado(*args, **kwargs):
        captura["engine"] = kwargs["engine"]
        return pd.DataFrame({"Clave": ["A"]})

    monkeypatch.setattr(pd, "read_excel", lector_simulado)

    archivo = leer_archivo(b"contenido simulado", "legado.xls")

    assert archivo.filas == 1
    assert captura["engine"] == "xlrd"


def test_rechaza_extension_no_compatible():
    with pytest.raises(ErrorLecturaArchivo, match="extensión no compatible"):
        leer_archivo(b"clave,valor\nA,1", "entrada.txt")


def test_rechaza_archivo_vacio():
    with pytest.raises(ErrorLecturaArchivo, match="está vacío"):
        leer_archivo(b"", "vacio.csv")
