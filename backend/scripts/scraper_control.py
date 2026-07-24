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
                fields="nextPageToken, files(id, name, mimeType, modifiedTime)",
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
        batch_ranges.append(f"'{ESTABLECIMIENTOS_SHEET}'!A3:K")

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
    pi_field_data = None

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
                # Si está marcada completa pero las primeras preguntas sustantivas
                # (AniosPI, Capacitadora, Comunidad1) vienen todas vacías, se
                # considera que ese Emaús no tiene Primera Infancia activa y no
                # se crea el registro pastoral_pi.
                primeras_respuestas = (
                    str(field_values.get("AniosPI") or "").strip(),
                    str(field_values.get("Capacitadora") or "").strip(),
                    str(field_values.get("Comunidad1") or "").strip(),
                )
                if any(primeras_respuestas):
                    pi_field_data = field_values
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
    estab_rows_data = get_values("estab_data") if has_establecimientos else []
    cantidad_establecimientos = count_filled_rows(estab_rows_data)

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
        "pi_field_data": pi_field_data,
        "estab_rows_data": estab_rows_data,
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

# Zonas: columna planilla → nombre en ee_zona.zona
_ZONAS = [
    ("EE_Zona_Urbana",        "Urbana"),
    ("EE_Zona_Periferica",    "Periférica"),
    ("EE_Zona_Rural",         "Rural"),
    ("EE_Zona_Inundable",     "Inundable"),
    ("EE_Zona_DifTransporte", "Dificultad de transporte"),
]

# Ambientes: columna planilla → nombre en ee_ambiente.ambiente
_AMBIENTES = [
    ("EE_Comedor",           "Comedor"),
    ("EE_Despensa",          "Despensa"),
    ("EE_EspacioRecreacion", "Espacio de recreación"),
    ("EE_Banio",             "Baño"),
    ("EE_Cocina",            "Cocina"),
]

# Ambientes con cantidad: columna tiene → columna cantidad → nombre
_AMBIENTES_CON_CANTIDAD = [
    ("EE_Banio", "EE_Banio_Nro", "Baño"),
]

# Servicios: columna planilla → nombre en ee_servicio.servicio
_SERVICIOS = [
    ("EE_Agua_Corriente",       "Agua corriente"),
    ("EE_Agua_AljibeReservorio","Aljibe/Reservorio"),
    ("EE_Agua_FueraDelTerreno", "Agua fuera del terreno"),
    ("EE_Luz_Red",              "Luz de red"),
    ("EE_Cloacas",              "Cloacas"),
    ("EE_Residuos",             "Recolección de residuos"),
    ("EE_SenalMovil",           "Señal móvil"),
    ("EE_Internet_Prov",        "Internet provisto"),
    ("EE_Combustible_Cocina",   "Combustible cocina"),
]

# Equipos cocina: columna planilla → nombre en ee_equipo_cocina.equipo
_EQUIPOS_COCINA = [
    ("EE_Cocina_Industrial",  "Cocina industrial"),
    ("EE_Cocina_Familiar",    "Cocina familiar"),
    ("EE_Cocina_Mechero",     "Mechero"),
    ("EE_Cocina_HeladeraInd", "Heladera industrial"),
    ("EE_Cocina_HeladeraFam", "Heladera familiar"),
    ("EE_Cocina_FreezerInd",  "Freezer industrial"),
    ("EE_Cocina_FreezerFam",  "Freezer familiar"),
]

# Equipos informáticos: columna planilla → nombre en ee_equipo_informatico.equipo
_EQUIPOS_INFORMATICO_COLS = [
    ("EquipInformatico_PCAllinOne",  "PC All-in-One"),
    ("EquipInformatico_PCEscritorio","PC escritorio"),
    ("EquipInformatico_Notebook",    "Notebook"),
    ("EquipInformatico_Tablet",      "Tablet"),
    ("EquipInformatico_Impresora",   "Impresora"),
    ("EquipInformatico_Multifuncion","Multifunción"),
    ("EquipInformatico_MonitorPlano","Monitor plano"),
    ("EquipInformatico_MonitorTubo", "Monitor de tubo"),
]

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
    "BF_Nro_ApEscolar":            "bf_apoyo_escolar",
    "BF_Nro_Inicial":              "bf_nivel_inicial",
    "BF_Nro_Primaria":             "bf_primaria",
    "BF_Nro_Secundaria":           "bf_secundaria",
    "BF_Nro_Asignaciones":         "bf_asignaciones",
    "BF_Nro_Discapacidad":         "bf_discapacidad",
    "BF_Nro_Discapacidad_CUD":     "bf_cud",
    "BTU_egresados":               "btu_egresados",
    "BTU_abandono":                "btu_abandonaron",
    "ApEscolar_Freq_Primaria":     "apoyo_primario_frecuencia",
    "ApEscolar_Freq_Secundaria":   "apoyo_secundario_frecuencia",
    "ApEscolar_Contenido_Prim_May":"apoyo_primario_contenido_principal",
    "ApEscolar_Contenido_Sec_May": "apoyo_secundario_contenido_principal",
    "AlfabDig_NT_AccesoInternet":       "internet_acceso",
    "AlfabDig_NT_AccesoInternet_Falta": "internet_falta_motivo",
    "AlfabDig_NT_Internet_Uso":         "internet_uso_social",
    "AlfabDig_NT_Internet_Estudio":     "internet_uso_estudio",
    "AlfabDig_NT_Formacion":            "jornadas_formacion_digital",
    "Articula_InstNivelSuperior":         "articula_nivel_superior",
    "Articula_InstNivelSuperior_Cuantas": "nivel_superior_cantidad",
}

# Tipos de columnas de relevamiento_ee (el resto se trata como int)
_EE_BOOL_COLS = {
    "itinerancia_realizo", "internet_acceso", "internet_uso_social",
    "internet_uso_estudio", "jornadas_formacion_digital", "articula_nivel_superior",
}
_EE_STR50_COLS = {
    "grupo_motor_frecuencia", "adolescentes_frecuencia", "itinerancia_frecuencia",
    "alfa_frecuencia", "dale_frecuencia_dias",
    "apoyo_primario_frecuencia", "apoyo_secundario_frecuencia",
}
_EE_STR200_COLS = {
    "internet_falta_motivo",
    "apoyo_primario_contenido_principal", "apoyo_secundario_contenido_principal",
}

