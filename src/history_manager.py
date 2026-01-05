"""
Módulo para gestionar el historial de facturas generadas
"""

import json
import os
from datetime import datetime
from typing import List, Dict
from pathlib import Path


HISTORY_FILE = "history.json"


def get_history_path() -> str:
    """Obtiene la ruta del archivo de historial"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    history_dir = os.path.join(base_dir, 'output', 'history')
    os.makedirs(history_dir, exist_ok=True)
    return os.path.join(history_dir, HISTORY_FILE)


def load_history() -> List[Dict]:
    """Carga el historial desde el archivo JSON"""
    history_path = get_history_path()
    if os.path.exists(history_path):
        try:
            with open(history_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_history(history: List[Dict]):
    """Guarda el historial en el archivo JSON"""
    history_path = get_history_path()
    try:
        with open(history_path, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error guardando historial: {e}")


def add_to_history(
    invoice_count: int,
    total_base: float,
    total_iva: float,
    total_amount: float,
    invoice_files: List[Dict],
    output_dir: str,
    iva_rate: float = 0.21
) -> Dict:
    """
    Añade un nuevo registro al historial
    
    Args:
        invoice_count: Número de facturas generadas
        total_base: Base imponible total
        total_iva: IVA total
        total_amount: Total con IVA
        invoice_files: Lista de archivos de facturas generadas
        output_dir: Directorio donde se guardaron las facturas
        
    Returns:
        Diccionario con el registro añadido
    """
    history = load_history()
    
    record = {
        'id': len(history) + 1,
        'timestamp': datetime.now().isoformat(),
        'date': datetime.now().strftime('%Y-%m-%d'),
        'month': datetime.now().strftime('%Y-%m'),
        'invoice_count': invoice_count,
        'total_base': total_base,
        'total_iva': total_iva,
        'total_amount': total_amount,
        'invoice_files': [
            {
                'number': inv['number'],
                'filename': inv['filename'],
                'path': inv['path'],
                'base': inv['invoice']['base_imponible'],
                'total': inv['invoice']['base_imponible'] * (1 + iva_rate)
            }
            for inv in invoice_files
        ],
        'output_dir': output_dir
    }
    
    history.append(record)
    save_history(history)
    
    return record


def get_history_by_month() -> Dict[str, List[Dict]]:
    """
    Obtiene el historial organizado por mes
    
    Returns:
        Diccionario con meses como keys y listas de registros como values
    """
    history = load_history()
    by_month = {}
    
    for record in history:
        month = record.get('month', datetime.now().strftime('%Y-%m'))
        if month not in by_month:
            by_month[month] = []
        by_month[month].append(record)
    
    # Ordenar cada mes por fecha (más reciente primero)
    for month in by_month:
        by_month[month].sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    # Ordenar meses (más reciente primero)
    return dict(sorted(by_month.items(), key=lambda x: x[0], reverse=True))


def get_month_summary(records: List[Dict]) -> Dict:
    """
    Calcula un resumen para un mes
    
    Returns:
        Diccionario con totales del mes
    """
    total_invoices = sum(r['invoice_count'] for r in records)
    total_base = sum(r['total_base'] for r in records)
    total_iva = sum(r['total_iva'] for r in records)
    total_amount = sum(r['total_amount'] for r in records)
    
    return {
        'total_invoices': total_invoices,
        'total_base': total_base,
        'total_iva': total_iva,
        'total_amount': total_amount,
        'processing_count': len(records)
    }

