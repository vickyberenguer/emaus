from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, UniqueConstraint, SmallInteger
from sqlalchemy.orm import relationship
from app.database import Base


class EspacioEducativo(Base):
    __tablename__ = "espacio_educativo"

    id = Column(Integer, primary_key=True, index=True)
    emaus_id = Column(Integer, ForeignKey("emaus.id"), nullable=False)
    nombre = Column(String(200), nullable=False)
    direccion = Column(String(500))
    geolocalizacion = Column(String(500))
    renabap = Column(Boolean, default=False)
    titularidad = Column(String(100))
    nombre_titular = Column(String(200))
    construccion_material = Column(String(100))
    rampa_acceso = Column(Boolean, default=False)
    acceso_principal = Column(String(100))
    activo = Column(Boolean, default=True)

    emaus = relationship("Emaus", back_populates="espacios_educativos")
    ambientes = relationship("EEAmbiente", back_populates="espacio_educativo")
    servicios = relationship("EEServicio", back_populates="espacio_educativo")
    equipos_cocina = relationship("EEEquipoCocina", back_populates="espacio_educativo")
    equipos_informaticos = relationship("EEEquipoInformatico", back_populates="espacio_educativo")
    relevamientos_ee = relationship("RelevamientoEE", back_populates="espacio_educativo")


class EEAmbiente(Base):
    __tablename__ = "ee_ambiente"

    id = Column(Integer, primary_key=True, index=True)
    espacio_educativo_id = Column(Integer, ForeignKey("espacio_educativo.id"), nullable=False)
    ambiente = Column(String(100), nullable=False)
    tiene = Column(Boolean, default=False)
    cantidad = Column(Integer)

    espacio_educativo = relationship("EspacioEducativo", back_populates="ambientes")


class EEServicio(Base):
    __tablename__ = "ee_servicio"

    id = Column(Integer, primary_key=True, index=True)
    espacio_educativo_id = Column(Integer, ForeignKey("espacio_educativo.id"), nullable=False)
    servicio = Column(String(100), nullable=False)
    valor = Column(String(200))

    espacio_educativo = relationship("EspacioEducativo", back_populates="servicios")


class EEEquipoCocina(Base):
    __tablename__ = "ee_equipo_cocina"

    id = Column(Integer, primary_key=True, index=True)
    espacio_educativo_id = Column(Integer, ForeignKey("espacio_educativo.id"), nullable=False)
    equipo = Column(String(100), nullable=False)
    tiene = Column(Boolean, default=False)

    espacio_educativo = relationship("EspacioEducativo", back_populates="equipos_cocina")


class EEEquipoInformatico(Base):
    __tablename__ = "ee_equipo_informatico"

    id = Column(Integer, primary_key=True, index=True)
    espacio_educativo_id = Column(Integer, ForeignKey("espacio_educativo.id"), nullable=False)
    equipo = Column(String(100), nullable=False)
    cantidad = Column(Integer)

    espacio_educativo = relationship("EspacioEducativo", back_populates="equipos_informaticos")


