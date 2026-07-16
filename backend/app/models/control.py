from sqlalchemy import Column, Integer, SmallInteger, String, Boolean, DateTime, BigInteger, Text, Enum, ForeignKey, ForeignKeyConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class ControlRelevamiento(Base):
    __tablename__ = "control_relevamiento"

    emaus_id = Column(Integer, ForeignKey("emaus.id"), primary_key=True)
    anio = Column(SmallInteger, primary_key=True)
    semestre = Column(String(1), primary_key=True)

    ee_count = Column(Integer, nullable=False, default=0)
    ee_declarados_completos = Column(Integer, nullable=False, default=0)
    ee_pendientes = Column(Integer, nullable=False, default=0)
    ee_con_errores = Column(Integer, nullable=False, default=0)

    pi_existe = Column(Boolean, nullable=False, default=False)
    pi_completa = Column(Boolean, nullable=False, default=False)
    pi_con_errores = Column(Boolean, nullable=False, default=False)

    talleres_completo = Column(Boolean, nullable=False, default=False)
    establecimientos_completo = Column(Boolean, nullable=False, default=False)

    total_asistentes_ee = Column(Integer, nullable=False, default=0)
    cantidad_talleres = Column(Integer, nullable=False, default=0)
    cantidad_establecimientos = Column(Integer, nullable=False, default=0)
    btu_actual = Column(Integer, nullable=True)
    bf_actual = Column(Integer, nullable=True)

    ultimo_sync = Column(DateTime, nullable=False)

    emaus = relationship("Emaus", foreign_keys=[emaus_id])
    validaciones = relationship(
        "ControlValidacionDetalle",
        primaryjoin="and_(ControlRelevamiento.emaus_id==ControlValidacionDetalle.emaus_id, "
                    "ControlRelevamiento.anio==ControlValidacionDetalle.anio, "
                    "ControlRelevamiento.semestre==ControlValidacionDetalle.semestre)",
        foreign_keys="[ControlValidacionDetalle.emaus_id, ControlValidacionDetalle.anio, ControlValidacionDetalle.semestre]",
    )
    aprobacion = relationship(
        "ControlAprobacion",
        primaryjoin="and_(ControlRelevamiento.emaus_id==ControlAprobacion.emaus_id, "
                    "ControlRelevamiento.anio==ControlAprobacion.anio, "
                    "ControlRelevamiento.semestre==ControlAprobacion.semestre)",
        foreign_keys="[ControlAprobacion.emaus_id, ControlAprobacion.anio, ControlAprobacion.semestre]",
        uselist=False,
    )


class ControlValidacionDetalle(Base):
    __tablename__ = "control_validacion_detalle"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    emaus_id = Column(Integer, nullable=False)
    anio = Column(SmallInteger, nullable=False)
    semestre = Column(String(1), nullable=False)
    hoja_nombre = Column(String(200), nullable=False)
    validacion_id = Column(String(100), nullable=False)
    severity = Column(Enum("error", "warning"), nullable=False)
    mensaje = Column(String(500), nullable=False)
    fecha = Column(DateTime, nullable=False)
    resuelto = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["emaus_id", "anio", "semestre"],
            ["control_relevamiento.emaus_id", "control_relevamiento.anio", "control_relevamiento.semestre"],
        ),
    )


class ControlAprobacion(Base):
    __tablename__ = "control_aprobacion"

    emaus_id = Column(Integer, ForeignKey("emaus.id"), primary_key=True)
    anio = Column(SmallInteger, primary_key=True)
    semestre = Column(String(1), primary_key=True)
    estado = Column(Enum("pendiente", "aprobado", "rechazado"), nullable=False, default="pendiente")
    aprobado_por = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    observaciones = Column(Text, nullable=True)
    fecha_aprobacion = Column(DateTime, nullable=True)

    emaus = relationship("Emaus", foreign_keys=[emaus_id])
    aprobador = relationship("Usuario", foreign_keys=[aprobado_por])
