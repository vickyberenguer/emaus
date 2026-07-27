from sqlalchemy import (
    Column, BigInteger, Integer, SmallInteger, String, Boolean, Date, Text,
    ForeignKey, UniqueConstraint, DateTime,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class BtuBecario(Base):
    __tablename__ = "btu_becario"
    __table_args__ = (
        UniqueConstraint("dni", "anio", name="uq_btu_becario_dni_anio"),
    )

    id = Column(BigInteger, primary_key=True, index=True)
    emaus_id = Column(Integer, ForeignKey("emaus.id"), nullable=False)
    anio = Column(SmallInteger, nullable=False)
    diocesis_nombre_hoja = Column(String(100))
    nro = Column(String(20))
    observaciones = Column(Text)
    certificados = Column(String(100))
    apellido_nombres = Column(String(200), nullable=False)
    dni = Column(String(20))
    sexo = Column(String(20))
    fecha_nacimiento = Column(Date)
    edad = Column(SmallInteger)
    percibe_progresar = Column(Boolean)
    institucion = Column(String(200))
    nivel = Column(String(20))
    ambito = Column(String(20))
    carrera = Column(String(200))
    rama = Column(String(50))
    duracion_carrera = Column(String(20))
    anio_comienzo_carrera = Column(String(10))
    anio_comienzo_beca = Column(String(10))
    anio_cursando = Column(String(10))
    continua_periodo_siguiente = Column(Boolean)
    motivo_baja = Column(String(200))
    mes_comienzo_beca = Column(String(20))
    mes_fin_beca = Column(String(20))
    activo = Column(Boolean, default=True)
    creado_en = Column(DateTime, server_default=func.now())
    actualizado_en = Column(DateTime, server_default=func.now(), onupdate=func.now())

    emaus = relationship("Emaus")
    meses = relationship("BtuBecarioMes", back_populates="becario", cascade="all, delete-orphan")


class BtuBecarioMes(Base):
    __tablename__ = "btu_becario_mes"
    __table_args__ = (
        UniqueConstraint("btu_becario_id", "mes", name="uq_btu_becario_mes"),
    )

    id = Column(BigInteger, primary_key=True, index=True)
    btu_becario_id = Column(BigInteger, ForeignKey("btu_becario.id", ondelete="CASCADE"), nullable=False)
    mes = Column(String(20), nullable=False)
    valor = Column(String(50))

    becario = relationship("BtuBecario", back_populates="meses")
