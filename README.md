# facturas

# Generador de Facturas desde Extracto Bancario Santander

Aplicación web para procesar extractos bancarios de Santander y generar facturas simplificadas en PDF con el formato de MallorCamp.

## Características

- ✅ Procesa extractos bancarios de Santander en formato Excel
- ✅ Filtra automáticamente solo transacciones de ingreso
- ✅ Divide transacciones mayores a 500€ en múltiples facturas
- ✅ Calcula IVA del 21% automáticamente
- ✅ Genera facturas en PDF con formato profesional
- ✅ Interfaz web intuitiva con Streamlit
- ✅ Descarga de facturas individuales o en ZIP

## Columnas del Extracto Santander

El sistema reconoce automáticamente las siguientes columnas del extracto:
- **Fecha Operación**: Fecha de la transacción
- **Concepto**: Descripción de la transacción
- **Importe**: Cantidad (positivo = ingreso, negativo = gasto)
- Otras columnas: Fecha Valor, Divisa, Saldo, Código, Referencias, etc. (no se usan para facturas)

## Instalación

1. Clonar o descargar el proyecto
2. Instalar dependencias:

```bash
pip install -r requirements.txt
```

## Uso

### Interfaz Web (Recomendado)

Ejecutar la aplicación Streamlit:

```bash
streamlit run app.py
```

La aplicación se abrirá en el navegador. Sube tu archivo Excel del extracto Santander y sigue las instrucciones.

### Línea de Comandos (Opcional)

```bash
python src/main.py input/extracto.xlsx
```

## Estructura del Proyecto

```
facturador/
├── src/
│   ├── santander_reader.py   # Lectura de extractos
│   ├── invoice_splitter.py   # División de facturas
│   ├── invoice_generator.py  # Generación de PDFs
│   └── main.py               # Script CLI
├── app.py                    # Aplicación Streamlit
├── config.py                 # Configuración
├── input/                    # Archivos Excel de entrada
└── output/                   # Facturas generadas
```

## Requisitos

- Python 3.8+
- pandas
- openpyxl
- reportlab
- streamlit

## Notas

- Solo se procesan transacciones de ingreso (valores positivos en columna "Importe")
- Las transacciones mayores a 500€ se dividen automáticamente
- El IVA se calcula sobre la base imponible (21%)
- Las facturas se numeran consecutivamente: T260001, T260002, etc.
