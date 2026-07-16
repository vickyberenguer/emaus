from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

from sqlalchemy import func
from app.database import get_db
from app.models.usuario import Usuario
from app.models.emaus import Emaus, ResponsableEmaus
from app.models.control import ControlRelevamiento, ControlValidacionDetalle, ControlAprobacion
from app.models.relevamiento import Relevamiento
from app.models.espacio_educativo import RelevamientoEE
from app.routers.auth import get_current_user, require_rol

router = APIRouter(prefix="/control", tags=["control"])

ANIO_ACTIVO = 2026
SEMESTRE_ACTIVO = "1"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ValidacionDetalleOut(BaseModel):
    id: int
    hoja_nombre: str
    validacion_id: str
    severity: str
    mensaje: str
    fecha: datetime
    resuelto: bool

    class Config:
        from_attributes = True


class AprobacionOut(BaseModel):
    estado: str
    aprobado_por: Optional[int]
    observaciones: Optional[str]
    fecha_aprobacion: Optional[datetime]

    class Config:
        from_attributes = True


class ControlEmausOut(BaseModel):
    emaus_id: int
    emaus_nombre: str
    diocesis_nombre: str
    anio: int
    semestre: str

    ee_count: int
    ee_declarados_completos: int
    ee_pendientes: int
    ee_con_errores: int

    pi_existe: bool
    pi_completa: bool
    pi_con_errores: bool

    talleres_completo: bool
    establecimientos_completo: bool

    total_asistentes_ee: int
    cantidad_talleres: int
    cantidad_establecimientos: int
    btu_actual: Optional[int]
    btu_relevado: int
    bf_actual: Optional[int]
    bf_relevado: int

    ultimo_sync: datetime
    spreadsheet_url: Optional[str]

    aprobacion: Optional[AprobacionOut]

    listo_para_aprobar: bool

    class Config:
        from_attributes = True


class ControlDetalleOut(ControlEmausOut):
    validaciones: List[ValidacionDetalleOut]


class AprobarRequest(BaseModel):
    estado: str  # "aprobado" o "rechazado"
    observaciones: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def spreadsheet_url(spreadsheet_id: Optional[str]) -> Optional[str]:
    if not spreadsheet_id:
        return None
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"


def is_listo(ctrl: ControlRelevamiento) -> bool:
    """True cuando todo está completo y sin errores (habilitado para aprobar)."""
    if ctrl.ee_con_errores > 0:
        return False
    if ctrl.ee_declarados_completos < ctrl.ee_count:
        return False
    if ctrl.pi_existe and (not ctrl.pi_completa or ctrl.pi_con_errores):
        return False
    if not ctrl.talleres_completo:
        return False
    if not ctrl.establecimientos_completo:
        return False
    return True


def emaus_ids_for_user(user: Usuario, db: Session) -> Optional[List[int]]:
    """None = ver todos (admin). Lista = solo esos Emaús (responsable)."""
    if user.rol == "admin":
        return None
    return [
        r.emaus_id for r in
        db.query(ResponsableEmaus).filter(ResponsableEmaus.responsable_id == user.id).all()
    ]


def build_control_out(ctrl: ControlRelevamiento, emaus: Emaus) -> dict:
    return {
        "emaus_id": ctrl.emaus_id,
        "emaus_nombre": emaus.nombre,
        "diocesis_nombre": emaus.diocesis.nombre if emaus.diocesis else "",
        "anio": ctrl.anio,
        "semestre": ctrl.semestre,
        "ee_count": ctrl.ee_count,
        "ee_declarados_completos": ctrl.ee_declarados_completos,
        "ee_pendientes": ctrl.ee_pendientes,
        "ee_con_errores": ctrl.ee_con_errores,
        "pi_existe": ctrl.pi_existe,
        "pi_completa": ctrl.pi_completa,
        "pi_con_errores": ctrl.pi_con_errores,
        "talleres_completo": ctrl.talleres_completo,
        "establecimientos_completo": ctrl.establecimientos_completo,
        "total_asistentes_ee": ctrl.total_asistentes_ee,
        "cantidad_talleres": ctrl.cantidad_talleres,
        "cantidad_establecimientos": ctrl.cantidad_establecimientos,
        "btu_actual": ctrl.btu_actual,
        "btu_relevado": 0,  # se sobreescribe en el endpoint
        "bf_actual": ctrl.bf_actual,
        "bf_relevado": 0,  # se sobreescribe en el endpoint
        "ultimo_sync": ctrl.ultimo_sync,
        "spreadsheet_url": spreadsheet_url(emaus.spreadsheet_id),
        "aprobacion": ctrl.aprobacion,
        "listo_para_aprobar": is_listo(ctrl),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=List[ControlEmausOut])
