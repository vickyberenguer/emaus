import unicodedata
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.usuario import Usuario
from app.models.emaus import Emaus, Diocesis, ResponsableEmaus
from app.models.control import ControlRelevamiento, ControlAprobacion
from app.models.relevamiento import Relevamiento
from app.models.pastoral_pi import (
    PastoralPI, PastoralPIEnfermedadNinos, PastoralPIEnfermedadEmbarazadas,
    PastoralPIAccionLider,
)
from app.models.establecimiento import EstablecimientoArticulado, EstablecimientoEstado
from app.models.btu_becario import BtuBecario
from app.models.relevamiento_taller import RelevamientoTaller, RelevamientoTallerPerfil
from app.models.espacio_educativo import (
    EspacioEducativo, RelevamientoEE, RelevamientoEEItineranciaRol,
    RelevamientoEEAccion, RelevamientoEEApoyoPrimarioContenido,
    RelevamientoEEApoyoSecundarioContenido,
    EEAmbiente, EEServicio, EEEquipoCocina, EEEquipoInformatico, EEZona,
    RelevamientoEEGrupoMotorRol, RelevamientoEEItineranciaActividad,
    RelevamientoEEItineranciaEspacio, RelevamientoEEBTUAbandonoMotivo,
    RelevamientoEEPreocupacionJoven, RelevamientoEENivelSuperior,
)
from app.routers.auth import get_current_user, require_rol
from app.routers.control import ANIO_ACTIVO, SEMESTRE_ACTIVO, emaus_ids_for_user

router = APIRouter(prefix="/tablero", tags=["tablero"])


def emaus_ids_for_tablero(user: Usuario, db: Session) -> Optional[List[int]]:
    """Como emaus_ids_for_user, pero en el módulo Tablero los Responsables ven
    todos los Emaús (a diferencia de Control, donde solo ven los propios).
    La única excepción dentro de Tablero es la pestaña "Estado de carga",
    que sigue usando emaus_ids_for_user directamente."""
    if user.rol == "responsable":
        return None
    return emaus_ids_for_user(user, db)


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
        .join(Emaus, and_(Emaus.id == ControlRelevamiento.emaus_id, Emaus.activo == True))
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
    region: Optional[List[str]] = Query(None),
    provincia: Optional[List[str]] = Query(None),
    emaus_id: Optional[List[int]] = Query(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_rol("admin", "responsable", "tablero")),
):
    """Valores disponibles para los filtros cascada del tablero."""
    q = (
        db.query(Diocesis.region, Diocesis.provincia, Emaus.id, Emaus.nombre,
                 EspacioEducativo.id, EspacioEducativo.nombre)
        .join(Emaus, and_(Emaus.diocesis_id == Diocesis.id, Emaus.activo == True))
        .join(Relevamiento, and_(
            Relevamiento.emaus_id == Emaus.id,
            Relevamiento.anio == anio,
            Relevamiento.semestre == semestre,
        ))
        .join(RelevamientoEE, RelevamientoEE.relevamiento_id == Relevamiento.id)
        .join(EspacioEducativo, and_(
            EspacioEducativo.id == RelevamientoEE.espacio_educativo_id,
            EspacioEducativo.activo == True,
        ))
        .distinct()
        .order_by(Diocesis.region, Diocesis.provincia, Emaus.nombre, EspacioEducativo.nombre)
    )

    # Para regiones y provincias siempre devolvemos el universo completo del período
    base_all = q.all()
    regiones  = sorted({r[0] for r in base_all if r[0]})

    # Provincias filtradas por región si corresponde
    if region:
        provincias = sorted({r[1] for r in base_all if r[0] in region and r[1]})
    else:
        provincias = sorted({r[1] for r in base_all if r[1]})

    # Emaús filtrados por región y/o provincia
    base_emaus = base_all
    if region:
        base_emaus = [r for r in base_emaus if r[0] in region]
    if provincia:
        base_emaus = [r for r in base_emaus if r[1] in provincia]
    emaus_list = {r[2]: r[3] for r in base_emaus}

    # EE filtrados por región, provincia y/o emaús
    # Se antepone el nombre del Emaús porque hay EE con el mismo nombre en
    # distintos Emaús y si no, no se puede distinguir a cuál pertenece cada uno.
    base_ee = base_emaus
    if emaus_id:
        base_ee = [r for r in base_ee if r[2] in emaus_id]
    ee_list = {r[4]: f"{r[3]} - {r[5]}" for r in base_ee}

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
    region: Optional[List[str]] = Query(None),
    provincia: Optional[List[str]] = Query(None),
    emaus_id: Optional[List[int]] = Query(None),
    ee_id: Optional[List[int]] = Query(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_rol("admin", "responsable", "tablero")),
):
    allowed_ids = emaus_ids_for_tablero(current_user, db)

    # Base query: relevamiento_ee con filtros
    ree_query = (
        db.query(RelevamientoEE.id)
        .join(Relevamiento, and_(
            Relevamiento.id == RelevamientoEE.relevamiento_id,
            Relevamiento.anio == anio,
            Relevamiento.semestre == semestre,
        ))
        .join(Emaus, and_(Emaus.id == Relevamiento.emaus_id, Emaus.activo == True))
        .join(Diocesis, Diocesis.id == Emaus.diocesis_id)
        .join(EspacioEducativo, and_(
            EspacioEducativo.id == RelevamientoEE.espacio_educativo_id,
            EspacioEducativo.activo == True,
        ))
    )
    if allowed_ids is not None:
        ree_query = ree_query.filter(Relevamiento.emaus_id.in_(allowed_ids))
    if region:
        ree_query = ree_query.filter(Diocesis.region.in_(region))
    if provincia:
        ree_query = ree_query.filter(Diocesis.provincia.in_(provincia))
    if emaus_id:
        ree_query = ree_query.filter(Relevamiento.emaus_id.in_(emaus_id))
    if ee_id:
        ree_query = ree_query.filter(RelevamientoEE.espacio_educativo_id.in_(ee_id))

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
    region: Optional[List[str]] = Query(None),
    provincia: Optional[List[str]] = Query(None),
    emaus_id: Optional[List[int]] = Query(None),
    ee_id: Optional[List[int]] = Query(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_rol("admin", "responsable", "tablero")),
):
    allowed_ids = emaus_ids_for_tablero(current_user, db)

    # EEs que participaron en el período con filtros
    ee_query = (
        db.query(
            EspacioEducativo.id, EspacioEducativo.construccion_material,
            EspacioEducativo.titularidad, EspacioEducativo.acceso_principal,
            EspacioEducativo.rampa_acceso, EspacioEducativo.espacio_recreacion,
        )
        .join(RelevamientoEE, RelevamientoEE.espacio_educativo_id == EspacioEducativo.id)
        .join(Relevamiento, and_(
            Relevamiento.id == RelevamientoEE.relevamiento_id,
            Relevamiento.anio == anio,
            Relevamiento.semestre == semestre,
        ))
        .join(Emaus, and_(Emaus.id == Relevamiento.emaus_id, Emaus.activo == True))
        .join(Diocesis, Diocesis.id == Emaus.diocesis_id)
        .filter(EspacioEducativo.activo == True)
        .distinct()
    )
    if allowed_ids is not None:
        ee_query = ee_query.filter(Relevamiento.emaus_id.in_(allowed_ids))
    if region:
        ee_query = ee_query.filter(Diocesis.region.in_(region))
    if provincia:
        ee_query = ee_query.filter(Diocesis.provincia.in_(provincia))
    if emaus_id:
        ee_query = ee_query.filter(Relevamiento.emaus_id.in_(emaus_id))
    if ee_id:
        ee_query = ee_query.filter(EspacioEducativo.id.in_(ee_id))

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

    # Titularidad (a quién pertenece el espacio: diócesis, parroquia, etc.)
    titularidad_counts = {}
    for r in ee_rows:
        k = r[2] or "Sin dato"
        titularidad_counts[k] = titularidad_counts.get(k, 0) + 1

    # Acceso principal (asfalto / ripio / tierra)
    acceso_counts = {}
    for r in ee_rows:
        k = r[3] or "Sin dato"
        acceso_counts[k] = acceso_counts.get(k, 0) + 1

    # Rampa de acceso para discapacidad (sí/no)
    rampa_si = sum(1 for r in ee_rows if r[4] is True)
    rampa_no = sum(1 for r in ee_rows if r[4] is False)
    rampa_sin_dato = total - rampa_si - rampa_no
    rampa = [
        {"valor": "Sí", "cantidad": rampa_si, "pct": pct(rampa_si)},
        {"valor": "No", "cantidad": rampa_no, "pct": pct(rampa_no)},
        {"valor": "Sin dato", "cantidad": rampa_sin_dato, "pct": pct(rampa_sin_dato)},
    ]

    # Espacio de recreación: no es sí/no, las respuestas son Cubierto/Descubierto/No tiene
    recreacion_counts = {}
    for r in ee_rows:
        k = r[5] or "Sin dato"
        recreacion_counts[k] = recreacion_counts.get(k, 0) + 1

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

    # Servicios: los de tipo "sí/no" (Agua corriente, Aljibe/Reservorio, Agua
    # fuera del terreno, Cloacas, Luz de red, Señal móvil) solo cuentan si la
    # respuesta fue afirmativa — antes se contaba cualquier respuesta (incluido
    # "No") como "tiene el servicio". Los de texto libre (Residuos, Internet
    # Provisto, Combustible Cocina) siguen contando cualquier respuesta no vacía.
    SERVICIOS_SI_NO = {
        "Agua corriente", "Aljibe/Reservorio", "Agua fuera del terreno",
        "Cloacas", "Luz de red", "Señal móvil",
    }
    AFIRMATIVOS = {"true", "verdadero", "sí", "si", "1"}
    serv_counts = {}
    for servicio, valor in db.query(EEServicio.servicio, EEServicio.valor).filter(
        EEServicio.espacio_educativo_id.in_(ee_ids)
    ).all():
        if servicio in SERVICIOS_SI_NO and (valor or "").strip().lower() not in AFIRMATIVOS:
            continue
        serv_counts[servicio] = serv_counts.get(servicio, 0) + 1

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
        "titularidad": bars(titularidad_counts),
        "construccion": bars(const_counts),
        "zonas": bars(zona_counts),
        "acceso_principal": bars(acceso_counts),
        "ambientes": bars(amb_counts),
        "espacio_recreacion": bars(recreacion_counts),
        "servicios": bars(serv_counts),
        "equipos_cocina": bars(cocina_counts),
        "equipos_informatico": informatico,
        "rampa": rampa,
    }


