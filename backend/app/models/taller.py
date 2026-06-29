from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Taller(Base):
    __tablename__ = "taller"

    id = Column(Integer, primary_key=True, index=True)
    relevamiento_id = Column(Integer, ForeignKey("relevamiento.id"), nullable=False)
    eje = Column(String(100), nullable=False)
    tematica = Column(String(200), nullable=False)
    cantidad_participantes = Column(Integer)
    cantidad_ee = Column(Integer)
    cantidad_comunidades_pi = Column(Integer)
    otras_instituciones = Column(String(500))
    perfil_capacitadores = Column(String(500))

    relevamiento = relationship("Relevamiento", back_populates="talleres")