class RelevamientoEE(Base):
    __tablename__ = "relevamiento_ee"
    __table_args__ = (
        UniqueConstraint("relevamiento_id", "espacio_educativo_id", name="uq_relevamiento_ee"),
    )

    id = Column(Integer, primary_key=True, index=True)
    relevamiento_id = Column(Integer, ForeignKey("relevamiento.id"), nullable=False)
    espacio_educativo_id = Column(Integer, ForeignKey("espacio_educativo.id"), nullable=False)

    asistentes_0_6 = Column(Integer)
    asistentes_7_14 = Column(Integer)
    asistentes_15_24 = Column(Integer)
    asistentes_25_35 = Column(Integer)
    asistentes_35_50 = Column(Integer)
    asistentes_mas_50 = Column(Integer)

    grupo_motor_cantidad = Column(Integer)
    grupo_motor_frecuencia = Column(String(100))

    adolescentes_referentes = Column(Integer)
    adolescentes_frecuencia = Column(String(100))

    itinerancia_realizo = Column(Boolean, default=False)
    itinerancia_frecuencia = Column(String(100))

    internet_acceso = Column(Boolean, default=False)
    internet_falta_motivo = Column(String(200))
    jornadas_formacion_digital = Column(Boolean, default=False)

    articula_nivel_superior = Column(Boolean, default=False)
    nivel_superior_cantidad = Column(Integer)

    bf_apoyo_escolar = Column(Integer)
    bf_nivel_inicial = Column(Integer)
    bf_primaria = Column(Integer)
    bf_secundaria = Column(Integer)
    bf_asignaciones = Column(Integer)
    bf_discapacidad = Column(Integer)
    bf_cud = Column(Integer)

    btu_regulares = Column(Integer)
    btu_egresados = Column(Integer)
    btu_abandonaron = Column(Integer)

    apoyo_primario_ninos = Column(Integer)
    apoyo_primario_frecuencia = Column(String(100))
    apoyo_primario_contenido_principal = Column(String(200))

    apoyo_secundario_adolescentes = Column(Integer)
    apoyo_secundario_frecuencia = Column(String(100))
    apoyo_secundario_contenido_principal = Column(String(200))

    alfa_total = Column(Integer)
    alfa_6_9 = Column(Integer)
    alfa_10_14 = Column(Integer)
    alfa_15_24 = Column(Integer)
    alfa_25_mas = Column(Integer)
    alfa_alfabetizadores = Column(Integer)
    alfa_frecuencia = Column(String(100))

    dale_total = Column(Integer)
    dale_6_9 = Column(Integer)
    dale_10_14 = Column(Integer)
    dale_15_24 = Column(Integer)
    dale_25_mas = Column(Integer)
    dale_educadores = Column(Integer)
    dale_frecuencia_dias = Column(Integer)

    relevamiento = relationship("Relevamiento", back_populates="relevamientos_ee")
    espacio_educativo = relationship("EspacioEducativo", back_populates="relevamientos_ee")
    acciones = relationship("RelevamientoEEAccion", back_populates="relevamiento_ee")
    necesidades_infra = relationship("RelevamientoEENecesidadInfra", back_populates="relevamiento_ee")
    preocupaciones_joven = relationship("RelevamientoEEPreocupacionJoven", back_populates="relevamiento_ee")
    niveles_superiores = relationship("RelevamientoEENivelSuperior", back_populates="relevamiento_ee")
    btu_abandono_motivos = relationship("RelevamientoEEBTUAbandonoMotivo", back_populates="relevamiento_ee")
    apoyo_primario_contenidos = relationship("RelevamientoEEApoyoPrimarioContenido", back_populates="relevamiento_ee")
    apoyo_secundario_contenidos = relationship("RelevamientoEEApoyoSecundarioContenido", back_populates="relevamiento_ee")
    itinerancia_espacios = relationship("RelevamientoEEItineranciaEspacio", back_populates="relevamiento_ee")
    itinerancia_actividades = relationship("RelevamientoEEItineranciaActividad", back_populates="relevamiento_ee")
    itinerancia_roles = relationship("RelevamientoEEItineranciaRol", back_populates="relevamiento_ee")
    digital_talleres = relationship("RelevamientoEEDigitalTaller", back_populates="relevamiento_ee")
    grupo_motor_roles = relationship("RelevamientoEEGrupoMotorRol", back_populates="relevamiento_ee")
    ubicacion_zonas = relationship("RelevamientoEEUbicacionZona", back_populates="relevamiento_ee")


class RelevamientoEEAccion(Base):
    __tablename__ = "relevamiento_ee_accion"

    id = Column(Integer, primary_key=True, index=True)
    relevamiento_ee_id = Column(Integer, ForeignKey("relevamiento_ee.id"), nullable=False)
    eje = Column(String(100), nullable=False)
    accion = Column(String(200), nullable=False)
    tiene = Column(Boolean, default=False)

    relevamiento_ee = relationship("RelevamientoEE", back_populates="acciones")


class RelevamientoEENecesidadInfra(Base):
    __tablename__ = "relevamiento_ee_necesidad_infra"

    id = Column(Integer, primary_key=True, index=True)
    relevamiento_ee_id = Column(Integer, ForeignKey("relevamiento_ee.id"), nullable=False)
    necesidad = Column(String(200), nullable=False)
    orden = Column(SmallInteger)

    relevamiento_ee = relationship("RelevamientoEE", back_populates="necesidades_infra")


class RelevamientoEEPreocupacionJoven(Base):
    __tablename__ = "relevamiento_ee_preocupacion_joven"

    id = Column(Integer, primary_key=True, index=True)
    relevamiento_ee_id = Column(Integer, ForeignKey("relevamiento_ee.id"), nullable=False)
    preocupacion = Column(String(200), nullable=False)
    ranking = Column(SmallInteger)

    relevamiento_ee = relationship("RelevamientoEE", back_populates="preocupaciones_joven")