@router.get("/grupo-motor")
def grupo_motor(
    anio: int = ANIO_ACTIVO,
    semestre: str = SEMESTRE_ACTIVO,
    region: Optional[List[str]] = Query(None),
    provincia: Optional[List[str]] = Query(None),
    emaus_id: Optional[List[int]] = Query(None),
    ee_id: Optional[List[int]] = Query(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_rol("admin", "responsable", "tablero")),
):
    allowed_ids = emaus_ids_for_tablero(current_user, db)

    ree_query = (
        db.query(RelevamientoEE.id, RelevamientoEE.grupo_motor_cantidad,
                 RelevamientoEE.grupo_motor_frecuencia)
        .join(Relevamiento, and_(
            Relevamiento.id == RelevamientoEE.relevamiento_id,
            Relevamiento.anio == anio,
            Relevamiento.semestre == semestre,
        ))
        .join(Emaus, and_(Emaus.id == Relevamiento.emaus_id, Emaus.activo == True))
        .join(Diocesis, Diocesis.id == Emaus.diocesis_id)
        .join(EspacioEducativo, and_(
            EspacioEducativo.id == RelevamientoEE.espacio_educativo_id,
            EspacioEducativo.activo == True,
        ))
    )
    if allowed_ids is not None:
        ree_query = ree_query.filter(Relevamiento.emaus_id.in_(allowed_ids))
    if region:
        ree_query = ree_query.filter(Diocesis.region.in_(region))
    if provincia:
        ree_query = ree_query.filter(Diocesis.provincia.in_(provincia))
    if emaus_id:
        ree_query = ree_query.filter(Relevamiento.emaus_id.in_(emaus_id))
    if ee_id:
        ree_query = ree_query.filter(RelevamientoEE.espacio_educativo_id.in_(ee_id))

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
    region: Optional[List[str]] = Query(None),
    provincia: Optional[List[str]] = Query(None),
    emaus_id: Optional[List[int]] = Query(None),
    ee_id: Optional[List[int]] = Query(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_rol("admin", "responsable", "tablero")),
):
    allowed_ids = emaus_ids_for_tablero(current_user, db)

    ree_query = (
        db.query(RelevamientoEE.id, RelevamientoEE.itinerancia_realizo,
                 RelevamientoEE.itinerancia_frecuencia)
        .join(Relevamiento, and_(
            Relevamiento.id == RelevamientoEE.relevamiento_id,
            Relevamiento.anio == anio,
            Relevamiento.semestre == semestre,
        ))
        .join(Emaus, and_(Emaus.id == Relevamiento.emaus_id, Emaus.activo == True))
        .join(Diocesis, Diocesis.id == Emaus.diocesis_id)
        .join(EspacioEducativo, and_(
            EspacioEducativo.id == RelevamientoEE.espacio_educativo_id,
            EspacioEducativo.activo == True,
        ))
    )
    if allowed_ids is not None:
        ree_query = ree_query.filter(Relevamiento.emaus_id.in_(allowed_ids))
    if region:
        ree_query = ree_query.filter(Diocesis.region.in_(region))
    if provincia:
        ree_query = ree_query.filter(Diocesis.provincia.in_(provincia))
    if emaus_id:
        ree_query = ree_query.filter(Relevamiento.emaus_id.in_(emaus_id))
    if ee_id:
        ree_query = ree_query.filter(RelevamientoEE.espacio_educativo_id.in_(ee_id))

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
    region: Optional[List[str]] = Query(None),
    provincia: Optional[List[str]] = Query(None),
    emaus_id: Optional[List[int]] = Query(None),
    ee_id: Optional[List[int]] = Query(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_rol("admin", "responsable", "tablero")),
):
    allowed_ids = emaus_ids_for_tablero(current_user, db)

    ree_query = (
        db.query(RelevamientoEE.id, RelevamientoEE.btu_regulares,
                 RelevamientoEE.btu_abandonaron, RelevamientoEE.btu_egresados,
                 Diocesis.id)
        .join(Relevamiento, and_(
            Relevamiento.id == RelevamientoEE.relevamiento_id,
            Relevamiento.anio == anio,
            Relevamiento.semestre == semestre,
        ))
        .join(Emaus, and_(Emaus.id == Relevamiento.emaus_id, Emaus.activo == True))
        .join(Diocesis, Diocesis.id == Emaus.diocesis_id)
        .join(EspacioEducativo, and_(
            EspacioEducativo.id == RelevamientoEE.espacio_educativo_id,
            EspacioEducativo.activo == True,
        ))
    )
    if allowed_ids is not None:
        ree_query = ree_query.filter(Relevamiento.emaus_id.in_(allowed_ids))
    if region:
        ree_query = ree_query.filter(Diocesis.region.in_(region))
    if provincia:
        ree_query = ree_query.filter(Diocesis.provincia.in_(provincia))
    if emaus_id:
        ree_query = ree_query.filter(Relevamiento.emaus_id.in_(emaus_id))
    if ee_id:
        ree_query = ree_query.filter(RelevamientoEE.espacio_educativo_id.in_(ee_id))

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


