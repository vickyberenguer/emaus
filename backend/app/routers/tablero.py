from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.usuario import Usuario
from app.models.emaus import Emaus, Diocesis, ResponsableEmaus
from app.models.control import ControlRelevamiento, ControlAprobacion
from app.models.relevamiento import Relevamiento
from app.models.espacio_educativo import EspacioEducativo, RelevamientoEE, RelevamientoEEItineranciaRol
from app.routers.auth import get_current_user, require_rol
from app.routers.control import ANIO_ACTIVO, SEMESTRE_ACTIVO, emaus_ids_for_user

router = APIRouter(prefix="/tablero", tags=["tablero"])


@router.get("/responsables")
def listar_responsables(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_rol("admin")),
):
    """Lista de responsables para el filtro (solo admin)."""
    rows = (
        db.query(Usuario)
        .join(ResponsableEmaus, ResponsableEmaus.responsable_id == Usuario.id)
        .distinct()
        .order_by(Usuario.nombre)
        .all()
    )
    return [{"id": u.id, "nombre": u.nombre} for u in rows]


@router.get("/estado-carga")
def estado_carga(
    anio: int = ANIO_ACTIVO,
    semestre: str = SEMESTRE_ACTIVO,
    responsable_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_rol("admin", "responsable")),
):
    allowed_ids = emaus_ids_for_user(current_user, db)

    # Si admin filtra por responsable, intersectar
    if responsable_id and current_user.rol == "admin":
        resp_ids = [
            r.emaus_id for r in
            db.query(ResponsableEmaus)
            .filter(ResponsableEmaus.responsable_id == responsable_id).all()
        ]
        allowed_ids = resp_ids

    query = (
        db.query(ControlRelevamiento, Emaus, ControlAprobacion)
        .join(Emaus, Emaus.id == ControlRelevamiento.emaus_id)
        .outerjoin(ControlAprobacion, and_(
            ControlAprobacion.emaus_id == ControlRelevamiento.emaus_id,
            ControlAprobacion.anio == ControlRelevamiento.anio,
            ControlAprobacion.semestre == ControlRelevamiento.semestre,
        ))
        .filter(
            ControlRelevamiento.anio == anio,
            ControlRelevamiento.semestre == semestre,
        )
    )
    if allowed_ids is not None:
        query = query.filter(ControlRelevamiento.emaus_id.in_(allowed_ids))

    rows = query.order_by(Emaus.nombre).all()

    emaus_list = []
    for ctrl, emaus, aprobacion in rows:
        ee_total = ctrl.ee_count or 0
        ee_completos = ctrl.ee_declarados_completos or 0
        ee_errores = ctrl.ee_con_errores or 0
        ee_pendientes = max(0, ee_total - ee_completos - ee_errores)

        aprobado = aprobacion is not None and aprobacion.estado == "aprobado"

        if aprobado:
            estado = "aprobado"
        elif ctrl.ee_con_errores > 0 or ctrl.pi_con_errores:
            estado = "error"
        elif ee_completos >= ee_total and ee_total > 0:
            estado = "listo"
        else:
            estado = "pendiente"

        emaus_list.append({
            "emaus_id": ctrl.emaus_id,
            "emaus_nombre": emaus.nombre,
            "ee_total": ee_total,
            "ee_completos": ee_completos,
            "ee_pendientes": ee_pendientes,
            "ee_errores": ee_errores,
            "total_asistentes": ctrl.total_asistentes_ee or 0,
            "cantidad_talleres": ctrl.cantidad_talleres or 0,
            "cantidad_establecimientos": ctrl.cantidad_establecimientos or 0,
            "estado": estado,
        })

    # Totales globales
    total_emaus = len(emaus_list)
    aprobados   = sum(1 for e in emaus_list if e["estado"] == "aprobado")
    listos      = sum(1 for e in emaus_list if e["estado"] == "listo")
    pendientes  = sum(1 for e in emaus_list if e["estado"] == "pendiente")
    con_errores = sum(1 for e in emaus_list if e["estado"] == "error")
    total_ee = sum(e["ee_total"] for e in emaus_list)
    total_ee_completos = sum(e["ee_completos"] for e in emaus_list)
    total_ee_pendientes = sum(e["ee_pendientes"] for e in emaus_list)
    total_ee_errores = sum(e["ee_errores"] for e in emaus_list)
    total_asistentes = sum(e["total_asistentes"] for e in emaus_list)

    return {
        "resumen": {
            "total_emaus": total_emaus,
            "emaus_aprobados": aprobados,
            "emaus_listos": listos,
            "emaus_pendientes": pendientes,
            "emaus_con_errores": con_errores,
            "total_ee": total_ee,
            "total_ee_completos": total_ee_completos,
            "total_ee_pendientes": total_ee_pendientes,
            "total_ee_errores": total_ee_errores,
            "total_asistentes": total_asistentes,
        },
        "emaus": emaus_list,
    }


