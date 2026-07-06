"""
Restaura las reglas de validación de datos (checkboxes y desplegables) en todas
las hojas EE de las planillas, tomando como fuente el Modelo EE.

No toca los valores cargados — solo actualiza las reglas de validación.

Uso:
    python restaurar_validaciones_ee.py --folder-id <ID>          # todas
    python restaurar_validaciones_ee.py --folder-id <ID> --emaus Cafayate
    python restaurar_validaciones_ee.py --folder-id <ID> --dry-run
"""

import argparse
import time
from pathlib import Path
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).parent
load_dotenv(SCRIPT_DIR.parent.parent / ".env")

import sys
sys.path.insert(0, str(SCRIPT_DIR.parent))

from scripts.scraper_control import (
    build_services, execute_with_retry, list_spreadsheets,
    EXCLUDED_SHEETS, NAME_CONTAINS,
)

MODELO_ID = "1Yohc-X7bnHTYJgwkhlECNnq9FQFVp8sX29HXrSWx_8M"
MODELO_SHEET = "Modelo EE"

# Hojas que NO son EE (se saltan)
NON_EE_SHEETS = EXCLUDED_SHEETS | {"Nuestra Señora del Valle"}  # hojas especiales conocidas

# Colores para C254:C261 — orden de preocupación 1 (más) a 8 (menos)
# Tomados del dropdown visual del Modelo EE
RANKING_COLORS = [
    {"red": 0.714, "green": 0.118, "blue": 0.118},  # 1 — rojo oscuro
    {"red": 0.957, "green": 0.698, "blue": 0.698},  # 2 — rosa
    {"red": 0.737, "green": 0.608, "blue": 0.851},  # 3 — lila
    {"red": 0.420, "green": 0.796, "blue": 0.773},  # 4 — teal
    {"red": 0.557, "green": 0.698, "blue": 0.835},  # 5 — azul
    {"red": 0.647, "green": 0.839, "blue": 0.655},  # 6 — verde
    {"red": 0.996, "green": 0.922, "blue": 0.545},  # 7 — amarillo
    {"red": 0.800, "green": 0.800, "blue": 0.800},  # 8 — gris
]
# Filas 254–261 (0-indexed: 253–260), columna C (índice 2)
RANKING_ROW_START = 253
RANKING_ROW_END = 261
RANKING_COL = 2  # C


def col_letter_to_index(col: str) -> int:
    """'A' → 0, 'B' → 1, 'AA' → 26, etc."""
    col = col.upper()
    result = 0
    for ch in col:
        result = result * 26 + (ord(ch) - ord('A') + 1)
    return result - 1


def cell_ref_to_grid(cell_ref: str):
    """'C132' → {rowIndex: 131, colIndex: 2}"""
    import re
    m = re.match(r'([A-Z]+)(\d+)', cell_ref.upper())
    col = col_letter_to_index(m.group(1))
    row = int(m.group(2)) - 1
    return row, col


def read_model_validations(sheets_svc) -> dict:
    """
    Lee todas las reglas de validación del Modelo EE.
    Retorna dict: {cell_ref: dataValidation_object}
    """
    resp = execute_with_retry(sheets_svc.spreadsheets().get(
        spreadsheetId=MODELO_ID,
        fields="sheets(properties(title),data(rowData(values(dataValidation))))"
    ))

    validations = {}
    for sheet in resp.get("sheets", []):
        if sheet["properties"]["title"] != MODELO_SHEET:
            continue
        for data in sheet.get("data", []):
            for row_idx, row in enumerate(data.get("rowData", [])):
                for col_idx, cell in enumerate(row.get("values", [])):
                    dv = cell.get("dataValidation")
                    if not dv:
                        continue
                    col_letter = (
                        chr(65 + col_idx) if col_idx < 26
                        else chr(64 + col_idx // 26) + chr(65 + col_idx % 26)
                    )
                    cell_ref = f"{col_letter}{row_idx + 1}"
                    validations[cell_ref] = dv
    return validations


def build_set_validation_requests(sheet_id: int, validations: dict) -> list:
    """
    Construye la lista de requests setDataValidation para aplicar
    todas las reglas del modelo a una hoja (identificada por sheet_id).
    """
    requests = []
    for cell_ref, dv in validations.items():
        row, col = cell_ref_to_grid(cell_ref)
        requests.append({
            "setDataValidation": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": row,
                    "endRowIndex": row + 1,
                    "startColumnIndex": col,
                    "endColumnIndex": col + 1,
                },
                "rule": {
                    "condition": dv["condition"],
                    "showCustomUi": dv.get("showCustomUi", True),
                    "strict": dv.get("strict", False),
                },
            }
        })
    return requests