BTU_ANIO_DEFAULT = 2026

BTU_EDAD_RANGOS = [
    ("17 o menos", None, 17),
    ("18-20", 18, 20),
    ("21-23", 21, 23),
    ("24-26", 24, 26),
    ("27-29", 27, 29),
    ("30-32", 30, 32),
    ("33-35", 33, 35),
    ("36-45", 36, 45),
    ("46 o más", 46, None),
]


def _btu_rango_edad(edad: int) -> str:
    for nombre, lo, hi in BTU_EDAD_RANGOS:
        if lo is None and edad <= hi:
            return nombre
        if hi is None and edad >= lo:
            return nombre
        if lo is not None and hi is not None and lo <= edad <= hi:
            return nombre
    return "Sin dato"


def _btu_anio_a_entero(valor) -> Optional[int]:
    try:
        return int(str(valor).strip()[:4])
    except (TypeError, ValueError):
        return None


def _normalizar_carrera(s: str) -> str:
    """Clave para agrupar carreras que difieren solo en mayúsculas/minúsculas/acentos."""
    sin_acentos = unicodedata.normalize('NFKD', s)
    sin_acentos = ''.join(c for c in sin_acentos if not unicodedata.combining(c))
    return ' '.join(sin_acentos.lower().split())


# Renombres explícitos: variantes de redacción que en la práctica son la misma
# carrera (además de las que solo difieren en mayúsculas/acentos, que se
# unifican automáticamente en unificar_carreras()).
_CARRERA_RENOMBRES = {
    "profesorado de educacion secundaria de historia": "Profesorado de historia",
    "profesorado de educacion secundaria de matematica": "Profesorado de matematica",
    "educacion fisica": "Profesorado de educacion fisica",
    # "Licenciatura en X" absorbe a "X" a secas, cuando ambas formas conviven
    "trabajo social": "Licenciatura en trabajo social",
    "enfermeria": "Licenciatura en Enfermeria",
    "psicopedagogia": "Licenciatura en psicopedagogia",
    "bioquimica": "Licenciatura en bioquimica",
    "fonoaudiologia": "Licenciatura en Fonoaudiología",
    "higiene y seguridad en el trabajo": "Licenciatura en higiene y seguridad en el trabajo",
    "ciencias de la educacion": "Licenciatura en ciencias de la educacion",
    "obstetricia": "Licenciatura en obstetricia",
    "psicologia": "Licenciatura en psicologia",
}


def _mejor_variante(variantes: List[str]) -> str:
    """Entre variantes que solo difieren en mayúsculas/acentos, prioriza la que
    tenga acentos y una capitalización prolija (ni todo mayúsculas ni todo
    minúsculas)."""
    def score(s: str):
        acentos = sum(1 for c in unicodedata.normalize('NFKD', s) if unicodedata.combining(c))
        return (acentos, 0 if s.isupper() else 1, 0 if s.islower() else 1, -len(s))
    return max(variantes, key=score)


def unificar_carreras(items: Dict[str, int]) -> Dict[str, int]:
    """Unifica variantes de una misma carrera: aplica renombres explícitos y
    agrupa lo que quede por mayúsculas/minúsculas/acentos, eligiendo como
    nombre final la variante mejor escrita (con acentos y capitalizada)."""
    renombradas: Dict[str, int] = {}
    for carrera, cantidad in items.items():
        nueva = _CARRERA_RENOMBRES.get(_normalizar_carrera(carrera), carrera)
        renombradas[nueva] = renombradas.get(nueva, 0) + cantidad

    grupos: Dict[str, List[str]] = {}
    for carrera in renombradas:
        grupos.setdefault(_normalizar_carrera(carrera), []).append(carrera)

    resultado: Dict[str, int] = {}
    for variantes in grupos.values():
        canonica = _mejor_variante(variantes)
        resultado[canonica] = sum(renombradas[v] for v in variantes)
    return resultado


