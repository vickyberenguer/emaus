from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.usuario import Usuario
from app.models.espacio_educativo import (
    EspacioEducativo,
    EEAmbiente,
    EEServicio,
    EEEquipoCocina,
    EEEquipoInformatico,
    RelevamientoEE,
    RelevamientoEEAccion,
    RelevamientoEENecesidadInfra,
    RelevamientoEEPreocupacionJoven,
    RelevamientoEENivelSuperior,
    RelevamientoEEBTUAbandonoMotivo,
    RelevamientoEEApoyoPrimarioContenido,
    RelevamientoEEApoyoSecundarioContenido,
    RelevamientoEEItineranciaEspacio,
    RelevamientoEEItineranciaActividad,
    RelevamientoEEItineranciaRol,
    RelevamientoEEDigitalTaller,
    RelevamientoEEGrupoMotorRol,
    RelevamientoEEUbicacionZona,
)
from app.routers.auth import get_current_user
from app.routers.relevamientos import get_relevamiento_or_404, check_acceso_lectura, check_acceso_escritura

router = APIRouter(prefix="/relevamientos/{relevamiento_id}/espacios-educativos", tags=["espacios-educativos"])


# --- Schemas: datos de base ---

class AmbienteItem(BaseModel):
    ambiente: str
    tiene: bool = False
    cantidad: int | None = None


class ServicioItem(BaseModel):
    servicio: str
    valor: str | None = None


class EquipoCocinaItem(BaseModel):
    equipo: str
    tiene: bool = False


class EquipoInformaticoItem(BaseModel):
    equipo: str
    cantidad: int | None = None


class EspacioEducativoBase(BaseModel):
    nombre: str
    direccion: str | None = None
    geolocalizacion: str | None = None
    renabap: bool = False
    titularidad: str | None = None
    nombre_titular: str | None = None
    construccion_material: str | None = None
    rampa_acceso: bool = False
    acceso_principal: str | None = None
    activo: bool = True

    ambientes: list[AmbienteItem] = []
    servicios: list[ServicioItem] = []
    equipos_cocina: list[EquipoCocinaItem] = []
    equipos_informaticos: list[EquipoInformaticoItem] = []


BASE_SCALAR_FIELDS = [
    "nombre", "direccion", "geolocalizacion", "renabap", "titularidad",
    "nombre_titular", "construccion_material", "rampa_acceso", "acceso_principal", "activo",
]


# --- Schemas: datos semestrales ---

class SimpleItem(BaseModel):
    valor: str


class NecesidadInfraItem(BaseModel):
    necesidad: str
    orden: int | None = None


class PreocupacionJovenItem(BaseModel):
    preocupacion: str
    ranking: int | None = None


class AccionEjeItem(BaseModel):
    eje: str
    accion: str
    tiene: bool = False


class NivelSuperiorItem(BaseModel):
    nombre_institucion: str
    tipo_acciones: str | None = None


class ItineranciaEspacioItem(BaseModel):
    espacio: str
    espacio_otro: str | None = None


class RolItem(BaseModel):
    rol: str
    rol_otro: str | None = None
    cantidad: int | None = None