def listar_control(
    anio: int = ANIO_ACTIVO,
    semestre: str = SEMESTRE_ACTIVO,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_rol("admin", "responsable")),
):
    allowed_ids = emaus_ids_for_user(current_user, db)

    query = (
        db.query(ControlRelevamiento, Emaus)
        .join(Emaus, Emaus.id == ControlRelevamiento.emaus_id)
        .filter(
            ControlRelevamiento.anio == anio,
            ControlRelevamiento.semestre == semestre,
        )
    )
    if allowed_ids is not None:
        query = query.filter(ControlRelevamiento.emaus_id.in_(allowed_ids))

    rows = query.order_by(Emaus.nombre).all()

    # BTU relevado: sum(btu_regulares) de relevamiento_ee por Emaús
    emaus_ids = [ctrl.emaus_id for ctrl, _ in rows]
    btu_relevado_map: dict = {}
    if emaus_ids:
        btu_rows = (
            db.query(Relevamiento.emaus_id, func.coalesce(func.sum(RelevamientoEE.btu_regulares), 0))
            .join(RelevamientoEE, RelevamientoEE.relevamiento_id == Relevamiento.id)
            .filter(
                Relevamiento.anio == anio,
                Relevamiento.semestre == semestre,
                Relevamiento.emaus_id.in_(emaus_ids),
            )
            .group_by(Relevamiento.emaus_id)
            .all()
        )
        btu_relevado_map = {r[0]: int(r[1]) for r in btu_rows}

    # BF relevado: sum(bf_apoyo_escolar) de relevamiento_ee por Emaús
    bf_relevado_map: dict = {}
    if emaus_ids:
        bf_rows = (
            db.query(Relevamiento.emaus_id, func.coalesce(func.sum(RelevamientoEE.bf_apoyo_escolar), 0))
            .join(RelevamientoEE, RelevamientoEE.relevamiento_id == Relevamiento.id)
            .filter(
                Relevamiento.anio == anio,
                Relevamiento.semestre == semestre,
                Relevamiento.emaus_id.in_(emaus_ids),
            )
            .group_by(Relevamiento.emaus_id)
            .all()
        )
        bf_relevado_map = {r[0]: int(r[1]) for r in bf_rows}

    result = []
    for ctrl, emaus in rows:
        out = build_control_out(ctrl, emaus)
        out["btu_relevado"] = btu_relevado_map.get(ctrl.emaus_id, 0)
        out["bf_relevado"] = bf_relevado_map.get(ctrl.emaus_id, 0)
        result.append(out)
    return result


@router.get("/sync/estado")
def sync_estado(current_user: Usuario = Depends(require_rol("admin", "responsable"))):
    """Último estado del proceso de sync."""
    from app.database import engine as db_engine
    from sqlalchemy import text as sa_text
    with db_engine.connect() as conn:
        row = conn.execute(sa_text("""
            SELECT id, iniciado_en, finalizado_en, estado, ok_count, err_count, skip_count
            FROM sync_estado ORDER BY id DESC LIMIT 1
        """)).fetchone()
    if not row:
        return {"estado": "nunca", "iniciado_en": None}
    return {
        "estado":        row.estado,
        "iniciado_en":   row.iniciado_en.isoformat() if row.iniciado_en else None,
        "finalizado_en": row.finalizado_en.isoformat() if row.finalizado_en else None,
        "ok_count":      row.ok_count,
        "err_count":     row.err_count,
        "skip_count":    row.skip_count,
    }