@router.get("/btu-becarios")
def btu_becarios(
    anio: int = BTU_ANIO_DEFAULT,
    region: Optional[List[str]] = Query(None),
    provincia: Optional[List[str]] = Query(None),
    emaus_id: Optional[List[int]] = Query(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_rol("admin", "responsable", "tablero")),
):
    """Datos individuales de becarios BTU (scrapeados aparte, ver
    scripts/scraper_btu_becarios.py). Solo becarios activos — nunca se
    expone DNI ni nombre, solo agregados."""
    allowed_ids = emaus_ids_for_tablero(current_user, db)

    query = (
        db.query(BtuBecario)
        .join(Emaus, and_(Emaus.id == BtuBecario.emaus_id, Emaus.activo == True))
        .join(Diocesis, Diocesis.id == Emaus.diocesis_id)
        .filter(BtuBecario.anio == anio, BtuBecario.activo == True)
    )
    if allowed_ids is not None:
        query = query.filter(BtuBecario.emaus_id.in_(allowed_ids))
    if region:
        query = query.filter(Diocesis.region.in_(region))
    if provincia:
        query = query.filter(Diocesis.provincia.in_(provincia))
    if emaus_id:
        query = query.filter(BtuBecario.emaus_id.in_(emaus_id))

    becarios = query.all()
    total = len(becarios)
    if not total:
        return {"total_becarios": 0}

    def pct(n, base=None):
        b = total if base is None else base
        return round(n / b * 100, 1) if b else 0

    # Edad promedio y antigüedades (se usa el año de la hoja como referencia)
    edades = [b.edad for b in becarios if b.edad is not None]
    edad_promedio = round(sum(edades) / len(edades), 1) if edades else None

    ant_beca = [anio - y for b in becarios if (y := _btu_anio_a_entero(b.anio_comienzo_beca)) is not None and anio - y >= 0]
    antiguedad_beca_promedio = round(sum(ant_beca) / len(ant_beca), 1) if ant_beca else None

    ant_alumno = [anio - y for b in becarios if (y := _btu_anio_a_entero(b.anio_comienzo_carrera)) is not None and anio - y >= 0]
    antiguedad_alumno_promedio = round(sum(ant_alumno) / len(ant_alumno), 1) if ant_alumno else None

    def contar(attr):
        counts = {}
        for b in becarios:
            k = getattr(b, attr) or "Sin dato"
            counts[k] = counts.get(k, 0) + 1
        return sorted(
            [{"valor": k, "cantidad": v, "pct": pct(v)} for k, v in counts.items()],
            key=lambda x: -x["cantidad"],
        )

    sexo = contar("sexo")
    ambito = contar("ambito")
    nivel = contar("nivel")

    # Edad y sexo por rango etario
    edad_sexo_counts = {r[0]: {"F": 0, "M": 0} for r in BTU_EDAD_RANGOS}
    for b in becarios:
        if b.edad is None or b.sexo not in ("F", "M"):
            continue
        edad_sexo_counts[_btu_rango_edad(b.edad)][b.sexo] += 1
    edad_sexo = [
        {"rango": r[0], "F": edad_sexo_counts[r[0]]["F"], "M": edad_sexo_counts[r[0]]["M"]}
        for r in BTU_EDAD_RANGOS
        if edad_sexo_counts[r[0]]["F"] or edad_sexo_counts[r[0]]["M"]
    ]

    # Ranking de Rama
    rama_counts = {}
    carreras_por_rama = {}
    for b in becarios:
        k = b.rama or "Sin clasificar"
        rama_counts[k] = rama_counts.get(k, 0) + 1
        carr = (b.carrera or "Sin dato").strip() or "Sin dato"
        carreras_por_rama.setdefault(k, {})
        carreras_por_rama[k][carr] = carreras_por_rama[k].get(carr, 0) + 1

    rama = sorted(
        [{"rama": k, "cantidad": v, "pct": pct(v)} for k, v in rama_counts.items()],
        key=lambda x: -x["cantidad"],
    )
    for k, carreras in carreras_por_rama.items():
        total_rama = rama_counts.get(k) or 1
        carreras = unificar_carreras(carreras)
        carreras_por_rama[k] = sorted(
            [{"carrera": c, "cantidad": v, "pct": round(v / total_rama * 100, 1)} for c, v in carreras.items()],
            key=lambda x: -x["cantidad"],
        )

    # Rama x Sexo
    rama_sexo_counts = {}
    for b in becarios:
        k = b.rama or "Sin clasificar"
        d = rama_sexo_counts.setdefault(k, {"F": 0, "M": 0})
        if b.sexo in ("F", "M"):
            d["F" if b.sexo == "F" else "M"] += 1
    rama_sexo = []
    for k, d in rama_sexo_counts.items():
        tot = d["F"] + d["M"]
        rama_sexo.append({
            "rama": k, "F": d["F"], "M": d["M"],
            "F_pct": round(d["F"] / tot * 100, 1) if tot else 0,
            "M_pct": round(d["M"] / tot * 100, 1) if tot else 0,
        })
    rama_sexo.sort(key=lambda x: -(x["F"] + x["M"]))

    # Instancia de la carrera: Principio / Mitad / Final según Anio_cursando / Duracion_Carrera
    instancia_counts = {}
    for b in becarios:
        anio_cursando = _btu_anio_a_entero(b.anio_cursando)
        duracion = _btu_anio_a_entero(b.duracion_carrera)
        if not anio_cursando or not duracion:
            continue
        p = anio_cursando / duracion * 100
        valor = "Principio" if p < 33 else ("Mitad" if p < 66 else "Final")
        instancia_counts[valor] = instancia_counts.get(valor, 0) + 1
    total_instancia = sum(instancia_counts.values())
    instancia_carrera = [
        {"valor": v, "cantidad": c, "pct": round(c / total_instancia * 100, 1) if total_instancia else 0}
        for v, c in instancia_counts.items()
    ]

    return {
        "total_becarios": total,
        "edad_promedio": edad_promedio,
        "antiguedad_beca_promedio": antiguedad_beca_promedio,
        "antiguedad_alumno_promedio": antiguedad_alumno_promedio,
        "sexo": sexo,
        "ambito": ambito,
        "nivel": nivel,
        "edad_sexo": edad_sexo,
        "rama": rama,
        "rama_sexo": rama_sexo,
        "carreras_por_rama": carreras_por_rama,
        "instancia_carrera": instancia_carrera,
    }


@router.get("/ayj-preocupaciones")
def ayj_preocupaciones(
    anio: int = ANIO_ACTIVO,
    semestre: str = SEMESTRE_ACTIVO,
    region: Optional[List[str]] = Query(None),
    provincia: Optional[List[str]] = Query(None),
    emaus_id: Optional[List[int]] = Query(None),
    ee_id: Optional[List[int]] = Query(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_rol("admin", "responsable", "tablero")),
):
    allowed_ids = emaus_ids_for_tablero(current_user, db)

    ree_query = (
        db.query(RelevamientoEE.id)
        .join(Relevamiento, and_(
            Relevamiento.id == RelevamientoEE.relevamiento_id,
            Relevamiento.anio == anio,
            Relevamiento.semestre == semestre,
        ))
        .join(Emaus, and_(Emaus.id == Relevamiento.emaus_id, Emaus.activo == True))
        .join(Diocesis, Diocesis.id == Emaus.diocesis_id)
        .join(EspacioEducativo, and_(
            EspacioEducativo.id == RelevamientoEE.espacio_educativo_id,
            EspacioEducativo.activo == True,
        ))
    )
    if allowed_ids is not None:
        ree_query = ree_query.filter(Relevamiento.emaus_id.in_(allowed_ids))
    if region:
        ree_query = ree_query.filter(Diocesis.region.in_(region))
    if provincia:
        ree_query = ree_query.filter(Diocesis.provincia.in_(provincia))
    if emaus_id:
        ree_query = ree_query.filter(Relevamiento.emaus_id.in_(emaus_id))
    if ee_id:
        ree_query = ree_query.filter(RelevamientoEE.espacio_educativo_id.in_(ee_id))

    ree_ids = [r[0] for r in ree_query.all()]
    total = len(ree_ids)
    if not total:
        return {"total_ee": 0}

    rows = (
        db.query(
            RelevamientoEEPreocupacionJoven.relevamiento_ee_id,
            RelevamientoEEPreocupacionJoven.preocupacion,
            RelevamientoEEPreocupacionJoven.ranking,
        )
        .filter(RelevamientoEEPreocupacionJoven.relevamiento_ee_id.in_(ree_ids))
        .all()
    )

    from collections import defaultdict
    stats = defaultdict(lambda: {"suma": 0, "cantidad": 0, "top1": 0})
    ee_con_dato = set()
    for ree_id, preo, rank in rows:
        if rank is None:
            continue
        ee_con_dato.add(ree_id)
        s = stats[preo]
        s["suma"] += rank
        s["cantidad"] += 1
        if rank == 1:
            s["top1"] += 1

    total_con_ranking = len(ee_con_dato)
    if not total_con_ranking:
        return {"total_ee": total, "total_con_ranking": 0, "situaciones": []}

    situaciones = [
        {
            "situacion": preo,
            "promedio": round(s["suma"] / s["cantidad"], 2),
            "cantidad": s["cantidad"],
            "veces_top1": s["top1"],
            "pct_top1": round(s["top1"] / total_con_ranking * 100, 1),
        }
        for preo, s in stats.items()
    ]
    situaciones.sort(key=lambda x: x["promedio"])

    return {
        "total_ee": total,
        "total_con_ranking": total_con_ranking,
        "situaciones": situaciones,
    }


