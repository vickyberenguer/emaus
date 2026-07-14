from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.usuario import Usuario
from app.models.emaus import Emaus, ResponsableEmaus
from app.models.control import ControlRelevamiento, ControlAprobacion
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
        .outerjoin(ControlAprobacion, (
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