_ITINERANCIA_ROLES = [
    ("Itinerancia_Rol1", "Itinerancia_Rol1_Cant"),
    ("Itinerancia_Rol2", "Itinerancia_Rol2_Cant"),
    ("Itinerancia_Rol3", "Itinerancia_Rol3_Cant"),
    ("Itinerancia_Rol4", "Itinerancia_Rol4_Cant"),
]

# Ranking preocupaciones de adolescentes y jóvenes → relevamiento_ee_preocupacion_joven
_AYJ_RANKS = [
    ("AyJ_rank_suicidio",        "Suicidio"),
    ("AyJ_rank_faltaproyecto",   "Falta de proyecto de vida"),
    ("AyJ_rank_consumo",         "Consumo problemático"),
    ("AyJ_rank_apuestas",        "Apuestas online"),
    ("AyJ_rank_saludmental",     "Salud mental"),
    ("AyJ_rank_violencia",       "Violencia"),
    ("AyJ_rank_violenciadigital","Violencia digital"),
    ("AyJ_rank_desvinculacion",  "Desvinculación educativa"),
]

# Motivos de abandono BTU (si/no) → relevamiento_ee_btu_abandono_motivo
_BTU_ABANDONO_MOTIVOS = [
    ("BTU_abandono_accesoboletoestudiantil", "Acceso al boleto estudiantil"),
    ("BTU_abandono_accesotranspor",          "Acceso al transporte"),
    ("BTU_abandono_cambiodomic",             "Cambio de domicilio"),
    ("BTU_abandono_costotransporte",         "Costo del transporte"),
    ("BTU_abandono_faltatiempo",             "Falta de tiempo"),
    ("BTU_abandono_horarios",                "Horarios"),
]

# Prioridades de infraestructura (si/no) → relevamiento_ee_necesidad_infra
_PRIORIDADES_INFRA = [
    ("Prioridad_Agua",            "Agua"),
    ("Prioridad_Arreglos",        "Arreglos generales"),
    ("Prioridad_Banio",           "Baño"),
    ("Prioridad_Climatizacion",   "Climatización"),
    ("Prioridad_Construccion",    "Construcción"),
    ("Prioridad_Electricidad",    "Electricidad"),
    ("Prioridad_Gas",             "Gas"),
    ("Prioridad_PinturaExterior", "Pintura exterior"),
    ("Prioridad_PinturaInterior", "Pintura interior"),
]

# Roles del grupo motor → relevamiento_ee_grupo_motor_rol
_GM_ROLES = [
    ("GM_Rol1", "GM_Rol1_Cant"),
    ("GM_Rol2", "GM_Rol2_Cant"),
    ("GM_Rol3", "GM_Rol3_Cant"),
    ("GM_Rol4", "GM_Rol4_Cant"),
]

# Actividades de itinerancia (si/no) → relevamiento_ee_itinerancia_actividad
_ITINERANCIA_ACTIVIDADES = [
    ("Itinerancia_Act_Alfabetizacion", "Alfabetización"),
    ("Itinerancia_Act_Charlas",        "Charlas"),
    ("Itinerancia_Act_Estim",          "Estimulación temprana"),
    ("Itinerancia_Act_Festividades",   "Festividades"),
    ("Itinerancia_Act_Merienda",       "Merienda"),
    ("Itinerancia_Act_PI",             "Primera infancia"),
    ("Itinerancia_Act_Recreacion",     "Recreación"),
    ("Itinerancia_Act_Reuniones",      "Reuniones"),
    ("Itinerancia_Act_Talleres",       "Talleres"),
]

# Espacios de itinerancia (si/no) → relevamiento_ee_itinerancia_espacio
_ITINERANCIA_ESPACIOS = [
    ("Itinerancia_Club",    "Club"),
    ("Itinerancia_Paraje",  "Paraje"),
    ("Itinerancia_Plaza",   "Plaza"),
    ("Itinerancia_Terreno", "Terreno"),
]

# Talleres de alfabetización digital (si/no) → relevamiento_ee_digital_taller
_DIGITAL_TALLERES = [
    ("AlfabDig_NT_Digitales",      "Herramientas digitales"),
    ("AlfabDig_NT_Tall_Redes",     "Redes sociales"),
    ("AlfabDig_NT_Tall_Seguridad", "Seguridad digital"),
    ("AlfabDig_NT_Tall_Trabajo",   "Herramientas para el trabajo"),
]