@router.get("/becas-familiares")
def becas_familiares(
    anio: int = ANIO_ACTIVO,
    semestre: str = SEMESTRE_ACTIVO,
    region: Optional[List[str]] = Query(None),
    provincia: Optional[List[str]] = Query(None),
    emaus_id: Optional[List[int]] = Query(None),
    ee_id: Optional[List[int]] = Query(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_rol("admin", "responsable", "tablero")),
):
    allowed_ids = emaus_ids_for_tablero(current_user, db)

    ree_query = (
        db.query(
            RelevamientoEE.id, RelevamientoEE.bf_apoyo_escolar,
            RelevamientoEE.bf_nivel_inicial, RelevamientoEE.bf_primaria,
            RelevamientoEE.bf_secundaria, RelevamientoEE.bf_asignaciones,
            RelevamientoEE.bf_discapacidad, RelevamientoEE.bf_cud,
            Diocesis.id,
        )
        .join(Relevamiento, and_(
            Relevamiento.id == RelevamientoEE.relevamiento_id,
            Relevamiento.anio == anio,
            Relevamiento.semestre == semestre,
        ))
        .join(Emaus, and_(Emaus.id == Relevamiento.emaus_id, Emaus.activo == True))
        .join(Diocesis, Diocesis.id == Emaus.diocesis_id)
        .join(EspacioEducativo, and_(
            EspacioEducativo.id == RelevamientoEE.espacio_educativo_id,
            EspacioEducativo.activo == True,
        ))
    )
    if allowed_ids is not None:
        ree_query = ree_query.filter(Relevamiento.emaus_id.in_(allowed_ids))
    if region:
        ree_query = ree_query.filter(Diocesis.region.in_(region))
    if provincia:
        ree_query = ree_query.filter(Diocesis.provincia.in_(provincia))
    if emaus_id:
        ree_query = ree_query.filter(Relevamiento.emaus_id.in_(emaus_id))
    if ee_id:
        ree_query = ree_query.filter(RelevamientoEE.espacio_educativo_id.in_(ee_id))

    ree_rows = ree_query.all()
    total = len(ree_rows)
    if not total:
        return {"total_ee": 0}

    def suma(idx): return sum(r[idx] for r in ree_rows if r[idx])

    apoyo_escolar = suma(1)
    nivel_inicial  = suma(2)
    primaria       = suma(3)
    secundaria     = suma(4)
    asignaciones   = suma(5)
    discapacidad   = suma(6)
    cud            = suma(7)
    diocesis_con_bf = len({r[8] for r in ree_rows if r[1]})

    niveles_raw = [
        ("Nivel Inicial", nivel_inicial),
        ("Escuela Primaria", primaria),
        ("Escuela Secundaria", secundaria),
        ("Apoyo Escolar", apoyo_escolar),
    ]
    max_val = max((v for _, v in niveles_raw), default=0) or 1
    niveles = sorted(
        [{"nivel": n, "cantidad": v, "pct": round(v / max_val * 100, 1)} for n, v in niveles_raw],
        key=lambda x: -x["cantidad"],
    )

    return {
        "total_ee": total,
        "diocesis_con_bf": diocesis_con_bf,
        "niveles": niveles,
        "asignaciones": asignaciones,
        "discapacidad": discapacidad,
        "cud": cud,
        "pct_cud": round(cud / discapacidad * 100, 1) if discapacidad else 0,
    }


@router.get("/primera-infancia")
def primera_infancia(
    anio: int = ANIO_ACTIVO,
    semestre: str = SEMESTRE_ACTIVO,
    region: Optional[List[str]] = Query(None),
    provincia: Optional[List[str]] = Query(None),
    emaus_id: Optional[List[int]] = Query(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_rol("admin", "responsable", "tablero")),
):
    # PI es un dato por Emaús (no por EE): sin filtro de EE.
    allowed_ids = emaus_ids_for_tablero(current_user, db)

    query = (
        db.query(PastoralPI, Diocesis.id)
        .join(Relevamiento, Relevamiento.id == PastoralPI.relevamiento_id)
        .join(Emaus, and_(Emaus.id == Relevamiento.emaus_id, Emaus.activo == True))
        .join(Diocesis, Diocesis.id == Emaus.diocesis_id)
        .filter(Relevamiento.anio == anio, Relevamiento.semestre == semestre)
    )
    if allowed_ids is not None:
        query = query.filter(Relevamiento.emaus_id.in_(allowed_ids))
    if region:
        query = query.filter(Diocesis.region.in_(region))
    if provincia:
        query = query.filter(Diocesis.provincia.in_(provincia))
    if emaus_id:
        query = query.filter(Relevamiento.emaus_id.in_(emaus_id))

    rows = query.all()
    total = len(rows)
    if not total:
        return {"total_emaus": 0}

    def suma(attr): return sum(getattr(pi, attr) or 0 for pi, _ in rows)

    diocesis_con_pi = len({d for _, d in rows})
    pi_ids = [pi.id for pi, _ in rows]

    # Metodología presentada a otras comunidades (Sí/No/Sin dato)
    si = sum(1 for pi, _ in rows if pi.presento_metodologia is True)
    no = sum(1 for pi, _ in rows if pi.presento_metodologia is False)
    sin_dato = total - si - no
    metodologia = [
        {"valor": "Sí",        "cantidad": si,       "pct": round(si / total * 100, 1)},
        {"valor": "No",        "cantidad": no,       "pct": round(no / total * 100, 1)},
        {"valor": "Sin dato",  "cantidad": sin_dato, "pct": round(sin_dato / total * 100, 1)},
    ]
    comunidades_metodologia = suma("comunidades_sin_pastoral")

    ninos_raw = [
        ("0 a 3 años", suma("ninos_0_3")),
        ("4 a 6 años", suma("ninos_4_6")),
    ]
    max_ninos = max((v for _, v in ninos_raw), default=0) or 1
    ninos = [{"grupo": g, "cantidad": v, "pct": round(v / max_ninos * 100, 1)} for g, v in ninos_raw]

    madres_raw = [
        ("Embarazadas 12 a 18 años", suma("madres_embarazadas_12_18")),
        ("Embarazadas 19 a 29 años", suma("madres_embarazadas_19_29")),
        ("Embarazadas 30 años o más", suma("madres_embarazadas_30_mas")),
        ("No embarazadas", suma("madres_no_embarazadas")),
    ]
    max_madres = max((v for _, v in madres_raw), default=0) or 1
    madres = [{"grupo": g, "cantidad": v, "pct": round(v / max_madres * 100, 1)} for g, v in madres_raw]

    def top_enfermedades(model, id_field):
        enf_rows = (
            db.query(model.enfermedad, func.count(model.id))
            .filter(id_field.in_(pi_ids))
            .group_by(model.enfermedad)
            .all()
        )
        total_enf = sum(r[1] for r in enf_rows) or 1
        return sorted(
            [{"enfermedad": r[0], "cantidad": r[1], "pct": round(r[1] / total_enf * 100, 1)} for r in enf_rows],
            key=lambda x: -x["cantidad"],
        )

    enfermedades_ninos = top_enfermedades(PastoralPIEnfermedadNinos, PastoralPIEnfermedadNinos.pastoral_pi_id)
    enfermedades_mujeres = top_enfermedades(PastoralPIEnfermedadEmbarazadas, PastoralPIEnfermedadEmbarazadas.pastoral_pi_id)

    return {
        "total_emaus": total,
        "diocesis_con_pi": diocesis_con_pi,
        "lideres": suma("lideres"),
        "capacitadoras": suma("capacitadoras"),
        "familias": suma("familias"),
        "comunidades_total": suma("comunidades_total"),
        "ninos": ninos,
        "madres": madres,
        "enfermedades_ninos": enfermedades_ninos,
        "enfermedades_mujeres": enfermedades_mujeres,
        "metodologia": metodologia,
        "comunidades_metodologia": comunidades_metodologia,
    }


