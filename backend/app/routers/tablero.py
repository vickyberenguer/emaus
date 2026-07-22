from typing import Dict, List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.usuario import Usuario
from app.models.emaus import Emaus, Diocesis, ResponsableEmaus
from app.models.control import ControlRelevamiento, ControlAprobacion
from app.models.relevamiento import Relevamiento
from app.models.espacio_educativo import (
    EspacioEducativo, RelevamientoEE, RelevamientoEEItineranciaRol,
    RelevamientoEEAccion, RelevamientoEEApoyoPrimarioContenido,
    RelevamientoEEApoyoSecundarioContenido,
    EEAmbiente, EEServicio, EEEquipoCocina, EEEquipoInformatico, EEZona,
    RelevamientoEEGrupoMotorRol, RelevamientoEEItineranciaActividad,
    RelevamientoEEItineranciaEspacio, RelevamientoEEBTUAbandonoMotivo,
)
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

    # Calcular BTU relevado (sum btu_regulares) por Emaús en un solo query
    emaus_ids_en_resultado = [ctrl.emaus_id for ctrl, _, _ in rows]
    btu_relevado_map: dict = {}
    if emaus_ids_en_resultado:
        btu_rows = (
            db.query(Relevamiento.emaus_id, func.coalesce(func.sum(RelevamientoEE.btu_regulares), 0))
            .join(RelevamientoEE, RelevamientoEE.relevamiento_id == Relevamiento.id)
            .filter(
                Relevamiento.anio == anio,
                Relevamiento.semestre == semestre,
                Relevamiento.emaus_id.in_(emaus_ids_en_resultado),
            )
            .group_by(Relevamiento.emaus_id)
            .all()
        )
        btu_relevado_map = {r[0]: int(r[1]) for r in btu_rows}

    emaus_list = []
    for ctrl, emaus, aprobacion in rows:
        ee_total = ctrl.ee_count or 0
        ee_completos = ctrl.ee_declarados_completos or 0
        ee_errores = ctrl.ee_con_errores or 0
        ee_pendientes = max(0, ee_total - ee_completos - ee_errores)

        btu_actual = ctrl.btu_actual
        btu_relevado = btu_relevado_map.get(ctrl.emaus_id, 0)
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
            "btu_relevado": btu_relevado,
            "btu_actual": btu_actual,
            "dif_btu": (btu_actual - btu_relevado) if btu_actual is not None else None,
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
    region: Optional[str] = None,
    provincia: Optional[str] = None,
    emaus_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_rol("admin", "responsable")),
):
    """Valores disponibles para los filtros cascada del tablero."""
    q = (
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
    )

    # Para regiones y provincias siempre devolvemos el universo completo del período
    base_all = q.all()
    regiones  = sorted({r[0] for r in base_all if r[0]})

    # Provincias filtradas por región si corresponde
    if region:
        provincias = sorted({r[1] for r in base_all if r[0] == region and r[1]})
    else:
        provincias = sorted({r[1] for r in base_all if r[1]})

    # Emaús filtrados por región y/o provincia
    base_emaus = base_all
    if region:
        base_emaus = [r for r in base_emaus if r[0] == region]
    if provincia:
        base_emaus = [r for r in base_emaus if r[1] == provincia]
    emaus_list = {r[2]: r[3] for r in base_emaus}

    # EE filtrados por región, provincia y/o emaús
    base_ee = base_emaus
    if emaus_id:
        base_ee = [r for r in base_ee if r[2] == emaus_id]
    ee_list = {r[4]: r[5] for r in base_ee}

    return {
        "regiones":  regiones,
        "provincias": provincias,
        "emaus":     [{"id": k, "nombre": v} for k, v in sorted(emaus_list.items(), key=lambda x: x[1])],
        "ee":        [{"id": k, "nombre": v} for k, v in sorted(ee_list.items(), key=lambda x: x[1])],
    }


