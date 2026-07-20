#!/usr/bin/env python3
"""
Envía las credenciales institucionales a cada alumno vía SendGrid Dynamic Templates.

Uso:
  SENDGRID_API_KEY=<key> python3 enviar_credenciales.py
  SENDGRID_API_KEY=<key> python3 enviar_credenciales.py --dry-run
"""

import argparse
import csv
import os
import sys
from datetime import datetime
from pathlib import Path

# ─── Configuración ────────────────────────────────────────────────────────────
TEMPLATE_ID   = ""   # Configurar en config.json → sendgrid.template_id
FROM_EMAIL    = ""   # Configurar en config.json → sendgrid.from_email
FROM_NAME     = ""   # Configurar en config.json → sendgrid.from_name
WORKSPACE_CSV = "subida_masiva_workspace.csv"
# ──────────────────────────────────────────────────────────────────────────────


def cargar_alumnos(csv_path: Path) -> list[dict]:
    alumnos = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            correo_personal = row.get("Recovery Email", "").strip()
            if not correo_personal:
                print(f"  [OMITIDO] {row.get('First Name [Required]')} {row.get('Last Name [Required]')} — sin correo personal")
                continue
            alumnos.append({
                "nombre":              row["First Name [Required]"].strip(),
                "correo_institucional": row["Email Address [Required]"].strip(),
                "contrasena":          row["Password [Required]"].strip(),
                "correo_personal":     correo_personal,
            })
    return alumnos


def enviar(alumno: dict, sg, dry_run: bool) -> tuple[int, str]:
    """Retorna (status_code, mensaje)."""
    from sendgrid.helpers.mail import Mail, To, DynamicTemplateData

    mensaje = Mail(
        from_email=(FROM_EMAIL, FROM_NAME),
        to_emails=To(alumno["correo_personal"], alumno["nombre"]),
    )
    mensaje.template_id = TEMPLATE_ID
    mensaje.dynamic_template_data = {
        "nombre":               alumno["nombre"],
        "correo_institucional": alumno["correo_institucional"],
        "contrasena":           alumno["contrasena"],
    }

    if dry_run:
        return 0, "DRY-RUN"

    response = sg.send(mensaje)
    return response.status_code, "OK" if response.status_code == 202 else response.body


def main() -> None:
    global TEMPLATE_ID, FROM_EMAIL, FROM_NAME

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Simula el envío sin llamar a la API")
    parser.add_argument("--test", metavar="EMAIL", help="Envía un correo de prueba a esta dirección y termina")
    parser.add_argument("--input", default=WORKSPACE_CSV)
    parser.add_argument("--template-id", default=TEMPLATE_ID, help="ID de Dynamic Template en SendGrid")
    parser.add_argument("--from-email", default=FROM_EMAIL, help="Remitente verificado en SendGrid")
    parser.add_argument("--from-name", default=FROM_NAME, help="Nombre del remitente")
    args = parser.parse_args()

    TEMPLATE_ID = args.template_id
    FROM_EMAIL = args.from_email
    FROM_NAME = args.from_name

    api_key = os.environ.get("SENDGRID_API_KEY")
    if not api_key and not args.dry_run:
        sys.exit("ERROR: define la variable de entorno SENDGRID_API_KEY antes de ejecutar.")

    if TEMPLATE_ID.startswith("d-CAMBIAR") or TEMPLATE_ID.startswith("d-xxx"):
        sys.exit("ERROR: reemplaza template_id en config.json con el ID real de tu Dynamic Template en SendGrid.")

    script_dir = Path(__file__).parent

    # ── Modo test: un correo real a la dirección indicada ──────────────────────
    if args.test:
        try:
            import sendgrid
        except ImportError:
            sys.exit("ERROR: instala la librería con:  pip install sendgrid")
        sg = sendgrid.SendGridAPIClient(api_key=api_key)
        alumno_prueba = {
            "nombre":               "Alumno de Prueba",
            "correo_institucional": "alumno.prueba@ejemplo.edu.mx",
            "contrasena":           "ContraseñaDemo123#",
            "correo_personal":      args.test,
        }
        print(f"Enviando correo de prueba a {args.test}...")
        status, msg = enviar(alumno_prueba, sg, dry_run=False)
        if status == 202:
            print(f"  [OK] Enviado — revisa tu bandeja de entrada.")
        else:
            print(f"  [ERR] {status}: {msg}")
        return
    # ──────────────────────────────────────────────────────────────────────────

    csv_path = Path(args.input)
    if not csv_path.is_absolute():
        csv_path = script_dir / args.input
    if not csv_path.exists():
        sys.exit(f"ERROR: no se encontró {csv_path}")

    alumnos = cargar_alumnos(csv_path)
    print(f"{'[DRY-RUN] ' if args.dry_run else ''}Enviando a {len(alumnos)} alumnos...\n")

    sg = None
    if not args.dry_run:
        try:
            import sendgrid
        except ImportError:
            sys.exit("ERROR: instala la librería con:  pip install sendgrid")
        sg = sendgrid.SendGridAPIClient(api_key=api_key)

    log: list[dict] = []
    ok = errores = 0

    for alumno in alumnos:
        status, msg = enviar(alumno, sg, args.dry_run)
        exito = args.dry_run or status == 202
        etiqueta = "OK " if exito else "ERR"
        print(f"  [{etiqueta}] {alumno['correo_personal']:<40}  →  {alumno['correo_institucional']}")
        if not exito:
            print(f"         {status}: {msg}")
        if exito:
            ok += 1
        else:
            errores += 1
        log.append({
            "Timestamp":             datetime.now().isoformat(timespec="seconds"),
            "Nombre":                alumno["nombre"],
            "Correo Personal":       alumno["correo_personal"],
            "Correo Institucional":  alumno["correo_institucional"],
            "Status":                status,
            "Resultado":             msg,
        })

    # Guardar log
    log_path = script_dir / "log_envios.csv"
    with open(log_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(log[0].keys()))
        writer.writeheader()
        writer.writerows(log)

    print(f"\n{'─'*55}")
    print(f"  Enviados OK : {ok}")
    if errores:
        print(f"  Con error   : {errores}")
    print(f"  Log guardado: {log_path.name}")


if __name__ == "__main__":
    main()
