from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_app_inicia_sin_excepciones_y_muestra_el_flujo_principal():
    ruta_app = Path(__file__).resolve().parents[1] / "app.py"

    app = AppTest.from_file(str(ruta_app), default_timeout=15).run()

    assert not app.exception
    assert any(
        "Carga los dos archivos" in elemento.value for elemento in app.subheader
    )
    assert len(app.info) == 1
    assert "Carga el archivo A" in app.info[0].value
