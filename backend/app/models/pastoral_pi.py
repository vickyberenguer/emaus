from sqlalchemy import Column, Integer, String, Boolean, Enum, ForeignKey, SmallInteger
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class AccionLiderEnum(str, enum.Enum):
    celebracion_vida = "celebracion_vida"
    visita_domiciliaria = "visita_domiciliaria"
    reunion_evaluacion = "reunion_evaluacion"


class PastoralPI(Base):
    __tablename__ = "pastoral_pi"

    id = Column(Integer, primary_key=True, index=True)
    relevamiento_id = Column(Integer, ForeignKey("relevamiento.id"), nullable=False, unique=True)
    anios_desarrollo = Column(Integer)
    comunidades_total = Column(Integer)
    presento_metodologia = Column(Boolean)
    comunidades_sin_pastoral = Column(Integer)
    capacitadoras = Column(Integer)
    lideres = Column(Integer)
    madres_embarazadas_12_18 = Column(Integer)
    madres_embarazadas_19_29 = Column(Integer)
    madres_embarazadas_30_mas = Column(Integer)
    madres_no_embarazadas = Column(Integer)
    ninos_0_3 = Column(Integer)
    ninos_4_6 = Column(Integer)
    familias = Column(Integer)
    lideres_todas_alfabetizadas = Column(Boolean)
    lideres_no_alfabetizadas_cantidad = Column(Integer)
    lideres_en_alfabetizacion = Column(Boolean)
    madres_todas_alfabetizadas = Column(Boolean)
    madres_no_alfabetizadas_cantidad = Column(Integer)
    madres_en_alfabetizacion = Column(Boolean)

    relevamiento = relationship("Relevamiento", back_populates="pastoral_pi")
    enfermedades_ninos = relationship("PastoralPIEnfermedadNinos", back_populates="pastoral_pi")
    enfermedades_embarazadas = relationship("PastoralPIEnfermedadEmbarazadas", back_populates="pastoral_pi")
    acciones_lider = relationship("PastoralPIAccionLider", back_populates="pastoral_pi")
    tematicas = relationship("PastoralPITematica", back_populates="pastoral_pi")
    articulaciones = relationship("PastoralPIArticulacion", back_populates="pastoral_pi")


class PastoralPIEnfermedadNinos(Base):
    __tablename__ = "pastoral_pi_enfermedad_ninos"

    id = Column(Integer, primary_key=True, index=True)
    pastoral_pi_id = Column(Integer, ForeignKey("pastoral_pi.id"), nullable=False)
    enfermedad = Column(String(200), nullable=False)
    enfermedad_otra = Column(String(200))
    orden = Column(SmallInteger)

    pastoral_pi = relationship("PastoralPI", back_populates="enfermedades_ninos")


class PastoralPIEnfermedadEmbarazadas(Base):
    __tablename__ = "pastoral_pi_enfermedad_embarazadas"

    id = Column(Integer, primary_key=True, index=True)
    pastoral_pi_id = Column(Integer, ForeignKey("pastoral_pi.id"), nullable=False)
    enfermedad = Column(String(200), nullable=False)
    enfermedad_otra = Column(String(200))
    orden = Column(SmallInteger)

    pastoral_pi = relationship("PastoralPI", back_populates="enfermedades_embarazadas")


class PastoralPIAccionLider(Base):
    __tablename__ = "pastoral_pi_accion_lider"

    id = Column(Integer, primary_key=True, index=True)
    pastoral_pi_id = Column(Integer, ForeignKey("pastoral_pi.id"), nullable=False)
    accion = Column(Enum(AccionLiderEnum), nullable=False)
    realiza = Column(Boolean, default=False)
    frecuencia = Column(String(100))
    cantidad_semestre = Column(Integer)

    pastoral_pi = relationship("PastoralPI", back_populates="acciones_lider")


class PastoralPITematica(Base):
    __tablename__ = "pastoral_pi_tematica"

    id = Column(Integer, primary_key=True, index=True)
    pastoral_pi_id = Column(Integer, ForeignKey("pastoral_pi.id"), nullable=False)
    tematica = Column(String(200), nullable=False)
    tematica_otra = Column(String(200))
    comunidades_cantidad = Column(Integer)

    pastoral_pi = relationship("PastoralPI", back_populates="tematicas")


class PastoralPIArticulacion(Base):
    __tablename__ = "pastoral_pi_articulacion"

    id = Column(Integer, primary_key=True, index=True)
    pastoral_pi_id = Column(Integer, ForeignKey("pastoral_pi.id"), nullable=False)
    organizacion = Column(String(200), nullable=False)
    organizacion_otra = Column(String(200))

    pastoral_pi = relationship("PastoralPI", back_populates="articulaciones")
