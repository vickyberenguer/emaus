from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app import models  # noqa: F401 — registra los modelos en el mapper de SQLAlchemy
from app.routers import auth, relevamientos, pastoral_pi, espacios_educativos, talleres, establecimientos, admin, catalogos

settings = get_settings()

app = FastAPI(
    title="Emaús — API de Relevamiento",
    version="1.0.0",
    # En producción deshabilitar docs para no exponer la API públicamente
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(relevamientos.router)
app.include_router(pastoral_pi.router)
app.include_router(espacios_educativos.router)
app.include_router(talleres.router)
app.include_router(establecimientos.router)
app.include_router(admin.router)
app.include_router(catalogos.router)


@app.get("/health")
def health():
    return {"status": "ok"}
