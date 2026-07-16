"""
Scraper de control de relevamiento Emaús.

Corre contra todas las planillas Google Sheets de un período dado,
ejecuta las validaciones definidas en especificacion_planillas.yaml,
resetea checks a Pendiente en hojas con errores, y guarda métricas
y detalle de errores en TiDB.

Uso:
    python scraper_control.py --anio 2026 --semestre 1 --folder-id <DRIVE_FOLDER_ID>
    python scraper_control.py --anio 2026 --semestre 1 --folder-id <ID> --emaus-id 180005
    python scraper_control.py --anio 2026 --semestre 1 --folder-id <ID> --dry-run
"""

import argparse
import json
import os
import socket
import sys

socket.setdefaulttimeout(90)  # 90s máximo por cualquier llamada de red
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.service_account import Credentials as SACredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle

from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent

# Cargar .env antes de leer cualquier variable de entorno
_env_path = SCRIPT_DIR.parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

SPREADSHEET_MIME = "application/vnd.google-apps.spreadsheet"
FOLDER_MIME = "application/vnd.google-apps.folder"

EXCLUDED_SHEETS = {"Pastoral Primera Infancia", "Talleres", "Establecimientos",
                   "Modelo EE", "EstablecimientosModelo", "Talleres enero-junio 2026",
                   "Establecimientos_aux"}

PI_SHEET_TITLE = "Pastoral Primera Infancia"
TALLERES_SHEET = "Talleres"
TALLERES_SHEET_ALT = "Talleres enero-junio 2026"
ESTABLECIMIENTOS_SHEET = "Establecimientos"

# Busca el YAML primero junto al script (Lambda), después en archivosdatos/ (local)
_yaml_local = SCRIPT_DIR.parent.parent / "archivosdatos" / "especificacion_planillas.yaml"
_yaml_bundled = SCRIPT_DIR / "especificacion_planillas.yaml"
YAML_PATH = _yaml_bundled if _yaml_bundled.exists() else _yaml_local
TOKEN_PATH = Path(os.getenv("GOOGLE_TOKEN_PATH", str(SCRIPT_DIR.parent.parent.parent /
    "Informes Emaus" / "2026_Mid" / "token.json")))
CLIENT_SECRET_PATH = Path(os.getenv("GOOGLE_CLIENT_SECRET_PATH", str(SCRIPT_DIR.parent.parent.parent /
    "Informes Emaus" / "2026_Mid" / "client_secret.json")))

ANIO_DEFAULT = 2026
SEMESTRE_DEFAULT = "1"

NAME_CONTAINS = "Informe Emaús de medio termino 2026"

# ---------------------------------------------------------------------------
# Google Auth
# ---------------------------------------------------------------------------

def build_services():
    """Construye los servicios de Google Sheets y Drive usando SA o OAuth."""
    sa_json = os.getenv("GCP_SERVICE_ACCOUNT_JSON")
    sa_path = os.getenv("GCP_SERVICE_ACCOUNT_JSON_PATH")

    if sa_json:
        info = json.loads(sa_json)
        creds = SACredentials.from_service_account_info(info, scopes=SCOPES)
    elif sa_path:
        creds = SACredentials.from_service_account_file(sa_path, scopes=SCOPES)
    else:
        creds = _oauth_creds()

    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    return sheets, drive


def _oauth_creds():
    creds = None
    if TOKEN_PATH.exists():
        with open(TOKEN_PATH, "rb") as f:
            try:
                creds = pickle.load(f)
            except Exception:
                creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "wb") as f:
            pickle.dump(creds, f)
    return creds


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------

def get_engine():
    import certifi
    host = os.environ["DB_HOST"]
    port = os.getenv("DB_PORT", "4000")
    user = os.environ["DB_USER"]
    password = os.environ["DB_PASSWORD"]
    name = os.getenv("DB_NAME", "emaus_relevamiento")
    url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}?ssl_ca={certifi.where()}"
    return create_engine(url, pool_pre_ping=True)


# ---------------------------------------------------------------------------
# Drive helpers
# ---------------------------------------------------------------------------

def list_spreadsheets(drive, folder_id: str, name_contains: str) -> List[Dict]:
    """
    Recorre la carpeta raíz recursivamente.
    Las planillas viven en subcarpetas con el nombre del Emaús.
    Retorna lista de {id, name, emaus_nombre} donde emaus_nombre es el nombre
    de la carpeta padre inmediata.
    """
    matches = []
    # folders = [(folder_id, nombre_carpeta_padre)
    folders = [(folder_id, "")]
    while folders:
        current, parent_name = folders.pop()
        page_token = None
        while True:
            resp = drive.files().list(
                q=f"'{current}' in parents and trashed = false",
                fields="nextPageToken, files(id, name, mimeType)",
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
                pageToken=page_token,
                corpora="allDrives",
                pageSize=100,
            ).execute()
            for item in resp.get("files", []):
                if item["mimeType"] == FOLDER_MIME:
                    folders.append((item["id"], item["name"]))
                elif item["mimeType"] == SPREADSHEET_MIME:
                    if name_contains.lower() in item["name"].lower():
                        item["emaus_nombre"] = parent_name
                        matches.append(item)
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
    return matches


# ---------------------------------------------------------------------------
# Sheets helpers
# ---------------------------------------------------------------------------

def execute_with_retry(request, retries=5):
    for attempt in range(retries):
        try:
            return request.execute()
        except HttpError as e:
            if e.resp.status in (429, 500, 503) and attempt < retries - 1:
                wait = 10 * (2 ** attempt)  # 10s, 20s, 40s, 80s
                print(f"      [rate limit / error {e.resp.status}] esperando {wait}s ...")
                time.sleep(wait)
            else:
                raise


def get_sheet_titles(sheets, spreadsheet_id: str) -> List[str]:
    resp = execute_with_retry(
        sheets.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields="sheets(properties(title))",
        )
    )
    return [s["properties"]["title"] for s in resp.get("sheets", [])]


def read_cell(sheets, spreadsheet_id: str, sheet_title: str, cell: str) -> Any:
    """Lee el valor de una celda. Retorna None si la hoja no existe o está vacía."""
    range_ref = f"'{sheet_title}'!{cell}"
    try:
        resp = execute_with_retry(
            sheets.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_ref,
            )
        )
        values = resp.get("values", [])
        return values[0][0] if values and values[0] else None
    except HttpError as e:
        if e.resp.status == 400:
            return None
        raise