# Instituciones de nivel superior → relevamiento_ee_nivel_superior
_ARTICULA_INSTITUCIONES = [
    ("Articula_Institucion1", "Articula_Institucion1_Acciones"),
    ("Articula_Institucion2", "Articula_Institucion2_Acciones"),
    ("Articula_Institucion3", "Articula_Institucion3_Acciones"),
    ("Articula_Institucion4", "Articula_Institucion4_Acciones"),
    ("Articula_Institucion5", "Articula_Institucion5_Acciones"),
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
                if col in _EE_BOOL_COLS:
                    row[col] = _to_bool(raw)
                elif col in _EE_STR50_COLS:
                    row[col] = str(raw).strip()[:50] if raw not in (None, "") else None
                elif col in _EE_STR200_COLS:
                    row[col] = str(raw).strip()[:200] if raw not in (None, "") else None
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

            # Roles de itinerancia (DELETE+INSERT batch para evitar duplicados)
            conn.execute(text(
                "DELETE FROM relevamiento_ee_itinerancia_rol WHERE relevamiento_ee_id = :ree_id"
            ), {"ree_id": ree_id})
            rol_itin_insert = []
            for rol_key, cant_key in _ITINERANCIA_ROLES:
                rol_val = fv.get(rol_key)
                if not rol_val:
                    continue
                rol_itin_insert.append({
                    "ree_id": ree_id, "rol": str(rol_val).strip()[:200],
                    "rol_otro": str(fv.get(f"{rol_key}_Otro") or "").strip() or None,
                    "cant": _to_int(fv.get(cant_key)),
                })
            if rol_itin_insert:
                conn.execute(text("""
                    INSERT INTO relevamiento_ee_itinerancia_rol
                        (relevamiento_ee_id, rol, rol_otro, cantidad)
                    VALUES (:ree_id, :rol, :rol_otro, :cant)
                """), rol_itin_insert)

            # Roles del grupo motor
            conn.execute(text(
                "DELETE FROM relevamiento_ee_grupo_motor_rol WHERE relevamiento_ee_id = :ree_id"
            ), {"ree_id": ree_id})
            gm_insert = [
                {"ree_id": ree_id, "rol": str(fv.get(rol_key)).strip()[:200],
                 "cant": _to_int(fv.get(cant_key))}
                for rol_key, cant_key in _GM_ROLES if fv.get(rol_key)
            ]
            if gm_insert:
                conn.execute(text("""
                    INSERT INTO relevamiento_ee_grupo_motor_rol
                        (relevamiento_ee_id, rol, cantidad)
                    VALUES (:ree_id, :rol, :cant)
                """), gm_insert)

            # Actividades de itinerancia
            conn.execute(text(
                "DELETE FROM relevamiento_ee_itinerancia_actividad WHERE relevamiento_ee_id = :ree_id"
            ), {"ree_id": ree_id})
            act_itin_insert = [
                {"ree_id": ree_id, "act": actividad}
                for col, actividad in _ITINERANCIA_ACTIVIDADES if _to_bool(fv.get(col))
            ]
            if act_itin_insert:
                conn.execute(text("""
                    INSERT INTO relevamiento_ee_itinerancia_actividad
                        (relevamiento_ee_id, actividad)
                    VALUES (:ree_id, :act)
                """), act_itin_insert)

            # Espacios de itinerancia
            conn.execute(text(
                "DELETE FROM relevamiento_ee_itinerancia_espacio WHERE relevamiento_ee_id = :ree_id"
            ), {"ree_id": ree_id})
            esp_itin_insert = [
                {"ree_id": ree_id, "esp": espacio, "otro": None}
                for col, espacio in _ITINERANCIA_ESPACIOS if _to_bool(fv.get(col))
            ]
            itin_otro = str(fv.get("Itinerancia_Otro") or "").strip()
            if itin_otro:
                esp_itin_insert.append({"ree_id": ree_id, "esp": "Otro", "otro": itin_otro[:200]})
            if esp_itin_insert:
                conn.execute(text("""
                    INSERT INTO relevamiento_ee_itinerancia_espacio
                        (relevamiento_ee_id, espacio, espacio_otro)
                    VALUES (:ree_id, :esp, :otro)
                """), esp_itin_insert)

            # Preocupaciones de adolescentes y jóvenes (ranking)
            conn.execute(text(
                "DELETE FROM relevamiento_ee_preocupacion_joven WHERE relevamiento_ee_id = :ree_id"
            ), {"ree_id": ree_id})
            ayj_insert = [
                {"ree_id": ree_id, "preo": preocupacion, "rank": rank}
                for col, preocupacion in _AYJ_RANKS
                if (rank := _to_int(fv.get(col))) is not None
            ]
            if ayj_insert:
                conn.execute(text("""
                    INSERT INTO relevamiento_ee_preocupacion_joven
                        (relevamiento_ee_id, preocupacion, ranking)
                    VALUES (:ree_id, :preo, :rank)
                """), ayj_insert)

            # Motivos de abandono BTU
            conn.execute(text(
                "DELETE FROM relevamiento_ee_btu_abandono_motivo WHERE relevamiento_ee_id = :ree_id"
            ), {"ree_id": ree_id})
            btu_motivo_insert = [
                {"ree_id": ree_id, "motivo": motivo}
                for col, motivo in _BTU_ABANDONO_MOTIVOS if _to_bool(fv.get(col))
            ]
            btu_otro = str(fv.get("BTU_abandono_otro") or "").strip()
            if btu_otro:
                btu_motivo_insert.append({"ree_id": ree_id, "motivo": f"Otro: {btu_otro}"[:200]})
            if btu_motivo_insert:
                conn.execute(text("""
                    INSERT INTO relevamiento_ee_btu_abandono_motivo
                        (relevamiento_ee_id, motivo)
                    VALUES (:ree_id, :motivo)
                """), btu_motivo_insert)

            # Necesidades de infraestructura (prioridades)
            conn.execute(text(
                "DELETE FROM relevamiento_ee_necesidad_infra WHERE relevamiento_ee_id = :ree_id"
            ), {"ree_id": ree_id})
            infra_insert = [
                {"ree_id": ree_id, "nec": necesidad}
                for col, necesidad in _PRIORIDADES_INFRA if _to_bool(fv.get(col))
            ]
            if infra_insert:
                conn.execute(text("""
                    INSERT INTO relevamiento_ee_necesidad_infra
                        (relevamiento_ee_id, necesidad)
                    VALUES (:ree_id, :nec)
                """), infra_insert)

            # Talleres de alfabetización digital
            conn.execute(text(
                "DELETE FROM relevamiento_ee_digital_taller WHERE relevamiento_ee_id = :ree_id"
            ), {"ree_id": ree_id})
            digital_insert = [
                {"ree_id": ree_id, "taller": taller}
                for col, taller in _DIGITAL_TALLERES if _to_bool(fv.get(col))
            ]
            if digital_insert:
                conn.execute(text("""
                    INSERT INTO relevamiento_ee_digital_taller
                        (relevamiento_ee_id, taller)
                    VALUES (:ree_id, :taller)
                """), digital_insert)

            # Instituciones de nivel superior con las que articula
            conn.execute(text(
                "DELETE FROM relevamiento_ee_nivel_superior WHERE relevamiento_ee_id = :ree_id"
            ), {"ree_id": ree_id})
            nivel_sup_insert = []
            for inst_key, acc_key in _ARTICULA_INSTITUCIONES:
                inst = str(fv.get(inst_key) or "").strip()
                if not inst:
                    continue
                acciones = str(fv.get(acc_key) or "").strip() or None
                nivel_sup_insert.append({
                    "ree_id": ree_id, "inst": inst[:200],
                    "acc": acciones[:500] if acciones else None,
                })
            if nivel_sup_insert:
                conn.execute(text("""
                    INSERT INTO relevamiento_ee_nivel_superior
                        (relevamiento_ee_id, nombre_institucion, tipo_acciones)
                    VALUES (:ree_id, :inst, :acc)
                """), nivel_sup_insert)

            # Acciones (relevamiento_ee_accion) — DELETE+INSERT batch en vez de
            # ON DUPLICATE KEY UPDATE por ítem (32 acciones posibles)
            conn.execute(text(
                "DELETE FROM relevamiento_ee_accion WHERE relevamiento_ee_id = :ree_id"
            ), {"ree_id": ree_id})
            accion_insert = []
            for yaml_name, (eje, accion) in _ACCION_MAP.items():
                raw = fv.get(yaml_name)
                if raw is None:
                    continue
                tiene = _to_bool(raw)
                if tiene is None:
                    continue
                accion_insert.append({"ree_id": ree_id, "eje": eje, "accion": accion, "tiene": tiene})
            if accion_insert:
                conn.execute(text("""
                    INSERT INTO relevamiento_ee_accion
                        (relevamiento_ee_id, eje, accion, tiene)
                    VALUES (:ree_id, :eje, :accion, :tiene)
                """), accion_insert)

            # Upsert contenidos apoyo escolar primaria
            _CONTENIDOS_PRIMARIA = [
                ("ApEscolar_Lengua",         "Lengua"),
                ("ApEscolar_Matematicas",    "Matemáticas"),
                ("ApEscolar_CciasNaturales", "Ciencias Naturales"),
                ("ApEscolar_CciasSociales",  "Ciencias Sociales"),
                ("ApEscolar_Ingles",         "Inglés"),
                ("ApEscolar_Otro",           "Otro"),
            ]
            conn.execute(text(
                "DELETE FROM relevamiento_ee_apoyo_primario_contenido WHERE relevamiento_ee_id = :ree_id"
            ), {"ree_id": ree_id})
            cont_prim_insert = [
                {"ree_id": ree_id, "contenido": contenido}
                for yaml_name, contenido in _CONTENIDOS_PRIMARIA
                if fv.get(yaml_name) is not None and _to_bool(fv.get(yaml_name))
            ]
            if cont_prim_insert:
                conn.execute(text("""
                    INSERT INTO relevamiento_ee_apoyo_primario_contenido
                        (relevamiento_ee_id, contenido)
                    VALUES (:ree_id, :contenido)
                """), cont_prim_insert)

            # Upsert contenidos apoyo escolar secundaria
            _CONTENIDOS_SECUNDARIA = [
                ("ApEscolar_Sec_Lengua",         "Lengua"),
                ("ApEscolar_Sec_Matematicas",    "Matemáticas"),
                ("ApEscolar_Sec_CciasNaturales", "Ciencias Naturales"),
                ("ApEscolar_Sec_CciasSociales",  "Ciencias Sociales"),
                ("ApEscolar_Sec_Ingles",         "Inglés"),
                ("ApEscolar_Sec_Otro",           "Otro"),
            ]
            conn.execute(text(
                "DELETE FROM relevamiento_ee_apoyo_secundario_contenido WHERE relevamiento_ee_id = :ree_id"
            ), {"ree_id": ree_id})
            cont_sec_insert = [
                {"ree_id": ree_id, "contenido": contenido}
                for yaml_name, contenido in _CONTENIDOS_SECUNDARIA
                if fv.get(yaml_name) is not None and _to_bool(fv.get(yaml_name))
            ]
            if cont_sec_insert:
                conn.execute(text("""
                    INSERT INTO relevamiento_ee_apoyo_secundario_contenido
                        (relevamiento_ee_id, contenido)
                    VALUES (:ree_id, :contenido)
                """), cont_sec_insert)

            # ── Características edilicias (tablas del EE, se actualizan en cada sync) ──

            # Datos edilicios en espacio_educativo
            conn.execute(
                text("""UPDATE espacio_educativo SET
                            construccion_material = :construccion,
                            titularidad = :titularidad,
                            nombre_titular = :titular,
                            rampa_acceso = :rampa,
                            acceso_principal = :acceso
                        WHERE id = :id"""),
                {
                    "construccion": str(fv.get("EE_Edil_Construccion") or "").strip()[:100] or None,
                    "titularidad":  str(fv.get("EE_Edil_Titularidad") or "").strip()[:100] or None,
                    "titular":      str(fv.get("EE_Edil_Titular") or "").strip()[:200] or None,
                    "rampa":        _to_bool(fv.get("EE_Edil_Rampa")),
                    "acceso":       str(fv.get("EE_Edil_AccesoPor") or "").strip()[:100] or None,
                    "id": ee_id,
                },
            )

            # ee_zona (multi-valor)
            conn.execute(text("DELETE FROM ee_zona WHERE espacio_educativo_id = :id"), {"id": ee_id})
            zonas_insert = [
                {"id": ee_id, "zona": nombre}
                for col, nombre in _ZONAS
                if _to_bool(fv.get(col))
            ]
            if zonas_insert:
                conn.execute(
                    text("INSERT INTO ee_zona (espacio_educativo_id, zona) VALUES (:id, :zona)"),
                    zonas_insert,
                )

            # ee_ambiente
            conn.execute(text("DELETE FROM ee_ambiente WHERE espacio_educativo_id = :id"), {"id": ee_id})
            amb_insert = []
            seen_amb = set()
            for col, nombre in _AMBIENTES:
                if nombre in seen_amb:
                    continue
                seen_amb.add(nombre)
                tiene = _to_bool(fv.get(col))
                # buscar cantidad si existe
                cantidad = None
                for c_col, c_cant_col, c_nombre in _AMBIENTES_CON_CANTIDAD:
                    if c_nombre == nombre:
                        cantidad = _to_int(fv.get(c_cant_col))
                        break
                amb_insert.append({"id": ee_id, "ambiente": nombre, "tiene": tiene, "cantidad": cantidad})
            if amb_insert:
                conn.execute(
                    text("INSERT INTO ee_ambiente (espacio_educativo_id, ambiente, tiene, cantidad) VALUES (:id, :ambiente, :tiene, :cantidad)"),
                    amb_insert,
                )

            # ee_servicio
            conn.execute(text("DELETE FROM ee_servicio WHERE espacio_educativo_id = :id"), {"id": ee_id})
            serv_insert = [
                {"id": ee_id, "servicio": nombre, "valor": str(fv.get(col) or "").strip() or None}
                for col, nombre in _SERVICIOS
                if fv.get(col) not in (None, "")
            ]
            if serv_insert:
                conn.execute(
                    text("INSERT INTO ee_servicio (espacio_educativo_id, servicio, valor) VALUES (:id, :servicio, :valor)"),
                    serv_insert,
                )

            # ee_equipo_cocina
            conn.execute(text("DELETE FROM ee_equipo_cocina WHERE espacio_educativo_id = :id"), {"id": ee_id})
            cocina_insert = [
                {"id": ee_id, "equipo": nombre, "tiene": _to_bool(fv.get(col))}
                for col, nombre in _EQUIPOS_COCINA
            ]
            if cocina_insert:
                conn.execute(
                    text("INSERT INTO ee_equipo_cocina (espacio_educativo_id, equipo, tiene) VALUES (:id, :equipo, :tiene)"),
                    cocina_insert,
                )

            # ee_equipo_informatico
            conn.execute(text("DELETE FROM ee_equipo_informatico WHERE espacio_educativo_id = :id"), {"id": ee_id})
            info_insert = [
                {"id": ee_id, "equipo": nombre, "cantidad": _to_int(fv.get(col))}
                for col, nombre in _EQUIPOS_INFORMATICO_COLS
                if _to_int(fv.get(col))
            ]
            if info_insert:
                conn.execute(
                    text("INSERT INTO ee_equipo_informatico (espacio_educativo_id, equipo, cantidad) VALUES (:id, :equipo, :cantidad)"),
                    info_insert,
                )


# ---------------------------------------------------------------------------
# Pastoral PI (Primera Infancia)
# ---------------------------------------------------------------------------

_PI_FIELD_MAP = {
    "AniosPI":                      "anios_desarrollo",
    "MetodologiaPresentada":        "presento_metodologia",
    "MetodologiaPresentada_SinDesarrollo": "comunidades_sin_pastoral",
    "Capacitadoras":                "capacitadoras",
    "Lideres":                      "lideres",
    "MadresEmbarazadas_12_18":      "madres_embarazadas_12_18",
    "MadresEmbarazadas_19_30":      "madres_embarazadas_19_29",
    "MadresEmbarazadas_30mas":      "madres_embarazadas_30_mas",
    "MadresNoEmbarazadas":          "madres_no_embarazadas",
    "Ninos_0_3":                    "ninos_0_3",
    "Ninos_4_6":                    "ninos_4_6",
    "Familias":                     "familias",
    "LideresSabenLeerEscribir":         "lideres_todas_alfabetizadas",
    "CantLideresNoSabenLeerEscribir":   "lideres_no_alfabetizadas_cantidad",
    "AlgunaLiderParticipaDale":         "lideres_en_alfabetizacion",
    "TodasMadresAlfabetizadas":         "madres_todas_alfabetizadas",
    "CantMadresNoAlfabetizadas":        "madres_no_alfabetizadas_cantidad",
    "AlgunaMadreParticipaAlfabetizacion": "madres_en_alfabetizacion",
}
_PI_BOOL_COLS = {
    "presento_metodologia", "lideres_todas_alfabetizadas", "lideres_en_alfabetizacion",
    "madres_todas_alfabetizadas", "madres_en_alfabetizacion",
}

_PI_ENFERMEDADES_NINOS = ["Enfermedad1_Ninos", "Enfermedad2_Ninos", "Enfermedad3_Ninos"]
_PI_ENFERMEDADES_EMBARAZADAS = ["Enfermedad1_Mujeres", "Enfermedad2_Mujeres", "Enfermedad3_Mujeres"]

# (columna si/no/desconozco, columna frecuencia, columna cantidad, valor enum)
_PI_ACCIONES_LIDER = [
    ("LideresCelebracionVida",      "LideresCelebracionVida_Frec",      "LideresCelebracionVida_Cant",      "celebracion_vida"),
    ("LideresVisitaDomiciliaria",   "LideresVisitaDomiciliaria_Frec",   "LideresVisitaDomiciliaria_Cant",   "visita_domiciliaria"),
    ("LideresReunionEvaluacion",    "LideresReunionEvaluacion_Frec",    "LideresReunionEvaluacion_Cant",    "reunion_evaluacion"),
]

# (columna si/no/desconozco, columna cantidad comunidades, nombre temática)
_PI_TEMATICAS = [
    ("Abordada_Vacunas",                "Abordada_Vacunas_Comunidades",                "Vacunas"),
    ("Abordada_Higiene",                "Abordada_Higiene_Comunidades",                "Higiene"),
    ("Abordada_PrimerosaAuxilios",      "Abordada_PrimerosaAuxilios_Comunidades",      "Primeros auxilios"),
    ("Abordada_EstimulacionAdecuada",   "Abordada_EstimulacionAdecuada_Comunidades",   "Estimulación adecuada"),
    ("Abordada_Lactancia",              "Abordada_Lactancia_Comunidades",              "Lactancia"),
    ("Abordada_Ternura",                "Abordada_Ternura_Comunidades",                "Ternura"),
    ("Abordada_Alimentacion",           "Abordada_Alimentacion_Comunidades",           "Alimentación"),
    ("Abordada_DerechosInfancias",      "Abordada_DerechosInfancias_Comunidades",      "Derechos de las infancias"),
    ("Abordada_DiscriminacionViolencia","Abordada_DiscriminacionViolencia_Comunidades","Discriminación y violencia"),
    ("Abordada_Autoestima",             "Abordada_Autoestima_Comunidades",             "Autoestima"),
    ("Abordada_Consumoproblematico",    "Abordada_Consumoproblematico_Comunidades",    "Consumo problemático"),
    ("Abordada_AbusoAcoso",             "Abordada_AbusoAcoso_Comunidades",             "Abuso y acoso"),
    ("Abordada_AdecuacionPI",           "Abordada_AdecuacionPI_Comunidades",           "Adecuación PI"),
    ("Abordada_MedioAmbiente",          "Abordada_MedioAmbiente_Comunidades",          "Medio ambiente"),
]

# (columna si/no/desconozco, nombre organización)
_PI_ARTICULACIONES = [
    ("Articula_CentroSalud", "Centro de salud"),
    ("Articula_Hospital",    "Hospital"),
    ("Articula_Municipio",   "Municipio"),
    ("Articula_DeptGenero",  "Departamento de género"),
]


def upsert_pastoral_pi(engine, emaus_id: int, anio: int, semestre: str,
                        pi_field_data: Optional[Dict]) -> None:
    """Upserta datos de la hoja Primera Infancia (PastoralPI y tablas relacionadas)."""
    if not pi_field_data:
        return

    fv = pi_field_data
    with engine.begin() as conn:
        rel = conn.execute(
            text("SELECT id FROM relevamiento WHERE emaus_id=:eid AND anio=:a AND semestre=:s LIMIT 1"),
            {"eid": emaus_id, "a": anio, "s": semestre},
        ).fetchone()
        if not rel:
            return
        relevamiento_id = rel[0]

        row: Dict[str, Any] = {"relevamiento_id": relevamiento_id}
        for yaml_name, col in _PI_FIELD_MAP.items():
            raw = fv.get(yaml_name)
            row[col] = _to_bool(raw) if col in _PI_BOOL_COLS else _to_int(raw)

        row["comunidades_total"] = sum(
            1 for col in ("Comunidad1", "Comunidad2", "Comunidad3", "Comunidad4")
            if str(fv.get(col) or "").strip()
        )

        cols = list(row.keys())
        placeholders = ", ".join(f":{c}" for c in cols)
        updates = ", ".join(f"{c} = VALUES({c})" for c in cols if c != "relevamiento_id")
        conn.execute(
            text(f"""
                INSERT INTO pastoral_pi ({', '.join(cols)})
                VALUES ({placeholders})
                ON DUPLICATE KEY UPDATE {updates}
            """),
            row,
        )
        pi_id = conn.execute(
            text("SELECT id FROM pastoral_pi WHERE relevamiento_id=:rid LIMIT 1"),
            {"rid": relevamiento_id},
        ).fetchone()[0]

        # Enfermedades más frecuentes en niños
        conn.execute(text(
            "DELETE FROM pastoral_pi_enfermedad_ninos WHERE pastoral_pi_id = :pid"
        ), {"pid": pi_id})
        enf_ninos_insert = [
            {"pid": pi_id, "enf": str(fv.get(col)).strip()[:200], "orden": i}
            for i, col in enumerate(_PI_ENFERMEDADES_NINOS, start=1)
            if str(fv.get(col) or "").strip()
        ]
        if enf_ninos_insert:
            conn.execute(text("""
                INSERT INTO pastoral_pi_enfermedad_ninos (pastoral_pi_id, enfermedad, orden)
                VALUES (:pid, :enf, :orden)
            """), enf_ninos_insert)

        # Enfermedades más frecuentes en embarazadas
        conn.execute(text(
            "DELETE FROM pastoral_pi_enfermedad_embarazadas WHERE pastoral_pi_id = :pid"
        ), {"pid": pi_id})
        enf_emb_insert = [
            {"pid": pi_id, "enf": str(fv.get(col)).strip()[:200], "orden": i}
            for i, col in enumerate(_PI_ENFERMEDADES_EMBARAZADAS, start=1)
            if str(fv.get(col) or "").strip()
        ]
        if enf_emb_insert:
            conn.execute(text("""
                INSERT INTO pastoral_pi_enfermedad_embarazadas (pastoral_pi_id, enfermedad, orden)
                VALUES (:pid, :enf, :orden)
            """), enf_emb_insert)

        # Acciones de líderes (celebración de vida, visita domiciliaria, reunión evaluación)
        conn.execute(text(
            "DELETE FROM pastoral_pi_accion_lider WHERE pastoral_pi_id = :pid"
        ), {"pid": pi_id})
        accion_lider_insert = []
        for si_col, frec_col, cant_col, accion in _PI_ACCIONES_LIDER:
            realiza = _to_bool(fv.get(si_col))
            if realiza is None:
                continue
            accion_lider_insert.append({
                "pid": pi_id, "accion": accion, "realiza": realiza,
                "frecuencia": str(fv.get(frec_col) or "").strip()[:100] or None,
                "cantidad": _to_int(fv.get(cant_col)),
            })
        if accion_lider_insert:
            conn.execute(text("""
                INSERT INTO pastoral_pi_accion_lider
                    (pastoral_pi_id, accion, realiza, frecuencia, cantidad_semestre)
                VALUES (:pid, :accion, :realiza, :frecuencia, :cantidad)
            """), accion_lider_insert)

        # Temáticas abordadas
        conn.execute(text(
            "DELETE FROM pastoral_pi_tematica WHERE pastoral_pi_id = :pid"
        ), {"pid": pi_id})
        tematica_insert = [
            {"pid": pi_id, "tematica": tematica, "otra": None, "cant": _to_int(fv.get(cant_col))}
            for si_col, cant_col, tematica in _PI_TEMATICAS if _to_bool(fv.get(si_col))
        ]
        otras = str(fv.get("Abordada_Otras") or "").strip()
        if otras:
            tematica_insert.append({
                "pid": pi_id, "tematica": "Otras", "otra": otras[:200],
                "cant": _to_int(fv.get("Abordada_Otras_Comunidades")),
            })
        if tematica_insert:
            conn.execute(text("""
                INSERT INTO pastoral_pi_tematica (pastoral_pi_id, tematica, tematica_otra, comunidades_cantidad)
                VALUES (:pid, :tematica, :otra, :cant)
            """), tematica_insert)

        # Articulación institucional
        conn.execute(text(
            "DELETE FROM pastoral_pi_articulacion WHERE pastoral_pi_id = :pid"
        ), {"pid": pi_id})
        articulacion_insert = [
            {"pid": pi_id, "org": organizacion}
            for col, organizacion in _PI_ARTICULACIONES if _to_bool(fv.get(col))
        ]
        if articulacion_insert:
            conn.execute(text("""
                INSERT INTO pastoral_pi_articulacion (pastoral_pi_id, organizacion)
                VALUES (:pid, :org)
            """), articulacion_insert)


# ---------------------------------------------------------------------------
# Establecimientos educativos articulados
# ---------------------------------------------------------------------------

def upsert_establecimientos(engine, emaus_id: int, anio: int, semestre: str,
                             estab_rows_data: Optional[List[List]]) -> None:
    """Upserta establecimiento_estado (por CUE) y establecimiento_articulado
    a partir de la hoja 'Establecimientos' de la planilla.

    Columnas (fila 3 en adelante): A=Jurisdicción, B=Ámbito, C=Departamento,
    D=Localidad, E=Establecimiento, F-J=Acciones, K=CUE.
    """
    if not estab_rows_data:
        return

    with engine.begin() as conn:
        rel = conn.execute(
            text("SELECT id FROM relevamiento WHERE emaus_id=:eid AND anio=:a AND semestre=:s LIMIT 1"),
            {"eid": emaus_id, "a": anio, "s": semestre},
        ).fetchone()
        if not rel:
            return
        relevamiento_id = rel[0]

        articulaciones = []
        for row in estab_rows_data:
            row = list(row) + [""] * (11 - len(row))  # padear por si la fila viene corta
            jurisdiccion, ambito, departamento, localidad, nombre = (str(x or "").strip() for x in row[0:5])
            cue = str(row[10] or "").strip()
            if not cue:
                continue  # sin CUE no se puede vincular/crear establecimiento_estado

            estab = conn.execute(
                text("SELECT id FROM establecimiento_estado WHERE cueanexo=:cue LIMIT 1"),
                {"cue": cue},
            ).fetchone()
            if estab:
                establecimiento_id = estab[0]
            else:
                res = conn.execute(text("""
                    INSERT INTO establecimiento_estado
                        (cueanexo, jurisdiccion, ambito, departamento, localidad, nombre, actualizado_en)
                    VALUES (:cue, :jur, :amb, :depto, :loc, :nom, :hoy)
                """), {"cue": cue, "jur": jurisdiccion or None, "amb": ambito or None,
                       "depto": departamento or None, "loc": localidad or None,
                       "nom": nombre or None, "hoy": datetime.utcnow().date()})
                establecimiento_id = res.lastrowid

            articulaciones.append({
                "rel_id": relevamiento_id,
                "estab_id": establecimiento_id,
                "institucion": bool(_to_bool(row[5])),
                "alfa": bool(_to_bool(row[6])),
                "seguimiento": bool(_to_bool(row[7])),
                "intercambio": bool(_to_bool(row[8])),
                "otros": bool(_to_bool(row[9])),
            })

        # Dedup por establecimiento_id (si el mismo CUE aparece más de una vez en la
        # planilla) para no violar el UNIQUE KEY (relevamiento_id, establecimiento_id)
        articulaciones = list({a["estab_id"]: a for a in articulaciones}.values())

        conn.execute(text(
            "DELETE FROM establecimiento_articulado WHERE relevamiento_id = :rid"
        ), {"rid": relevamiento_id})
        if articulaciones:
            conn.execute(text("""
                INSERT INTO establecimiento_articulado
                    (relevamiento_id, establecimiento_id, accion_institucion,
                     accion_articulacion_alfa, accion_seguimiento, accion_intercambio, accion_otros)
                VALUES (:rel_id, :estab_id, :institucion, :alfa, :seguimiento, :intercambio, :otros)
            """), articulaciones)


# ---------------------------------------------------------------------------
# Persistencia en TiDB
# ---------------------------------------------------------------------------

def upsert_control(engine, emaus_id: int, anio: int, semestre: str, metrics: Dict):
    errors = metrics.pop("validation_errors", [])
    ee_field_data = metrics.pop("ee_field_data", {})
    pi_field_data = metrics.pop("pi_field_data", None)
    estab_rows_data = metrics.pop("estab_rows_data", None)
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
    if pi_field_data:
        upsert_pastoral_pi(engine, emaus_id, anio, semestre, pi_field_data)
    if estab_rows_data:
        upsert_establecimientos(engine, emaus_id, anio, semestre, estab_rows_data)


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


def _get_file_modified_time(drive, file_id: str) -> Optional[datetime]:
    """Consulta solo el metadato modifiedTime de un archivo de Drive (liviano, sin leer datos)."""
    if not file_id:
        return None
    try:
        meta = execute_with_retry(
            drive.files().get(fileId=file_id, fields="modifiedTime", supportsAllDrives=True)
        )
        return _parse_drive_datetime(meta.get("modifiedTime"))
    except Exception as e:
        print(f"  [warn] No se pudo consultar modifiedTime de {file_id}: {e}")
        return None


def sync_btu_bf_directo(engine, sheets_svc, drive_svc, emaus_list: List[Dict],
                         anio: int, semestre: str, force: bool = False) -> None:
    """
    Actualiza btu_actual/bf_actual en control_relevamiento leyendo las planillas
    externas BTU y BF, pero solo si cambiaron desde el último sync (según
    modifiedTime de Drive) — evita releer ~120 filas en cada sync cuando nada
    cambió, y actualiza directamente por UPDATE en vez de depender de que el
    emaús individual también haya cambiado (así los cambios en BTU/BF se
    reflejan aunque ninguna planilla de EE se haya modificado).
    """
    with engine.begin() as conn:
        estado = {r[0]: r[1] for r in conn.execute(
            text("SELECT nombre, ultima_modificacion FROM sync_planilla_externa")
        ).fetchall()}

    for clave, spreadsheet_id_env, leer_fn, campo in (
        ("btu", "BTU_SPREADSHEET_ID", leer_btu_planilla, "btu_actual"),
        ("bf",  "BF_SPREADSHEET_ID",  leer_bf_planilla,  "bf_actual"),
    ):
        spreadsheet_id = os.getenv(spreadsheet_id_env, "")
        if not spreadsheet_id:
            print(f"  [warn] {spreadsheet_id_env} no configurado")
            continue

        modified_time = _get_file_modified_time(drive_svc, spreadsheet_id)
        ultima = estado.get(clave)
        if not force and modified_time is not None and ultima is not None and modified_time <= ultima:
            print(f"  [SKIP-SINCAMBIOS] planilla {clave.upper()} sin cambios desde el último sync")
            continue

        mapa: Dict[str, int] = leer_fn(sheets_svc, spreadsheet_id)
        if not mapa:
            print(f"  [warn] No se leyeron datos de {clave.upper()}")
            continue
        print(f"  {clave.upper()} leídos para {len(mapa)} Emaús — aplicando cambios")

        with engine.begin() as conn:
            for emaus in emaus_list:
                valor = mapa.get(emaus["nombre"])
                if valor is None:
                    continue
                conn.execute(text(f"""
                    UPDATE control_relevamiento
                    SET {campo} = COALESCE(:valor, {campo})
                    WHERE emaus_id = :emaus_id AND anio = :anio AND semestre = :semestre
                """), {"valor": valor, "emaus_id": emaus["id"], "anio": anio, "semestre": semestre})

            if modified_time is not None:
                conn.execute(text("""
                    UPDATE sync_planilla_externa SET ultima_modificacion = :mt WHERE nombre = :nombre
                """), {"mt": modified_time, "nombre": clave})


def find_emaus_id(engine, nombre: str) -> Optional[int]:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id FROM emaus WHERE nombre = :nombre AND activo = TRUE LIMIT 1"),
            {"nombre": nombre},
        ).fetchone()
    return row[0] if row else None