class RelevamientoEEUpdate(BaseModel):
    asistentes_0_6: int | None = None
    asistentes_7_14: int | None = None
    asistentes_15_24: int | None = None
    asistentes_25_35: int | None = None
    asistentes_35_50: int | None = None
    asistentes_mas_50: int | None = None
    grupo_motor_cantidad: int | None = None
    grupo_motor_frecuencia: str | None = None
    adolescentes_referentes: int | None = None
    adolescentes_frecuencia: str | None = None
    itinerancia_realizo: bool = False
    itinerancia_frecuencia: str | None = None
    internet_acceso: bool = False
    internet_falta_motivo: str | None = None
    jornadas_formacion_digital: bool = False
    articula_nivel_superior: bool = False
    nivel_superior_cantidad: int | None = None
    bf_apoyo_escolar: int | None = None
    bf_nivel_inicial: int | None = None
    bf_primaria: int | None = None
    bf_secundaria: int | None = None
    bf_asignaciones: int | None = None
    bf_discapacidad: int | None = None
    bf_cud: int | None = None
    btu_regulares: int | None = None
    btu_egresados: int | None = None
    btu_abandonaron: int | None = None
    apoyo_primario_ninos: int | None = None
    apoyo_primario_frecuencia: str | None = None
    apoyo_primario_contenido_principal: str | None = None
    apoyo_secundario_adolescentes: int | None = None
    apoyo_secundario_frecuencia: str | None = None
    apoyo_secundario_contenido_principal: str | None = None
    alfa_total: int | None = None
    alfa_6_9: int | None = None
    alfa_10_14: int | None = None
    alfa_15_24: int | None = None
    alfa_25_mas: int | None = None
    alfa_alfabetizadores: int | None = None
    alfa_frecuencia: str | None = None
    dale_total: int | None = None
    dale_6_9: int | None = None
    dale_10_14: int | None = None
    dale_15_24: int | None = None
    dale_25_mas: int | None = None
    dale_educadores: int | None = None
    dale_frecuencia_dias: int | None = None

    acciones: list[AccionEjeItem] = []
    necesidades_infra: list[NecesidadInfraItem] = []
    preocupaciones_joven: list[PreocupacionJovenItem] = []
    niveles_superiores: list[NivelSuperiorItem] = []
    btu_abandono_motivos: list[SimpleItem] = []
    apoyo_primario_contenidos: list[SimpleItem] = []
    apoyo_secundario_contenidos: list[SimpleItem] = []
    itinerancia_espacios: list[ItineranciaEspacioItem] = []
    itinerancia_actividades: list[SimpleItem] = []
    itinerancia_roles: list[RolItem] = []
    digital_talleres: list[SimpleItem] = []
    grupo_motor_roles: list[RolItem] = []
    ubicacion_zonas: list[SimpleItem] = []


EE_SCALAR_FIELDS = [
    "asistentes_0_6", "asistentes_7_14", "asistentes_15_24", "asistentes_25_35",
    "asistentes_35_50", "asistentes_mas_50", "grupo_motor_cantidad", "grupo_motor_frecuencia",
    "adolescentes_referentes", "adolescentes_frecuencia", "itinerancia_realizo", "itinerancia_frecuencia",
    "internet_acceso", "internet_falta_motivo", "jornadas_formacion_digital", "articula_nivel_superior",
    "nivel_superior_cantidad", "bf_apoyo_escolar", "bf_nivel_inicial", "bf_primaria", "bf_secundaria",
    "bf_asignaciones", "bf_discapacidad", "bf_cud", "btu_regulares", "btu_egresados", "btu_abandonaron",
    "apoyo_primario_ninos", "apoyo_primario_frecuencia", "apoyo_primario_contenido_principal",
    "apoyo_secundario_adolescentes", "apoyo_secundario_frecuencia", "apoyo_secundario_contenido_principal",
    "alfa_total", "alfa_6_9", "alfa_10_14", "alfa_15_24", "alfa_25_mas", "alfa_alfabetizadores", "alfa_frecuencia",
    "dale_total", "dale_6_9", "dale_10_14", "dale_15_24", "dale_25_mas", "dale_educadores", "dale_frecuencia_dias",
]


class EspacioEducativoCompleto(EspacioEducativoBase, RelevamientoEEUpdate):
    id: int  # id del espacio_educativo
    emaus_id: int

    class Config:
        from_attributes = True


# --- Helpers ---

def _serializar(ee: EspacioEducativo, rel_ee: RelevamientoEE | None) -> dict:
    data = {f: getattr(ee, f) for f in BASE_SCALAR_FIELDS}
    data["id"] = ee.id
    data["emaus_id"] = ee.emaus_id
    data["ambientes"] = ee.ambientes
    data["servicios"] = ee.servicios
    data["equipos_cocina"] = ee.equipos_cocina
    data["equipos_informaticos"] = ee.equipos_informaticos

    for f in EE_SCALAR_FIELDS:
        data[f] = getattr(rel_ee, f) if rel_ee else None

    subtablas = [
        "acciones", "necesidades_infra", "preocupaciones_joven", "niveles_superiores",
        "btu_abandono_motivos", "apoyo_primario_contenidos", "apoyo_secundario_contenidos",
        "itinerancia_espacios", "itinerancia_actividades", "itinerancia_roles",
        "digital_talleres", "grupo_motor_roles", "ubicacion_zonas",
    ]
    for s in subtablas:
        data[s] = getattr(rel_ee, s) if rel_ee else []

    return data


