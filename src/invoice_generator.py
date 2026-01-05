"""
Módulo para generar facturas en PDF con formato MallorCamp
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime
from typing import Dict
import os
import sys

# Agregar el directorio padre al path para importar config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


# Colores (aproximados al diseño)
COLOR_DARK_GREEN = colors.HexColor('#2d5016')  # Verde oscuro para logo
COLOR_BLACK = colors.black
COLOR_GREY = colors.HexColor('#666666')


def format_currency(amount: float) -> str:
    """Formatea un importe como moneda europea (formato: 1.234,56)"""
    # Formatear con punto como separador de miles y coma como decimal
    return f"{amount:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def generate_invoice_number(year: int, number: int) -> str:
    """Genera el número de factura según el formato configurado"""
    return config.INVOICE_NUMBER_FORMAT.format(year=year, number=number)


def create_invoice_pdf(invoice_data: Dict, invoice_number: str, output_path: str):
    """
    Genera un PDF de factura con el formato de MallorCamp.
    
    Args:
        invoice_data: Diccionario con 'fecha', 'concepto', 'base_imponible'
        invoice_number: Número de factura (ej: T260001)
        output_path: Ruta donde guardar el PDF
    """
    # Crear el documento
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm
    )
    
    # Contenedor para los elementos
    story = []
    
    # Estilos
    styles = getSampleStyleSheet()
    
    # Estilo para título "Factura Simplificada"
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=22,  # Ligeramente más pequeño para coincidir con el diseño
        textColor=COLOR_BLACK,
        fontName='Helvetica-Bold',
        leading=26,
        spaceAfter=0  # Sin espacio después, se controla con Spacer
    )
    
    # Estilo para número y fecha
    info_style = ParagraphStyle(
        'InfoStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=COLOR_BLACK,
        fontName='Helvetica',
        leading=12
    )
    
    # Estilo para datos de empresa
    company_style = ParagraphStyle(
        'CompanyStyle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=COLOR_BLACK,
        fontName='Helvetica',
        leading=11,
        spaceAfter=4
    )
    
    # Estilo para tagline
    tagline_style = ParagraphStyle(
        'TaglineStyle',
        parent=styles['Normal'],
        fontSize=8,
        textColor=COLOR_DARK_GREEN,
        fontName='Helvetica',
        leading=10
    )
    
    # HEADER
    fecha_str = invoice_data.get('fecha', datetime.now().strftime('%d/%m/%Y'))
    info_text = f'<b>Número #</b> {invoice_number}<br/><b>Fecha</b> {fecha_str}'
    
    # Cargar logo si existe
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logo_path = os.path.join(base_dir, 'assets', 'logo.png')
    logo_image = None
    if os.path.exists(logo_path):
        try:
            # Calcular dimensiones del logo para limitar tamaño
            from PIL import Image as PILImage
            pil_img = PILImage.open(logo_path)
            img_width, img_height = pil_img.size
            aspect_ratio = img_height / img_width if img_width > 0 else 1
            
            # Limitar tamaño: ancho máximo 40mm, altura máxima 25mm
            max_width = 40*mm
            max_height = 25*mm
            
            # Calcular dimensiones finales manteniendo proporción
            if aspect_ratio > (max_height / max_width):
                final_height = max_height
                final_width = max_height / aspect_ratio
            else:
                final_width = max_width
                final_height = max_width * aspect_ratio
            
            logo_image = Image(logo_path, width=final_width, height=final_height)
        except Exception as e:
            logo_image = None
    
    # Crear tabla para header: título a la izquierda, logo a la derecha
    header_data = [[
        Paragraph('Factura Simplificada', title_style),
        logo_image if logo_image else Paragraph('', info_style)
    ]]
    header_table = Table(header_data, colWidths=[140*mm, 55*mm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2*mm),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    
    # Número y fecha debajo del título
    story.append(Paragraph(info_text, info_style))
    story.append(Spacer(1, 6*mm))
    
    # DATOS DE EMPRESA (lado izquierdo)
    company_text = f"""
    <b>{config.COMPANY_DATA['name']}</b><br/>
    {config.COMPANY_DATA['address']}<br/>
    CIF: {config.COMPANY_DATA['cif']}<br/>
    Tel: {config.COMPANY_DATA['phone']}<br/>
    Email: {config.COMPANY_DATA['email']}
    """
    story.append(Paragraph(company_text, company_style))
    story.append(Spacer(1, 10*mm))
    
    # TABLA DE CONCEPTOS
    base_imponible = invoice_data['base_imponible']
    iva_amount = base_imponible * config.IVA_RATE
    total = base_imponible + iva_amount
    
    concepto = invoice_data.get('concepto', 'Sin concepto')
    
    # Headers de la tabla
    table_data = [
        ['CONCEPTO', 'PRECIO', 'UNIDADES', 'SUBTOTAL', 'IVA', 'TOTAL']
    ]
    
    # Fila de datos - usar Paragraph para concepto para permitir word wrap
    concepto_para = Paragraph(concepto, ParagraphStyle(
        'ConceptoStyle',
        parent=styles['Normal'],
        fontSize=8,
        textColor=COLOR_BLACK,
        fontName='Helvetica',
        leading=10,
        alignment=TA_LEFT
    ))
    
    table_data.append([
        concepto_para,
        '',  # PRECIO vacío (no se usa en este formato)
        '1',
        format_currency(base_imponible) + '€',
        '21%',
        format_currency(total) + '€'
    ])
    
    # Crear tabla con anchos ajustados
    # Ancho disponible: A4 (210mm) - márgenes (40mm) = 170mm
    # Distribución: CONCEPTO (más ancho), PRECIO (vacío), UNIDADES, SUBTOTAL, IVA, TOTAL
    concept_table = Table(table_data, colWidths=[80*mm, 12*mm, 18*mm, 20*mm, 15*mm, 20*mm])
    concept_table.setStyle(TableStyle([
        # Headers - todos alineados a la izquierda como en la imagen
        ('BACKGROUND', (0, 0), (-1, 0), colors.white),
        ('TEXTCOLOR', (0, 0), (-1, 0), COLOR_BLACK),
        ('ALIGN', (0, 0), (-1, 0), 'LEFT'),  # Headers a la izquierda
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),  # Tamaño más pequeño
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        # Línea separadora debajo de headers
        ('LINEBELOW', (0, 0), (-1, 0), 1, COLOR_BLACK),
        # Datos
        ('FONTNAME', (1, 1), (5, 1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, 1), 8),  # Mismo tamaño para todos
        ('BOTTOMPADDING', (0, 1), (-1, 1), 8),
        ('TOPPADDING', (0, 1), (-1, 1), 8),
        # Alineación: concepto a la izquierda, números a la derecha
        ('ALIGN', (0, 1), (0, 1), 'LEFT'),
        ('ALIGN', (1, 1), (5, 1), 'RIGHT'),
        ('VALIGN', (0, 1), (0, 1), 'TOP'),
        # Padding horizontal igual a cero (los márgenes del documento ya proporcionan el espacio)
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    
    story.append(concept_table)
    story.append(Spacer(1, 15*mm))
    
    # RESUMEN (parte inferior derecha)
    summary_data = [
        ['BASE IMPONIBLE:', format_currency(base_imponible) + '€'],
        ['IVA 21%:', format_currency(iva_amount) + '€'],
        ['TOTAL:', format_currency(total) + '€']
    ]
    
    summary_table = Table(summary_data, colWidths=[55*mm, 45*mm])
    summary_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        # Padding horizontal igual a cero
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        # Línea superior
        ('LINEABOVE', (0, 0), (-1, 0), 1, COLOR_BLACK),
        # BASE IMPONIBLE y TOTAL en negrita
        ('FONTNAME', (0, 0), (1, 0), 'Helvetica-Bold'),  # BASE IMPONIBLE
        ('FONTNAME', (0, 2), (1, 2), 'Helvetica-Bold'),  # TOTAL
        ('FONTSIZE', (0, 2), (1, 2), 10),  # Mismo tamaño para TOTAL
    ]))
    
    # Alinear tabla a la derecha usando contenedor
    summary_container = Table([[summary_table]], colWidths=[195*mm])
    summary_container.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'RIGHT'),
    ]))
    story.append(Spacer(1, 10*mm))
    story.append(summary_container)
    
    # Espacio flexible para empujar el footer al final
    story.append(Spacer(1, 1))
    
    # FOOTER
    # Línea horizontal
    footer_line = Table([['']], colWidths=[195*mm])
    footer_line.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (0, 0), 0.5, COLOR_BLACK),
    ]))
    story.append(footer_line)
    story.append(Spacer(1, 4*mm))
    
    # Referencia y registro
    footer_text = f"""
    {invoice_number} - {format_currency(total)}€<br/>
    {config.COMPANY_DATA['registry']}
    """
    
    footer_table_data = [
        [
            Paragraph(footer_text, ParagraphStyle(
                'FooterStyle',
                parent=styles['Normal'],
                fontSize=7,
                textColor=COLOR_BLACK,
                fontName='Helvetica',
                leading=9
            )),
            Paragraph('Pág. 1 de 1', ParagraphStyle(
                'PageStyle',
                parent=styles['Normal'],
                fontSize=7,
                textColor=COLOR_BLACK,
                fontName='Helvetica',
                leading=9,
                alignment=TA_RIGHT
            ))
        ]
    ]
    
    footer_table = Table(footer_table_data, colWidths=[150*mm, 45*mm])
    footer_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    story.append(footer_table)
    
    # Construir el PDF
    doc.build(story)


def generate_invoices(invoices: list, output_dir: str, start_number: int = 1) -> list:
    """
    Genera múltiples facturas en PDF.
    
    Args:
        invoices: Lista de facturas a generar (cada una con 'fecha', 'concepto', 'base_imponible')
        output_dir: Directorio donde guardar los PDFs
        start_number: Número inicial para la numeración
        
    Returns:
        Lista de rutas de los archivos generados
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    generated_files = []
    current_year = datetime.now().year
    current_number = start_number
    
    for invoice in invoices:
        # Generar número de factura
        invoice_number = generate_invoice_number(current_year, current_number)
        
        # Nombre del archivo
        filename = f"FAC-{invoice_number}.pdf"
        filepath = os.path.join(output_dir, filename)
        
        # Generar PDF
        create_invoice_pdf(invoice, invoice_number, filepath)
        
        generated_files.append({
            'path': filepath,
            'filename': filename,
            'number': invoice_number,
            'invoice': invoice
        })
        
        current_number += 1
    
    return generated_files