@router.get("/debug-periodos")
def debug_periodos(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_rol("admin")),
):
    """Diagnóstico: qué años/semestres tienen datos en relevamiento_ee."""
    rows = (
        db.query(Relevamiento.anio, Relevamiento.semestre, func.count(RelevamientoEE.id))
        .outerjoin(RelevamientoEE, RelevamientoEE.relevamiento_id == Relevamiento.id)
        .group_by(Relevamiento.anio, Relevamiento.semestre)
        .order_by(Relevamiento.anio, Relevamiento.semestre)
        .all()
    )
    total_ree = db.query(func.count(RelevamientoEE.id)).scalar()
    total_rel = db.query(func.count(Relevamiento.id)).scalar()
    return {
        "total_relevamiento": total_rel,
        "total_relevamiento_ee": total_ree,
        "por_periodo": [
            {"anio": r[0], "semestre": r[1], "ree_count": r[2]} for r in rows
        ],
    }


@router.get("/acciones")
def acciones(
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

    # Base query: relevamiento_ee con filtros
    ree_query = (
        db.query(RelevamientoEE.id)
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
        ree_query = ree_query.filter(Relevamiento.emaus_id.in_(allowed_ids))
    if region:
        ree_query = ree_query.filter(Diocesis.region == region)
    if provincia:
        ree_query = ree_query.filter(Diocesis.provincia == provincia)
    if emaus_id:
        ree_query = ree_query.filter(Relevamiento.emaus_id == emaus_id)
    if ee_id:
        ree_query = ree_query.filter(RelevamientoEE.espacio_educativo_id == ee_id)

    ree_ids = [r[0] for r in ree_query.all()]
    total_ree = len(ree_ids)

    if not ree_ids:
        return {"total_ee": 0, "ejes": []}

    from collections import defaultdict
    from sqlalchemy import case

    # Conteos por eje+accion — distinct por EE para evitar duplicados del scraper
    accion_rows = (
        db.query(
            RelevamientoEEAccion.eje,
            RelevamientoEEAccion.accion,
            func.count(func.distinct(RelevamientoEEAccion.relevamiento_ee_id)).label("total_reg"),
            func.count(func.distinct(
                case((RelevamientoEEAccion.tiene == True, RelevamientoEEAccion.relevamiento_ee_id), else_=None)
            )).label("si"),
            func.count(func.distinct(
                case((RelevamientoEEAccion.tiene == False, RelevamientoEEAccion.relevamiento_ee_id), else_=None)
            )).label("no"),
        )
        .filter(RelevamientoEEAccion.relevamiento_ee_id.in_(ree_ids))
        .group_by(RelevamientoEEAccion.eje, RelevamientoEEAccion.accion)
        .order_by(RelevamientoEEAccion.eje, RelevamientoEEAccion.accion)
        .all()
    )

    # Agrupador por eje: EEs con al menos una accion tiene=True en ese eje
    agrup_rows = (
        db.query(
            RelevamientoEEAccion.eje,
            func.count(func.distinct(RelevamientoEEAccion.relevamiento_ee_id)).label("si"),
        )
        .filter(
            RelevamientoEEAccion.relevamiento_ee_id.in_(ree_ids),
            RelevamientoEEAccion.tiene == True,
        )
        .group_by(RelevamientoEEAccion.eje)
        .all()
    )
    agrup_map = {r[0]: r[1] for r in agrup_rows}

    ejes_dict = defaultdict(list)
    for row in accion_rows:
        si = int(row.si or 0)
        no = int(row.no or 0)
        sin_dato = max(0, total_ree - si - no)
        ejes_dict[row.eje].append({
            "accion": row.accion,
            "si": si,
            "no": no,
            "sin_dato": sin_dato,
            "total": total_ree,
        })

    EJE_ORDER = [
        "Primera infancia",
        "Apoyo a las trayectorias educativas",
        "Salud integral",
        "Integración comunitaria",
        "Nuevas tecnologías",
    ]

    ejes = []
    for eje in EJE_ORDER:
        if eje not in ejes_dict:
            continue
        si_agrup = agrup_map.get(eje, 0)
        no_agrup = total_ree - si_agrup
        ejes.append({
            "eje": eje,
            "agrupador": {
                "si": si_agrup,
                "no": no_agrup,
                "sin_dato": 0,
                "total": total_ree,
            },
            "acciones": ejes_dict[eje],
        })

    return {"total_ee": total_ree, "ejes": ejes}


def _sum(val):
    return val or 0


@router.get("/edilicias")
def edilicias(
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

    # EEs que participaron en el período con filtros
    ee_query = (
        db.query(EspacioEducativo.id, EspacioEducativo.construccion_material)
        .join(RelevamientoEE, RelevamientoEE.espacio_educativo_id == EspacioEducativo.id)
        .join(Relevamiento, and_(
            Relevamiento.id == RelevamientoEE.relevamiento_id,
            Relevamiento.anio == anio,
            Relevamiento.semestre == semestre,
        ))
        .join(Emaus, Emaus.id == Relevamiento.emaus_id)
        .join(Diocesis, Diocesis.id == Emaus.diocesis_id)
        .distinct()
    )
    if allowed_ids is not None:
        ee_query = ee_query.filter(Relevamiento.emaus_id.in_(allowed_ids))
    if region:
        ee_query = ee_query.filter(Diocesis.region == region)
    if provincia:
        ee_query = ee_query.filter(Diocesis.provincia == provincia)
    if emaus_id:
        ee_query = ee_query.filter(Relevamiento.emaus_id == emaus_id)
    if ee_id:
        ee_query = ee_query.filter(EspacioEducativo.id == ee_id)

    ee_rows = ee_query.all()
    ee_ids = [r[0] for r in ee_rows]
    total = len(ee_ids)
    if not total:
        return {"total_ee": 0}

    def pct(n): return round(n / total * 100, 1) if total else 0
    def bars(counts, base=None):
        b = base or total
        return sorted(
            [{"label": k, "cantidad": v, "pct": round(v / b * 100, 1) if b else 0}
             for k, v in counts.items()],
            key=lambda x: -x["cantidad"]
        )

    # Construcción material
    const_counts = {}
    for r in ee_rows:
        k = r[1] or "Sin dato"
        const_counts[k] = const_counts.get(k, 0) + 1

    # Zonas (multi-valor)
    zona_counts = {}
    for r in db.query(EEZona.zona, func.count(EEZona.id)).filter(
        EEZona.espacio_educativo_id.in_(ee_ids)
    ).group_by(EEZona.zona).all():
        zona_counts[r[0]] = r[1]

    # Ambientes
    amb_rows = db.query(EEAmbiente.ambiente, func.sum(func.if_(EEAmbiente.tiene, 1, 0))).filter(
        EEAmbiente.espacio_educativo_id.in_(ee_ids)
    ).group_by(EEAmbiente.ambiente).all()
    amb_counts = {r[0]: int(r[1] or 0) for r in amb_rows}

    # Servicios (presencia = tener registro)
    serv_rows = db.query(EEServicio.servicio, func.count(EEServicio.id)).filter(
        EEServicio.espacio_educativo_id.in_(ee_ids)
    ).group_by(EEServicio.servicio).all()
    serv_counts = {r[0]: r[1] for r in serv_rows}

    # Equipos cocina
    cocina_rows = db.query(EEEquipoCocina.equipo, func.sum(func.if_(EEEquipoCocina.tiene, 1, 0))).filter(
        EEEquipoCocina.espacio_educativo_id.in_(ee_ids)
    ).group_by(EEEquipoCocina.equipo).all()
    cocina_counts = {r[0]: int(r[1] or 0) for r in cocina_rows}

    # Equipos informáticos
    info_rows = db.query(
        EEEquipoInformatico.equipo,
        func.count(EEEquipoInformatico.espacio_educativo_id.distinct()),
        func.sum(EEEquipoInformatico.cantidad),
    ).filter(
        EEEquipoInformatico.espacio_educativo_id.in_(ee_ids)
    ).group_by(EEEquipoInformatico.equipo).all()
    informatico = sorted(
        [{"label": r[0], "ee_count": r[1], "unidades": int(r[2] or 0),
          "pct": pct(r[1])} for r in info_rows],
        key=lambda x: -x["ee_count"]
    )

    return {
        "total_ee": total,
        "construccion": bars(const_counts),
        "zonas": bars(zona_counts),
        "ambientes": bars(amb_counts),
        "servicios": bars(serv_counts),
        "equipos_cocina": bars(cocina_counts),
        "equipos_informatico": informatico,
    }


@router.get("/grupo-motor")
def grupo_motor(
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

    ree_query = (
        db.query(RelevamientoEE.id, RelevamientoEE.grupo_motor_cantidad,
                 RelevamientoEE.grupo_motor_frecuencia)
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
        ree_query = ree_query.filter(Relevamiento.emaus_id.in_(allowed_ids))
    if region:
        ree_query = ree_query.filter(Diocesis.region == region)
    if provincia:
        ree_query = ree_query.filter(Diocesis.provincia == provincia)
    if emaus_id:
        ree_query = ree_query.filter(Relevamiento.emaus_id == emaus_id)
    if ee_id:
        ree_query = ree_query.filter(RelevamientoEE.espacio_educativo_id == ee_id)

    ree_rows = ree_query.all()
    ree_ids = [r[0] for r in ree_rows]
    total = len(ree_ids)
    if not total:
        return {"total_ee": 0}

    def pct(n): return round(n / total * 100, 1) if total else 0

    # Frecuencia de reunión
    freq_counts: Dict[str, int] = {}
    for r in ree_rows:
        k = r[2] or "Sin dato"
        freq_counts[k] = freq_counts.get(k, 0) + 1
    frecuencia = sorted(
        [{"valor": k, "cantidad": v, "pct": pct(v)} for k, v in freq_counts.items()],
        key=lambda x: -x["cantidad"],
    )

    # Cantidad de integrantes — estadística + rangos
    cantidades = [r[1] for r in ree_rows if r[1] is not None]
    promedio = round(sum(cantidades) / len(cantidades), 1) if cantidades else None
    mediana = None
    if cantidades:
        s = sorted(cantidades)
        n = len(s)
        mediana = s[n // 2] if n % 2 else round((s[n // 2 - 1] + s[n // 2]) / 2, 1)

    def rango_de(n):
        if n == 0: return "0"
        if n <= 3: return "1-3"
        if n <= 6: return "4-6"
        if n <= 10: return "7-10"
        return "11+"

    rango_counts: Dict[str, int] = {}
    sin_dato = 0
    for r in ree_rows:
        if r[1] is None:
            sin_dato += 1
        else:
            k = rango_de(r[1])
            rango_counts[k] = rango_counts.get(k, 0) + 1
    orden_rangos = ["0", "1-3", "4-6", "7-10", "11+"]
    rangos = [
        {"rango": k, "cantidad": rango_counts.get(k, 0), "pct": pct(rango_counts.get(k, 0))}
        for k in orden_rangos if rango_counts.get(k, 0) > 0
    ]
    if sin_dato:
        rangos.append({"rango": "Sin dato", "cantidad": sin_dato, "pct": pct(sin_dato)})

    # Roles del grupo motor (texto libre, hasta 4 por EE) — % sobre EE distintos
    rol_rows = (
        db.query(
            RelevamientoEEGrupoMotorRol.rol,
            func.count(func.distinct(RelevamientoEEGrupoMotorRol.relevamiento_ee_id)),
        )
        .filter(RelevamientoEEGrupoMotorRol.relevamiento_ee_id.in_(ree_ids))
        .group_by(RelevamientoEEGrupoMotorRol.rol)
        .all()
    )
    roles = sorted(
        [{"rol": r[0], "cantidad": r[1], "pct": pct(r[1])} for r in rol_rows],
        key=lambda x: -x["cantidad"],
    )

    return {
        "total_ee": total,
        "frecuencia": frecuencia,
        "cantidad": {"promedio": promedio, "mediana": mediana, "rangos": rangos},
        "roles": roles,
    }


@router.get("/itinerancia")
def itinerancia(
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

    ree_query = (
        db.query(RelevamientoEE.id, RelevamientoEE.itinerancia_realizo,
                 RelevamientoEE.itinerancia_frecuencia)
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
        ree_query = ree_query.filter(Relevamiento.emaus_id.in_(allowed_ids))
    if region:
        ree_query = ree_query.filter(Diocesis.region == region)
    if provincia:
        ree_query = ree_query.filter(Diocesis.provincia == provincia)
    if emaus_id:
        ree_query = ree_query.filter(Relevamiento.emaus_id == emaus_id)
    if ee_id:
        ree_query = ree_query.filter(RelevamientoEE.espacio_educativo_id == ee_id)

    ree_rows = ree_query.all()
    total = len(ree_rows)
    if not total:
        return {"total_ee": 0}

    def pct(n, base): return round(n / base * 100, 1) if base else 0

    # ¿Realiza itinerancia?
    si = sum(1 for r in ree_rows if r[1] is True)
    no = sum(1 for r in ree_rows if r[1] is False)
    sin_dato = total - si - no
    realiza = [
        {"valor": "Sí", "cantidad": si, "pct": pct(si, total)},
        {"valor": "No", "cantidad": no, "pct": pct(no, total)},
        {"valor": "Sin dato", "cantidad": sin_dato, "pct": pct(sin_dato, total)},
    ]

    # Ids de EE que realizan itinerancia — base para el resto de las secciones
    ree_ids_realiza = [r[0] for r in ree_rows if r[1] is True]
    total_realiza = len(ree_ids_realiza)

    if not total_realiza:
        return {"total_ee": total, "realiza": realiza, "total_realiza": 0,
                "frecuencia": [], "actividades": [], "espacios": [], "roles": []}

    # Frecuencia — sobre EE que realizan itinerancia
    freq_counts: Dict[str, int] = {}
    for r in ree_rows:
        if r[1] is True:
            k = r[2] or "Sin dato"
            freq_counts[k] = freq_counts.get(k, 0) + 1
    frecuencia = sorted(
        [{"valor": k, "cantidad": v, "pct": pct(v, total_realiza)} for k, v in freq_counts.items()],
        key=lambda x: -x["cantidad"],
    )

    # Actividades realizadas
    act_rows = (
        db.query(
            RelevamientoEEItineranciaActividad.actividad,
            func.count(func.distinct(RelevamientoEEItineranciaActividad.relevamiento_ee_id)),
        )
        .filter(RelevamientoEEItineranciaActividad.relevamiento_ee_id.in_(ree_ids_realiza))
        .group_by(RelevamientoEEItineranciaActividad.actividad)
        .all()
    )
    actividades = sorted(
        [{"actividad": r[0], "cantidad": r[1], "pct": pct(r[1], total_realiza)} for r in act_rows],
        key=lambda x: -x["cantidad"],
    )

    # Espacios donde se realiza
    esp_rows = (
        db.query(
            RelevamientoEEItineranciaEspacio.espacio,
            func.count(func.distinct(RelevamientoEEItineranciaEspacio.relevamiento_ee_id)),
        )
        .filter(RelevamientoEEItineranciaEspacio.relevamiento_ee_id.in_(ree_ids_realiza))
        .group_by(RelevamientoEEItineranciaEspacio.espacio)
        .all()
    )
    espacios = sorted(
        [{"espacio": r[0], "cantidad": r[1], "pct": pct(r[1], total_realiza)} for r in esp_rows],
        key=lambda x: -x["cantidad"],
    )

    # Roles (texto libre)
    rol_rows = (
        db.query(
            RelevamientoEEItineranciaRol.rol,
            func.count(func.distinct(RelevamientoEEItineranciaRol.relevamiento_ee_id)),
        )
        .filter(RelevamientoEEItineranciaRol.relevamiento_ee_id.in_(ree_ids_realiza))
        .group_by(RelevamientoEEItineranciaRol.rol)
        .all()
    )
    roles = sorted(
        [{"rol": r[0], "cantidad": r[1], "pct": pct(r[1], total_realiza)} for r in rol_rows],
        key=lambda x: -x["cantidad"],
    )

    return {
        "total_ee": total,
        "realiza": realiza,
        "total_realiza": total_realiza,
        "frecuencia": frecuencia,
        "actividades": actividades,
        "espacios": espacios,
        "roles": roles,
    }


@router.get("/btu")
def btu(
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

    ree_query = (
        db.query(RelevamientoEE.id, RelevamientoEE.btu_regulares,
                 RelevamientoEE.btu_abandonaron, RelevamientoEE.btu_egresados,
                 Diocesis.id)
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
        ree_query = ree_query.filter(Relevamiento.emaus_id.in_(allowed_ids))
    if region:
        ree_query = ree_query.filter(Diocesis.region == region)
    if provincia:
        ree_query = ree_query.filter(Diocesis.provincia == provincia)
    if emaus_id:
        ree_query = ree_query.filter(Relevamiento.emaus_id == emaus_id)
    if ee_id:
        ree_query = ree_query.filter(RelevamientoEE.espacio_educativo_id == ee_id)

    ree_rows = ree_query.all()
    total = len(ree_rows)
    if not total:
        return {"total_ee": 0}

    ree_ids = [r[0] for r in ree_rows]
    regulares    = sum(r[1] for r in ree_rows if r[1])
    interrumpidos= sum(r[2] for r in ree_rows if r[2])
    egresados    = sum(r[3] for r in ree_rows if r[3])
    diocesis_con_btu = len({r[4] for r in ree_rows if r[1]})

    # Motivos de interrupción — los 6 estructurados + un solo grupo "Otro"
    # (texto libre, sin normalizar variantes)
    motivo_label = func.if_(
        RelevamientoEEBTUAbandonoMotivo.motivo.like("Otro:%"),
        "Otro",
        RelevamientoEEBTUAbandonoMotivo.motivo,
    )
    motivo_rows = (
        db.query(motivo_label, func.count(func.distinct(RelevamientoEEBTUAbandonoMotivo.relevamiento_ee_id)))
        .filter(RelevamientoEEBTUAbandonoMotivo.relevamiento_ee_id.in_(ree_ids))
        .group_by(motivo_label)
        .all()
    )
    total_con_motivo = len({
        r[0] for r in
        db.query(RelevamientoEEBTUAbandonoMotivo.relevamiento_ee_id)
        .filter(RelevamientoEEBTUAbandonoMotivo.relevamiento_ee_id.in_(ree_ids)).all()
    })
    def pct(n): return round(n / total_con_motivo * 100, 1) if total_con_motivo else 0
    motivos = sorted(
        [{"motivo": r[0], "cantidad": r[1], "pct": pct(r[1])} for r in motivo_rows],
        key=lambda x: -x["cantidad"],
    )

    return {
        "total_ee": total,
        "diocesis_con_btu": diocesis_con_btu,
        "regulares": regulares,
        "interrumpidos": interrumpidos,
        "egresados": egresados,
        "total_con_motivo": total_con_motivo,
        "motivos": motivos,
    }


@router.get("/internet")
def internet(
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

    q = (
        db.query(RelevamientoEE.internet_acceso, RelevamientoEE.internet_falta_motivo)
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
        q = q.filter(Relevamiento.emaus_id.in_(allowed_ids))
    if region:
        q = q.filter(Diocesis.region == region)
    if provincia:
        q = q.filter(Diocesis.provincia == provincia)
    if emaus_id:
        q = q.filter(Relevamiento.emaus_id == emaus_id)
    if ee_id:
        q = q.filter(RelevamientoEE.espacio_educativo_id == ee_id)

    rows = q.all()
    total = len(rows)
    if not total:
        return {"total_ee": 0, "acceso": [], "motivos": []}

    si = sum(1 for r in rows if r[0] is True)
    no = sum(1 for r in rows if r[0] is False)
    sin_respuesta = total - si - no

    motivo_counts = {}
    for r in rows:
        if r[1]:
            motivo_counts[r[1]] = motivo_counts.get(r[1], 0) + 1
    total_sin_internet = no
    motivos = sorted(
        [{"motivo": k, "cantidad": v,
          "pct": round(v / total_sin_internet * 100, 1) if total_sin_internet else 0}
         for k, v in motivo_counts.items()],
        key=lambda x: -x["cantidad"]
    )

    return {
        "total_ee": total,
        "acceso": [
            {"valor": "Sí",           "cantidad": si,           "pct": round(si / total * 100, 1)},
            {"valor": "No",           "cantidad": no,           "pct": round(no / total * 100, 1)},
            {"valor": "Sin respuesta","cantidad": sin_respuesta,"pct": round(sin_respuesta / total * 100, 1)},
        ],
        "motivos": motivos,
    }


@router.get("/apoyo-escolar")
def apoyo_escolar(
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

    # Base query: relevamiento_ee del período con filtros
    ree_query = (
        db.query(RelevamientoEE.id,
                 RelevamientoEE.apoyo_primario_frecuencia,
                 RelevamientoEE.apoyo_secundario_frecuencia)
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
        ree_query = ree_query.filter(Relevamiento.emaus_id.in_(allowed_ids))
    if region:
        ree_query = ree_query.filter(Diocesis.region == region)
    if provincia:
        ree_query = ree_query.filter(Diocesis.provincia == provincia)
    if emaus_id:
        ree_query = ree_query.filter(Relevamiento.emaus_id == emaus_id)
    if ee_id:
        ree_query = ree_query.filter(RelevamientoEE.espacio_educativo_id == ee_id)

    ree_rows = ree_query.all()
    ree_ids = [r[0] for r in ree_rows]
    total_ee = len(ree_ids)

    if not ree_ids:
        return {"total_ee": 0, "primaria": None, "secundaria": None}

    FREQ_ORDER = ["Una vez a la semana", "Dos veces a la semana", "Más de dos veces a la semana"]

    def build_nivel(freq_field_idx, contenido_model):
        # Frecuencia — solo EEs con frecuencia != NULL
        freq_counts = {}
        sin_respuesta = 0
        total_con_apoyo = 0
        for row in ree_rows:
            freq = row[freq_field_idx]
            if freq is None:
                sin_respuesta += 1
            else:
                total_con_apoyo += 1
                freq_counts[freq] = freq_counts.get(freq, 0) + 1

        frecuencia = [{"valor": f, "cantidad": freq_counts.get(f, 0)} for f in FREQ_ORDER]
        frecuencia.append({"valor": "Sin respuesta", "cantidad": sin_respuesta})

        # Contenidos — sobre EEs con apoyo en este nivel
        ree_con_apoyo_ids = [
            ree_rows[i][0] for i in range(len(ree_rows))
            if ree_rows[i][freq_field_idx] is not None
        ]

        contenido_rows = (
            db.query(contenido_model.contenido, func.count(contenido_model.relevamiento_ee_id).label("n"))
            .filter(contenido_model.relevamiento_ee_id.in_(ree_con_apoyo_ids))
            .group_by(contenido_model.contenido)
            .order_by(func.count(contenido_model.relevamiento_ee_id).desc())
            .all()
        ) if ree_con_apoyo_ids else []

        contenidos = [
            {
                "contenido": r.contenido,
                "si": r.n,
                "no": total_con_apoyo - r.n,
                "pct": round(r.n / total_con_apoyo * 100, 1) if total_con_apoyo else 0,
            }
            for r in contenido_rows
        ]

        return {
            "total_ee": total_ee,
            "total_con_apoyo": total_con_apoyo,
            "frecuencia": frecuencia,
            "contenidos": contenidos,
        }

    return {
        "total_ee": total_ee,
        "primaria":   build_nivel(1, RelevamientoEEApoyoPrimarioContenido),
        "secundaria": build_nivel(2, RelevamientoEEApoyoSecundarioContenido),
    }


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
