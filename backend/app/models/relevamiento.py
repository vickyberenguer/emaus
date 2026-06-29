from sqlalchemy import Column, Integer, String, Boolean, Enum, ForeignKey, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class EstadoEnum(str, enum.Enum):
    borrador = "borrador"
    enviado = "enviado"
    validado = "validado"
    rechazado = "rechazado"


class SemestreEnum(str, enum.Enum):
    primero = "1"
    segundo = "2"


class Relevamiento(Base):
    __tablename__ = "relevamiento"
    __table_args__ = (
        UniqueConstraint("emaus_id", "anio", "semestre", name="uq_relevamiento_periodo"),
    )

    id = Column(Integer, primary_key=True, index=True)
    emaus_id = Column(Integer, ForeignKey("emaus.id"), nullable=False)
    atl_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    anio = Column(Integer, nullable=False)
    semestre = Column(Enum(SemestreEnum, values_callable=lambda e: [m.value for m in e]), nullable=False)
    estado = Column(Enum(EstadoEnum, values_callable=lambda e: [m.value for m in e]), default=EstadoEnum.borrador, nullable=False)
    comentario_rechazo = Column(Text)
    creado_en = Column(DateTime, server_default=func.now())
    enviado_en = Column(DateTime)
    validado_en = Column(DateTime)

    emaus = relationship("Emaus", back_populates="relevamientos")
    atl = relationship("Usuario")
    pastoral_pi = relationship("PastoralPI", back_populates="relevamiento", uselist=False)
    relevamientos_ee = relationship("RelevamientoEE", back_populates="relevamiento")
    talleres = relationship("Taller", back_populates="relevamiento")
    establecimientos_articulados = relationship("EstablecimientoArticulado", back_populates="relevamiento")
