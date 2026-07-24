"""
Gestión de Espacios Educativos desde Admin: alta y baja con sincronización en Google Sheets.
"""
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.espacio_educativo import EspacioEducativo
from app.models.emaus import Emaus
from app.models.usuario import Usuario
from app.routers.auth import require_rol

router = APIRouter(prefix="/admin/ee", tags=["admin-ee"])

MODEL_SPREADSHEET_ID = os.getenv("MODEL_SPREADSHEET_ID", "")
MODEL_SHEET_NAME = "Modelo EE"


# ---------------------------------------------------------------------------
# Helpers Google Sheets
# ---------------------------------------------------------------------------

def _build_sheets():
    from scripts.scraper_control import build_services
    sheets_svc, _ = build_services()
    return sheets_svc


def _normalizar_titulo(name: str) -> str:
    """Normaliza un título de hoja para comparación laxa: sin espacios extra, sin
    prefijo 'EE ', y en minúsculas — evita fallos silenciosos por diferencias de
    mayúsculas/espacios entre nombre_hoja (DB) y el título real en Sheets."""
    s = (name or "").strip()
    if s.upper().startswith("EE "):
        s = s[3:].strip()
    return s.lower()


def _get_sheet_id(sheets_svc, spreadsheet_id: str, title: str) -> Optional[int]:
    resp = sheets_svc.spreadsheets().get(
        spreadsheetId=spreadsheet_id, fields="sheets.properties"
    ).execute()
    hojas = resp.get("sheets", [])
    # 1. Match exacto
    for s in hojas:
        if s["properties"]["title"] == title:
            return s["properties"]["sheetId"]
    # 2. Match normalizado (mayúsculas/espacios/prefijo "EE " distintos)
    objetivo = _normalizar_titulo(title)
    for s in hojas:
        if _normalizar_titulo(s["properties"]["title"]) == objetivo:
            return s["properties"]["sheetId"]
    return None


def _copiar_modelo_a_planilla(sheets_svc, target_spreadsheet_id: str, nombre_hoja: str) -> bool:
    """Copia 'Modelo EE' al spreadsheet del Emaús y lo renombra. Retorna True si OK."""
    modelo_sheet_id = _get_sheet_id(sheets_svc, MODEL_SPREADSHEET_ID, MODEL_SHEET_NAME)
    if modelo_sheet_id is None:
        return False

    # Copiar hoja
    resp = sheets_svc.spreadsheets().sheets().copyTo(
        spreadsheetId=MODEL_SPREADSHEET_ID,
        sheetId=modelo_sheet_id,
        body={"destinationSpreadsheetId": target_spreadsheet_id},
    ).execute()
    new_sheet_id = resp["sheetId"]

    # Renombrar a nombre_hoja
    sheets_svc.spreadsheets().batchUpdate(
        spreadsheetId=target_spreadsheet_id,
        body={"requests": [{"updateSheetProperties": {
            "properties": {"sheetId": new_sheet_id, "title": nombre_hoja},
            "fields": "title",
        }}]},
    ).execute()
    return True


def _ocultar_hoja(sheets_svc, spreadsheet_id: str, nombre_hoja: str) -> bool:
    """Oculta la hoja del EE en la planilla del Emaús. Retorna True si OK."""
    sheet_id = _get_sheet_id(sheets_svc, spreadsheet_id, nombre_hoja)
    if sheet_id is None:
        return False

    sheets_svc.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"updateSheetProperties": {
            "properties": {"sheetId": sheet_id, "hidden": True},
            "fields": "hidden",
        }}]},
    ).execute()
    return True


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
def listar_ee(
    emaus_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_rol("admin")),
):
    """Lista EEs activos e inactivos de un Emaús."""
    emaus = db.query(Emaus).filter(Emaus.id == emaus_id).first()
    if not emaus:
        raise HTTPException(404, "Emaús no encontrado")

    ees = (
        db.query(EspacioEducativo)
        .filter(EspacioEducativo.emaus_id == emaus_id)
        .order_by(EspacioEducativo.activo.desc(), EspacioEducativo.nombre)
        .all()
    )
    return [
        {"id": ee.id, "nombre": ee.nombre, "nombre_hoja": ee.nombre_hoja, "activo": ee.activo}
        for ee in ees
    ]


class AltaEEBody(BaseModel):
    emaus_id: int
    nombre: str
    nombre_hoja: str


@router.post("")
def alta_ee(
    body: AltaEEBody,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_rol("admin")),
):
    """Crea un EE en DB y copia la hoja modelo en la planilla del Emaús."""
    emaus = db.query(Emaus).filter(Emaus.id == body.emaus_id).first()
    if not emaus:
        raise HTTPException(404, "Emaús no encontrado")

    # Verificar que no exista ya un EE con ese nombre en el Emaús
    existente = db.query(EspacioEducativo).filter(
        EspacioEducativo.emaus_id == body.emaus_id,
        EspacioEducativo.nombre == body.nombre.strip(),
    ).first()
    if existente:
        raise HTTPException(400, f"Ya existe un EE con ese nombre en {emaus.nombre}")

    # Crear en DB
    ee = EspacioEducativo(
        emaus_id=body.emaus_id,
        nombre=body.nombre.strip(),
        nombre_hoja=body.nombre_hoja.strip(),
        activo=True,
    )
    db.add(ee)
    db.commit()
    db.refresh(ee)

    # Copiar hoja modelo en Sheets si el Emaús tiene spreadsheet
    sheets_ok = False
    sheets_msg = "Emaús sin planilla asociada — EE creado solo en DB"
    if emaus.spreadsheet_id and MODEL_SPREADSHEET_ID:
        try:
            sheets_svc = _build_sheets()
            sheets_ok = _copiar_modelo_a_planilla(sheets_svc, emaus.spreadsheet_id, body.nombre_hoja.strip())
            sheets_msg = "Hoja copiada en la planilla" if sheets_ok else "No se encontró la hoja modelo"
        except Exception as e:
            sheets_msg = f"Error en Sheets: {e}"

    return {"id": ee.id, "nombre": ee.nombre, "nombre_hoja": ee.nombre_hoja, "sheets": sheets_msg}


@router.patch("/{ee_id}/baja")
def baja_ee(
    ee_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_rol("admin")),
):
    """Da de baja un EE (activo=False) y oculta su hoja en la planilla del Emaús."""
    ee = db.query(EspacioEducativo).filter(EspacioEducativo.id == ee_id).first()
    if not ee:
        raise HTTPException(404, "EE no encontrado")
    if not ee.activo:
        raise HTTPException(400, "El EE ya está dado de baja")

    emaus = db.query(Emaus).filter(Emaus.id == ee.emaus_id).first()

    ee.activo = False
    db.commit()

    # Ocultar hoja en Sheets
    sheets_ok = False
    sheets_msg = "Emaús sin planilla — solo dado de baja en DB"
    if emaus and emaus.spreadsheet_id and ee.nombre_hoja:
        try:
            sheets_svc = _build_sheets()
            sheets_ok = _ocultar_hoja(sheets_svc, emaus.spreadsheet_id, ee.nombre_hoja)
            sheets_msg = "Hoja ocultada en la planilla" if sheets_ok else f"Hoja '{ee.nombre_hoja}' no encontrada en la planilla"
        except Exception as e:
            sheets_msg = f"Error en Sheets: {e}"
    elif emaus and emaus.spreadsheet_id and not ee.nombre_hoja:
        sheets_msg = "EE sin nombre_hoja asignado — solo dado de baja en DB"

    return {"id": ee.id, "nombre": ee.nombre, "activo": False, "sheets": sheets_msg}