def build_ranking_color_requests(sheet_id: int) -> list:
    """
    Formato condicional para C254:C261 — cada valor 1-8 tiene un color distinto
    para que el ATL vea visualmente si repitió un número.
    También borra cualquier formato condicional anterior en ese rango para evitar duplicados.
    """
    requests = []

    # Primero limpiar formatos condicionales existentes en el rango
    # (no hay un request directo para eso; los addConditionalFormatRule se apilan,
    # así que usamos deleteConditionalFormatRule por índice — se maneja al final)

    grid_range = {
        "sheetId": sheet_id,
        "startRowIndex": RANKING_ROW_START,
        "endRowIndex": RANKING_ROW_END,
        "startColumnIndex": RANKING_COL,
        "endColumnIndex": RANKING_COL + 1,
    }

    for i, color in enumerate(RANKING_COLORS):
        value = str(i + 1)
        requests.append({
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [grid_range],
                    "booleanRule": {
                        "condition": {
                            "type": "TEXT_EQ",
                            "values": [{"userEnteredValue": value}],
                        },
                        "format": {
                            "backgroundColor": color,
                        },
                    },
                },
                "index": 0,
            }
        })
    return requests


def build_formula_c16_request(sheet_id: int) -> dict:
    """Setea C16 = =SUMA(C10:C15) como fórmula."""
    return {
        "updateCells": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 15,  # fila 16 (0-indexed)
                "endRowIndex": 16,
                "startColumnIndex": 2,  # columna C
                "endColumnIndex": 3,
            },
            "rows": [{
                "values": [{
                    "userEnteredValue": {"formulaValue": "=SUMA(C10:C15)"},
                }]
            }],
            "fields": "userEnteredValue",
        }
    }


def delete_existing_conditional_formats(sheets_svc, spreadsheet_id: str,
                                        sheet_id: int) -> list:
    """
    Devuelve requests para eliminar los formatos condicionales existentes
    en C254:C261 de esta hoja, para no acumular duplicados en cada corrida.
    """
    resp = execute_with_retry(sheets_svc.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets(properties(sheetId),conditionalFormats)"
    ))
    requests = []
    for sheet in resp.get("sheets", []):
        if sheet["properties"]["sheetId"] != sheet_id:
            continue
        cfs = sheet.get("conditionalFormats", [])
        # Recorrer en reversa para no alterar índices al eliminar
        for idx in reversed(range(len(cfs))):
            cf = cfs[idx]
            for r in cf.get("ranges", []):
                if (r.get("sheetId") == sheet_id
                        and r.get("startRowIndex", 0) >= RANKING_ROW_START
                        and r.get("endRowIndex", 0) <= RANKING_ROW_END):
                    requests.append({
                        "deleteConditionalFormatRule": {
                            "sheetId": sheet_id,
                            "index": idx,
                        }
                    })
                    break
    return requests


def get_ee_sheets(sheets_svc, spreadsheet_id: str) -> list:
    """Retorna lista de {title, sheetId} de hojas EE en la planilla."""
    resp = execute_with_retry(sheets_svc.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets(properties(title,sheetId))"
    ))
    result = []
    for sheet in resp.get("sheets", []):
        title = sheet["properties"]["title"]
        if title.strip() not in NON_EE_SHEETS and title.strip() not in {
            s.strip() for s in NON_EE_SHEETS
        }:
            result.append({
                "title": title,
                "sheetId": sheet["properties"]["sheetId"],
            })
    return result