@router.get("/primera-infancia-acciones")
def primera_infancia_acciones(
    anio: int = ANIO_ACTIVO,
    semestre: str = SEMESTRE_ACTIVO,
    region: Optional[List[str]] = Query(None),
    provincia: Optional[List[str]] = Query(None),
    emaus_id: Optional[List[int]] = Query(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_rol("admin", "responsable", "tablero")),
):
    # PI es un dato por Emaús (no por EE): sin filtro de EE.
    allowed_ids = emaus_ids_for_tablero(current_user, db)

    query = (
        db.query(PastoralPI.id, Diocesis.id)
        .join(Relevamiento, Relevamiento.id == PastoralPI.relevamiento_id)
        .join(Emaus, and_(Emaus.id == Relevamiento.emaus_id, Emaus.activo == True))
        .join(Diocesis, Diocesis.id == Emaus.diocesis_id)
        .filter(Relevamiento.anio == anio, Relevamiento.semestre == semestre)
    )
    if allowed_ids is not None:
        query = query.filter(Relevamiento.emaus_id.in_(allowed_ids))
    if region:
        query = query.filter(Diocesis.region.in_(region))
    if provincia:
        query = query.filter(Diocesis.provincia.in_(provincia))
    if emaus_id:
        query = query.filter(Relevamiento.emaus_id.in_(emaus_id))

    rows = query.all()
    total = len(rows)
    if not total:
        return {"total_emaus": 0}

    diocesis_por_pi = {pi_id: dioc_id for pi_id, dioc_id in rows}
    pi_ids = list(diocesis_por_pi.keys())

    accion_rows = (
        db.query(
            PastoralPIAccionLider.pastoral_pi_id,
            PastoralPIAccionLider.accion,
            PastoralPIAccionLider.frecuencia,
            PastoralPIAccionLider.cantidad_semestre,
        )
        .filter(PastoralPIAccionLider.pastoral_pi_id.in_(pi_ids))
        .filter(PastoralPIAccionLider.realiza == True)
        .all()
    )

    ACCIONES = [
        ("celebracion_vida",     "Celebración de la vida"),
        ("visita_domiciliaria",  "Visita domiciliaria"),
        ("reunion_evaluacion",   "Reunión de evaluación"),
    ]

    resultado = {}
    for clave, label in ACCIONES:
        filas = [r for r in accion_rows if r[1] == clave]
        diocesis_con_accion = len({diocesis_por_pi[r[0]] for r in filas})
        cantidad_total = sum(r[3] or 0 for r in filas)

        freq_counts: Dict[str, int] = {}
        for r in filas:
            k = (r[2] or "Sin dato").strip() or "Sin dato"
            freq_counts[k] = freq_counts.get(k, 0) + 1
        total_freq = len(filas) or 1
        frecuencia = sorted(
            [{"valor": k, "cantidad": v, "pct": round(v / total_freq * 100, 1)} for k, v in freq_counts.items()],
            key=lambda x: -x["cantidad"],
        )

        resultado[clave] = {
            "label": label,
            "diocesis_con_accion": diocesis_con_accion,
            "cantidad_total": cantidad_total,
            "frecuencia": frecuencia,
        }

    return {"total_emaus": total, "acciones": resultado}


@router.get("/articulaciones")
def articulaciones_tab(
    anio: int = ANIO_ACTIVO,
    semestre: str = SEMESTRE_ACTIVO,
    region: Optional[List[str]] = Query(None),
    provincia: Optional[List[str]] = Query(None),
    emaus_id: Optional[List[int]] = Query(None),
    ee_id: Optional[List[int]] = Query(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_rol("admin", "responsable", "tablero")),
):
    """Articulación con instituciones educativas de Nivel Superior
    (Terciario/Universitario) — campos C238-C251 de la hoja EE."""
    allowed_ids = emaus_ids_for_tablero(current_user, db)

    ree_query = (
        db.query(RelevamientoEE, Diocesis.id)
        .join(Relevamiento, and_(
            Relevamiento.id == RelevamientoEE.relevamiento_id,
            Relevamiento.anio == anio,
            Relevamiento.semestre == semestre,
        ))
        .join(Emaus, and_(Emaus.id == Relevamiento.emaus_id, Emaus.activo == True))
        .join(Diocesis, Diocesis.id == Emaus.diocesis_id)
        .join(EspacioEducativo, and_(
            EspacioEducativo.id == RelevamientoEE.espacio_educativo_id,
            EspacioEducativo.activo == True,
        ))
    )
    if allowed_ids is not None:
        ree_query = ree_query.filter(Relevamiento.emaus_id.in_(allowed_ids))
    if region:
        ree_query = ree_query.filter(Diocesis.region.in_(region))
    if provincia:
        ree_query = ree_query.filter(Diocesis.provincia.in_(provincia))
    if emaus_id:
        ree_query = ree_query.filter(Relevamiento.emaus_id.in_(emaus_id))
    if ee_id:
        ree_query = ree_query.filter(RelevamientoEE.espacio_educativo_id.in_(ee_id))

    ree_rows = ree_query.all()
    total = len(ree_rows)
    if not total:
        return {"total_ee": 0}

    def pct(n, sobre):
        return round(n / sobre * 100, 1) if sobre else 0

    diocesis_con_articulacion = len({
        diocesis_id for ree, diocesis_id in ree_rows if ree.articula_nivel_superior is True
    })

    articula_counts = {"Sí": 0, "No": 0, "Sin dato": 0}
    for ree, _ in ree_rows:
        if ree.articula_nivel_superior is True:
            articula_counts["Sí"] += 1
        elif ree.articula_nivel_superior is False:
            articula_counts["No"] += 1
        else:
            articula_counts["Sin dato"] += 1
    articula = sorted(
        [{"valor": k, "cantidad": v, "pct": pct(v, total)} for k, v in articula_counts.items() if v > 0],
        key=lambda x: -x["cantidad"],
    )

    ree_articula_si = [ree for ree, _ in ree_rows if ree.articula_nivel_superior is True]
    total_articula_si = len(ree_articula_si)
    cantidad_counts: Dict[str, int] = {}
    for ree in ree_articula_si:
        k = str(ree.nivel_superior_cantidad) if ree.nivel_superior_cantidad else "Sin dato"
        cantidad_counts[k] = cantidad_counts.get(k, 0) + 1
    cantidad_instituciones = sorted(
        [{"valor": k, "cantidad": v, "pct": pct(v, total_articula_si)} for k, v in cantidad_counts.items()],
        key=lambda x: (x["valor"] == "Sin dato", int(x["valor"]) if x["valor"] != "Sin dato" else 0),
    )

    ree_ids = [ree.id for ree, _ in ree_rows]
    acciones_rows = (
        db.query(RelevamientoEENivelSuperior.tipo_acciones, func.count())
        .filter(RelevamientoEENivelSuperior.relevamiento_ee_id.in_(ree_ids))
        .group_by(RelevamientoEENivelSuperior.tipo_acciones)
        .all()
    ) if ree_ids else []
    total_acciones = sum(c for _, c in acciones_rows)
    acciones = sorted(
        [{"valor": (t or "Sin dato"), "cantidad": c, "pct": pct(c, total_acciones)} for t, c in acciones_rows],
        key=lambda x: -x["cantidad"],
    )

    return {
        "total_ee": total,
        "diocesis_con_articulacion": diocesis_con_articulacion,
        "articula": articula,
        "cantidad_instituciones": cantidad_instituciones,
        "acciones": acciones,
    }