def _get_ee_or_404(db: Session, emaus_id: int, ee_id: int) -> EspacioEducativo:
    ee = db.query(EspacioEducativo).filter(
        EspacioEducativo.id == ee_id, EspacioEducativo.emaus_id == emaus_id
    ).first()
    if not ee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Espacio educativo no encontrado")
    return ee


SIMPLE_FIELD_MAP = {
    "btu_abandono_motivos": ("motivo", RelevamientoEEBTUAbandonoMotivo),
    "apoyo_primario_contenidos": ("contenido", RelevamientoEEApoyoPrimarioContenido),
    "apoyo_secundario_contenidos": ("contenido", RelevamientoEEApoyoSecundarioContenido),
    "itinerancia_actividades": ("actividad", RelevamientoEEItineranciaActividad),
    "digital_talleres": ("taller", RelevamientoEEDigitalTaller),
    "ubicacion_zonas": ("zona", RelevamientoEEUbicacionZona),
}


def _sync_subtablas(db: Session, rel_ee_id: int, body: RelevamientoEEUpdate):
    db.query(RelevamientoEEAccion).filter(RelevamientoEEAccion.relevamiento_ee_id == rel_ee_id).delete()
    for item in body.acciones:
        db.add(RelevamientoEEAccion(relevamiento_ee_id=rel_ee_id, **item.model_dump()))

    db.query(RelevamientoEENecesidadInfra).filter(RelevamientoEENecesidadInfra.relevamiento_ee_id == rel_ee_id).delete()
    for item in body.necesidades_infra:
        db.add(RelevamientoEENecesidadInfra(relevamiento_ee_id=rel_ee_id, **item.model_dump()))

    db.query(RelevamientoEEPreocupacionJoven).filter(RelevamientoEEPreocupacionJoven.relevamiento_ee_id == rel_ee_id).delete()
    for item in body.preocupaciones_joven:
        db.add(RelevamientoEEPreocupacionJoven(relevamiento_ee_id=rel_ee_id, **item.model_dump()))

    db.query(RelevamientoEENivelSuperior).filter(RelevamientoEENivelSuperior.relevamiento_ee_id == rel_ee_id).delete()
    for item in body.niveles_superiores:
        db.add(RelevamientoEENivelSuperior(relevamiento_ee_id=rel_ee_id, **item.model_dump()))

    db.query(RelevamientoEEItineranciaEspacio).filter(RelevamientoEEItineranciaEspacio.relevamiento_ee_id == rel_ee_id).delete()
    for item in body.itinerancia_espacios:
        db.add(RelevamientoEEItineranciaEspacio(relevamiento_ee_id=rel_ee_id, **item.model_dump()))

    db.query(RelevamientoEEItineranciaRol).filter(RelevamientoEEItineranciaRol.relevamiento_ee_id == rel_ee_id).delete()
    for item in body.itinerancia_roles:
        db.add(RelevamientoEEItineranciaRol(relevamiento_ee_id=rel_ee_id, **item.model_dump()))

    db.query(RelevamientoEEGrupoMotorRol).filter(RelevamientoEEGrupoMotorRol.relevamiento_ee_id == rel_ee_id).delete()
    for item in body.grupo_motor_roles:
        db.add(RelevamientoEEGrupoMotorRol(relevamiento_ee_id=rel_ee_id, **item.model_dump()))

    for campo, (col_name, model) in SIMPLE_FIELD_MAP.items():
        db.query(model).filter(model.relevamiento_ee_id == rel_ee_id).delete()
        for item in getattr(body, campo):
            db.add(model(relevamiento_ee_id=rel_ee_id, **{col_name: item.valor}))


