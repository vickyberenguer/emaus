from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Literal

from app.database import get_db
from app.models.usuario import Usuario
from app.models.relevamiento import Relevamiento, EstadoEnum, SemestreEnum
from app.models.emaus import ResponsableEmaus
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


def _get_relevamiento_or_404(db: Session, relevamiento_id: int) -> Relevamiento:
    relevamiento = db.query(Relevamiento).filter(Relevamiento.id == relevamiento_id).first()
    if not relevamiento:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relevamiento no encontrado")
    return relevamiento


def _check_acceso_lectura(relevamiento: Relevamiento, current_user: Usuario, db: Session):
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


@router.post("", response_model=RelevamientoResponse, status_code=status.HTTP_201_CREATED)
def crear_relevamiento(
    body: RelevamientoCreate,
    current_user: Usuario = Depends(require_rol("atl")),
    db: Session = Depends(get_db),
):
    if not current_user.emaus_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tu usuario no tiene un Emaús asignado",
        )

    relevamiento = Relevamiento(
        emaus_id=current_user.emaus_id,
        atl_id=current_user.id,
        anio=body.anio,
        semestre=SemestreEnum(body.semestre),
        estado=EstadoEnum.borrador,
    )
    db.add(relevamiento)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un relevamiento para ese Emaús en ese período",
        )
    db.refresh(relevamiento)
    return relevamiento


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
