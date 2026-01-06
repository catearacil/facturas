"""
Módulo para dividir transacciones grandes en múltiples facturas
"""

from typing import List, Dict
import os
import sys

# Agregar el directorio padre al path para importar config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def split_transaction(transaction: Dict, max_total: float = None) -> List[Dict]:
    """
    Divide una transacción en múltiples facturas si el TOTAL (con IVA) supera el límite.
    
    Args:
        transaction: Diccionario con 'fecha', 'concepto', 'importe' (base imponible), 'importe_con_iva' (total con IVA)
        max_total: Límite máximo de TOTAL (con IVA) por factura (default desde config)
        
    Returns:
        Lista de facturas a generar, cada una con total <= max_total
    """
    if max_total is None:
        max_total = config.MAX_INVOICE_BASE  # Este es el límite del TOTAL con IVA
    
    base_imponible = transaction['importe']
    fecha = transaction['fecha']
    concepto = transaction['concepto']
    # Obtener el importe con IVA si existe (para preservarlo al dividir)
    importe_con_iva = transaction.get('importe_con_iva')
    
    # Si no tenemos importe_con_iva, calcularlo desde la base imponible
    if importe_con_iva is None:
        importe_con_iva = base_imponible * (1 + config.IVA_RATE)
    
    invoices = []
    
    # Si el TOTAL (con IVA) es menor o igual al límite, una sola factura
    if importe_con_iva <= max_total:
        invoice_data = {
            'fecha': fecha,
            'concepto': concepto,
            'base_imponible': base_imponible,
            'original_amount': base_imponible,
            'part_number': 1,
            'total_parts': 1,
            'importe_con_iva': round(importe_con_iva, 2)
        }
        invoices.append(invoice_data)
    else:
        # Dividir en múltiples facturas basándose en el TOTAL (con IVA)
        num_invoices = int(importe_con_iva / max_total)
        if importe_con_iva % max_total > 0:
            num_invoices += 1
        
        # Calcular el importe TOTAL por factura (con IVA)
        total_per_invoice = importe_con_iva / num_invoices
        
        for i in range(num_invoices):
            # Para la última factura, usar el resto para evitar errores de redondeo
            if i == num_invoices - 1:
                invoice_total = importe_con_iva - (total_per_invoice * (num_invoices - 1))
            else:
                invoice_total = total_per_invoice
            
            # Calcular la base imponible desde el total con IVA
            invoice_base = invoice_total / (1 + config.IVA_RATE)
            
            invoice_data = {
                'fecha': fecha,
                'concepto': concepto,
                'base_imponible': round(invoice_base, 2),
                'original_amount': base_imponible,
                'part_number': i + 1,
                'total_parts': num_invoices,
                'importe_con_iva': round(invoice_total, 2)
            }
            invoices.append(invoice_data)
    
    return invoices


def process_transactions(transactions: List[Dict], max_total: float = None) -> tuple:
    """
    Procesa una lista de transacciones y las divide en facturas según el límite del TOTAL (con IVA).
    
    Args:
        transactions: Lista de transacciones con 'fecha', 'concepto', 'importe', 'importe_con_iva'
        max_total: Límite máximo de TOTAL (con IVA) por factura (default desde config)
        
    Returns:
        Tupla: (lista_de_facturas, transacciones_divididas)
        donde transacciones_divididas es una lista de dicts con información sobre divisiones
    """
    if max_total is None:
        max_total = config.MAX_INVOICE_BASE  # Este es el límite del TOTAL con IVA
    
    all_invoices = []
    split_transactions = []  # Rastrear transacciones que se dividieron
    
    for transaction in transactions:
        invoices = split_transaction(transaction, max_total)
        
        # Si se dividió en más de una factura, registrar la información
        if len(invoices) > 1:
            importe_con_iva_original = transaction.get('importe_con_iva', transaction['importe'] * (1 + config.IVA_RATE))
            split_transactions.append({
                'fecha': transaction['fecha'],
                'concepto': transaction['concepto'],
                'importe_original': importe_con_iva_original,  # Total con IVA original
                'num_facturas': len(invoices),
                'limite_aplicado': max_total
            })
        
        all_invoices.extend(invoices)
    
    return all_invoices, split_transactions

