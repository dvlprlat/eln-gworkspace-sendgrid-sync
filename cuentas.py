#!/usr/bin/env python3
"""Herramienta de alta masiva de cuentas Google Workspace — Escuela Libre de Negocios."""

import csv
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

__version__ = "1.1.0"

DIR = Path(__file__).parent
CONFIG_PATH = DIR / "config.json"


def cargar_config() -> dict:
    if not CONFIG_PATH.exists():
        print("\n  ERROR: no se encontró config.json")
        print("  Copia config.ejemplo.json → config.json y completa las credenciales.")
        sys.exit(1)
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


# ── Helpers de UI ──────────────────────────────────────────────────────────────

def header():
    ancho = 36
    titulo = f"  Cuentas ELN — v{__version__}"
    print(f"\n╔{'═' * ancho}╗")
    print(f"║{titulo:<{ancho}}║")
    print(f"╚{'═' * ancho}╝\n")


def preguntar(prompt: str, opciones: list[str] | None = None) -> str:
    while True:
        resp = input(prompt).strip()
        if opciones is None or resp in opciones:
            return resp
        print(f"  Opción inválida. Elige: {', '.join(opciones)}")


def confirmar(mensaje: str) -> bool:
    resp = preguntar(f"{mensaje} [s/n]: ", ["s", "n", "S", "N"])
    return resp.lower() == "s"


def separador():
    print("─" * 50)


# ── Auto-detección de archivos ─────────────────────────────────────────────────

