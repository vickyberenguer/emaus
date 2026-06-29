from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.usuario import Usuario
from app.models.catalogo import Catalogo
from app.routers.auth import get_current_user

router = APIRouter(prefix="/catalogos", tags=["catalogos"])


class CatalogoItemResponse(BaseModel):
    id: int
    valor: str

    class Config:
        from_attributes = True


@router.get("/{categoria}", response_model=list[CatalogoItemResponse])
def listar_catalogo_activo(
    categoria: str,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Catálogo de solo lectura para los formularios (cualquier usuario autenticado)."""
    return db.query(Catalogo).filter(
        Catalogo.categoria == categoria, Catalogo.activo == True
    ).order_by(Catalogo.orden).all()
