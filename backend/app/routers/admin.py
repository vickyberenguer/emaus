from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, date
import io
import unicodedata

from openpyxl import load_workbook

from app.database import get_db
from app.models.usuario import Usuario, RolEnum
from app.models.emaus import Emaus, ResponsableEmaus
from app.models.catalogo import Catalogo
from app.models.establecimiento import EstablecimientoEstado
from app.models.padron_importacion import PadronImportacion
from app.routers.auth import get_current_user, require_rol, hash_password

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_rol("admin"))])


# ============================================================
# Usuarios
# ============================================================

class UsuarioCreate(BaseModel):
    nombre: str
    apellido: str
    email: str
    password: str
    rol: str  # atl | responsable | admin
    emaus_id: int | None = None


class UsuarioUpdate(BaseModel):
    nombre: str | None = None
    apellido: str | None = None
    email: str | None = None
    password: str | None = None
    rol: str | None = None
    emaus_id: int | None = None
    activo: bool | None = None


class UsuarioResponse(BaseModel):
    id: int
    nombre: str
    apellido: str
    email: str
    rol: str
    activo: bool
    emaus_id: int | None
    creado_en: datetime | None

    class Config:
        from_attributes = True


@router.get("/usuarios", response_model=list[UsuarioResponse])
def listar_usuarios(db: Session = Depends(get_db)):
    return db.query(Usuario).order_by(Usuario.apellido, Usuario.nombre).all()


