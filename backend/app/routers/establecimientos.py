from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.usuario import Usuario
from app.models.establecimiento import EstablecimientoEstado, EstablecimientoArticulado
from app.routers.auth import get_current_user
from app.routers.relevamientos import get_relevamiento_or_404, check_acceso_lectura, check_acceso_escritura

router = APIRouter(tags=["establecimientos"])


class ArticulacionItem(BaseModel):
    establecimiento_id: int
    accion_institucion: bool = False
    accion_articulacion_alfa: bool = False
    accion_seguimiento: bool = False
    accion_intercambio: bool = False
    accion_otros: bool = False
    detalle_otros: str | None = None


class ArticulacionResponse(ArticulacionItem):
    id: int
    relevamiento_id: int
    nombre: str | None = None
    jurisdiccion: str | None = None
    localidad: str | None = None

    class Config:
        from_attributes = True


class EstablecimientoBusqueda(BaseModel):
    id: int
    cueanexo: str
    nombre: str | None
    jurisdiccion: str | None
    localidad: str | None
    domicilio: str | None

    class Config:
        from_attributes = True


@router.get("/establecimientos", response_model=list[EstablecimientoBusqueda])
def buscar_establecimientos(
    q: str = Query(..., min_length=3, description="Texto a buscar en el nombre del establecimiento"),
    jurisdiccion: str | None = None,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(EstablecimientoEstado).filter(EstablecimientoEstado.nombre.ilike(f"%{q}%"))
    if jurisdiccion:
        query = query.filter(EstablecimientoEstado.jurisdiccion == jurisdiccion)
    return query.limit(50).all()


@router.get("/relevamientos/{relevamiento_id}/establecimientos", response_model=list[ArticulacionResponse])
def listar_establecimientos_articulados(
    relevamiento_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    relevamiento = get_relevamiento_or_404(db, relevamiento_id)
    check_acceso_lectura(relevamiento, current_user, db)

    rows = db.query(EstablecimientoArticulado).filter(
        EstablecimientoArticulado.relevamiento_id == relevamiento_id
    ).all()
    resultado = []
    for r in rows:
        resultado.append(ArticulacionResponse(
            id=r.id,
            relevamiento_id=r.relevamiento_id,
            establecimiento_id=r.establecimiento_id,
            accion_institucion=r.accion_institucion,
            accion_articulacion_alfa=r.accion_articulacion_alfa,
            accion_seguimiento=r.accion_seguimiento,
            accion_intercambio=r.accion_intercambio,
            accion_otros=r.accion_otros,
            detalle_otros=r.detalle_otros,
            nombre=r.establecimiento.nombre if r.establecimiento else None,
            jurisdiccion=r.establecimiento.jurisdiccion if r.establecimiento else None,
            localidad=r.establecimiento.localidad if r.establecimiento else None,
        ))
    return resultado


@router.put("/relevamientos/{relevamiento_id}/establecimientos", response_model=list[ArticulacionResponse])
def guardar_establecimientos_articulados(
    relevamiento_id: int,
    body: list[ArticulacionItem],
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    relevamiento = get_relevamiento_or_404(db, relevamiento_id)
    check_acceso_escritura(relevamiento, current_user)

    db.query(EstablecimientoArticulado).filter(
        EstablecimientoArticulado.relevamiento_id == relevamiento_id
    ).delete()

    nuevos = []
    for item in body:
        articulado = EstablecimientoArticulado(relevamiento_id=relevamiento_id, **item.model_dump())
        db.add(articulado)
        nuevos.append(articulado)

    db.commit()
    for a in nuevos:
        db.refresh(a)

    return [ArticulacionResponse(
        id=a.id,
        relevamiento_id=a.relevamiento_id,
        establecimiento_id=a.establecimiento_id,
        accion_institucion=a.accion_institucion,
        accion_articulacion_alfa=a.accion_articulacion_alfa,
        accion_seguimiento=a.accion_seguimiento,
        accion_intercambio=a.accion_intercambio,
        accion_otros=a.accion_otros,
        detalle_otros=a.detalle_otros,
        nombre=a.establecimiento.nombre if a.establecimiento else None,
        jurisdiccion=a.establecimiento.jurisdiccion if a.establecimiento else None,
        localidad=a.establecimiento.localidad if a.establecimiento else None,
    ) for a in nuevos]