def _sync_base_subtablas(db: Session, ee_id: int, body: EspacioEducativoBase):
    db.query(EEAmbiente).filter(EEAmbiente.espacio_educativo_id == ee_id).delete()
    for item in body.ambientes:
        db.add(EEAmbiente(espacio_educativo_id=ee_id, **item.model_dump()))

    db.query(EEServicio).filter(EEServicio.espacio_educativo_id == ee_id).delete()
    for item in body.servicios:
        db.add(EEServicio(espacio_educativo_id=ee_id, **item.model_dump()))

    db.query(EEEquipoCocina).filter(EEEquipoCocina.espacio_educativo_id == ee_id).delete()
    for item in body.equipos_cocina:
        db.add(EEEquipoCocina(espacio_educativo_id=ee_id, **item.model_dump()))

    db.query(EEEquipoInformatico).filter(EEEquipoInformatico.espacio_educativo_id == ee_id).delete()
    for item in body.equipos_informaticos:
        db.add(EEEquipoInformatico(espacio_educativo_id=ee_id, **item.model_dump()))


# --- Endpoints ---

@router.get("")
def listar_espacios_educativos(
    relevamiento_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    relevamiento = get_relevamiento_or_404(db, relevamiento_id)
    check_acceso_lectura(relevamiento, current_user, db)

    espacios = db.query(EspacioEducativo).filter(
        EspacioEducativo.emaus_id == relevamiento.emaus_id, EspacioEducativo.activo == True
    ).all()
    rel_ee_por_ee = {
        r.espacio_educativo_id: r
        for r in db.query(RelevamientoEE).filter(RelevamientoEE.relevamiento_id == relevamiento_id).all()
    }
    return [_serializar(ee, rel_ee_por_ee.get(ee.id)) for ee in espacios]


@router.post("", status_code=status.HTTP_201_CREATED)
def crear_espacio_educativo(
    relevamiento_id: int,
    body: EspacioEducativoBase,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    relevamiento = get_relevamiento_or_404(db, relevamiento_id)
    check_acceso_escritura(relevamiento, current_user)

    ee = EspacioEducativo(emaus_id=relevamiento.emaus_id, **{f: getattr(body, f) for f in BASE_SCALAR_FIELDS})
    db.add(ee)
    db.flush()
    _sync_base_subtablas(db, ee.id, body)

    rel_ee = RelevamientoEE(relevamiento_id=relevamiento_id, espacio_educativo_id=ee.id)
    db.add(rel_ee)
    db.commit()
    db.refresh(ee)
    db.refresh(rel_ee)
    return _serializar(ee, rel_ee)


@router.put("/{ee_id}")
def actualizar_espacio_educativo(
    relevamiento_id: int,
    ee_id: int,
    body: EspacioEducativoBase,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    relevamiento = get_relevamiento_or_404(db, relevamiento_id)
    check_acceso_escritura(relevamiento, current_user)
    ee = _get_ee_or_404(db, relevamiento.emaus_id, ee_id)

    for f in BASE_SCALAR_FIELDS:
        setattr(ee, f, getattr(body, f))
    _sync_base_subtablas(db, ee.id, body)

    db.commit()
    db.refresh(ee)
    rel_ee = db.query(RelevamientoEE).filter(
        RelevamientoEE.relevamiento_id == relevamiento_id, RelevamientoEE.espacio_educativo_id == ee_id
    ).first()
    return _serializar(ee, rel_ee)


@router.put("/{ee_id}/datos-semestrales")
def actualizar_datos_semestrales(
    relevamiento_id: int,
    ee_id: int,
    body: RelevamientoEEUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    relevamiento = get_relevamiento_or_404(db, relevamiento_id)
    check_acceso_escritura(relevamiento, current_user)
    ee = _get_ee_or_404(db, relevamiento.emaus_id, ee_id)

    rel_ee = db.query(RelevamientoEE).filter(
        RelevamientoEE.relevamiento_id == relevamiento_id, RelevamientoEE.espacio_educativo_id == ee_id
    ).first()
    if not rel_ee:
        rel_ee = RelevamientoEE(relevamiento_id=relevamiento_id, espacio_educativo_id=ee_id)
        db.add(rel_ee)
        db.flush()

    for f in EE_SCALAR_FIELDS:
        setattr(rel_ee, f, getattr(body, f))
    _sync_subtablas(db, rel_ee.id, body)

    db.commit()
    db.refresh(ee)
    db.refresh(rel_ee)
    return _serializar(ee, rel_ee)
