#!/usr/bin/env python3
"""
Procesa el CSV de alumnos de nuevo ingreso y genera:
  - subida_masiva_workspace.csv  → subida masiva en Google Workspace
  - reporte_problemas.csv        → correos personales con problemas detectados
  - revision_manual.csv          → filas auto-corregidas que requieren verificación
"""

import argparse
import csv
import re
import sys
import unicodedata
from pathlib import Path

# ─── Configuración ────────────────────────────────────────────────────────────
DOMAIN = "eln.edu.mx"
DEFAULT_PASSWORD = ""          # Requerido: pasar vía --password o usar cuentas.py
ORG_UNIT_PATH = ""             # Requerido: pasar vía --ou o usar cuentas.py
INPUT_CSV = ""
DEFAULT_EXISTING_CSV = ""
# ──────────────────────────────────────────────────────────────────────────────

DOMAIN_TYPOS = {
    "gmai.com": "gmail.com",
    "gmial.com": "gmail.com",
    "gmaill.com": "gmail.com",
    "gmal.com": "gmail.com",
    "gamil.com": "gmail.com",
    "hotmial.com": "hotmail.com",
    "homail.com": "hotmail.com",
    "hotmal.com": "hotmail.com",
    "outlok.com": "outlook.com",
    "outloook.com": "outlook.com",
    "iclud.com": "icloud.com",
    "icoud.com": "icloud.com",
}


def strip_invisible(text: str) -> str:
    """Elimina caracteres Unicode invisibles/de control."""
    return "".join(
        ch for ch in text
        if unicodedata.category(ch) not in ("Cf", "Cc", "Co", "Cn")
        or ch in ("\t", "\n", "\r")
    )


def normalizar(texto: str) -> str:
    """Quita acentos, convierte a minúsculas, conserva solo [a-z0-9]."""
    nfkd = unicodedata.normalize("NFKD", texto)
    ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", ascii_str.lower())


def validar_email(email_raw: str) -> tuple[str, list[tuple[str, str]]]:
    """
    Retorna (email_limpio, [(severidad, descripción), ...]).
    severidad: 'ERROR' | 'ADVERTENCIA'
    """
    problemas: list[tuple[str, str]] = []
    email = email_raw

    # Paso 0: normalizar variantes Unicode de compatibilidad a ASCII (p.ej. fuente monoespaciada matemática)
    email_nfkd = unicodedata.normalize("NFKD", email).encode("ascii", "ignore").decode("ascii")
    if email_nfkd != email:
        problemas.append(("ADVERTENCIA", f"Caracteres Unicode no-ASCII normalizados: {email!r} → {email_nfkd!r}"))
        email = email_nfkd

    # Paso 1: quitar caracteres invisibles
    sin_invisibles = strip_invisible(email)
    if sin_invisibles != email:
        problemas.append(("ADVERTENCIA", "Contiene caracteres invisibles Unicode (eliminados)"))
        email = sin_invisibles

    # Paso 2: espacios al inicio/fin
    if email != email.strip():
        problemas.append(("ADVERTENCIA", "Tiene espacios al inicio o al final (eliminados)"))
        email = email.strip()

    # Paso 3: espacios o saltos de línea internos
    if re.search(r"\s", email):
        email_sin_ws = re.sub(r"\s+", "", email)
        problemas.append(
            ("ADVERTENCIA", f"Contiene espacios/saltos de línea internos; posible: {email_sin_ws!r}")
        )
        email = email_sin_ws

    # Estructura básica
    if "@" not in email:
        problemas.append(("ERROR", "No contiene '@'"))
        return email, problemas

    local, _, domain = email.rpartition("@")

    # Punto al inicio/fin de la parte local (auto-corregible)
    if local.startswith(".") or local.endswith("."):
        local_corr = local.strip(".")
        problemas.append(("ADVERTENCIA", f"Parte local empieza o termina con punto: {local!r} → corregido a {local_corr!r}"))
        local = local_corr
        email = f"{local}@{domain}"

    # Punto al inicio/fin del dominio (auto-corregible)
    if domain.startswith(".") or domain.endswith("."):
        domain_corr = domain.strip(".")
        problemas.append(("ADVERTENCIA", f"Dominio empieza o termina con punto: {domain!r} → corregido a {domain_corr!r}"))
        domain = domain_corr
        email = f"{local}@{domain}"

    # Dominio inválido
    if not domain or "." not in domain:
        problemas.append(("ERROR", f"Dominio inválido: {domain!r}"))
        return email, problemas

    # Typo conocido en el dominio → corregir automáticamente
    domain_lower = domain.lower()
    if domain_lower in DOMAIN_TYPOS:
        correcto = DOMAIN_TYPOS[domain_lower]
        problemas.append(
            ("ADVERTENCIA", f"Dominio corregido: {domain!r} → {correcto!r}")
        )
        email = f"{local}@{correcto}"

    return email, problemas


