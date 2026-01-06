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
    # Obtener el importe con IVA si existe (para preservarlo al dividir)
    importe_con_iva = transaction.get('importe_con_iva')
    
    invoices = []
    
    # Si la base es menor o igual al límite, una sola factura
    if base_imponible <= max_base:
        invoice_data = {
            'fecha': fecha,
            'concepto': concepto,
            'base_imponible': base_imponible,
            'original_amount': base_imponible,
            'part_number': 1,
            'total_parts': 1
        }
        # Preservar el importe con IVA si existe
        if importe_con_iva:
            invoice_data['importe_con_iva'] = importe_con_iva
        invoices.append(invoice_data)
    else:
        # Dividir en múltiples facturas
        num_invoices = int(base_imponible / max_base)
        if base_imponible % max_base > 0:
            num_invoices += 1
        
        # Calcular el importe por factura (base imponible)
        amount_per_invoice = base_imponible / num_invoices
        
        # Si tenemos importe con IVA, también dividirlo proporcionalmente
        importe_con_iva_per_invoice = importe_con_iva / num_invoices if importe_con_iva else None
        
        for i in range(num_invoices):
            # Para la última factura, usar el resto para evitar errores de redondeo
            if i == num_invoices - 1:
                invoice_base = base_imponible - (amount_per_invoice * (num_invoices - 1))
                if importe_con_iva:
                    invoice_total = importe_con_iva - (importe_con_iva_per_invoice * (num_invoices - 1))
                else:
                    invoice_total = None
            else:
                invoice_base = amount_per_invoice
                invoice_total = importe_con_iva_per_invoice if importe_con_iva else None
            
            invoice_data = {
                'fecha': fecha,
                'concepto': concepto,
                'base_imponible': round(invoice_base, 2),
                'original_amount': base_imponible,
                'part_number': i + 1,
                'total_parts': num_invoices
            }
            # Preservar el importe con IVA si existe
            if invoice_total:
                invoice_data['importe_con_iva'] = round(invoice_total, 2)
            invoices.append(invoice_data)
    
    return invoices


def process_transactions(transactions: List[Dict], max_base: float = None) -> tuple:
    """
    Procesa una lista de transacciones y las divide en facturas según el límite.
    
    Args:
        transactions: Lista de transacciones con 'fecha', 'concepto', 'importe'
        max_base: Límite máximo de base imponible por factura (default desde config)
        
    Returns:
        Tupla: (lista_de_facturas, transacciones_divididas)
        donde transacciones_divididas es una lista de dicts con información sobre divisiones
    """
    if max_base is None:
        max_base = config.MAX_INVOICE_BASE
    
    all_invoices = []
    split_transactions = []  # Rastrear transacciones que se dividieron
    
    for transaction in transactions:
        invoices = split_transaction(transaction, max_base)
        
        # Si se dividió en más de una factura, registrar la información
        if len(invoices) > 1:
            split_transactions.append({
                'fecha': transaction['fecha'],
                'concepto': transaction['concepto'],
                'importe_original': transaction['importe'],
                'num_facturas': len(invoices),
                'limite_aplicado': max_base
            })
        
        all_invoices.extend(invoices)
    
    return all_invoices, split_transactions

