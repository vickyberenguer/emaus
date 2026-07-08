import os
from mangum import Mangum
from app.main import app

_mangum = Mangum(app, lifespan="off")


def handler(event, context):
    # Evento de EventBridge Scheduler o invocación directa (botón sync) — no tiene httpMethod
    if "httpMethod" not in event and "requestContext" not in event:
        from scripts.scraper_control import run_sync
        folder_id = os.getenv("DRIVE_FOLDER_ID", "")
        if not folder_id:
            return {"ok": False, "error": "DRIVE_FOLDER_ID no configurado"}
        anio = event.get("anio", int(os.getenv("ANIO_ACTIVO", "2026")))
        semestre = event.get("semestre", os.getenv("SEMESTRE_ACTIVO", "1"))
        emaus_id = event.get("emaus_id", None)
        result = run_sync(folder_id, anio=anio, semestre=semestre, emaus_id=emaus_id)
        print(f"[sync] source={event.get('source','eventbridge')} result={result}")
        return result

    # Evento HTTP normal (API Gateway)
    return _mangum(event, context)