def read_range(sheets, spreadsheet_id: str, sheet_title: str, range_a1: str) -> List[List]:
    range_ref = f"'{sheet_title}'!{range_a1}"
    try:
        resp = execute_with_retry(
            sheets.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_ref,
            )
        )
        return resp.get("values", [])
    except HttpError as e:
        if e.resp.status == 400:
            return []
        raise


def set_cell(sheets, spreadsheet_id: str, sheet_title: str, cell: str, value: Any):
    range_ref = f"'{sheet_title}'!{cell}"
    execute_with_retry(
        sheets.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_ref,
            valueInputOption="RAW",
            body={"values": [[value]]},
        )
    )


def reset_completion_to_pending(sheets, spreadsheet_id: str, sheet_title: str):
    """Resetea el bloque de declaración a Pendiente en la hoja indicada."""
    # Layout estándar EE/PI: E4=checkbox, E5=fecha, E6=estado
    # Layout diagonal Talleres/Establecimientos: B1=checkbox, C1=fecha, D1=estado
    diagonal = sheet_title in {"Talleres", "Establecimientos",
                               "Talleres enero-junio 2026", "EstablecimientosModelo"}
    if diagonal:
        set_cell(sheets, spreadsheet_id, sheet_title, "B1", False)
        set_cell(sheets, spreadsheet_id, sheet_title, "C1", "")
        set_cell(sheets, spreadsheet_id, sheet_title, "D1", "Pendiente")
    else:
        set_cell(sheets, spreadsheet_id, sheet_title, "E4", False)
        set_cell(sheets, spreadsheet_id, sheet_title, "E5", "")
        set_cell(sheets, spreadsheet_id, sheet_title, "E6", "Pendiente")


def is_sheet_declared_complete(sheets, spreadsheet_id: str, sheet_title: str) -> bool:
    diagonal = sheet_title in {"Talleres", "Establecimientos",
                               "Talleres enero-junio 2026", "EstablecimientosModelo"}
    if diagonal:
        checkbox = read_cell(sheets, spreadsheet_id, sheet_title, "B1")
        status = read_cell(sheets, spreadsheet_id, sheet_title, "D1")
    else:
        checkbox = read_cell(sheets, spreadsheet_id, sheet_title, "E4")
        status = read_cell(sheets, spreadsheet_id, sheet_title, "E6")

    declared_values = {"completa", "completada", "completada (con advertencias)"}
    if isinstance(checkbox, bool) and checkbox:
        return True
    if str(checkbox).strip().lower() in {"true", "verdadero", "sí", "si", "*"}:
        return True
    if str(status).strip().lower() in declared_values:
        return True
    return False


def count_rows_with_data(sheets, spreadsheet_id: str, sheet_title: str,
                         range_a1: str, min_cols: int = 2) -> int:
    """Cuenta filas que tienen al menos min_cols columnas con datos."""
    values = read_range(sheets, spreadsheet_id, sheet_title, range_a1)
    count = 0
    for row in values:
        filled = sum(1 for cell in row[:min_cols] if str(cell).strip())
        if filled >= min_cols:
            count += 1
    return count


def read_total_asistentes(sheets, spreadsheet_id: str, sheet_title: str) -> int:
    """Lee C16 (total asistentes) de una hoja EE."""
    val = read_cell(sheets, spreadsheet_id, sheet_title, "C16")
    try:
        return int(float(str(val))) if val is not None and str(val).strip() else 0
    except (ValueError, TypeError):
        return 0


# ---------------------------------------------------------------------------
# Validaciones
# ---------------------------------------------------------------------------