def _parse_drive_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parsea el modifiedTime de Drive API (RFC3339, ej '2026-07-20T12:34:56.789Z') a datetime naive UTC."""
    if not value:
        return None
    try:
        return datetime.strptime(value.split(".")[0].replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
    except (ValueError, TypeError):
        return None


def get_all_emaus(engine) -> List[Dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, nombre, spreadsheet_id, ultima_modificacion_sheet "
                 "FROM emaus WHERE activo = TRUE ORDER BY nombre")
        ).fetchall()
    return [{"id": r[0], "nombre": r[1], "spreadsheet_id": r[2],
             "ultima_modificacion_sheet": r[3]} for r in rows]


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
    parser.add_argument("--force", action="store_true",
                        help="Procesar todos los emaús aunque su planilla no haya cambiado desde el último sync")
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
    modified_by_id: Dict[str, datetime] = {}
    for item in all_spreadsheets:
        emaus_name = item.get("emaus_nombre", "").strip()
        if emaus_name:
            sheet_map[emaus_name] = item["id"]
            print(f"    Planilla: {emaus_name} → {item['id'][:20]}...")
        dt = _parse_drive_datetime(item.get("modifiedTime"))
        if dt is not None:
            modified_by_id[item["id"]] = dt


    # BTU/BF: se releen y aplican solo si sus planillas externas cambiaron
    if not args.dry_run:
        sync_btu_bf_directo(engine, sheets_svc, drive_svc, emaus_list,
                             args.anio, args.semestre, force=args.force)

    ok = err = skip = 0

    for emaus in emaus_list:
        if args.emaus_id and emaus["id"] != args.emaus_id:
            continue

        spreadsheet_id = emaus.get("spreadsheet_id") or sheet_map.get(emaus["nombre"])
        if not spreadsheet_id:
            print(f"  [SKIP] {emaus['nombre']} — sin planilla asociada")
            skip += 1
            continue

        modified_time = modified_by_id.get(spreadsheet_id)
        if (not args.force and args.emaus_id is None and modified_time is not None
                and emaus.get("ultima_modificacion_sheet") is not None
                and modified_time <= emaus["ultima_modificacion_sheet"]):
            print(f"  [SKIP-SINCAMBIOS] {emaus['nombre']} — planilla sin cambios desde el último sync")
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
            n_err = len([e for e in metrics["validation_errors"] if e["severity"] == "error"])
            n_warn = len([e for e in metrics["validation_errors"] if e["severity"] == "warning"])

            if not args.dry_run:
                upsert_control(engine, emaus["id"], args.anio, args.semestre, metrics)
                if modified_time is not None:
                    with engine.begin() as conn:
                        conn.execute(text(
                            "UPDATE emaus SET ultima_modificacion_sheet = :mt WHERE id = :id"
                        ), {"mt": modified_time, "id": emaus["id"]})

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
             emaus_id: int = None, dry_run: bool = False, apply_reset: bool = False,
             force: bool = False) -> dict:
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
    # modifiedTime viene gratis en la misma llamada de list_spreadsheets — se usa
    # para saltear emaús cuya planilla no cambió desde el último sync exitoso.
    modified_by_id: Dict[str, datetime] = {
        item["id"]: dt
        for item in all_spreadsheets
        if (dt := _parse_drive_datetime(item.get("modifiedTime"))) is not None
    }

    # BTU/BF: se releen y aplican solo si sus planillas externas cambiaron
    if not dry_run:
        sync_btu_bf_directo(engine, sheets_svc, drive_svc, emaus_list, anio, semestre, force=force)

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

            modified_time = modified_by_id.get(spreadsheet_id)
            # En sync completo (sin emaus_id explícito), saltear si la planilla no
            # cambió desde el último sync exitoso — evita relecturas/reescrituras
            # innecesarias y es la principal causa de que el sync completo exceda
            # el timeout de Lambda.
            if (not force and emaus_id is None and modified_time is not None
                    and emaus.get("ultima_modificacion_sheet") is not None
                    and modified_time <= emaus["ultima_modificacion_sheet"]):
                skip += 1
                continue

            try:
                metrics = scrape_spreadsheet(
                    sheets_svc, spreadsheet_id, spec,
                    anio, semestre, dry_run,
                    apply_reset=apply_reset,
                )
                metrics["_spreadsheet_id"] = spreadsheet_id
                if not dry_run:
                    upsert_control(engine, emaus["id"], anio, semestre, metrics)
                    if modified_time is not None:
                        with engine.begin() as conn:
                            conn.execute(text(
                                "UPDATE emaus SET ultima_modificacion_sheet = :mt WHERE id = :id"
                            ), {"mt": modified_time, "id": emaus["id"]})
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
