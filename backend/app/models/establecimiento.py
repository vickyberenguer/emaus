from sqlalchemy import Column, Integer, String, Boolean, Date, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class EstablecimientoEstado(Base):
    __tablename__ = "establecimiento_estado"

    id = Column(Integer, primary_key=True, index=True)
    cueanexo = Column(String(50), nullable=False, unique=True, index=True)
    jurisdiccion = Column(String(100), index=True)
    sector = Column(String(50))
    ambito = Column(String(50))
    departamento = Column(String(200))
    cod_departamento = Column(String(50))
    localidad = Column(String(200), index=True)
    cod_localidad = Column(String(50))
    nombre = Column(String(500))
    domicilio = Column(String(500))
    codigo_postal = Column(String(20))
    telefono = Column(String(500))
    mail = Column(String(500))
    nivel_inicial_maternal = Column(Boolean, default=False)
    nivel_inicial_infantes = Column(Boolean, default=False)
    primario = Column(Boolean, default=False)
    secundario = Column(Boolean, default=False)
    adultos = Column(Boolean, default=False)
    formacion_profesional = Column(Boolean, default=False)
    alfabetizacion = Column(Boolean, default=False)
    actualizado_en = Column(Date)

    articulaciones = relationship("EstablecimientoArticulado", back_populates="establecimiento")


class EstablecimientoArticulado(Base):
    __tablename__ = "establecimiento_articulado"
    __table_args__ = (
        UniqueConstraint("relevamiento_id", "establecimiento_id", name="uq_establecimiento_articulado"),
    )

    id = Column(Integer, primary_key=True, index=True)
    relevamiento_id = Column(Integer, ForeignKey("relevamiento.id"), nullable=False)
    establecimiento_id = Column(Integer, ForeignKey("establecimiento_estado.id"), nullable=False)
    accion_institucion = Column(Boolean, default=False)
    accion_articulacion_alfa = Column(Boolean, default=False)
    accion_seguimiento = Column(Boolean, default=False)
    accion_intercambio = Column(Boolean, default=False)
    accion_otros = Column(Boolean, default=False)
    detalle_otros = Column(Text)

    relevamiento = relationship("Relevamiento", back_populates="establecimientos_articulados")
    establecimiento = relationship("EstablecimientoEstado", back_populates="articulaciones")