def auto_corregir_nombres(nombre: str, apellidos: str) -> tuple[str, str, str | None]:
    """
    Retorna (nombre_corregido, apellidos_corregidos, motivo_o_None).
    motivo_o_None es None si no se aplicó ninguna corrección.
    """
    n = nombre.strip()
    a = apellidos.strip()

    # Quitar contenido entre paréntesis de apellidos (p.ej. "Madrigal (Caballero)")
    a_sin_paren = re.sub(r"\(.*?\)", "", a).strip()

    # Caso 1: ambas columnas idénticas → nombre completo repetido
    if n == a and n:
        palabras = n.split()
        if len(palabras) >= 4:
            nombre_corr = " ".join(palabras[-2:])
            apels_corr = " ".join(palabras[:-2])
            return nombre_corr, apels_corr, "Nombre completo en ambas columnas; últimas 2 palabras → Nombre"
        if len(palabras) == 3:
            nombre_corr = palabras[-1]
            apels_corr = " ".join(palabras[:-1])
            return nombre_corr, apels_corr, "Nombre completo en ambas columnas; última palabra → Nombre"

    # Caso 2: apellidos termina con el valor exacto del nombre (nombre repetido al final)
    if n and a_sin_paren.endswith(n) and len(a_sin_paren) > len(n):
        apels_corr = a_sin_paren[: -len(n)].strip()
        if apels_corr:
            return n, apels_corr, "Nombre repetido al final de Apellidos (eliminado)"

    return n, a_sin_paren if a_sin_paren != a else a, None if a_sin_paren == a else "Paréntesis eliminados de Apellidos"


def generar_correo_institucional(
    nombre: str,
    apellidos: str,
    existentes: set[str],
    asignados: set[str],
) -> str:
    """Genera el correo institucional más corto disponible."""
    apellidos_limpio = re.sub(r"\(.*?\)", "", apellidos).strip()
    palabras_apellidos = apellidos_limpio.split()

    nombre_norm = normalizar(nombre)
    ap1 = normalizar(palabras_apellidos[0]) if palabras_apellidos else ""
    ap2 = normalizar(palabras_apellidos[1]) if len(palabras_apellidos) > 1 else ""

    def libre(correo: str) -> bool:
        return correo not in existentes and correo not in asignados

    candidato_base = f"{nombre_norm}.{ap1}@{DOMAIN}"
    if libre(candidato_base):
        return candidato_base

    if ap2:
        candidato_2ap = f"{nombre_norm}.{ap1}{ap2}@{DOMAIN}"
        if libre(candidato_2ap):
            return candidato_2ap

    n = 2
    while True:
        candidato_n = f"{nombre_norm}.{ap1}{n}@{DOMAIN}"
        if libre(candidato_n):
            return candidato_n
        n += 1


