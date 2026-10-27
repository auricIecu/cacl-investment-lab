import os
from pathlib import Path


def source_path():
    value = os.environ.get("CA_WORKBOOK")
    if not value:
        raise RuntimeError("Defina CA_WORKBOOK con la ruta del Excel CA para ejecutar las pruebas.")
    path = Path(value)
    if not path.is_file():
        raise FileNotFoundError(path)
    return path
