"""
Importa Diócesis y Emaús desde el CSV provisto por la usuaria.

Uso:
    cd backend && source venv/bin/activate
    python scripts/importar_diocesis_emaus.py /ruta/al/DatosDiocesisEmaus.csv

Columnas esperadas: Emaus, Provincia, Region, Diocesis

Unifica manualmente dos inconsistencias conocidas del CSV (confirmadas con la usuaria):
- "Santo Tome" / "Santo Tomé" -> una sola diócesis "Santo Tomé"
- "Cafayate" / "Prelatura de Cafayate" -> una sola diócesis "Prelatura de Cafayate"
"""
import csv
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.emaus import Diocesis, Emaus

OVERRIDES = {
    "santo tome": "Santo Tomé",
    "cafayate": "Prelatura de Cafayate",
    "prelatura de cafayate": "Prelatura de Cafayate",
}


def normalizar(texto: str) -> str:
    texto = texto.strip().lower()
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def nombre_canonico(nombre_diocesis: str) -> str:
    clave = normalizar(nombre_diocesis)
    return OVERRIDES.get(clave, nombre_diocesis.strip())


def main(csv_path: str):
    db = SessionLocal()

    diocesis_por_clave: dict[tuple[str, str], Diocesis] = {}
    emaus_creados = 0
    diocesis_creadas = 0

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        filas = list(reader)

    for fila in filas:
        emaus_nombre = fila["Emaus"].strip()
        provincia = fila["Provincia"].strip()
        region = fila["Region"].strip()
        diocesis_nombre = nombre_canonico(fila["Diocesis"])

        clave = (normalizar(diocesis_nombre), normalizar(provincia))
        diocesis = diocesis_por_clave.get(clave)
        if not diocesis:
            diocesis = db.query(Diocesis).filter(
                Diocesis.nombre == diocesis_nombre, Diocesis.provincia == provincia
            ).first()
        if not diocesis:
            diocesis = Diocesis(nombre=diocesis_nombre, provincia=provincia, region=region)
            db.add(diocesis)
            db.flush()
            diocesis_creadas += 1
        diocesis_por_clave[clave] = diocesis

        existe_emaus = db.query(Emaus).filter(
            Emaus.nombre == emaus_nombre, Emaus.diocesis_id == diocesis.id
        ).first()
        if existe_emaus:
            print(f"  (ya existía) Emaús '{emaus_nombre}' en diócesis '{diocesis_nombre}'")
            continue

        db.add(Emaus(diocesis_id=diocesis.id, nombre=emaus_nombre, activo=True))
        emaus_creados += 1

    db.commit()
    print(f"\nListo. Diócesis nuevas: {diocesis_creadas}. Emaús nuevos: {emaus_creados}.")
    db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python importar_diocesis_emaus.py /ruta/al/csv")
        sys.exit(1)
    main(sys.argv[1])
