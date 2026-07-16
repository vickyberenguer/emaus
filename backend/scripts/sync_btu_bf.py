"""
Actualiza btu_actual y bf_actual en control_relevamiento
leyendo las planillas externas BTU y BF.
No toca ninguna planilla de EE — solo lee BTU_SPREADSHEET_ID y BF_SPREADSHEET_ID.

Uso:
    python scripts/sync_btu_bf.py --anio 2026 --semestre 1
    python scripts/sync_btu_bf.py --anio 2026 --semestre 1 --emaus-id 180049
"""
import argparse
import os
import sys
from pathlib import Path

# Agregar backend/ al path para poder importar scripts.scraper_control
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Cargar .env
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if _env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_path)

from sqlalchemy import text
from scripts.scraper_control import (
    build_services, get_engine, get_all_emaus,
    leer_btu_planilla, leer_bf_planilla,
)

ANIO_DEFAULT    = 2026
SEMESTRE_DEFAULT = "1"


def main():
    parser = argparse.ArgumentParser(description="Sync BTU y BF desde planillas externas")
    parser.add_argument("--anio",      type=int, default=ANIO_DEFAULT)
    parser.add_argument("--semestre",  default=SEMESTRE_DEFAULT)
    parser.add_argument("--emaus-id",  type=int, default=None)
    parser.add_argument("--dry-run",   action="store_true")
    args = parser.parse_args()

    sheets_svc, _ = build_services()
    engine        = get_engine()
    emaus_list    = get_all_emaus(engine)

    # Leer planillas
    btu_id = os.getenv("BTU_SPREADSHEET_ID", "")
    bf_id  = os.getenv("BF_SPREADSHEET_ID",  "")

    btu_map = leer_btu_planilla(sheets_svc, btu_id)
    bf_map  = leer_bf_planilla(sheets_svc,  bf_id)

    print(f"BTU: {len(btu_map)} Emaús leídos  — {sorted(btu_map.keys())}")
    print(f"BF:  {len(bf_map)} Emaús leídos   — {sorted(bf_map.keys())}")
    print()

    ok = sin_match = sin_control = 0

    for emaus in emaus_list:
        if args.emaus_id and emaus["id"] != args.emaus_id:
            continue

        nombre    = emaus["nombre"]
        btu_val   = btu_map.get(nombre)
        bf_val    = bf_map.get(nombre)

        if btu_val is None and bf_val is None:
            print(f"  [sin match] {nombre}")
            sin_match += 1
            continue

        if args.dry_run:
            print(f"  [dry] {nombre}: BTU={btu_val}  BF={bf_val}")
            ok += 1
            continue

        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE control_relevamiento
                SET btu_actual = COALESCE(:btu, btu_actual),
                    bf_actual  = COALESCE(:bf,  bf_actual)
                WHERE emaus_id = :emaus_id
                  AND anio     = :anio
                  AND semestre = :semestre
            """), {
                "btu":      btu_val,
                "bf":       bf_val,
                "emaus_id": emaus["id"],
                "anio":     args.anio,
                "semestre": args.semestre,
            })

        if result.rowcount == 0:
            print(f"  [sin registro] {nombre} — no existe en control_relevamiento para {args.anio}/S{args.semestre}")
            sin_control += 1
        else:
            print(f"  OK {nombre}: BTU={btu_val}  BF={bf_val}")
            ok += 1

    print(f"\nResumen: {ok} OK | {sin_match} sin match en planilla | {sin_control} sin registro en control")


if __name__ == "__main__":
    main()
