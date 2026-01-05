"""
Módulo para dividir transacciones grandes en múltiples facturas
"""

from typing import List, Dict
import os
import sys

# Agregar el directorio padre al path para importar config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def split_transaction(transaction: Dict, max_base: float = None) -> List[Dict]:
    """
    Divide una transacción en múltiples facturas si la base imponible supera el límite.
    
    Args:
        transaction: Diccionario con 'fecha', 'concepto', 'importe' (base imponible)
        max_base: Límite máximo de base imponible por factura (default desde config)
        
    Returns:
        Lista de facturas a generar, cada una con base_imponible <= max_base
    """
    if max_base is None:
        max_base = config.MAX_INVOICE_BASE
    
    base_imponible = transaction['importe']
    fecha = transaction['fecha']
    concepto = transaction['concepto']
    
    invoices = []
    
    # Si la base es menor o igual al límite, una sola factura
    if base_imponible <= max_base:
        invoices.append({
            'fecha': fecha,
            'concepto': concepto,
            'base_imponible': base_imponible,
            'original_amount': base_imponible,
            'part_number': 1,
            'total_parts': 1
        })
    else:
        # Dividir en múltiples facturas
        num_invoices = int(base_imponible / max_base)
        if base_imponible % max_base > 0:
            num_invoices += 1
        
        # Calcular el importe por factura
        amount_per_invoice = base_imponible / num_invoices
        
        for i in range(num_invoices):
            # Para la última factura, usar el resto para evitar errores de redondeo
            if i == num_invoices - 1:
                invoice_base = base_imponible - (amount_per_invoice * (num_invoices - 1))
            else:
                invoice_base = amount_per_invoice
            
            invoices.append({
                'fecha': fecha,
                'concepto': concepto,
                'base_imponible': round(invoice_base, 2),
                'original_amount': base_imponible,
                'part_number': i + 1,
                'total_parts': num_invoices
            })
    
    return invoices


def process_transactions(transactions: List[Dict], max_base: float = None) -> List[Dict]:
    """
    Procesa una lista de transacciones y las divide en facturas según el límite.
    
    Args:
        transactions: Lista de transacciones con 'fecha', 'concepto', 'importe'
        max_base: Límite máximo de base imponible por factura (default desde config)
        
    Returns:
        Lista de todas las facturas a generar
    """
    if max_base is None:
        max_base = config.MAX_INVOICE_BASE
    
    all_invoices = []
    
    for transaction in transactions:
        invoices = split_transaction(transaction, max_base)
        all_invoices.extend(invoices)
    
    return all_invoices

