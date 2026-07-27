# Conciliador de Excel y CSV

Aplicación local de **KNDEZ DATA TOOLS** para comparar y conciliar dos archivos
tabulares de forma clara, reproducible y sin enviar información a servicios
externos.

La interfaz está completamente en español y funciona con archivos CSV, XLSX y
XLS. El procesamiento ocurre temporalmente en memoria: la aplicación no crea
copias permanentes de los archivos cargados.

## Qué hace

1. Carga un archivo A y un archivo B.
2. Informa el nombre, número de filas y número de columnas de cada archivo.
3. Permite seleccionar una columna clave diferente en cada archivo.
4. Permite seleccionar columnas de importe y definir una tolerancia numérica.
5. Separa los resultados en:

   - coincidencias;
   - registros que solo están en A;
   - registros que solo están en B;
   - diferencias de importe;
   - claves duplicadas y las filas relacionadas.

6. Genera un Excel con las hojas exactas `Resumen`, `Coincidencias`,
   `Solo_en_A`, `Solo_en_B`, `Diferencias` y `Duplicados`.

## Reglas de comparación

- Los encabezados se muestran y seleccionan con su escritura original. Pueden
  tener espacios, mayúsculas, acentos y un orden distinto entre archivos.
- Para comparar claves se crea una versión auxiliar temporal que ignora
  espacios al inicio y al final, diferencias entre mayúsculas y minúsculas y
  acentos. Los valores originales nunca se reemplazan en las tablas ni en el
  Excel exportado.
- Una diferencia de importe menor o igual a la tolerancia se considera
  coincidencia.
- Los importes aceptan formatos frecuentes como `1,234.56`, `1.234,56`,
  símbolos de moneda y valores negativos entre paréntesis.
- Si una clave está duplicada en cualquiera de los archivos, todas las filas
  relacionadas se envían a `Duplicados`. Así se evita crear emparejamientos
  ambiguos o productos cartesianos.
- Una fila sin clave se conserva como registro exclusivo del archivo donde
  aparece.

## Requisitos

- Windows, macOS o Linux.
- Python 3.10 o posterior.
- Dependencias gratuitas incluidas en `requirements.txt`.

No se necesita Excel instalado para ejecutar la aplicación.

## Instalación paso a paso

Abre PowerShell, entra a la carpeta del proyecto y crea un entorno virtual:

```powershell
cd "ruta\al\proyecto"
py -m venv .venv
```

Activa el entorno:

```powershell
.\.venv\Scripts\Activate.ps1
```

Si PowerShell no permite activar scripts, puedes omitir la activación y usar
directamente el ejecutable del entorno en los comandos siguientes.

Instala las dependencias:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Ejecutar la aplicación

Desde la carpeta `conciliador-excel`:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Streamlit mostrará una dirección local, normalmente
`http://localhost:8501`. La aplicación se abre en el navegador, pero los
archivos se procesan en la computadora donde se ejecuta Python.

Para detenerla, vuelve a PowerShell y presiona `Ctrl+C`.

## Probar con datos ficticios

La carpeta `datos_demo` incluye:

- `demostracion_archivo_A.csv`
- `demostracion_archivo_B.csv`

También se pueden descargar desde la sección de demostración al final de la
aplicación. Todos sus nombres, entidades y operaciones son ficticios.

Configuración sugerida para observar todos los casos:

- clave A: `ID Operación`;
- clave B: `REFERENCIA`;
- importe A: `Importe MXN`;
- importe B: `Importe registrado`;
- tolerancia: `0.50`.

El ejemplo contiene coincidencias, una diferencia de importe, registros
exclusivos y una clave duplicada.

## Ejecutar las pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Las pruebas cubren lectura de CSV y Excel, compatibilidad de enrutamiento para
XLS, conciliación, tolerancias, importes inválidos, duplicados, conservación de
valores y exportación con las seis hojas requeridas.

## Estructura

```text
conciliador-excel/
├── .streamlit/
│   └── config.toml
├── datos_demo/
├── src/
│   └── conciliador_excel/
│       ├── exportacion.py
│       ├── lectura.py
│       └── reconciliacion.py
├── tests/
├── app.py
├── pytest.ini
├── requirements.txt
└── README.md
```

- `app.py`: interfaz y coordinación de Streamlit.
- `lectura.py`: lectura y validación de CSV, XLSX y XLS.
- `reconciliacion.py`: comparación reutilizable, sin dependencia de Streamlit.
- `exportacion.py`: creación y formato del libro Excel.
- `tests`: pruebas automáticas.

## Privacidad y límites

- No subas información personal o confidencial a una instalación que no
  controles.
- Esta versión no publica, sincroniza ni despliega datos.
- Se procesa la primera hoja de cada archivo Excel.
- El límite de carga configurado es de 100 MB por archivo; archivos muy grandes
  pueden requerir más memoria.
- El formato XLS se admite para lectura mediante `xlrd`. La descarga siempre se
  genera como XLSX moderno.

## Solución de problemas

**El archivo no abre**

Confirma que la extensión sea CSV, XLSX o XLS y que el archivo no esté dañado.
Para Excel, verifica que `openpyxl` y `xlrd` se instalaron con
`requirements.txt`.

**Todo aparece en “Solo en A” o “Solo en B”**

Revisa que seleccionaste las columnas clave correctas. Si las claves contienen
formatos conceptualmente distintos —por ejemplo, ceros a la izquierda en un
archivo y no en el otro— deben corregirse en la fuente; la aplicación no cambia
esos valores silenciosamente.

**No se calculan diferencias de importe**

Selecciona una columna de importe en ambos archivos. Si se selecciona solo una,
la aplicación muestra un mensaje y no realiza una conciliación parcial.

**Hay filas en “Duplicados” que solo aparecen una vez en su archivo**

La misma clave está duplicada en el otro archivo. La fila relacionada también
se aparta para que una persona decida cómo emparejarla.

---

**KNDEZ DATA TOOLS** · Conciliador de Excel y CSV
