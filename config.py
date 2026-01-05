"""
Configuración del generador de facturas
"""

# Configuración de IVA
IVA_RATE = 0.21  # 21%

# Límite máximo de base imponible por factura
MAX_INVOICE_BASE = 500.00  # €

# Formato de numeración de facturas
INVOICE_NUMBER_FORMAT = "T{year}{number:04d}"  # Ej: T260001, T260002

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