def cargar_existentes(path: str) -> set[str]:
    p = Path(path)
    if not p.exists():
        print(f"[AVISO] Archivo de cuentas existentes no encontrado: {path}", file=sys.stderr)
        return set()
    existentes: set[str] = set()
    with open(p, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        email_col = next((k for k in (reader.fieldnames or []) if "Email Address" in k), None)
        if not email_col:
            print(f"[AVISO] No se encontró columna 'Email Address' en {path}", file=sys.stderr)
            return existentes
        for row in reader:
            val = row.get(email_col, "").strip().lower()
            if val:
                existentes.add(val)
    print(f"[INFO] {len(existentes)} cuentas existentes cargadas desde {p.name}")
    return existentes


def titulo(texto: str) -> str:
    """Title-case que preserva tildes y ñ."""
    return " ".join(w.capitalize() for w in texto.split())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="CSV de alumnos (Nombre, Apellidos, Correo Personal)")
    parser.add_argument("--existing", default="", help="User_Download de Workspace para evitar colisiones")
    parser.add_argument("--password", required=True, help="Contraseña temporal para las cuentas nuevas")
    parser.add_argument("--ou", required=True, help="Unidad organizativa de Workspace (ej. /Mi Org/Alumnos)")
    args = parser.parse_args()

    script_dir = Path(__file__).parent

    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = script_dir / args.input
    if not input_path.exists():
        sys.exit(f"ERROR: no se encontró el archivo de entrada: {input_path}")

    existing_path = Path(args.existing)
    if not existing_path.is_absolute():
        existing_path = script_dir / args.existing

    existentes = cargar_existentes(str(existing_path))
    asignados: set[str] = set()

    filas_workspace: list[dict] = []
    filas_problemas: list[dict] = []
    filas_revision: list[dict] = []

    with open(input_path, newline="", encoding="utf-8-sig") as f:
        lines = [ln for ln in f if ln.strip().replace(",", "").replace(";", "")]
    reader = csv.DictReader(lines)

    required_cols = {"Nombre", "Apellidos", "Correo Personal"}
    if not required_cols.issubset(set(reader.fieldnames or [])):
        sys.exit(f"ERROR: el CSV no tiene las columnas requeridas {required_cols}. Columnas encontradas: {reader.fieldnames}")

    for fila_num, row in enumerate(reader, start=2):
        if True:
            nombre_orig = row["Nombre"].strip()
            apellidos_orig = row["Apellidos"].strip()
            email_orig = row["Correo Personal"]

            if not nombre_orig and not apellidos_orig and not email_orig.strip():
                continue

            # ── Corregir nombres ───────────────────────────────────────────
            nombre, apellidos, motivo_nombres = auto_corregir_nombres(nombre_orig, apellidos_orig)
            motivos: list[str] = [motivo_nombres] if motivo_nombres else []

            # ── Validar y limpiar email personal ──────────────────────────
            email_limpio, problemas_email = validar_email(email_orig)
            if email_limpio != email_orig.strip():
                motivos.append(f"Email limpiado: {email_orig.strip()!r} → {email_limpio!r}")

            tiene_error = any(sev == "ERROR" for sev, _ in problemas_email)

            for sev, det in problemas_email:
                filas_problemas.append({
                    "Fila": fila_num,
                    "Nombre": nombre_orig,
                    "Apellidos": apellidos_orig,
                    "Correo Personal": email_orig.strip(),
                    "Severidad": sev,
                    "Detalle": det,
                })

            # ── Validar que tengamos nombre y apellido utilizables ─────────
            if not nombre or not apellidos:
                filas_problemas.append({
                    "Fila": fila_num,
                    "Nombre": nombre_orig,
                    "Apellidos": apellidos_orig,
                    "Correo Personal": email_orig.strip(),
                    "Severidad": "ERROR",
                    "Detalle": "No se pudo determinar Nombre o Apellidos; requiere revisión manual",
                })
                continue

            # ── Generar correo institucional ───────────────────────────────
            correo_inst = generar_correo_institucional(nombre, apellidos, existentes, asignados)
            asignados.add(correo_inst)

            filas_workspace.append({
                "First Name [Required]": titulo(nombre),
                "Last Name [Required]": titulo(apellidos),
                "Email Address [Required]": correo_inst,
                "Password [Required]": args.password,
                "Org Unit Path [Required]": args.ou,
                "Change Password at Next Sign-In [UPLOAD ONLY]": "TRUE",
                "Recovery Email": email_limpio,
                "Home Secondary Email": email_limpio,
            })

            # ── Registrar auto-correcciones para revisión ──────────────────
            if motivos:
                filas_revision.append({
                    "Fila": fila_num,
                    "Nombre Original": nombre_orig,
                    "Apellidos Original": apellidos_orig,
                    "Nombre Corregido": titulo(nombre),
                    "Apellidos Corregidos": titulo(apellidos),
                    "Correo Institucional": correo_inst,
                    "Motivo": "; ".join(motivos),
                })

    out_dir = input_path.parent

    # ── subida_masiva_workspace.csv ────────────────────────────────────────
    ws_fields = [
        "First Name [Required]",
        "Last Name [Required]",
        "Email Address [Required]",
        "Password [Required]",
        "Org Unit Path [Required]",
        "Change Password at Next Sign-In [UPLOAD ONLY]",
        "Recovery Email",
        "Home Secondary Email",
    ]
    ws_path = out_dir / "subida_masiva_workspace.csv"
    with open(ws_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ws_fields)
        writer.writeheader()
        writer.writerows(filas_workspace)
    print(f"[OK] {ws_path.name}  ({len(filas_workspace)} cuentas)")

    # ── reporte_problemas.csv ──────────────────────────────────────────────
    prob_path = out_dir / "reporte_problemas.csv"
    prob_fields = ["Fila", "Nombre", "Apellidos", "Correo Personal", "Severidad", "Detalle"]
    with open(prob_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=prob_fields)
        writer.writeheader()
        writer.writerows(filas_problemas)
    print(f"[OK] {prob_path.name}  ({len(filas_problemas)} problemas)")

    # ── revision_manual.csv ────────────────────────────────────────────────
    rev_path = out_dir / "revision_manual.csv"
    rev_fields = [
        "Fila", "Nombre Original", "Apellidos Original",
        "Nombre Corregido", "Apellidos Corregidos",
        "Correo Institucional", "Motivo",
    ]
    with open(rev_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rev_fields)
        writer.writeheader()
        writer.writerows(filas_revision)
    print(f"[OK] {rev_path.name}  ({len(filas_revision)} filas para revisar)")


if __name__ == "__main__":
    main()