def load_validations(yaml_path: Path) -> Dict:
    with open(yaml_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def parse_si_no(value) -> Optional[str]:
    """Normaliza un valor de celda Sí/No a 'Sí', 'No' o None."""
    if value is None or str(value).strip() == "":
        return None
    v = str(value).strip().lower()
    if v in {"sí", "si", "s", "yes", "true", "verdadero", "1", "*"}:
        return "Sí"
    if v in {"no", "n", "false", "0"}:
        return "No"
    return str(value).strip()


def cell_has_value(val) -> bool:
    if val is None:
        return False
    s = str(val).strip()
    return s != "" and s != "0"


def cell_numeric(val) -> float:
    try:
        return float(str(val).strip()) if val is not None and str(val).strip() else 0.0
    except (ValueError, TypeError):
        return 0.0


def read_sheet_fields(sheets, spreadsheet_id: str, sheet_title: str,
                      field_defs: List[Dict]) -> Dict[str, Any]:
    """Lee todos los campos de una hoja en una sola operación batch."""
    cells = [f["cell"] for f in field_defs]
    # Deduplicate preserving order
    unique_cells = list(dict.fromkeys(cells))
    ranges = [f"'{sheet_title}'!{c}" for c in unique_cells]

    try:
        resp = execute_with_retry(
            sheets.spreadsheets().values().batchGet(
                spreadsheetId=spreadsheet_id,
                ranges=ranges,
            )
        )
    except HttpError as e:
        if e.resp.status == 400:
            return {}
        raise

    cell_values: Dict[str, Any] = {}
    for value_range in resp.get("valueRanges", []):
        range_str = value_range.get("range", "")
        # Extract cell reference from "SheetName!C3"
        cell_ref = range_str.split("!")[-1].strip("'") if "!" in range_str else ""
        # Normalize (remove $ signs, uppercase)
        cell_ref = cell_ref.replace("$", "").upper()
        values = value_range.get("values", [])
        cell_values[cell_ref] = values[0][0] if values and values[0] else None

    result = {}
    for field in field_defs:
        name = field["name"]
        cell = field["cell"].upper()
        result[name] = cell_values.get(cell)
    return result


def eval_condition(condition: Dict, field_values: Dict[str, Any]) -> bool:
    """Evalúa una condición simple o compuesta sobre los valores de campos."""
    if "all_of" in condition:
        return all(eval_condition(c, field_values) for c in condition["all_of"])
    if "any_of" in condition:
        return any(eval_condition(c, field_values) for c in condition["any_of"])

    field = condition.get("field")
    val = field_values.get(field) if field else None

    if "equals" in condition:
        return parse_si_no(val) == parse_si_no(condition["equals"]) or str(val) == str(condition["equals"])
    if "not_equals" in condition:
        return not (parse_si_no(val) == parse_si_no(condition["not_equals"]))
    if "is_empty" in condition:
        return not cell_has_value(val)
    if "not_empty" in condition:
        return cell_has_value(val)
    if "greater_than" in condition:
        return cell_numeric(val) > float(condition["greater_than"])
    if "sum_of" in condition:
        total = sum(cell_numeric(field_values.get(f)) for f in condition["sum_of"])
        if "equals_field" in condition:
            return total == cell_numeric(field_values.get(condition["equals_field"]))
        if "equals" in condition:
            return total == float(condition["equals"])
    if "all_unique" in condition:
        vals = [field_values.get(f) for f in condition["all_unique"]]
        nums = [cell_numeric(v) for v in vals if cell_has_value(v)]
        return len(nums) == len(set(nums))
    return False


def eval_requires(requires: Dict, field_values: Dict[str, Any]) -> bool:
    """Evalúa si el conjunto de requisitos se cumple."""
    if "require_all" in requires:
        return all(eval_condition(c, field_values) for c in requires["require_all"])
    if "require_any_of" in requires:
        return any(eval_condition(c, field_values) for c in requires["require_any_of"])
    return True


def validate_sheet(field_values: Dict[str, Any], validations: List[Dict],
                   sheet_id: str) -> List[Dict]:
    """
    Corre las validaciones del YAML sobre los valores de la hoja.
    Retorna lista de errores/warnings encontrados.
    """
    errors = []
    for rule in validations:
        if rule.get("sheet") != sheet_id:
            continue

        # Evaluar condición when (si existe)
        when = rule.get("when")
        if when and not eval_condition(when, field_values):
            continue

        # Evaluar requisitos
        passes = True
        if "require_all" in rule:
            passes = all(eval_condition(c, field_values) for c in rule["require_all"])
        elif "require_any_of" in rule:
            passes = any(eval_condition(c, field_values) for c in rule["require_any_of"])

        if not passes:
            errors.append({
                "validacion_id": rule["id"],
                "severity": rule.get("severity", "error"),
                "mensaje": rule.get("message", rule.get("mensaje", "")),
            })

    return errors


# ---------------------------------------------------------------------------
# Scraping por planilla
# ---------------------------------------------------------------------------

def _parse_completion_from_values(values: List[List], diagonal: bool) -> bool:
    """Parsea si una hoja está declarada completa a partir de valores batchGet."""
    declared_values = {"completa", "completada", "completada (con advertencias)"}
    if diagonal:
        # B1:D1 → una sola fila con [checkbox, fecha, estado]
        row = values[0] if values else []
        checkbox = row[0] if len(row) > 0 else ""
        status = row[2] if len(row) > 2 else ""
    else:
        # E4:E6 → tres filas [[checkbox],[fecha],[estado]]
        checkbox = values[0][0] if values and values[0] else ""
        status = values[2][0] if len(values) > 2 and values[2] else ""

    if isinstance(checkbox, bool) and checkbox:
        return True
    if str(checkbox).strip().lower() in {"true", "verdadero", "sí", "si", "*"}:
        return True
    if str(status).strip().lower() in declared_values:
        return True
    return False


def scrape_spreadsheet(sheets, spreadsheet_id: str, spec: Dict,
                       anio: int, semestre: str, dry_run: bool, apply_reset: bool = False) -> Dict:
    """
    Scrapa una planilla completa con el mínimo de llamadas API posible.
    Usa batchGet para leer completion + C16 de todas las hojas en una sola llamada.
    """
    all_titles = get_sheet_titles(sheets, spreadsheet_id)

    ee_titles = [t for t in all_titles if t not in EXCLUDED_SHEETS]
    has_pi = PI_SHEET_TITLE in all_titles
    # Detectar nombre real de la hoja Talleres (puede ser el nombre estándar o el alternativo)
    talleres_sheet_name = TALLERES_SHEET if TALLERES_SHEET in all_titles else (
        TALLERES_SHEET_ALT if TALLERES_SHEET_ALT in all_titles else None
    )
    has_talleres = talleres_sheet_name is not None
    has_establecimientos = ESTABLECIMIENTOS_SHEET in all_titles

    ee_field_defs = next((s["fields"] for s in spec["sheets"] if s["id"] == "ee"), [])
    pi_field_defs = next((s["fields"] for s in spec["sheets"] if s["id"] == "pi"), [])
    validations = spec.get("validations", [])

    now = datetime.utcnow()
    all_validation_errors: List[Dict] = []

    # --- Batch 1: leer completion + C16 de todos los EE + PI + Talleres + Establecimientos ---
    batch_ranges = []
    range_index: Dict[str, int] = {}

    for title in ee_titles:
        idx = len(batch_ranges)
        range_index[f"ee_completion_{title}"] = idx
        batch_ranges.append(f"'{title}'!E4:E6")

        idx = len(batch_ranges)
        range_index[f"ee_c16_{title}"] = idx
        batch_ranges.append(f"'{title}'!C16")

    if has_pi:
        idx = len(batch_ranges)
        range_index["pi_completion"] = idx
        batch_ranges.append(f"'{PI_SHEET_TITLE}'!E4:E6")

    if has_talleres:
        idx = len(batch_ranges)
        range_index["talleres_completion"] = idx
        batch_ranges.append(f"'{talleres_sheet_name}'!B1:D1")

        idx = len(batch_ranges)
        range_index["talleres_data"] = idx
        batch_ranges.append(f"'{talleres_sheet_name}'!A3:B")

    if has_establecimientos:
        idx = len(batch_ranges)
        range_index["estab_completion"] = idx
        batch_ranges.append(f"'{ESTABLECIMIENTOS_SHEET}'!B1:D1")

        idx = len(batch_ranges)
        range_index["estab_data"] = idx
        batch_ranges.append(f"'{ESTABLECIMIENTOS_SHEET}'!A2:B")

    batch_resp = execute_with_retry(
        sheets.spreadsheets().values().batchGet(
            spreadsheetId=spreadsheet_id,
            ranges=batch_ranges,
        )
    )
    value_ranges = batch_resp.get("valueRanges", [])

    def get_values(key: str) -> List[List]:
        idx = range_index.get(key)
        if idx is None or idx >= len(value_ranges):
            return []
        return value_ranges[idx].get("values", [])

    # --- EE sheets ---
    ee_declarados = 0
    ee_pendientes = 0
    ee_con_errores = 0
    total_asistentes = 0
    ee_field_data: Dict[str, Dict] = {}  # title → field_values (solo hojas declaradas)

    for title in ee_titles:
        completion_vals = get_values(f"ee_completion_{title}")
        declared = _parse_completion_from_values(completion_vals, diagonal=False)

        c16_vals = get_values(f"ee_c16_{title}")
        try:
            asistentes = int(float(c16_vals[0][0])) if c16_vals and c16_vals[0] else 0
        except (ValueError, TypeError):
            asistentes = 0
        total_asistentes += asistentes

        # Leer campos detallados para todos los EE (declarados o no) para poblar relevamiento_ee
        field_values = read_sheet_fields(sheets, spreadsheet_id, title, ee_field_defs)
        ee_field_data[title] = field_values

        if declared:
            errors = validate_sheet(field_values, validations, "ee")

            hard_errors = [e for e in errors if e["severity"] == "error"]
            if hard_errors:
                ee_con_errores += 1
                if not dry_run and apply_reset:
                    reset_completion_to_pending(sheets, spreadsheet_id, title)
                for e in errors:
                    all_validation_errors.append({**e, "hoja_nombre": title, "fecha": now})
            else:
                ee_declarados += 1
                for e in [w for w in errors if w["severity"] == "warning"]:
                    all_validation_errors.append({**e, "hoja_nombre": title, "fecha": now})
        else:
            ee_pendientes += 1

    # --- PI ---
    pi_completa = False
    pi_con_errores = False

    if has_pi:
        declared = _parse_completion_from_values(get_values("pi_completion"), diagonal=False)
        if declared:
            field_values = read_sheet_fields(sheets, spreadsheet_id, PI_SHEET_TITLE, pi_field_defs)
            errors = validate_sheet(field_values, validations, "pi")
            hard_errors = [e for e in errors if e["severity"] == "error"]
            if hard_errors:
                pi_con_errores = True
                if not dry_run and apply_reset:
                    reset_completion_to_pending(sheets, spreadsheet_id, PI_SHEET_TITLE)
                for e in errors:
                    all_validation_errors.append({**e, "hoja_nombre": PI_SHEET_TITLE, "fecha": now})
            else:
                pi_completa = True
                for e in [w for w in errors if w["severity"] == "warning"]:
                    all_validation_errors.append({**e, "hoja_nombre": PI_SHEET_TITLE, "fecha": now})

    # --- Talleres / Establecimientos ---
    talleres_completo = has_talleres and _parse_completion_from_values(
        get_values("talleres_completion"), diagonal=True)
    establecimientos_completo = has_establecimientos and _parse_completion_from_values(
        get_values("estab_completion"), diagonal=True)

    def count_filled_rows(values: List[List], min_cols: int = 2) -> int:
        return sum(
            1 for row in values
            if sum(1 for cell in row[:min_cols] if str(cell).strip()) >= min_cols
        )

    cantidad_talleres = count_filled_rows(get_values("talleres_data")) if has_talleres else 0
    cantidad_establecimientos = count_filled_rows(get_values("estab_data")) if has_establecimientos else 0

    return {
        "ee_count": len(ee_titles),
        "ee_declarados_completos": ee_declarados,
        "ee_pendientes": ee_pendientes,
        "ee_con_errores": ee_con_errores,
        "pi_existe": has_pi,
        "pi_completa": pi_completa,
        "pi_con_errores": pi_con_errores,
        "talleres_completo": talleres_completo,
        "establecimientos_completo": establecimientos_completo,
        "total_asistentes_ee": total_asistentes,
        "cantidad_talleres": cantidad_talleres,
        "cantidad_establecimientos": cantidad_establecimientos,
        "ultimo_sync": now,
        "validation_errors": all_validation_errors,
        "ee_field_data": ee_field_data,
    }


# ---------------------------------------------------------------------------
# Mapeo de campos de planilla → columnas de relevamiento_ee
# ---------------------------------------------------------------------------

# Mapeo campo YAML → (eje, nombre acción) para relevamiento_ee_accion
_ACCION_MAP = {
    "Accion_PI_Pastoral":        ("Primera infancia",                    "Pastoral PI"),
    "Accion_PI_Capacitaciones":  ("Primera infancia",                    "Capacitaciones, talleres y encuentros"),
    "Accion_PI_EspPI":           ("Primera infancia",                    "Espacios de Primera Infancia"),
    "Accion_PI_EstimTemprana":   ("Primera infancia",                    "Estimulación temprana"),
    "Accion_ATE_BF":             ("Apoyo a las trayectorias educativas", "Becas Familiares"),
    "Accion_ATE_ApoyoEscolar":   ("Apoyo a las trayectorias educativas", "Apoyo escolar"),
    "Accion_ATE_BTU":            ("Apoyo a las trayectorias educativas", "Becas Terciarias y universitarias"),
    "Accion_ATE_AlfabInicial":   ("Apoyo a las trayectorias educativas", "Alfabetización inicial"),
    "Accion_ATE_DALE":           ("Apoyo a las trayectorias educativas", "Propuesta DALE"),
    "Accion_ATE_ActLectoEscOral":("Apoyo a las trayectorias educativas", "Actividades de lectoescritura y oralidad"),
    "Accion_ATE_RinconLectura":  ("Apoyo a las trayectorias educativas", "Rincón de lectura"),
    "Accion_ATE_AlfabAdultos":   ("Apoyo a las trayectorias educativas", "Alfabetización de adultos"),
    "Accion_ATE_PromSE":         ("Apoyo a las trayectorias educativas", "Promotores socio-educativos"),
    "Accion_IC_Itinerancia":     ("Integración comunitaria",             "Itinerancia"),
    "Accion_IC_Mochileros":      ("Integración comunitaria",             "Mochileros"),
    "Accion_IC_Ludoteca":        ("Integración comunitaria",             "Ludoteca"),
    "Accion_IC_ActCultRecre":    ("Integración comunitaria",             "Actividades culturales y recreativas"),
    "Accion_IC_Desarrollo":      ("Integración comunitaria",             "Desarrollo habilidades duras y blandas"),
    "Accion_IC_HabTrabajo":      ("Integración comunitaria",             "Habilidades para el mundo del trabajo"),
    "Accion_IC_TalleresMuj":     ("Integración comunitaria",             "Talleres para mujeres"),
    "Accion_IC_Adolescentes":    ("Integración comunitaria",             "Propuestas para adolescentes"),
    "Accion_IC_TallOficio":      ("Integración comunitaria",             "Talleres de oficio"),
    "Accion_NT_CapacTall":       ("Nuevas tecnologías",                  "Capacitaciones y talleres"),
    "Accion_NT_EquiInfInt":      ("Nuevas tecnologías",                  "Equipamiento informático e internet"),
    "Accion_NT_Tramites":        ("Nuevas tecnologías",                  "Trámites del estado (ANSES, AUH, CUD, etc)"),
    "Accion_NT_AccesoDig":       ("Nuevas tecnologías",                  "Acceso digital comunitario"),
    "Accion_SI_Deportes":        ("Salud integral",                      "Deportes"),
    "Accion_SI_Alimentacion":    ("Salud integral",                      "Alimentación saludable"),
    "Accion_SI_Meriendas":       ("Salud integral",                      "Meriendas"),
    "Accion_SI_ControlesMed":    ("Salud integral",                      "Controles médicos"),
    "Accion_SI_CapacitTall":     ("Salud integral",                      "Capacitaciones, talleres y encuentros"),
    "Accion_SI_Huertas":         ("Salud integral",                      "Huertas comunitarias"),
}

_EE_FIELD_MAP = {
    "Asistentes_0_6":               "asistentes_0_6",
    "Asistentes_7_14":              "asistentes_7_14",
    "Asistentes_15_24":             "asistentes_15_24",
    "Asistentes_25_34":             "asistentes_25_35",  # nombre distinto en DB
    "Asistentes_35_50":             "asistentes_35_50",
    "Asistentes_Mas50":             "asistentes_mas_50",
    "GM_RC_Nro":                    "grupo_motor_cantidad",
    "GM_RC_Freq":                   "grupo_motor_frecuencia",
    "AyJ_Nro":                      "adolescentes_referentes",
    "AyJ_Freq":                     "adolescentes_frecuencia",
    "Itinerancia_Activ":            "itinerancia_realizo",
    "Itinerancia_Freq":             "itinerancia_frecuencia",
    "ApEscolar_Nro_Primaria":       "apoyo_primario_ninos",
    "ApEscolar_Nro_Secundaria":     "apoyo_secundario_adolescentes",
    "Alfabetizacion_Nro":           "alfa_total",
    "Alfabetizacion_6_9":           "alfa_6_9",
    "Alfabetizacion_10_14":         "alfa_10_14",
    "Alfabetizacion_15_24":         "alfa_15_24",
    "Alfabetizacion_25mas":         "alfa_25_mas",
    "Alfabetizacion_CantAlfabetizadores": "alfa_alfabetizadores",
    "Alfabetizacion_Freq":          "alfa_frecuencia",
    "DALE_Nro":                     "dale_total",
    "DALE_6_9":                     "dale_6_9",
    "DALE_10_14":                   "dale_10_14",
    "DALE_15_24":                   "dale_15_24",
    "DALE_25mas":                   "dale_25_mas",
    "DALE_EducadoresDale":          "dale_educadores",
    "DALE_Freq":                    "dale_frecuencia_dias",
    "BTU_regulares":                "btu_regulares",
}

_ITINERANCIA_ROLES = [
    ("Itinerancia_Rol1", "Itinerancia_Rol1_Cant"),
    ("Itinerancia_Rol2", "Itinerancia_Rol2_Cant"),
    ("Itinerancia_Rol3", "Itinerancia_Rol3_Cant"),
    ("Itinerancia_Rol4", "Itinerancia_Rol4_Cant"),
]


def _to_int(val) -> Optional[int]:
    try:
        return int(float(str(val).strip())) if val not in (None, "", "None") else None
    except (ValueError, TypeError):
        return None


def _to_bool(val) -> Optional[bool]:
    if val is None or val == "":
        return None
    s = str(val).strip().lower()
    if s in ("true", "verdadero", "sí", "si", "1"):
        return True
    if s in ("false", "falso", "no", "0"):
        return False
    return None


def _normalize_ee_name(name: str) -> str:
    """Normaliza nombre de EE para comparación: quita prefijo 'EE ', espacios y pasa a minúsculas."""
    s = name.strip()
    if s.upper().startswith("EE "):
        s = s[3:].strip()
    return s.lower()


def upsert_relevamiento_ee(engine, emaus_id: int, anio: int, semestre: str,
                           ee_field_data: Dict[str, Dict]) -> None:
    """Upserta datos detallados de cada EE en relevamiento_ee y relevamiento_ee_itinerancia_rol."""
    if not ee_field_data:
        return

    with engine.begin() as conn:
        # Buscar el relevamiento para este emaus/anio/semestre
        rel = conn.execute(
            text("SELECT id FROM relevamiento WHERE emaus_id=:eid AND anio=:a AND semestre=:s LIMIT 1"),
            {"eid": emaus_id, "a": anio, "s": semestre},
        ).fetchone()
        if not rel:
            return  # no hay relevamiento abierto para este período, nada que hacer
        relevamiento_id = rel[0]

        # Precargar mapa nombre → id (exacto y normalizado) para este emaus
        ee_rows = conn.execute(
            text("SELECT id, nombre, nombre_hoja FROM espacio_educativo "
                 "WHERE emaus_id = :eid AND activo = TRUE"),
            {"eid": emaus_id},
        ).fetchall()
        ee_by_nombre_exacto = {r[1]: r[0] for r in ee_rows}
        ee_by_nombre_hoja   = {r[2]: r[0] for r in ee_rows if r[2]}
        ee_by_normalizado   = {_normalize_ee_name(r[1]): r[0] for r in ee_rows}

        for title, fv in ee_field_data.items():
            nombre_c4 = str(fv.get("NombreEE") or "").strip()
            # Prioridad: nombre_hoja exacto > C4 exacto > C4 normalizado > título normalizado
            ee_id = (
                ee_by_nombre_hoja.get(title)
                or (nombre_c4 and ee_by_nombre_exacto.get(nombre_c4))
                or (nombre_c4 and ee_by_normalizado.get(_normalize_ee_name(nombre_c4)))
                or ee_by_normalizado.get(_normalize_ee_name(title))
            )
            if not ee_id:
                print(f"      [warn] EE no encontrado: hoja='{title}' C4='{nombre_c4}' (emaus_id={emaus_id})")
                continue

            # Construir dict de columnas para relevamiento_ee
            row: Dict[str, Any] = {
                "relevamiento_id": relevamiento_id,
                "espacio_educativo_id": ee_id,
            }
            for yaml_name, col in _EE_FIELD_MAP.items():
                raw = fv.get(yaml_name)
                if col == "itinerancia_realizo":
                    row[col] = _to_bool(raw)
                elif col in ("grupo_motor_frecuencia", "adolescentes_frecuencia",
                             "itinerancia_frecuencia", "alfa_frecuencia", "dale_frecuencia_dias"):
                    row[col] = str(raw).strip()[:50] if raw not in (None, "") else None
                else:
                    row[col] = _to_int(raw)

            cols = list(row.keys())
            placeholders = ", ".join(f":{c}" for c in cols)
            updates = ", ".join(f"{c} = VALUES({c})" for c in cols if c not in ("relevamiento_id", "espacio_educativo_id"))
            conn.execute(
                text(f"""
                    INSERT INTO relevamiento_ee ({', '.join(cols)})
                    VALUES ({placeholders})
                    ON DUPLICATE KEY UPDATE {updates}
                """),
                row,
            )
            ree_id = conn.execute(
                text("SELECT id FROM relevamiento_ee WHERE relevamiento_id=:rid AND espacio_educativo_id=:eid LIMIT 1"),
                {"rid": relevamiento_id, "eid": ee_id},
            ).fetchone()[0]

            # Upsert roles de itinerancia
            for rol_key, cant_key in _ITINERANCIA_ROLES:
                rol_val = fv.get(rol_key)
                cant_val = _to_int(fv.get(cant_key))
                if not rol_val or cant_val is None:
                    continue
                conn.execute(text("""
                    INSERT INTO relevamiento_ee_itinerancia_rol
                        (relevamiento_ee_id, rol, cantidad)
                    VALUES (:ree_id, :rol, :cant)
                    ON DUPLICATE KEY UPDATE cantidad = VALUES(cantidad)
                """), {"ree_id": ree_id, "rol": str(rol_val)[:50], "cant": cant_val})

            # Upsert acciones (relevamiento_ee_accion)
            for yaml_name, (eje, accion) in _ACCION_MAP.items():
                raw = fv.get(yaml_name)
                if raw is None:
                    continue
                tiene = _to_bool(raw)
                if tiene is None:
                    continue
                conn.execute(text("""
                    INSERT INTO relevamiento_ee_accion
                        (relevamiento_ee_id, eje, accion, tiene)
                    VALUES (:ree_id, :eje, :accion, :tiene)
                    ON DUPLICATE KEY UPDATE tiene = VALUES(tiene)
                """), {"ree_id": ree_id, "eje": eje, "accion": accion, "tiene": tiene})


# ---------------------------------------------------------------------------
# Persistencia en TiDB
# ---------------------------------------------------------------------------

def upsert_control(engine, emaus_id: int, anio: int, semestre: str, metrics: Dict):
    errors = metrics.pop("validation_errors", [])
    ee_field_data = metrics.pop("ee_field_data", {})
    metrics.setdefault("btu_actual", None)
    metrics.setdefault("bf_actual", None)

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO control_relevamiento
                (emaus_id, anio, semestre,
                 ee_count, ee_declarados_completos, ee_pendientes, ee_con_errores,
                 pi_existe, pi_completa, pi_con_errores,
                 talleres_completo, establecimientos_completo,
                 total_asistentes_ee, cantidad_talleres, cantidad_establecimientos,
                 btu_actual, bf_actual, ultimo_sync)
            VALUES
                (:emaus_id, :anio, :semestre,
                 :ee_count, :ee_declarados_completos, :ee_pendientes, :ee_con_errores,
                 :pi_existe, :pi_completa, :pi_con_errores,
                 :talleres_completo, :establecimientos_completo,
                 :total_asistentes_ee, :cantidad_talleres, :cantidad_establecimientos,
                 :btu_actual, :bf_actual, :ultimo_sync)
            ON DUPLICATE KEY UPDATE
                ee_count = VALUES(ee_count),
                ee_declarados_completos = VALUES(ee_declarados_completos),
                ee_pendientes = VALUES(ee_pendientes),
                ee_con_errores = VALUES(ee_con_errores),
                pi_existe = VALUES(pi_existe),
                pi_completa = VALUES(pi_completa),
                pi_con_errores = VALUES(pi_con_errores),
                talleres_completo = VALUES(talleres_completo),
                establecimientos_completo = VALUES(establecimientos_completo),
                total_asistentes_ee = VALUES(total_asistentes_ee),
                cantidad_talleres = VALUES(cantidad_talleres),
                cantidad_establecimientos = VALUES(cantidad_establecimientos),
                btu_actual = COALESCE(VALUES(btu_actual), btu_actual),
                bf_actual = COALESCE(VALUES(bf_actual), bf_actual),
                ultimo_sync = VALUES(ultimo_sync)
        """), {**metrics, "emaus_id": emaus_id, "anio": anio, "semestre": semestre})

        # Marcar errores anteriores como resueltos
        conn.execute(text("""
            UPDATE control_validacion_detalle
            SET resuelto = TRUE
            WHERE emaus_id = :emaus_id AND anio = :anio AND semestre = :semestre
              AND resuelto = FALSE
        """), {"emaus_id": emaus_id, "anio": anio, "semestre": semestre})

        # Insertar errores nuevos
        if errors:
            conn.execute(
                text("""
                    INSERT INTO control_validacion_detalle
                        (emaus_id, anio, semestre, hoja_nombre, validacion_id, severity, mensaje, fecha)
                    VALUES
                        (:emaus_id, :anio, :semestre, :hoja_nombre, :validacion_id, :severity, :mensaje, :fecha)
                """),
                [{"emaus_id": emaus_id, "anio": anio, "semestre": semestre, **e} for e in errors],
            )

        # Crear aprobacion en estado pendiente si no existe
        conn.execute(text("""
            INSERT IGNORE INTO control_aprobacion (emaus_id, anio, semestre, estado)
            VALUES (:emaus_id, :anio, :semestre, 'pendiente')
        """), {"emaus_id": emaus_id, "anio": anio, "semestre": semestre})

        # Guardar spreadsheet_id en emaus si no estaba
        conn.execute(text("""
            UPDATE emaus SET spreadsheet_id = :sid
            WHERE id = :emaus_id AND (spreadsheet_id IS NULL OR spreadsheet_id = '')
        """), {"sid": metrics.get("_spreadsheet_id", ""), "emaus_id": emaus_id})

    # Upsert datos detallados por EE (fuera de la transacción principal para no mezclar errores)
    if ee_field_data:
        upsert_relevamiento_ee(engine, emaus_id, anio, semestre, ee_field_data)


_EMAUS_NAME_FIXES = {
    "San Francisco (Las Varillas)": "Las Varillas",
    "San Roque": "Roque Saénz Peña",
}

_BTU_EMAUS_MAP = {
    "San Francisco (Las Varillas)": "Las Varillas",
    "San Roque": "Roque Saénz Peña",
}


def leer_btu_planilla(sheets_svc, spreadsheet_id: str) -> Dict[str, int]:
    """Lee la planilla BTU y retorna {nombre_emaus_normalizado: btu_actual}."""
    if not spreadsheet_id:
        return {}
    try:
        resp = sheets_svc.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range="A1:C60",
            valueRenderOption="UNFORMATTED_VALUE",
        ).execute()
    except Exception as e:
        print(f"  [warn] No se pudo leer planilla BTU: {e}")
        return {}

    result = {}
    for row in resp.get("values", []):
        if len(row) < 3:
            continue
        nombre = str(row[1]).strip()
        if not nombre or nombre == "DIOCESIS":
            continue
        try:
            cant = int(float(str(row[2])))
        except (ValueError, TypeError):
            continue
        nombre_real = _BTU_EMAUS_MAP.get(nombre, _EMAUS_NAME_FIXES.get(nombre, nombre))
        result[nombre_real] = cant
    return result


def leer_bf_planilla(sheets_svc, spreadsheet_id: str) -> Dict[str, int]:
    """Lee la planilla BF y retorna {nombre_emaus: bf_actual}. Col A = nombre, Col B = cantidad."""
    if not spreadsheet_id:
        return {}
    try:
        resp = sheets_svc.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range="A1:B60",
            valueRenderOption="UNFORMATTED_VALUE",
        ).execute()
    except Exception as e:
        print(f"  [warn] No se pudo leer planilla BF: {e}")
        return {}

    result = {}
    for row in resp.get("values", []):
        if len(row) < 2:
            continue
        nombre = str(row[0]).strip()
        if not nombre:
            continue
        try:
            cant = int(float(str(row[1])))
        except (ValueError, TypeError):
            continue
        nombre_real = _EMAUS_NAME_FIXES.get(nombre, nombre)
        result[nombre_real] = cant
    return result


def find_emaus_id(engine, nombre: str) -> Optional[int]:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id FROM emaus WHERE nombre = :nombre AND activo = TRUE LIMIT 1"),
            {"nombre": nombre},
        ).fetchone()
    return row[0] if row else None


def get_all_emaus(engine) -> List[Dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, nombre, spreadsheet_id FROM emaus WHERE activo = TRUE ORDER BY nombre")
        ).fetchall()
    return [{"id": r[0], "nombre": r[1], "spreadsheet_id": r[2]} for r in rows]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--anio", type=int, default=ANIO_DEFAULT)
    parser.add_argument("--semestre", default=SEMESTRE_DEFAULT)
    parser.add_argument("--folder-id", required=True, help="ID de la carpeta raíz en Google Drive")
    parser.add_argument("--emaus-id", type=int, default=None, help="Procesar solo este Emaús")
    parser.add_argument("--dry-run", action="store_true", help="No modificar Sheets ni DB")
    parser.add_argument("--apply-reset", action="store_true",
                        help="Resetear a Pendiente las hojas con errores (por defecto NO resetea)")
    args = parser.parse_args()

    spec = load_validations(YAML_PATH)
    sheets_svc, drive_svc = build_services()
    engine = get_engine()

    print(f"Buscando planillas en carpeta {args.folder_id} ...")
    all_spreadsheets = list_spreadsheets(drive_svc, args.folder_id, NAME_CONTAINS)
    print(f"  Planillas encontradas: {len(all_spreadsheets)}")

    emaus_list = get_all_emaus(engine)
    emaus_by_name = {e["nombre"]: e for e in emaus_list}
    emaus_by_id = {e["id"]: e for e in emaus_list}

    # Construir mapa emaus_nombre → spreadsheet_id
    # emaus_nombre viene del nombre de la carpeta padre de cada planilla
    sheet_map: Dict[str, str] = {}
    for item in all_spreadsheets:
        emaus_name = item.get("emaus_nombre", "").strip()
        if emaus_name:
            sheet_map[emaus_name] = item["id"]
            print(f"    Planilla: {emaus_name} → {item['id'][:20]}...")


    # Leer BTU y BF una sola vez antes del loop
    btu_spreadsheet_id = os.getenv("BTU_SPREADSHEET_ID", "")
    btu_map: Dict[str, int] = leer_btu_planilla(sheets_svc, btu_spreadsheet_id)
    if btu_map:
        print(f"  BTU leídos para {len(btu_map)} Emaús")
    else:
        print(f"  [warn] No se leyeron datos BTU (BTU_SPREADSHEET_ID={btu_spreadsheet_id!r})")

    bf_spreadsheet_id = os.getenv("BF_SPREADSHEET_ID", "")
    bf_map: Dict[str, int] = leer_bf_planilla(sheets_svc, bf_spreadsheet_id)
    if bf_map:
        print(f"  BF leídos para {len(bf_map)} Emaús")
    else:
        print(f"  [warn] No se leyeron datos BF (BF_SPREADSHEET_ID={bf_spreadsheet_id!r})")

    ok = err = skip = 0

    for emaus in emaus_list:
        if args.emaus_id and emaus["id"] != args.emaus_id:
            continue

        spreadsheet_id = emaus.get("spreadsheet_id") or sheet_map.get(emaus["nombre"])
        if not spreadsheet_id:
            print(f"  [SKIP] {emaus['nombre']} — sin planilla asociada")
            skip += 1
            continue

        print(f"  [{emaus['id']}] {emaus['nombre']} ...", end=" ", flush=True)
        try:
            metrics = scrape_spreadsheet(
                sheets_svc, spreadsheet_id, spec,
                args.anio, args.semestre, args.dry_run,
                apply_reset=args.apply_reset,
            )
            metrics["_spreadsheet_id"] = spreadsheet_id
            metrics["btu_actual"] = btu_map.get(emaus["nombre"])
            metrics["bf_actual"]  = bf_map.get(emaus["nombre"])
            n_err = len([e for e in metrics["validation_errors"] if e["severity"] == "error"])
            n_warn = len([e for e in metrics["validation_errors"] if e["severity"] == "warning"])

            if not args.dry_run:
                upsert_control(engine, emaus["id"], args.anio, args.semestre, metrics)

            print(f"OK — EE {metrics['ee_declarados_completos']}/{metrics['ee_count']}, "
                  f"errores={n_err}, warnings={n_warn}")
            ok += 1
        except Exception as exc:
            print(f"ERROR — {exc}")
            err += 1
            time.sleep(5)
        else:
            time.sleep(1.5)  # pausa entre planillas para respetar quota

    print(f"\nResumen: {ok} OK, {err} errores, {skip} sin planilla")
    if args.dry_run:
        print("(dry-run: no se modificó nada)")


def _sync_estado_write(engine, sync_id: int, estado: str, ok: int, err: int, skip: int, detalle: str = None):
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE sync_estado
            SET estado=:estado, finalizado_en=:fin, ok_count=:ok, err_count=:err,
                skip_count=:skip, detalle=:det
            WHERE id=:sid
        """), {"estado": estado, "fin": datetime.utcnow(), "ok": ok, "err": err,
               "skip": skip, "det": detalle, "sid": sync_id})
        conn.commit()


