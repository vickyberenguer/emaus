from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Literal

from app.database import get_db
from app.models.usuario import Usuario, RolEnum
from app.models.relevamiento import Relevamiento, EstadoEnum, SemestreEnum
from app.models.emaus import Emaus, ResponsableEmaus
from app.routers.auth import get_current_user, require_rol

router = APIRouter(prefix="/relevamientos", tags=["relevamientos"])


# --- Schemas ---

class RelevamientoCreate(BaseModel):
    anio: int
    semestre: Literal["1", "2"]


class RelevamientoEstadoUpdate(BaseModel):
    accion: Literal["enviar", "validar", "rechazar"]
    comentario_rechazo: str | None = None


class RelevamientoResponse(BaseModel):
    id: int
    emaus_id: int
    atl_id: int
    anio: int
    semestre: str
    estado: str
    comentario_rechazo: str | None
    creado_en: datetime | None
    enviado_en: datetime | None
    validado_en: datetime | None

    class Config:
        from_attributes = True


# --- Helpers ---

def _emaus_ids_responsable(db: Session, responsable_id: int) -> list[int]:
    rows = db.query(ResponsableEmaus.emaus_id).filter(
        ResponsableEmaus.responsable_id == responsable_id
    ).all()
    return [r[0] for r in rows]


def get_relevamiento_or_404(db: Session, relevamiento_id: int) -> Relevamiento:
    relevamiento = db.query(Relevamiento).filter(Relevamiento.id == relevamiento_id).first()
    if not relevamiento:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relevamiento no encontrado")
    return relevamiento


# Alias interno usado por los endpoints de este mismo módulo
_get_relevamiento_or_404 = get_relevamiento_or_404


def check_acceso_lectura(relevamiento: Relevamiento, current_user: Usuario, db: Session):
    if current_user.rol == "admin":
        return
    if current_user.rol == "atl":
        if relevamiento.emaus_id != current_user.emaus_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenés acceso a este relevamiento")
        return
    if current_user.rol == "responsable":
        if relevamiento.emaus_id not in _emaus_ids_responsable(db, current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenés acceso a este relevamiento")
        return


_check_acceso_lectura = check_acceso_lectura


def check_acceso_escritura(relevamiento: Relevamiento, current_user: Usuario):
    """Solo el ATL dueño del relevamiento (mientras está en borrador) o un admin pueden editar sus secciones."""
    if current_user.rol == "admin":
        return
    if current_user.rol == "atl" and relevamiento.emaus_id == current_user.emaus_id:
        if relevamiento.estado != EstadoEnum.borrador:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se puede editar un relevamiento en borrador",
            )
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenés permiso para editar este relevamiento")


# --- Endpoints ---

@router.get("", response_model=list[RelevamientoResponse])
def listar_relevamientos(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Relevamiento)

    if current_user.rol == "atl":
        query = query.filter(Relevamiento.emaus_id == current_user.emaus_id)
    elif current_user.rol == "responsable":
        emaus_ids = _emaus_ids_responsable(db, current_user.id)
        query = query.filter(Relevamiento.emaus_id.in_(emaus_ids))
    # admin ve todo, sin filtro

    return query.order_by(Relevamiento.anio.desc(), Relevamiento.semestre.desc()).all()


class GenerarRelevamientosResponse(BaseModel):
    creados: int
    ya_existian: int
    sin_atl: list[str]


@router.post("/generar", response_model=GenerarRelevamientosResponse, dependencies=[Depends(require_rol("admin"))])
def generar_relevamientos_periodo(
    body: RelevamientoCreate,
    db: Session = Depends(get_db),
):
    """El admin abre el período: crea un relevamiento en borrador para cada Emaús activo que tenga un ATL asignado."""
    emaus_activos = db.query(Emaus).filter(Emaus.activo == True).all()
    semestre = SemestreEnum(body.semestre)

    creados = 0
    ya_existian = 0
    sin_atl = []

    for emaus in emaus_activos:
        atl = db.query(Usuario).filter(Usuario.emaus_id == emaus.id, Usuario.rol == RolEnum.atl, Usuario.activo == True).first()
        if not atl:
            sin_atl.append(emaus.nombre)
            continue

        existe = db.query(Relevamiento).filter(
            Relevamiento.emaus_id == emaus.id, Relevamiento.anio == body.anio, Relevamiento.semestre == semestre,
        ).first()
        if existe:
            ya_existian += 1
            continue

        db.add(Relevamiento(emaus_id=emaus.id, atl_id=atl.id, anio=body.anio, semestre=semestre, estado=EstadoEnum.borrador))
        creados += 1

    db.commit()
    return GenerarRelevamientosResponse(creados=creados, ya_existian=ya_existian, sin_atl=sin_atl)


@router.get("/{relevamiento_id}", response_model=RelevamientoResponse)
def detalle_relevamiento(
    relevamiento_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    relevamiento = _get_relevamiento_or_404(db, relevamiento_id)
    _check_acceso_lectura(relevamiento, current_user, db)
    return relevamiento


@router.put("/{relevamiento_id}/estado", response_model=RelevamientoResponse)
def cambiar_estado_relevamiento(
    relevamiento_id: int,
    body: RelevamientoEstadoUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    relevamiento = _get_relevamiento_or_404(db, relevamiento_id)
    ahora = datetime.now(timezone.utc)

    if body.accion == "enviar":
        puede = current_user.rol == "admin" or (
            current_user.rol == "atl" and relevamiento.emaus_id == current_user.emaus_id
        )
        if not puede:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenés permiso para enviar este relevamiento")
        if relevamiento.estado != EstadoEnum.borrador and current_user.rol != "admin":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Solo se puede enviar un relevamiento en borrador")
        relevamiento.estado = EstadoEnum.enviado
        relevamiento.enviado_en = ahora

    elif body.accion == "validar":
        puede = current_user.rol == "admin" or (
            current_user.rol == "responsable" and relevamiento.emaus_id in _emaus_ids_responsable(db, current_user.id)
        )
        if not puede:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenés permiso para validar este relevamiento")
        if relevamiento.estado != EstadoEnum.enviado and current_user.rol != "admin":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Solo se puede validar un relevamiento enviado")
        relevamiento.estado = EstadoEnum.validado
        relevamiento.validado_en = ahora

    elif body.accion == "rechazar":
        puede = current_user.rol == "admin" or (
            current_user.rol == "responsable" and relevamiento.emaus_id in _emaus_ids_responsable(db, current_user.id)
        )
        if not puede:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenés permiso para rechazar este relevamiento")
        if relevamiento.estado != EstadoEnum.enviado and current_user.rol != "admin":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Solo se puede rechazar un relevamiento enviado")
        if not body.comentario_rechazo:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El rechazo requiere un comentario")
        relevamiento.estado = EstadoEnum.borrador
        relevamiento.comentario_rechazo = body.comentario_rechazo

    db.commit()
    db.refresh(relevamiento)
    return relevamiento