class RelevamientoEENivelSuperior(Base):
    __tablename__ = "relevamiento_ee_nivel_superior"

    id = Column(Integer, primary_key=True, index=True)
    relevamiento_ee_id = Column(Integer, ForeignKey("relevamiento_ee.id"), nullable=False)
    nombre_institucion = Column(String(200), nullable=False)
    tipo_acciones = Column(String(500))

    relevamiento_ee = relationship("RelevamientoEE", back_populates="niveles_superiores")


class RelevamientoEEBTUAbandonoMotivo(Base):
    __tablename__ = "relevamiento_ee_btu_abandono_motivo"

    id = Column(Integer, primary_key=True, index=True)
    relevamiento_ee_id = Column(Integer, ForeignKey("relevamiento_ee.id"), nullable=False)
    motivo = Column(String(200), nullable=False)

    relevamiento_ee = relationship("RelevamientoEE", back_populates="btu_abandono_motivos")


class RelevamientoEEApoyoPrimarioContenido(Base):
    __tablename__ = "relevamiento_ee_apoyo_primario_contenido"

    id = Column(Integer, primary_key=True, index=True)
    relevamiento_ee_id = Column(Integer, ForeignKey("relevamiento_ee.id"), nullable=False)
    contenido = Column(String(200), nullable=False)

    relevamiento_ee = relationship("RelevamientoEE", back_populates="apoyo_primario_contenidos")


class RelevamientoEEApoyoSecundarioContenido(Base):
    __tablename__ = "relevamiento_ee_apoyo_secundario_contenido"

    id = Column(Integer, primary_key=True, index=True)
    relevamiento_ee_id = Column(Integer, ForeignKey("relevamiento_ee.id"), nullable=False)
    contenido = Column(String(200), nullable=False)

    relevamiento_ee = relationship("RelevamientoEE", back_populates="apoyo_secundario_contenidos")


class RelevamientoEEItineranciaEspacio(Base):
    __tablename__ = "relevamiento_ee_itinerancia_espacio"

    id = Column(Integer, primary_key=True, index=True)
    relevamiento_ee_id = Column(Integer, ForeignKey("relevamiento_ee.id"), nullable=False)
    espacio = Column(String(200), nullable=False)
    espacio_otro = Column(String(200))

    relevamiento_ee = relationship("RelevamientoEE", back_populates="itinerancia_espacios")


class RelevamientoEEItineranciaActividad(Base):
    __tablename__ = "relevamiento_ee_itinerancia_actividad"

    id = Column(Integer, primary_key=True, index=True)
    relevamiento_ee_id = Column(Integer, ForeignKey("relevamiento_ee.id"), nullable=False)
    actividad = Column(String(200), nullable=False)

    relevamiento_ee = relationship("RelevamientoEE", back_populates="itinerancia_actividades")


class RelevamientoEEItineranciaRol(Base):
    __tablename__ = "relevamiento_ee_itinerancia_rol"

    id = Column(Integer, primary_key=True, index=True)
    relevamiento_ee_id = Column(Integer, ForeignKey("relevamiento_ee.id"), nullable=False)
    rol = Column(String(200), nullable=False)
    rol_otro = Column(String(200))
    cantidad = Column(Integer)

    relevamiento_ee = relationship("RelevamientoEE", back_populates="itinerancia_roles")


class RelevamientoEEDigitalTaller(Base):
    __tablename__ = "relevamiento_ee_digital_taller"

    id = Column(Integer, primary_key=True, index=True)
    relevamiento_ee_id = Column(Integer, ForeignKey("relevamiento_ee.id"), nullable=False)
    taller = Column(String(200), nullable=False)

    relevamiento_ee = relationship("RelevamientoEE", back_populates="digital_talleres")


class RelevamientoEEGrupoMotorRol(Base):
    __tablename__ = "relevamiento_ee_grupo_motor_rol"

    id = Column(Integer, primary_key=True, index=True)
    relevamiento_ee_id = Column(Integer, ForeignKey("relevamiento_ee.id"), nullable=False)
    rol = Column(String(200), nullable=False)
    rol_otro = Column(String(200))
    cantidad = Column(Integer)

    relevamiento_ee = relationship("RelevamientoEE", back_populates="grupo_motor_roles")


class RelevamientoEEUbicacionZona(Base):
    __tablename__ = "relevamiento_ee_ubicacion_zona"

    id = Column(Integer, primary_key=True, index=True)
    relevamiento_ee_id = Column(Integer, ForeignKey("relevamiento_ee.id"), nullable=False)
    zona = Column(String(100), nullable=False)

    relevamiento_ee = relationship("RelevamientoEE", back_populates="ubicacion_zonas")