def run_sync(folder_id: str, anio: int = ANIO_DEFAULT, semestre: str = SEMESTRE_DEFAULT,
             emaus_id: int = None, dry_run: bool = False, apply_reset: bool = False) -> dict:
    """
    Entrada callable para Lambda/router — misma lógica que main() pero sin argparse.
    Retorna {"ok": int, "err": int, "skip": int}.
    """
    spec = load_validations(YAML_PATH)
    sheets_svc, drive_svc = build_services()
    engine = get_engine()

    # Registrar inicio del sync
    sync_id = None
    if not dry_run:
        with engine.connect() as conn:
            res = conn.execute(text(
                "INSERT INTO sync_estado (iniciado_en, estado) VALUES (:t, 'corriendo')"
            ), {"t": datetime.utcnow()})
            conn.commit()
            sync_id = res.lastrowid

    all_spreadsheets = list_spreadsheets(drive_svc, folder_id, NAME_CONTAINS)
    emaus_list = get_all_emaus(engine)
    sheet_map: Dict[str, str] = {
        item.get("emaus_nombre", "").strip(): item["id"]
        for item in all_spreadsheets
        if item.get("emaus_nombre", "").strip()
    }

    # Leer datos BTU y BF de planillas externas (una sola vez para todo el sync)
    btu_spreadsheet_id = os.getenv("BTU_SPREADSHEET_ID", "")
    btu_map: Dict[str, int] = leer_btu_planilla(sheets_svc, btu_spreadsheet_id)
    if btu_map:
        print(f"  BTU leídos para {len(btu_map)} Emaús")
    else:
        print(f"  [warn] No se leyeron datos BTU (BTU_SPREADSHEET_ID={btu_spreadsheet_id!r})")

    bf_spreadsheet_id = os.getenv("BF_SPREADSHEET_ID", "")
    bf_map: Dict[str, int] = leer_bf_planilla(sheets_svc, bf_spreadsheet_id)
    if bf_map:
        print(f"  BF leídos para {len(bf_map)} Emaús")
    else:
        print(f"  [warn] No se leyeron datos BF (BF_SPREADSHEET_ID={bf_spreadsheet_id!r})")

    ok = err = skip = 0
    errores_detalle = []

    try:
        for emaus in emaus_list:
            if emaus_id and emaus["id"] != emaus_id:
                continue

            spreadsheet_id = emaus.get("spreadsheet_id") or sheet_map.get(emaus["nombre"])
            if not spreadsheet_id:
                skip += 1
                continue

            try:
                metrics = scrape_spreadsheet(
                    sheets_svc, spreadsheet_id, spec,
                    anio, semestre, dry_run,
                    apply_reset=apply_reset,
                )
                metrics["_spreadsheet_id"] = spreadsheet_id
                metrics["btu_actual"] = btu_map.get(emaus["nombre"])
                metrics["bf_actual"] = bf_map.get(emaus["nombre"])
                if not dry_run:
                    upsert_control(engine, emaus["id"], anio, semestre, metrics)
                ok += 1
            except Exception as exc:
                errores_detalle.append(f"{emaus['nombre']}: {exc}")
                err += 1
                time.sleep(5)
            else:
                time.sleep(1.5)

        if sync_id:
            _sync_estado_write(engine, sync_id, "ok", ok, err, skip,
                               "\n".join(errores_detalle) or None)
    except Exception as exc:
        if sync_id:
            _sync_estado_write(engine, sync_id, "error", ok, err, skip, str(exc))
        raise

    return {"ok": ok, "err": err, "skip": skip}


if __name__ == "__main__":
    main()