def apply_validations_to_spreadsheet(sheets_svc, spreadsheet_id: str,
                                     validations: dict, emaus_nombre: str,
                                     dry_run: bool):
    ee_sheets = get_ee_sheets(sheets_svc, spreadsheet_id)
    if not ee_sheets:
        print(f"    Sin hojas EE — salteando")
        return 0

    print(f"    {len(ee_sheets)} hojas EE: {[s['title'] for s in ee_sheets]}")

    if dry_run:
        total = len(validations) * len(ee_sheets)
        print(f"    [dry-run] Se aplicarían {total} validaciones + colores C254:C261 "
              f"+ fórmula C16 en {len(ee_sheets)} hojas")
        return len(ee_sheets)

    all_requests = []

    for sheet in ee_sheets:
        sid = sheet["sheetId"]

        # 1. Validaciones del modelo
        all_requests.extend(build_set_validation_requests(sid, validations))

        # 2. Fórmula C16 = SUMA(C10:C15)
        all_requests.append(build_formula_c16_request(sid))

        # 3. Limpiar formatos condicionales existentes en C254:C261
        all_requests.extend(delete_existing_conditional_formats(
            sheets_svc, spreadsheet_id, sid))

        # 4. Agregar formato condicional de colores 1-8
        all_requests.extend(build_ranking_color_requests(sid))

    # Ejecutar en lotes de 500 requests
    BATCH_SIZE = 500
    for i in range(0, len(all_requests), BATCH_SIZE):
        batch = all_requests[i:i + BATCH_SIZE]
        execute_with_retry(sheets_svc.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": batch}
        ))
        if i + BATCH_SIZE < len(all_requests):
            time.sleep(1)

    n_val = len(validations) * len(ee_sheets)
    print(f"    OK — {n_val} validaciones + colores + fórmula C16 en {len(ee_sheets)} hojas")
    return len(ee_sheets)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder-id", required=True)
    parser.add_argument("--emaus", default=None,
                        help="Nombre del Emaús a procesar (ej: 'Cafayate'). "
                             "Si no se indica, procesa todos.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Solo muestra qué haría, sin escribir nada")
    args = parser.parse_args()

    sheets_svc, drive_svc = build_services()

    print("Leyendo reglas de validación del Modelo EE...")
    validations = read_model_validations(sheets_svc)
    print(f"  {len(validations)} reglas encontradas en el modelo")

    print(f"\nBuscando planillas en carpeta {args.folder_id} ...")
    all_spreadsheets = list_spreadsheets(drive_svc, args.folder_id, NAME_CONTAINS)
    print(f"  {len(all_spreadsheets)} planillas encontradas")

    if args.dry_run:
        print("  [MODO DRY-RUN — no se escribe nada]\n")

    ok = err = skip = 0

    for item in all_spreadsheets:
        emaus_nombre = item.get("emaus_nombre", "").strip()
        spreadsheet_id = item["id"]

        if args.emaus and emaus_nombre.lower() != args.emaus.lower():
            continue

        print(f"\n[{emaus_nombre}] {spreadsheet_id[:20]}...")
        try:
            n = apply_validations_to_spreadsheet(
                sheets_svc, spreadsheet_id, validations,
                emaus_nombre, args.dry_run
            )
            ok += 1
        except Exception as exc:
            print(f"    ERROR — {exc}")
            err += 1
            time.sleep(5)
        else:
            time.sleep(2)  # pausa entre planillas

    print(f"\nResumen: {ok} OK, {err} errores, {skip} salteados")
    if args.dry_run:
        print("(dry-run — no se modificó nada)")


if __name__ == "__main__":
    main()
