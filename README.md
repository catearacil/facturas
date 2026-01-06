# Generador de Facturas - MallorCamp

Aplicación para generar facturas desde extractos bancarios de Santander.

## Instalación

1. Clonar el repositorio
2. Instalar dependencias:

```bash
python3 -m pip install -r requirements.txt
```

3. Configurar base de datos (opcional pero recomendado):

```bash
# Copiar el archivo de ejemplo
cp .env.example .env

# Editar .env con tus credenciales de Neon
# O simplemente usar la cadena de conexión que ya está en el código
```

## Uso

### Aplicación Web (Streamlit)

```bash
python3 -m streamlit run app.py
```

O usando el script de conveniencia:

```bash
./run.sh
```

### CLI (Línea de comandos)

```bash
python3 src/main.py input/extracto.xlsx -o output
```

## Configuración de Base de Datos

### Desarrollo Local

1. Crear archivo `.env` en la raíz del proyecto:

```bash
cp .env.example .env
```

2. Editar `.env` con tu cadena de conexión de Neon:

```
DATABASE_URL=postgresql://usuario:password@host/database?sslmode=require
```

**Nota:** Si no creas el archivo `.env`, la aplicación usará la cadena de conexión por defecto configurada en el código.

### Streamlit Cloud

1. Ve a Settings → Secrets en tu app
2. Añade:

```toml
DATABASE_URL = "postgresql://usuario:password@host/database?sslmode=require"
```

## Estructura del Proyecto

```
facturador/
├── src/
│   ├── santander_reader.py    # Lee extractos Excel de Santander
│   ├── invoice_splitter.py    # Divide transacciones grandes
│   ├── invoice_generator.py   # Genera PDFs de facturas
│   ├── history_manager.py      # Gestiona historial (BD o JSON)
│   ├── db_manager.py          # Gestión de conexión PostgreSQL
│   └── main.py                # Script CLI opcional
├── assets/
│   └── logo.png               # Logo de MallorCamp
├── input/                     # Directorio para archivos Excel
├── output/                    # Directorio de salida
│   ├── history/               # Historial (si usa JSON)
│   └── user_config.json       # Configuración del usuario
├── app.py                     # Aplicación Streamlit principal
├── config.py                  # Configuración global
├── requirements.txt           # Dependencias Python
└── .env                       # Variables de entorno (no se sube a Git)
```

## Características

- ✅ Lectura automática de extractos Excel de Santander
- ✅ Detección inteligente de columnas
- ✅ División automática de transacciones grandes
- ✅ Generación de PDFs con formato MallorCamp
- ✅ Historial persistente en PostgreSQL (Neon)
- ✅ Interfaz web con Streamlit
- ✅ Exportación de transacciones excluidas/divididas

## Notas

- El historial se guarda en PostgreSQL para persistencia entre reinicios
- Si la BD no está disponible, se usa JSON como fallback automático
- Los archivos PDF se generan en `output/` o en directorios temporales
