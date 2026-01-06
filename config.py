"""
Configuración del generador de facturas
"""

# Configuración de IVA
IVA_RATE = 0.21  # 21%

# Límite máximo de TOTAL (con IVA) por factura
MAX_INVOICE_BASE = 400.00  # € (este es el límite del TOTAL con IVA incluido)

# Formato de numeración de facturas
INVOICE_NUMBER_FORMAT = "T{year}{number:04d}"  # Ej: T260001, T260002

# Último número de factura usado por año (para continuar la numeración)
# Formato: {año: último_número}
# Ejemplo: Si la última factura de 2025 fue T250263, poner: 2025: 263
LAST_INVOICE_NUMBERS = {
    2025: 263,  # Última factura del 2025: T250263
    # Para 2026 y siguientes, se calculará automáticamente desde el historial
}

# Datos de la empresa
COMPANY_DATA = {
    "name": "MALLORCAMP SPORT SL.",
    "address": "Avenida Pere Mas i Reus nro 23. Edificio Siesta 1. apto 517. Puerto de Alcudia (07400), Islas Baleares, España",
    "cif": "B44754299",
    "phone": "+34623963563",
    "email": "contact.mallorcamp@gmail.com",
    "registry": "MALLORCAMP SPORT, S.L. CIF B44754299 Registrada en el Registre Mercantil de Mallorca Tom 2998, Foli 195, Fulla PM-96514"
}

# Tagline de la empresa
COMPANY_TAGLINE = "Tennis & Padel training in Mallorca"

# Concepto fijo para todas las facturas
INVOICE_CONCEPT = "Consultoría de Tenis"