@router.get("/establecimientos")
def establecimientos_tab(
    anio: int = ANIO_ACTIVO,
    semestre: str = SEMESTRE_ACTIVO,
    region: Optional[List[str]] = Query(None),
    provincia: Optional[List[str]] = Query(None),
    emaus_id: Optional[List[int]] = Query(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_rol("admin", "responsable", "tablero")),
):
    # Establecimientos es un dato por Emaús (cargado directo en la app, no por EE ni scrapeado).
    allowed_ids = emaus_ids_for_tablero(current_user, db)

    query = (
        db.query(EstablecimientoArticulado, EstablecimientoEstado)
        .join(Relevamiento, Relevamiento.id == EstablecimientoArticulado.relevamiento_id)
        .join(Emaus, and_(Emaus.id == Relevamiento.emaus_id, Emaus.activo == True))
        .join(Diocesis, Diocesis.id == Emaus.diocesis_id)
        .outerjoin(EstablecimientoEstado, EstablecimientoEstado.id == EstablecimientoArticulado.establecimiento_id)
        .filter(Relevamiento.anio == anio, Relevamiento.semestre == semestre)
    )
    if allowed_ids is not None:
        query = query.filter(Relevamiento.emaus_id.in_(allowed_ids))
    if region:
        query = query.filter(Diocesis.region.in_(region))
    if provincia:
        query = query.filter(Diocesis.provincia.in_(provincia))
    if emaus_id:
        query = query.filter(Relevamiento.emaus_id.in_(emaus_id))

    rows = query.all()
    total = len(rows)
    if not total:
        return {"total_establecimientos": 0}

    def pct(n): return round(n / total * 100, 1) if total else 0

    acciones_raw = [
        ("Alfabetización", sum(1 for a, _ in rows if a.accion_articulacion_alfa)),
        ("Seguimiento",     sum(1 for a, _ in rows if a.accion_seguimiento)),
        ("Intercambio",     sum(1 for a, _ in rows if a.accion_intercambio)),
        ("Institución",     sum(1 for a, _ in rows if a.accion_institucion)),
        ("Otras",           sum(1 for a, _ in rows if a.accion_otros)),
    ]
    acciones = sorted(
        [{"accion": n, "cantidad": v, "pct": pct(v)} for n, v in acciones_raw],
        key=lambda x: -x["cantidad"],
    )

    ambito_counts: Dict[str, int] = {}
    jurisdiccion_counts: Dict[str, int] = {}
    for a, e in rows:
        amb = (e.ambito if e else None) or "Sin dato"
        ambito_counts[amb] = ambito_counts.get(amb, 0) + 1
        jur = (e.jurisdiccion if e else None) or "Sin dato"
        jurisdiccion_counts[jur] = jurisdiccion_counts.get(jur, 0) + 1

    ambito = sorted(
        [{"valor": k, "cantidad": v, "pct": pct(v)} for k, v in ambito_counts.items()],
        key=lambda x: -x["cantidad"],
    )
    jurisdiccion = sorted(
        [{"jurisdiccion": k, "cantidad": v, "pct": pct(v)} for k, v in jurisdiccion_counts.items()],
        key=lambda x: -x["cantidad"],
    )

    niveles_raw = [
        ("Primario",                          sum(1 for _, e in rows if e and e.primario)),
        ("Secundario",                        sum(1 for _, e in rows if e and e.secundario)),
        ("Adultos",                           sum(1 for _, e in rows if e and e.adultos)),
        ("Formación Profesional",             sum(1 for _, e in rows if e and e.formacion_profesional)),
        ("Alfabetización",                    sum(1 for _, e in rows if e and e.alfabetizacion)),
        ("Nivel Inicial - Jardín Maternal",   sum(1 for _, e in rows if e and e.nivel_inicial_maternal)),
        ("Nivel Inicial - Jardín de Infantes", sum(1 for _, e in rows if e and e.nivel_inicial_infantes)),
    ]
    niveles = sorted(
        [{"nivel": n, "cantidad": v, "pct": pct(v)} for n, v in niveles_raw],
        key=lambda x: -x["cantidad"],
    )

    return {
        "total_establecimientos": total,
        "acciones": acciones,
        "ambito": ambito,
        "niveles": niveles,
        "jurisdiccion": jurisdiccion,
    }


