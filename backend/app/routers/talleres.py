from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.usuario import Usuario
from app.models.taller import Taller
from app.routers.auth import get_current_user
from app.routers.relevamientos import get_relevamiento_or_404, check_acceso_lectura, check_acceso_escritura

router = APIRouter(prefix="/relevamientos/{relevamiento_id}/talleres", tags=["talleres"])


class TallerUpdate(BaseModel):
    eje: str
    tematica: str
    cantidad_participantes: int | None = None
    cantidad_ee: int | None = None
    cantidad_comunidades_pi: int | None = None
    otras_instituciones: str | None = None
    perfil_capacitadores: str | None = None


class TallerResponse(TallerUpdate):
    id: int
    relevamiento_id: int

    class Config:
        from_attributes = True


def _get_taller_or_404(db: Session, relevamiento_id: int, taller_id: int) -> Taller:
    taller = db.query(Taller).filter(
        Taller.id == taller_id, Taller.relevamiento_id == relevamiento_id
    ).first()
    if not taller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Taller no encontrado")
    return taller


@router.get("", response_model=list[TallerResponse])
def listar_talleres(
    relevamiento_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    relevamiento = get_relevamiento_or_404(db, relevamiento_id)
    check_acceso_lectura(relevamiento, current_user, db)
    return db.query(Taller).filter(Taller.relevamiento_id == relevamiento_id).all()


@router.post("", response_model=TallerResponse, status_code=status.HTTP_201_CREATED)
def crear_taller(
    relevamiento_id: int,
    body: TallerUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    relevamiento = get_relevamiento_or_404(db, relevamiento_id)
    check_acceso_escritura(relevamiento, current_user)

    taller = Taller(relevamiento_id=relevamiento_id, **body.model_dump())
    db.add(taller)
    db.commit()
    db.refresh(taller)
    return taller


@router.put("/{taller_id}", response_model=TallerResponse)
def actualizar_taller(
    relevamiento_id: int,
    taller_id: int,
    body: TallerUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    relevamiento = get_relevamiento_or_404(db, relevamiento_id)
    check_acceso_escritura(relevamiento, current_user)
    taller = _get_taller_or_404(db, relevamiento_id, taller_id)

    for field, value in body.model_dump().items():
        setattr(taller, field, value)

    db.commit()
    db.refresh(taller)
    return taller


@router.delete("/{taller_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_taller(
    relevamiento_id: int,
    taller_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    relevamiento = get_relevamiento_or_404(db, relevamiento_id)
    check_acceso_escritura(relevamiento, current_user)
    taller = _get_taller_or_404(db, relevamiento_id, taller_id)

    db.delete(taller)
    db.commit()