@router.post("/usuarios", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
def crear_usuario(body: UsuarioCreate, db: Session = Depends(get_db)):
    if db.query(Usuario).filter(Usuario.email == body.email.lower().strip()).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe un usuario con ese email")

    usuario = Usuario(
        nombre=body.nombre,
        apellido=body.apellido,
        email=body.email.lower().strip(),
        password_hash=hash_password(body.password),
        rol=RolEnum(body.rol),
        emaus_id=body.emaus_id,
        activo=True,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.put("/usuarios/{usuario_id}", response_model=UsuarioResponse)
def actualizar_usuario(usuario_id: int, body: UsuarioUpdate, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    data = body.model_dump(exclude_unset=True)
    if "password" in data:
        usuario.password_hash = hash_password(data.pop("password"))
    if "rol" in data:
        usuario.rol = RolEnum(data.pop("rol"))
    if "email" in data and data["email"]:
        data["email"] = data["email"].lower().strip()

    for field, value in data.items():
        setattr(usuario, field, value)

    db.commit()
    db.refresh(usuario)
    return usuario


# ============================================================
# Asignación Responsable → Emaús
# ============================================================

class ResponsableEmausResponse(BaseModel):
    responsable_id: int
    nombre: str
    apellido: str
    email: str
    emaus_ids: list[int]


class ResponsableEmausUpdate(BaseModel):
    emaus_ids: list[int]


@router.get("/responsable-emaus", response_model=list[ResponsableEmausResponse])
def listar_asignaciones(db: Session = Depends(get_db)):
    responsables = db.query(Usuario).filter(Usuario.rol == RolEnum.responsable).all()
    resultado = []
    for r in responsables:
        emaus_ids = [
            row[0] for row in db.query(ResponsableEmaus.emaus_id)
            .filter(ResponsableEmaus.responsable_id == r.id).all()
        ]
        resultado.append(ResponsableEmausResponse(
            responsable_id=r.id, nombre=r.nombre, apellido=r.apellido, email=r.email, emaus_ids=emaus_ids,
        ))
    return resultado


@router.put("/responsable-emaus/{responsable_id}", response_model=ResponsableEmausResponse)
def actualizar_asignaciones(responsable_id: int, body: ResponsableEmausUpdate, db: Session = Depends(get_db)):
    responsable = db.query(Usuario).filter(
        Usuario.id == responsable_id, Usuario.rol == RolEnum.responsable
    ).first()
    if not responsable:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Responsable no encontrado")

    if body.emaus_ids:
        encontrados = db.query(Emaus.id).filter(Emaus.id.in_(body.emaus_ids)).count()
        if encontrados != len(set(body.emaus_ids)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Alguno de los Emaús no existe")

    db.query(ResponsableEmaus).filter(ResponsableEmaus.responsable_id == responsable_id).delete()
    for emaus_id in set(body.emaus_ids):
        db.add(ResponsableEmaus(responsable_id=responsable_id, emaus_id=emaus_id))
    db.commit()

    return ResponsableEmausResponse(
        responsable_id=responsable.id, nombre=responsable.nombre, apellido=responsable.apellido,
        email=responsable.email, emaus_ids=list(set(body.emaus_ids)),
    )


# ============================================================
# Catálogos
# ============================================================

class CatalogoCreate(BaseModel):
    categoria: str
    valor: str
    orden: int = 0


class CatalogoUpdate(BaseModel):
    valor: str | None = None
    activo: bool | None = None
    orden: int | None = None


class CatalogoResponse(BaseModel):
    id: int
    categoria: str
    valor: str
    activo: bool
    orden: int

    class Config:
        from_attributes = True


@router.get("/catalogos/{categoria}", response_model=list[CatalogoResponse])
def listar_catalogo(categoria: str, db: Session = Depends(get_db)):
    return db.query(Catalogo).filter(Catalogo.categoria == categoria).order_by(Catalogo.orden).all()


@router.post("/catalogos", response_model=CatalogoResponse, status_code=status.HTTP_201_CREATED)
def crear_item_catalogo(body: CatalogoCreate, db: Session = Depends(get_db)):
    item = Catalogo(categoria=body.categoria, valor=body.valor, orden=body.orden, activo=True)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/catalogos/{item_id}", response_model=CatalogoResponse)
def actualizar_item_catalogo(item_id: int, body: CatalogoUpdate, db: Session = Depends(get_db)):
    item = db.query(Catalogo).filter(Catalogo.id == item_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ítem de catálogo no encontrado")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


# ============================================================
# Padrón de establecimientos educativos
# ============================================================

class PadronEstadoResponse(BaseModel):
    total_registros: int
    ultima_importacion: datetime | None
    ultimo_usuario_id: int | None
    ultimo_total_procesados: int | None
    ultimo_insertados: int | None
    ultimo_actualizados: int | None


# Encabezados esperados en la fila 13 del Excel del Ministerio → columna del modelo.
# Se normalizan (minúsculas, sin acentos) antes de comparar.
ENCABEZADOS_PADRON = {
    "cueanexo": "cueanexo",
    "jurisdiccion": "jurisdiccion",
    "sector": "sector",
    "ambito": "ambito",
    "departamento": "departamento",
    "cod_depto": "cod_departamento",
    "codigo departamento": "cod_departamento",
    "localidad": "localidad",
    "cod_localidad": "cod_localidad",
    "codigo localidad": "cod_localidad",
    "nombre": "nombre",
    "domicilio": "domicilio",
    "cp": "codigo_postal",
    "codigo postal": "codigo_postal",
    "telefono": "telefono",
    "mail": "mail",
    "email": "mail",
    "inicial - jardin maternal": "nivel_inicial_maternal",
    "inicial - jardin de infantes": "nivel_inicial_infantes",
    "primario": "primario",
    "secundario": "secundario",
    "adultos": "adultos",
    "formacion profesional": "formacion_profesional",
    "alfabetizacion": "alfabetizacion",
}

BOOLEAN_FIELDS = {
    "nivel_inicial_maternal", "nivel_inicial_infantes", "primario",
    "secundario", "adultos", "formacion_profesional", "alfabetizacion",
}


def _normalizar(texto: str) -> str:
    texto = texto.strip().lower()
    texto = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    return texto


@router.get("/padron/estado", response_model=PadronEstadoResponse)
def estado_padron(db: Session = Depends(get_db)):
    total = db.query(EstablecimientoEstado).count()
    ultima = db.query(PadronImportacion).order_by(PadronImportacion.fecha.desc()).first()
    return PadronEstadoResponse(
        total_registros=total,
        ultima_importacion=ultima.fecha if ultima else None,
        ultimo_usuario_id=ultima.usuario_id if ultima else None,
        ultimo_total_procesados=ultima.total_procesados if ultima else None,
        ultimo_insertados=ultima.insertados if ultima else None,
        ultimo_actualizados=ultima.actualizados if ultima else None,
    )


@router.post("/padron/importar")
def importar_padron(
    file: UploadFile = File(...),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo debe ser .xlsx")

    contenido = file.file.read()
    try:
        wb = load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se pudo leer el archivo Excel")

    hoja = wb.active
    filas = hoja.iter_rows(values_only=True)

    # Encabezados en la fila 13 (índice 12)
    for _ in range(12):
        next(filas, None)
    encabezados = next(filas, None)
    if not encabezados:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se encontraron encabezados en la fila 13")

    columna_a_campo: dict[int, str] = {}
    for idx, encabezado in enumerate(encabezados):
        if not encabezado:
            continue
        campo = ENCABEZADOS_PADRON.get(_normalizar(str(encabezado)))
        if campo:
            columna_a_campo[idx] = campo

    if "cueanexo" not in columna_a_campo.values():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se encontró la columna 'cueanexo' en los encabezados (fila 13)",
        )

    existentes = {e.cueanexo: e for e in db.query(EstablecimientoEstado).all()}
    procesados = insertados = actualizados = 0
    hoy = date.today()

    for fila in filas:
        valores = {campo: fila[idx] for idx, campo in columna_a_campo.items() if idx < len(fila)}
        cueanexo = valores.get("cueanexo")
        if not cueanexo:
            continue
        cueanexo = str(cueanexo).strip()
        procesados += 1

        for campo in BOOLEAN_FIELDS:
            if campo in valores:
                valores[campo] = bool(valores[campo]) and str(valores[campo]).strip() not in ("0", "", "False", "NO", "No")

        if cueanexo in existentes:
            estab = existentes[cueanexo]
            for campo, valor in valores.items():
                setattr(estab, campo, valor)
            estab.actualizado_en = hoy
            actualizados += 1
        else:
            valores["cueanexo"] = cueanexo
            valores["actualizado_en"] = hoy
            estab = EstablecimientoEstado(**valores)
            db.add(estab)
            existentes[cueanexo] = estab
            insertados += 1

    registro = PadronImportacion(
        usuario_id=current_user.id,
        total_procesados=procesados,
        insertados=insertados,
        actualizados=actualizados,
    )
    db.add(registro)
    db.commit()

    return {
        "total_procesados": procesados,
        "insertados": insertados,
        "actualizados": actualizados,
    }
