# Cuentas ELN

Herramienta de línea de comandos para el alta masiva de cuentas Google Workspace y envío de credenciales a nuevos alumnos.

Diseñada para flujos de onboarding escolar: toma un CSV de alumnos, genera el archivo de subida para el Admin Console de Google Workspace, y envía correos de bienvenida con credenciales vía SendGrid.

---

## Características

- Menú interactivo que guía el flujo completo paso a paso
- Soporte para múltiples tipos de cuenta (estudiantes, docentes, etc.) con contraseña y unidad organizativa independientes por tipo
- Detección y corrección automática de errores comunes en los datos de entrada:
  - Typos de dominio de email (`gmai.com` → `gmail.com`, `hotmial.com` → `hotmail.com`, etc.)
  - Caracteres Unicode de fuente monoespaciada copiados desde WhatsApp o Google Docs (normalización NFKD)
  - Nombres repetidos en ambas columnas — el script infiere la separación correcta
  - Espacios y saltos de línea dentro del email
- Generación automática de correo institucional con manejo de colisiones
- Reporte detallado de problemas encontrados y correcciones aplicadas
- Archivado automático de logs históricos de envío

---

## Requisitos

- Python 3.10+
- Paquete [`sendgrid`](https://pypi.org/project/sendgrid/): `pip install sendgrid`
- Cuenta de [SendGrid](https://sendgrid.com/) con un Dynamic Template configurado y remitente verificado
- Acceso a Google Workspace Admin Console

---

## Instalación

```bash
git clone https://github.com/tu-usuario/cuentas-eln.git
cd cuentas-eln
pip install sendgrid
cp config.ejemplo.json config.json
```

Edita `config.json` con tus credenciales (ver sección [Configuración](#configuración)).

---

## Configuración

`config.json` no se sube al repositorio (está en `.gitignore`). Usa `config.ejemplo.json` como plantilla:

```json
{
  "sendgrid": {
    "api_key": "SG.xxxx",
    "template_id": "d-xxxx",
    "from_email": "soporte@tudominio.edu",
    "from_name": "Nombre de tu institución"
  },
  "tipos": {
    "Estudiantes": {
      "password": "ContraseñaTemporal1#",
      "ou": "/Tu Org/Estudiantes/Ciclo 2026"
    },
    "Docentes": {
      "password": "ContraseñaTemporal2#",
      "ou": "/Tu Org/Docentes"
    }
  }
}
```

Para agregar un nuevo tipo de cuenta, basta con agregar una entrada al objeto `tipos`.

---

## Uso

```bash
./cuentas.py
```

Menú principal:

```
╔════════════════════════════════════╗
║   Cuentas ELN — v1.1.0            ║
╚════════════════════════════════════╝

  1. Procesar cuentas nuevas
  2. Enviar correos de bienvenida
  3. Flujo completo (1 + 2)
  4. Probar envío (correo de prueba)
  0. Salir
```

---

## Flujo de trabajo típico

### 1. Preparar archivos de entrada

Colocar en el directorio del proyecto:

- **CSV de alumnos** con columnas exactas: `Nombre`, `Apellidos`, `Correo Personal`
- **User_Download** descargado desde Google Workspace Admin Console (`Admin > Users > Download users`), necesario para evitar colisiones de correo institucional con cuentas existentes

### 2. Procesar (opción 1)

El script detecta automáticamente los archivos más recientes, pide confirmación y genera:

| Archivo | Contenido |
|---|---|
| `subida_masiva_workspace.csv` | Listo para subir al Admin Console |
| `reporte_problemas.csv` | Errores y advertencias en los datos de entrada |
| `revision_manual.csv` | Correcciones automáticas aplicadas, para verificar |

> **Revisar siempre** `reporte_problemas.csv` antes de continuar. Ningún `ERROR` debe quedar sin resolver.

### 3. Subir a Google Workspace

Admin Console → Users → ícono de subida → **Upload multiple users** → seleccionar `subida_masiva_workspace.csv`.

### 4. Enviar correos (opción 2)

Una vez que las cuentas estén activas en Workspace, ejecutar la opción 2. El script pide confirmación explícita antes de enviar. El log queda en `log_envios.csv`; los logs anteriores se archivan automáticamente en `logs/`.

### Prueba de envío (opción 4)

Antes de un envío masivo, usar la opción 4 para enviar un correo de prueba a tu propia dirección y verificar que el template se ve bien.

---

## Uso avanzado (scripts independientes)

Los scripts también pueden usarse directamente desde la línea de comandos:

```bash
# Procesar CSV
python3 procesar_cuentas.py \
  --input "alumnos.csv" \
  --existing "User_Download.csv" \
  --password "ContraseñaTemporal1#" \
  --ou "/Mi Org/Estudiantes/Ciclo 2026"

# Enviar correos
SENDGRID_API_KEY=SG.xxxx python3 enviar_credenciales.py

# Prueba
SENDGRID_API_KEY=SG.xxxx python3 enviar_credenciales.py --test tu@correo.com

# Simulación sin llamar a la API
SENDGRID_API_KEY=SG.xxxx python3 enviar_credenciales.py --dry-run
```

---

## Licencia

MIT
