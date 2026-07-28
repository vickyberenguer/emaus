from sqlalchemy import Column, BigInteger, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class RelevamientoTaller(Base):
    __tablename__ = "relevamiento_taller"

    id = Column(BigInteger, primary_key=True, index=True)
    relevamiento_id = Column(Integer, ForeignKey("relevamiento.id"), nullable=False)
    eje = Column(String(100))
    tematica = Column(String(300))
    rubro_tematico = Column(String(100))
    cantidad_participantes = Column(Integer)
    cantidad_espacios_educativos = Column(Integer)
    cantidad_comunidades_pi = Column(Integer)
    otras_instituciones = Column(Integer)
    perfil_capacitadores_texto = Column(String(500))

    relevamiento = relationship("Relevamiento")
    perfiles = relationship("RelevamientoTallerPerfil", back_populates="taller", cascade="all, delete-orphan")


class RelevamientoTallerPerfil(Base):
    __tablename__ = "relevamiento_taller_perfil"

    id = Column(BigInteger, primary_key=True, index=True)
    taller_id = Column(BigInteger, ForeignKey("relevamiento_taller.id", ondelete="CASCADE"), nullable=False)
    perfil = Column(String(100), nullable=False)

    taller = relationship("RelevamientoTaller", back_populates="perfiles")