def detectar_input_csv() -> Path | None:
    candidatos = sorted(
        list(DIR.glob("Cuentas *.csv")) + list(DIR.glob("Correos ELN *.csv")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidatos[0] if candidatos else None


def detectar_user_download() -> Path | None:
    candidatos = sorted(
        DIR.glob("User_Download_*.csv"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidatos[0] if candidatos else None


def pedir_archivo(descripcion: str, detectado: Path | None) -> Path:
    if detectado:
        print(f"  {descripcion}: {detectado.name}")
        if confirmar("  ¿Usar este archivo?"):
            return detectado
    ruta = input(f"  Ruta del {descripcion}: ").strip()
    p = Path(ruta)
    if not p.is_absolute():
        p = DIR / p
    if not p.exists():
        print(f"  ERROR: no se encontró {p}")
        sys.exit(1)
    return p


# ── Leer archivos de resultado ─────────────────────────────────────────────────

def leer_reporte_problemas() -> tuple[int, int]:
    """Retorna (n_advertencias, n_errores)."""
    ruta = DIR / "reporte_problemas.csv"
    if not ruta.exists():
        return 0, 0
    advertencias = errores = 0
    with open(ruta, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("Severidad") == "ADVERTENCIA":
                advertencias += 1
            elif row.get("Severidad") == "ERROR":
                errores += 1
    return advertencias, errores


def leer_n_cuentas_workspace() -> int:
    ruta = DIR / "subida_masiva_workspace.csv"
    if not ruta.exists():
        return 0
    with open(ruta, newline="", encoding="utf-8-sig") as f:
        return sum(1 for _ in csv.DictReader(f))


# ── Archivado de log anterior ──────────────────────────────────────────────────

def archivar_log() -> None:
    log_actual = DIR / "log_envios.csv"
    if not log_actual.exists():
        return
    logs_dir = DIR / "logs"
    logs_dir.mkdir(exist_ok=True)
    sello = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = logs_dir / f"log_envios_{sello}.csv"
    shutil.move(str(log_actual), str(destino))
    print(f"  Log anterior archivado → logs/{destino.name}")


# ── Ejecutar subproceso ────────────────────────────────────────────────────────

def ejecutar(cmd: list[str], extra_env: dict | None = None) -> bool:
    """Ejecuta cmd mostrando stdout en tiempo real. Muestra stderr solo si hay error."""
    env = {**os.environ, **(extra_env or {})}
    resultado = subprocess.run(cmd, cwd=DIR, stderr=subprocess.PIPE, text=True, env=env)
    if resultado.returncode != 0:
        print("\n  ERROR al ejecutar el proceso:")
        if resultado.stderr.strip():
            for linea in resultado.stderr.strip().splitlines():
                print(f"  {linea}")
        return False
    return True


# ── Acciones ───────────────────────────────────────────────────────────────────

def accion_procesar(config: dict) -> bool:
    """Retorna True si terminó sin errores bloqueantes."""
    tipos = config.get("tipos", {})
    claves = list(tipos.keys())
    n_tipos = len(claves)

    separador()
    print("  TIPO DE CUENTA\n")
    for i, nombre in enumerate(claves, 1):
        print(f"  {i}. {nombre}")
    print(f"  {n_tipos + 1}. Personalizado")
    print()

    opciones_validas = [str(i) for i in range(1, n_tipos + 2)]
    tipo_sel = preguntar("  Selecciona: ", opciones_validas)

    if tipo_sel == str(n_tipos + 1):
        password = input("  Contraseña temporal: ").strip()
        ou = input("  Unidad organizativa (ej. /Cuentas Prepa/X): ").strip()
    else:
        cfg_tipo = tipos[claves[int(tipo_sel) - 1]]
        password = cfg_tipo.get("password")
        ou = cfg_tipo.get("ou")

    separador()
    print("  ARCHIVOS DE ENTRADA\n")
    input_csv = pedir_archivo("CSV de cuentas nuevas", detectar_input_csv())
    existing_csv = pedir_archivo("User_Download", detectar_user_download())

    separador()
    print()

    cmd = [
        sys.executable, str(DIR / "procesar_cuentas.py"),
        "--input", str(input_csv),
        "--existing", str(existing_csv),
    ]
    if password:
        cmd += ["--password", password]
    if ou:
        cmd += ["--ou", ou]

    if not ejecutar(cmd):
        return False

    advertencias, errores = leer_reporte_problemas()
    n_cuentas = leer_n_cuentas_workspace()

    print(f"\n  Resultado:")
    print(f"    Cuentas generadas : {n_cuentas}")
    print(f"    Advertencias      : {advertencias}")
    print(f"    Errores           : {errores}")

    if errores > 0:
        print(f"\n  ⚠  Hay {errores} ERROR(ES) en reporte_problemas.csv.")
        print("  Resuélvelos antes de subir el archivo a Workspace.")
        return False
    if advertencias > 0:
        print(f"\n  ℹ  Revisa revision_manual.csv — se aplicaron correcciones automáticas.")

    return True


def accion_enviar(config: dict) -> None:
    n = leer_n_cuentas_workspace()
    if n == 0:
        print("\n  No hay cuentas en subida_masiva_workspace.csv.")
        print("  Ejecuta primero la opción 1 (Procesar).")
        return

    separador()
    print(f"\n  Se enviarán correos a {n} destinatario(s).")
    print("  Asegúrate de que las cuentas ya estén activas en Google Workspace.")
    print()

    if not confirmar("  ¿Confirmas el envío?"):
        print("  Envío cancelado.")
        return

    archivar_log()
    print()

    sg = config.get("sendgrid", {})
    cmd = [sys.executable, str(DIR / "enviar_credenciales.py")]
    if sg.get("template_id"):
        cmd += ["--template-id", sg["template_id"]]
    if sg.get("from_email"):
        cmd += ["--from-email", sg["from_email"]]
    if sg.get("from_name"):
        cmd += ["--from-name", sg["from_name"]]

    api_key = sg.get("api_key", "")
    ejecutar(cmd, extra_env={"SENDGRID_API_KEY": api_key} if api_key else None)


def accion_prueba(config: dict) -> None:
    separador()
    correo = input("  Correo de destino para la prueba: ").strip()
    if not correo:
        print("  Dirección vacía, cancelado.")
        return

    sg = config.get("sendgrid", {})
    cmd = [sys.executable, str(DIR / "enviar_credenciales.py"), "--test", correo]
    if sg.get("template_id"):
        cmd += ["--template-id", sg["template_id"]]
    if sg.get("from_email"):
        cmd += ["--from-email", sg["from_email"]]
    if sg.get("from_name"):
        cmd += ["--from-name", sg["from_name"]]

    api_key = sg.get("api_key", "")
    print()
    ejecutar(cmd, extra_env={"SENDGRID_API_KEY": api_key} if api_key else None)


# ── Menú principal ─────────────────────────────────────────────────────────────

def menu(config: dict) -> None:
    while True:
        header()
        print("  1. Procesar cuentas nuevas")
        print("  2. Enviar correos de bienvenida")
        print("  3. Flujo completo (1 + 2)")
        print("  4. Probar envío (correo de prueba)")
        print("  0. Salir")
        print()

        opcion = preguntar("> ", ["0", "1", "2", "3", "4"])
        print()

        if opcion == "0":
            print("  Hasta luego.\n")
            break

        elif opcion == "1":
            accion_procesar(config)

        elif opcion == "2":
            accion_enviar(config)

        elif opcion == "3":
            sin_errores = accion_procesar(config)
            if sin_errores:
                print()
                if confirmar("  ¿Continuar con el envío de correos?"):
                    accion_enviar(config)
                else:
                    print("  Envío omitido.")

        elif opcion == "4":
            accion_prueba(config)

        input("\n  [Enter para continuar]")


if __name__ == "__main__":
    try:
        config = cargar_config()
        menu(config)
    except KeyboardInterrupt:
        print("\n\n  Interrumpido.\n")
