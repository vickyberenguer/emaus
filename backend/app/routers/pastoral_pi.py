from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.usuario import Usuario
from app.models.pastoral_pi import (
    PastoralPI,
    PastoralPIEnfermedadNinos,
    PastoralPIEnfermedadEmbarazadas,
    PastoralPIAccionLider,
    PastoralPITematica,
    PastoralPIArticulacion,
)
from app.routers.auth import get_current_user
from app.routers.relevamientos import get_relevamiento_or_404, check_acceso_lectura, check_acceso_escritura

router = APIRouter(prefix="/relevamientos/{relevamiento_id}/pastoral-pi", tags=["pastoral-pi"])


# --- Schemas ---

class EnfermedadItem(BaseModel):
    enfermedad: str
    enfermedad_otra: str | None = None
    orden: int | None = None


class AccionLiderItem(BaseModel):
    accion: str  # celebracion_vida | visita_domiciliaria | reunion_evaluacion
    realiza: bool = False
    frecuencia: str | None = None
    cantidad_semestre: int | None = None


class TematicaItem(BaseModel):
    tematica: str
    tematica_otra: str | None = None
    comunidades_cantidad: int | None = None


class ArticulacionItem(BaseModel):
    organizacion: str
    organizacion_otra: str | None = None


class PastoralPIUpdate(BaseModel):
    anios_desarrollo: int | None = None
    presento_metodologia: bool | None = None
    comunidades_sin_pastoral: int | None = None
    capacitadoras: int | None = None
    lideres: int | None = None
    madres_embarazadas_12_18: int | None = None
    madres_embarazadas_19_29: int | None = None
    madres_embarazadas_30_mas: int | None = None
    madres_no_embarazadas: int | None = None
    ninos_0_3: int | None = None
    ninos_4_6: int | None = None
    familias: int | None = None
    lideres_todas_alfabetizadas: bool | None = None
    lideres_no_alfabetizadas_cantidad: int | None = None
    lideres_en_alfabetizacion: bool | None = None
    madres_todas_alfabetizadas: bool | None = None
    madres_no_alfabetizadas_cantidad: int | None = None
    madres_en_alfabetizacion: bool | None = None

    enfermedades_ninos: list[EnfermedadItem] = []
    enfermedades_embarazadas: list[EnfermedadItem] = []
    acciones_lider: list[AccionLiderItem] = []
    tematicas: list[TematicaItem] = []
    articulaciones: list[ArticulacionItem] = []


class PastoralPIResponse(PastoralPIUpdate):
    id: int
    relevamiento_id: int

    class Config:
        from_attributes = True


SCALAR_FIELDS = [
    "anios_desarrollo", "presento_metodologia", "comunidades_sin_pastoral",
    "capacitadoras", "lideres", "madres_embarazadas_12_18", "madres_embarazadas_19_29",
    "madres_embarazadas_30_mas", "madres_no_embarazadas", "ninos_0_3", "ninos_4_6",
    "familias", "lideres_todas_alfabetizadas", "lideres_no_alfabetizadas_cantidad",
    "lideres_en_alfabetizacion", "madres_todas_alfabetizadas",
    "madres_no_alfabetizadas_cantidad", "madres_en_alfabetizacion",
]


# --- Endpoints ---

@router.get("", response_model=PastoralPIResponse | None)
def obtener_pastoral_pi(
    relevamiento_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    relevamiento = get_relevamiento_or_404(db, relevamiento_id)
    check_acceso_lectura(relevamiento, current_user, db)
    return db.query(PastoralPI).filter(PastoralPI.relevamiento_id == relevamiento_id).first()


@router.put("", response_model=PastoralPIResponse)
def guardar_pastoral_pi(
    relevamiento_id: int,
    body: PastoralPIUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    relevamiento = get_relevamiento_or_404(db, relevamiento_id)
    check_acceso_escritura(relevamiento, current_user)

    pastoral = db.query(PastoralPI).filter(PastoralPI.relevamiento_id == relevamiento_id).first()
    if not pastoral:
        pastoral = PastoralPI(relevamiento_id=relevamiento_id)
        db.add(pastoral)
        db.flush()

    for field in SCALAR_FIELDS:
        setattr(pastoral, field, getattr(body, field))

    db.query(PastoralPIEnfermedadNinos).filter(PastoralPIEnfermedadNinos.pastoral_pi_id == pastoral.id).delete()
    for item in body.enfermedades_ninos:
        db.add(PastoralPIEnfermedadNinos(pastoral_pi_id=pastoral.id, **item.model_dump()))

    db.query(PastoralPIEnfermedadEmbarazadas).filter(PastoralPIEnfermedadEmbarazadas.pastoral_pi_id == pastoral.id).delete()
    for item in body.enfermedades_embarazadas:
        db.add(PastoralPIEnfermedadEmbarazadas(pastoral_pi_id=pastoral.id, **item.model_dump()))

    db.query(PastoralPIAccionLider).filter(PastoralPIAccionLider.pastoral_pi_id == pastoral.id).delete()
    for item in body.acciones_lider:
        db.add(PastoralPIAccionLider(pastoral_pi_id=pastoral.id, **item.model_dump()))

    db.query(PastoralPITematica).filter(PastoralPITematica.pastoral_pi_id == pastoral.id).delete()
    for item in body.tematicas:
        db.add(PastoralPITematica(pastoral_pi_id=pastoral.id, **item.model_dump()))

    db.query(PastoralPIArticulacion).filter(PastoralPIArticulacion.pastoral_pi_id == pastoral.id).delete()
    for item in body.articulaciones:
        db.add(PastoralPIArticulacion(pastoral_pi_id=pastoral.id, **item.model_dump()))

    db.commit()
    db.refresh(pastoral)
    return pastoral
