from sqlalchemy import Column, Integer, String, Boolean
from app.database import Base


class Catalogo(Base):
    __tablename__ = "catalogo"

    id = Column(Integer, primary_key=True, index=True)
    categoria = Column(String(100), nullable=False, index=True)
    valor = Column(String(200), nullable=False)
    activo = Column(Boolean, default=True)
    orden = Column(Integer, default=0)
