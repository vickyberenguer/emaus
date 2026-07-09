import os
from mangum import Mangum
from app.main import app

_mangum = Mangum(app, lifespan="off")


def handler(event, context):
    # Detectar evento HTTP (API Gateway REST = httpMethod, HTTP API v2 = requestContext.http)
    is_http = "httpMethod" in event or (
        "requestContext" in event and isinstance(event.get("requestContext"), dict)
        and "http" in event["requestContext"]
    )
    print(f"[handler] source={event.get('source','?')} is_http={is_http} keys={list(event.keys())[:8]}")
    if not is_http:
        from scripts.scraper_control import run_sync
        folder_id = os.getenv("DRIVE_FOLDER_ID", "")
        if not folder_id:
            return {"ok": False, "error": "DRIVE_FOLDER_ID no configurado"}
        anio = event.get("anio", int(os.getenv("ANIO_ACTIVO", "2026")))
        semestre = event.get("semestre", os.getenv("SEMESTRE_ACTIVO", "1"))
        emaus_id = event.get("emaus_id", None)
        apply_reset = event.get("apply_reset", True)
        result = run_sync(folder_id, anio=anio, semestre=semestre, emaus_id=emaus_id, apply_reset=apply_reset)
        print(f"[sync] source={event.get('source','eventbridge')} result={result}")
        return result

    # Evento HTTP normal (API Gateway)
    return _mangum(event, context)