@router.get("/{emaus_id}", response_model=ControlDetalleOut)
def detalle_control(
    emaus_id: int,
    anio: int = ANIO_ACTIVO,
    semestre: str = SEMESTRE_ACTIVO,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_rol("admin", "responsable")),
):
    allowed_ids = emaus_ids_for_user(current_user, db)
    if allowed_ids is not None and emaus_id not in allowed_ids:
        raise HTTPException(status_code=403, detail="Sin acceso a este Emaús")

    ctrl = db.query(ControlRelevamiento).filter(
        ControlRelevamiento.emaus_id == emaus_id,
        ControlRelevamiento.anio == anio,
        ControlRelevamiento.semestre == semestre,
    ).first()
    if not ctrl:
        raise HTTPException(status_code=404, detail="Sin datos de control para este Emaús")

    emaus = db.query(Emaus).filter(Emaus.id == emaus_id).first()

    validaciones = db.query(ControlValidacionDetalle).filter(
        ControlValidacionDetalle.emaus_id == emaus_id,
        ControlValidacionDetalle.anio == anio,
        ControlValidacionDetalle.semestre == semestre,
        ControlValidacionDetalle.resuelto == False,
    ).order_by(ControlValidacionDetalle.severity, ControlValidacionDetalle.hoja_nombre).all()

    out = build_control_out(ctrl, emaus)
    out["validaciones"] = validaciones
    return out


@router.patch("/{emaus_id}/aprobar")
def aprobar_emaus(
    emaus_id: int,
    body: AprobarRequest,
    anio: int = ANIO_ACTIVO,
    semestre: str = SEMESTRE_ACTIVO,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_rol("admin", "responsable")),
):
    if body.estado not in ("aprobado", "rechazado"):
        raise HTTPException(status_code=400, detail="estado debe ser 'aprobado' o 'rechazado'")

    allowed_ids = emaus_ids_for_user(current_user, db)
    if allowed_ids is not None and emaus_id not in allowed_ids:
        raise HTTPException(status_code=403, detail="Sin acceso a este Emaús")

    ctrl = db.query(ControlRelevamiento).filter(
        ControlRelevamiento.emaus_id == emaus_id,
        ControlRelevamiento.anio == anio,
        ControlRelevamiento.semestre == semestre,
    ).first()
    if not ctrl:
        raise HTTPException(status_code=404, detail="Sin datos de control")

    if body.estado == "aprobado" and not is_listo(ctrl):
        raise HTTPException(status_code=400, detail="El Emaús aún tiene hojas pendientes o con errores")

    aprobacion = db.query(ControlAprobacion).filter(
        ControlAprobacion.emaus_id == emaus_id,
        ControlAprobacion.anio == anio,
        ControlAprobacion.semestre == semestre,
    ).first()

    if not aprobacion:
        aprobacion = ControlAprobacion(emaus_id=emaus_id, anio=anio, semestre=semestre)
        db.add(aprobacion)

    aprobacion.estado = body.estado
    aprobacion.aprobado_por = current_user.id
    aprobacion.observaciones = body.observaciones
    aprobacion.fecha_aprobacion = datetime.utcnow()
    db.commit()

    return {"ok": True, "estado": body.estado}


@router.post("/sync")
def trigger_sync(
    anio: int = ANIO_ACTIVO,
    semestre: str = SEMESTRE_ACTIVO,
    emaus_id: Optional[int] = None,
    current_user: Usuario = Depends(require_rol("admin")),
):
    """
    En Lambda: invoca la misma función de forma asíncrona (InvokeAsync) para
    que el scraper corra sin límite de timeout de API Gateway.
    En local: corre directamente (útil para desarrollo).
    """
    import os, json
    folder_id = os.getenv("DRIVE_FOLDER_ID", "")
    if not folder_id:
        raise HTTPException(status_code=500, detail="DRIVE_FOLDER_ID no configurado")

    lambda_name = os.getenv("AWS_LAMBDA_FUNCTION_NAME", "")
    if lambda_name:
        # En Lambda: invocar asíncronamente para que corra sin límite de API Gateway
        import boto3, json
        payload = {"source": "manual-sync", "anio": anio, "semestre": semestre, "apply_reset": True}
        if emaus_id:
            payload["emaus_id"] = emaus_id
        boto3.client("lambda", region_name=os.getenv("AWS_REGION", "us-east-1")).invoke(
            FunctionName=lambda_name,
            InvocationType="Event",
            Payload=json.dumps(payload).encode(),
        )
    else:
        # Local: thread en background
        import threading
        from scripts.scraper_control import run_sync
        threading.Thread(
            target=run_sync,
            args=(folder_id, anio, semestre, emaus_id),
            kwargs={"apply_reset": True},
            daemon=True,
        ).start()

    return {"ok": True, "message": "Sync iniciado"}