@router.get("/internet")
def internet(
    anio: int = ANIO_ACTIVO,
    semestre: str = SEMESTRE_ACTIVO,
    region: Optional[List[str]] = Query(None),
    provincia: Optional[List[str]] = Query(None),
    emaus_id: Optional[List[int]] = Query(None),
    ee_id: Optional[List[int]] = Query(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_rol("admin", "responsable", "tablero")),
):
    allowed_ids = emaus_ids_for_tablero(current_user, db)

    q = (
        db.query(RelevamientoEE.internet_acceso, RelevamientoEE.internet_falta_motivo)
        .join(Relevamiento, and_(
            Relevamiento.id == RelevamientoEE.relevamiento_id,
            Relevamiento.anio == anio,
            Relevamiento.semestre == semestre,
        ))
        .join(Emaus, and_(Emaus.id == Relevamiento.emaus_id, Emaus.activo == True))
        .join(Diocesis, Diocesis.id == Emaus.diocesis_id)
        .join(EspacioEducativo, and_(
            EspacioEducativo.id == RelevamientoEE.espacio_educativo_id,
            EspacioEducativo.activo == True,
        ))
    )
    if allowed_ids is not None:
        q = q.filter(Relevamiento.emaus_id.in_(allowed_ids))
    if region:
        q = q.filter(Diocesis.region.in_(region))
    if provincia:
        q = q.filter(Diocesis.provincia.in_(provincia))
    if emaus_id:
        q = q.filter(Relevamiento.emaus_id.in_(emaus_id))
    if ee_id:
        q = q.filter(RelevamientoEE.espacio_educativo_id.in_(ee_id))

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
    region: Optional[List[str]] = Query(None),
    provincia: Optional[List[str]] = Query(None),
    emaus_id: Optional[List[int]] = Query(None),
    ee_id: Optional[List[int]] = Query(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_rol("admin", "responsable", "tablero")),
):
    allowed_ids = emaus_ids_for_tablero(current_user, db)

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
        .join(Emaus, and_(Emaus.id == Relevamiento.emaus_id, Emaus.activo == True))
        .join(Diocesis, Diocesis.id == Emaus.diocesis_id)
        .join(EspacioEducativo, and_(
            EspacioEducativo.id == RelevamientoEE.espacio_educativo_id,
            EspacioEducativo.activo == True,
        ))
    )
    if allowed_ids is not None:
        ree_query = ree_query.filter(Relevamiento.emaus_id.in_(allowed_ids))
    if region:
        ree_query = ree_query.filter(Diocesis.region.in_(region))
    if provincia:
        ree_query = ree_query.filter(Diocesis.provincia.in_(provincia))
    if emaus_id:
        ree_query = ree_query.filter(Relevamiento.emaus_id.in_(emaus_id))
    if ee_id:
        ree_query = ree_query.filter(RelevamientoEE.espacio_educativo_id.in_(ee_id))

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
    region: Optional[List[str]] = Query(None),
    provincia: Optional[List[str]] = Query(None),
    emaus_id: Optional[List[int]] = Query(None),
    ee_id: Optional[List[int]] = Query(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_rol("admin", "responsable", "tablero")),
):
    allowed_ids = emaus_ids_for_tablero(current_user, db)

    query = (
        db.query(RelevamientoEE)
        .join(Relevamiento, and_(
            Relevamiento.id == RelevamientoEE.relevamiento_id,
            Relevamiento.anio == anio,
            Relevamiento.semestre == semestre,
        ))
        .join(Emaus, and_(Emaus.id == Relevamiento.emaus_id, Emaus.activo == True))
        .join(Diocesis, Diocesis.id == Emaus.diocesis_id)
        .join(EspacioEducativo, and_(
            EspacioEducativo.id == RelevamientoEE.espacio_educativo_id,
            EspacioEducativo.activo == True,
        ))
    )

    if allowed_ids is not None:
        query = query.filter(Relevamiento.emaus_id.in_(allowed_ids))
    if region:
        query = query.filter(Diocesis.region.in_(region))
    if provincia:
        query = query.filter(Diocesis.provincia.in_(provincia))
    if emaus_id:
        query = query.filter(Relevamiento.emaus_id.in_(emaus_id))
    if ee_id:
        query = query.filter(RelevamientoEE.espacio_educativo_id.in_(ee_id))

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

    # Cantidad de Emaús distintos en el alcance filtrado
    relevamiento_ids = list({r.relevamiento_id for r in rees})
    emaus_count = 0
    if relevamiento_ids:
        emaus_count = db.query(func.count(func.distinct(Relevamiento.emaus_id))) \
            .filter(Relevamiento.id.in_(relevamiento_ids)).scalar() or 0

    # Provincias distintas en el alcance filtrado
    provincias_count = 0
    if relevamiento_ids:
        provincias_count = db.query(func.count(func.distinct(Diocesis.provincia))) \
            .join(Emaus, and_(Emaus.diocesis_id == Diocesis.id, Emaus.activo == True)) \
            .join(Relevamiento, Relevamiento.emaus_id == Emaus.id) \
            .filter(Relevamiento.id.in_(relevamiento_ids)).scalar() or 0

    # Emaús con Primera Infancia cargada, dentro del mismo alcance filtrado
    pi_count = 0
    if relevamiento_ids:
        pi_count = db.query(func.count(func.distinct(Relevamiento.emaus_id))) \
            .join(PastoralPI, PastoralPI.relevamiento_id == Relevamiento.id) \
            .filter(Relevamiento.id.in_(relevamiento_ids)).scalar() or 0

    btu_total = s("btu_regulares")
    bf_total = s("bf_nivel_inicial") + s("bf_primaria") + s("bf_secundaria")

    return {
        "ee_count": ee_count,
        "emaus_count": emaus_count,
        "provincias_count": provincias_count,
        "pi_count": pi_count,
        "btu_total": btu_total,
        "bf_total": bf_total,
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


@router.get("/talleres")
def talleres_tab(
    anio: int = ANIO_ACTIVO,
    semestre: str = SEMESTRE_ACTIVO,
    region: Optional[List[str]] = Query(None),
    provincia: Optional[List[str]] = Query(None),
    emaus_id: Optional[List[int]] = Query(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_rol("admin", "responsable", "tablero")),
):
    """Datos de la hoja Talleres (una fila por taller, ver scraper_control.py
    upsert_talleres). rubro_tematico y perfil_capacitador se clasifican por
    palabras clave a partir de texto libre — primer intento, se puede ajustar."""
    allowed_ids = emaus_ids_for_tablero(current_user, db)

    query = (
        db.query(RelevamientoTaller)
        .join(Relevamiento, RelevamientoTaller.relevamiento_id == Relevamiento.id)
        .join(Emaus, and_(Emaus.id == Relevamiento.emaus_id, Emaus.activo == True))
        .join(Diocesis, Diocesis.id == Emaus.diocesis_id)
        .filter(Relevamiento.anio == anio, Relevamiento.semestre == semestre)
    )
    if allowed_ids is not None:
        query = query.filter(Relevamiento.emaus_id.in_(allowed_ids))
    if region:
        query = query.filter(Diocesis.region.in_(region))
    if provincia:
        query = query.filter(Diocesis.provincia.in_(provincia))
    if emaus_id:
        query = query.filter(Relevamiento.emaus_id.in_(emaus_id))

    talleres_rows = query.all()
    total = len(talleres_rows)
    if not total:
        return {"total_talleres": 0}

    def pct(n):
        return round(n / total * 100, 1) if total else 0

    total_participantes = sum(t.cantidad_participantes or 0 for t in talleres_rows)
    total_espacios = sum(t.cantidad_espacios_educativos or 0 for t in talleres_rows)
    total_otras_instituciones = sum(t.otras_instituciones or 0 for t in talleres_rows)

    def contar(attr):
        counts = {}
        for t in talleres_rows:
            k = getattr(t, attr) or "Sin dato"
            counts[k] = counts.get(k, 0) + 1
        return sorted(
            [{"valor": k, "cantidad": v, "pct": pct(v)} for k, v in counts.items()],
            key=lambda x: -x["cantidad"],
        )

    eje = contar("eje")
    rubro_tematico = contar("rubro_tematico")

    # Perfil capacitador: viene de la tabla hija (un taller puede tener varios,
    # así que el total de este gráfico puede superar la cantidad de talleres).
    taller_ids = [t.id for t in talleres_rows]
    perfil_rows = (
        db.query(RelevamientoTallerPerfil.perfil,
                  func.count(func.distinct(RelevamientoTallerPerfil.taller_id)))
        .filter(RelevamientoTallerPerfil.taller_id.in_(taller_ids))
        .group_by(RelevamientoTallerPerfil.perfil)
        .all()
    ) if taller_ids else []
    perfil_capacitador = sorted(
        [{"valor": r[0], "cantidad": r[1], "pct": pct(r[1])} for r in perfil_rows],
        key=lambda x: -x["cantidad"],
    )

    return {
        "total_talleres": total,
        "total_participantes": total_participantes,
        "total_espacios_educativos": total_espacios,
        "total_otras_instituciones": total_otras_instituciones,
        "eje": eje,
        "rubro_tematico": rubro_tematico,
        "perfil_capacitador": perfil_capacitador,
    }
