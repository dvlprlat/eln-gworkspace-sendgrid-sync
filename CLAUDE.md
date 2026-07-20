# Cuentas — Escuela Libre de Negocios

Sistema de alta masiva de cuentas Google Workspace y envío de bienvenida para nuevos estudiantes.

## Configuración inicial

Al clonar el repositorio por primera vez:

```bash
cp config.ejemplo.json config.json
# Editar config.json con contraseñas, OUs y datos de SendGrid reales
```

`config.json` está en `.gitignore` — nunca se sube al repositorio. Contiene:
- Contraseñas temporales por tipo de cuenta (Estudiantes, Guías, etc.)
- Unidades organizativas de Workspace
- Template ID y remitente de SendGrid

Para agregar un nuevo tipo de cuenta, editar `config.json` → sección `"tipos"`.

---

## Flujo completo

### 1. Preparar archivos de entrada

Colocar en este directorio:
- **CSV de nuevos estudiantes** con columnas exactas: `Nombre`, `Apellidos`, `Correo Personal`
- **User_Download actualizado** descargado desde Google Workspace Admin Console:  
  `Admin > Users > Download users`  
  El export evita colisiones de correo institucional con cuentas ya existentes.

### 2. Generar CSV para Workspace

```bash
python3 procesar_cuentas.py \
  --input "Cuentas Nuevo Ingreso 2026 - Consolidado Masivo DD de MES.csv" \
  --existing "User_Download_DDMMYYYY_HHMMSS.csv"
```

Genera tres archivos:
- `subida_masiva_workspace.csv` — listo para subir al Admin Console
- `reporte_problemas.csv` — advertencias/errores en datos de entrada (ADVERTENCIA = corregido automáticamente, ERROR = requiere intervención)
- `revision_manual.csv` — correcciones automáticas aplicadas, verificar que tengan sentido

**Revisar siempre** `reporte_problemas.csv` antes de subir. Ningún ERROR debe quedar sin resolver.

### 3. Subida a Google Workspace

1. Admin Console > Users > ícono de subida > **Upload multiple users**
2. Subir `subida_masiva_workspace.csv`
3. Verificar que las cuentas queden en: `/Cuentas Prepa/estudiantes/Nuevo Ingreso 2026`

### 4. Envío de correos de bienvenida

```bash
# Prueba con un correo propio:
SENDGRID_API_KEY=<key> python3 enviar_credenciales.py --test tu@correo.com

# Envío masivo real:
SENDGRID_API_KEY=<key> python3 enviar_credenciales.py
```

El log queda en `log_envios.csv`. Todos los registros deben tener Status `202`.  
Desde v1.1.0 el log anterior se archiva automáticamente en `logs/` antes de cada envío.

---

## Configuración actual

Todos los valores de configuración (contraseñas, unidades organizativas, SendGrid) se administran en `config.json`. Ver `config.ejemplo.json` como referencia.

## Casos especiales conocidos

- **Caracteres Unicode matemáticos en emails** (p.ej. fuente monoespaciada copiada desde WhatsApp o docs): el script los normaliza automáticamente con NFKD → se reportan en `revision_manual.csv`. Verificar que el correo resultante sea correcto.
- **Typos de dominio** (gmai.com, hotmial.com, etc.): corregidos automáticamente.
- **Nombre repetido en ambas columnas**: el script infiere la separación y lo reporta para revisión.
- **Espacios/saltos de línea en el email**: eliminados automáticamente.