@router.get("/filtros")
def filtros_participantes(
    anio: int = ANIO_ACTIVO,
    semestre: str = SEMESTRE_ACTIVO,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_rol("admin", "responsable")),
):
    """Valores disponibles para los filtros cascada del tablero de participantes."""
    base = (
        db.query(Diocesis.region, Diocesis.provincia, Emaus.id, Emaus.nombre,
                 EspacioEducativo.id, EspacioEducativo.nombre)
        .join(Emaus, Emaus.diocesis_id == Diocesis.id)
        .join(Relevamiento, and_(
            Relevamiento.emaus_id == Emaus.id,
            Relevamiento.anio == anio,
            Relevamiento.semestre == semestre,
        ))
        .join(RelevamientoEE, RelevamientoEE.relevamiento_id == Relevamiento.id)
        .join(EspacioEducativo, EspacioEducativo.id == RelevamientoEE.espacio_educativo_id)
        .distinct()
        .order_by(Diocesis.region, Diocesis.provincia, Emaus.nombre, EspacioEducativo.nombre)
        .all()
    )

    regiones  = sorted({r[0] for r in base if r[0]})
    provincias = sorted({r[1] for r in base if r[1]})
    emaus_list = {r[2]: r[3] for r in base}
    ee_list    = {r[4]: r[5] for r in base}

    return {
        "regiones":  regiones,
        "provincias": provincias,
        "emaus":     [{"id": k, "nombre": v} for k, v in sorted(emaus_list.items(), key=lambda x: x[1])],
        "ee":        [{"id": k, "nombre": v} for k, v in sorted(ee_list.items(), key=lambda x: x[1])],
    }


def _sum(val):
    return val or 0


@router.get("/participantes")
def participantes(
    anio: int = ANIO_ACTIVO,
    semestre: str = SEMESTRE_ACTIVO,
    region: Optional[str] = None,
    provincia: Optional[str] = None,
    emaus_id: Optional[int] = None,
    ee_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_rol("admin", "responsable")),
):
    allowed_ids = emaus_ids_for_user(current_user, db)

    query = (
        db.query(RelevamientoEE)
        .join(Relevamiento, and_(
            Relevamiento.id == RelevamientoEE.relevamiento_id,
            Relevamiento.anio == anio,
            Relevamiento.semestre == semestre,
        ))
        .join(Emaus, Emaus.id == Relevamiento.emaus_id)
        .join(Diocesis, Diocesis.id == Emaus.diocesis_id)
        .join(EspacioEducativo, EspacioEducativo.id == RelevamientoEE.espacio_educativo_id)
    )

    if allowed_ids is not None:
        query = query.filter(Relevamiento.emaus_id.in_(allowed_ids))
    if region:
        query = query.filter(Diocesis.region == region)
    if provincia:
        query = query.filter(Diocesis.provincia == provincia)
    if emaus_id:
        query = query.filter(Relevamiento.emaus_id == emaus_id)
    if ee_id:
        query = query.filter(RelevamientoEE.espacio_educativo_id == ee_id)

    rees = query.all()
    ee_count = len(rees)

    # Itinerancia: suma de roles por relevamiento_ee_id
    ree_ids = [r.id for r in rees]
    iti_sum = 0
    if ree_ids:
        iti_sum = db.query(func.coalesce(func.sum(RelevamientoEEItineranciaRol.cantidad), 0))\
            .filter(RelevamientoEEItineranciaRol.relevamiento_ee_id.in_(ree_ids))\
            .scalar() or 0

    # Agregados
    def s(field): return sum(_sum(getattr(r, field)) for r in rees)

    asistentes_0_6    = s("asistentes_0_6")
    asistentes_7_14   = s("asistentes_7_14")
    asistentes_15_24  = s("asistentes_15_24")
    asistentes_25_35  = s("asistentes_25_35")
    asistentes_35_50  = s("asistentes_35_50")
    asistentes_mas_50 = s("asistentes_mas_50")
    total_asistentes  = asistentes_0_6 + asistentes_7_14 + asistentes_15_24 + asistentes_25_35 + asistentes_35_50 + asistentes_mas_50

    grupo_motor = s("grupo_motor_cantidad")
    total_colaboradores = int(iti_sum) + grupo_motor

    return {
        "ee_count": ee_count,
        "asistentes": {
            "total": total_asistentes,
            "0_6":    asistentes_0_6,
            "7_14":   asistentes_7_14,
            "15_24":  asistentes_15_24,
            "25_35":  asistentes_25_35,
            "35_50":  asistentes_35_50,
            "mas_50": asistentes_mas_50,
        },
        "apoyo_escolar": {
            "primaria":    s("apoyo_primario_ninos"),
            "secundaria":  s("apoyo_secundario_adolescentes"),
        },
        "alfabetizacion": {
            "total":          s("alfa_total"),
            "6_9":            s("alfa_6_9"),
            "10_14":          s("alfa_10_14"),
            "15_24":          s("alfa_15_24"),
            "25_mas":         s("alfa_25_mas"),
            "alfabetizadores":s("alfa_alfabetizadores"),
        },
        "dale": {
            "total":          s("dale_total"),
            "6_9":            s("dale_6_9"),
            "10_14":          s("dale_10_14"),
            "15_24":          s("dale_15_24"),
            "25_mas":         s("dale_25_mas"),
            "educadores":     s("dale_educadores"),
        },
        "ayj": {
            "total": s("adolescentes_referentes"),
        },
        "colaboradores": {
            "total":        total_colaboradores,
            "grupo_motor":  grupo_motor,
            "itinerancia":  int(iti_sum),
        },
    }
