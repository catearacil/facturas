"""
Módulo para gestionar el historial de facturas generadas
Usa PostgreSQL (Neon) para persistencia
"""

import json
import os
import re
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

# Intentar importar el gestor de BD, si falla usar JSON como fallback
try:
    from src.db_manager import (
        load_history_from_db, 
        save_history_to_db, 
        delete_from_db as delete_from_db_func,
        delete_month_from_db as delete_month_from_db_func,
        init_database
    )
    USE_DATABASE = True
except ImportError:
    USE_DATABASE = False
    print("Advertencia: No se pudo importar db_manager, usando JSON como fallback")


HISTORY_FILE = "history.json"


def get_history_path() -> str:
    """Obtiene la ruta del archivo de historial (fallback)"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    history_dir = os.path.join(base_dir, 'output', 'history')
    os.makedirs(history_dir, exist_ok=True)
    return os.path.join(history_dir, HISTORY_FILE)


def load_history() -> List[Dict]:
    """Carga el historial desde la base de datos o archivo JSON (fallback)"""
    if USE_DATABASE:
        try:
            return load_history_from_db()
        except Exception as e:
            print(f"Error cargando desde BD, usando JSON fallback: {e}")
            # Fallback a JSON
            pass
    
    # Fallback: cargar desde JSON
    history_path = get_history_path()
    if os.path.exists(history_path):
        try:
            with open(history_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_history(history: List[Dict]):
    """
    Guarda el historial. 
    Nota: Esta función ya no se usa directamente, se usa add_to_history que guarda individualmente.
    Se mantiene para compatibilidad.
    """
    # Ya no guardamos todo el historial de una vez, se guarda registro por registro
    pass


def add_to_history(
    invoice_count: int,
    total_base: float,
    total_iva: float,
    total_amount: float,
    invoice_files: List[Dict],
    output_dir: str,
    iva_rate: float = 0.21,
    excluded_transactions: List[Dict] = None,
    split_transactions: List[Dict] = None,
    processing_info: Dict = None
) -> Dict:
    """
    Añade un nuevo registro al historial (en base de datos o JSON)
    
    Args:
        invoice_count: Número de facturas generadas
        total_base: Base imponible total
        total_iva: IVA total
        total_amount: Total con IVA
        invoice_files: Lista de archivos de facturas generadas
        output_dir: Directorio donde se guardaron las facturas
        excluded_transactions: Lista de transacciones excluidas (opcional)
        split_transactions: Lista de transacciones divididas (opcional)
        processing_info: Información del procesamiento (opcional)
        
    Returns:
        Diccionario con el registro añadido
    """
    record = {
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
                'total': inv['invoice'].get('importe_con_iva', inv['invoice']['base_imponible'] * (1 + iva_rate)),
                'fecha': inv['invoice'].get('fecha', '')
            }
            for inv in invoice_files
        ],
        'output_dir': output_dir,
        'excluded_transactions': excluded_transactions or [],
        'split_transactions': split_transactions or [],
        'processing_info': processing_info or {},
        'iva_rate': iva_rate
    }
    
    if USE_DATABASE:
        try:
            record_id = save_history_to_db(record)
            record['id'] = record_id
            record['timestamp'] = datetime.now().isoformat()
            return record
        except Exception as e:
            print(f"Error guardando en BD, usando JSON fallback: {e}")
            # Fallback a JSON
            pass
    
    # Fallback: guardar en JSON
    history = load_history()
    record['id'] = len(history) + 1
    record['timestamp'] = datetime.now().isoformat()
    history.append(record)
    
    history_path = get_history_path()
    try:
        with open(history_path, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error guardando historial: {e}")
    
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


def delete_from_history(record_id: int) -> bool:
    """
    Elimina un registro del historial por su ID
    
    Args:
        record_id: ID del registro a eliminar
        
    Returns:
        True si se eliminó correctamente, False si no se encontró
    """
    if USE_DATABASE:
        try:
            return delete_from_db_func(record_id)
        except Exception as e:
            print(f"Error eliminando de BD, usando JSON fallback: {e}")
            # Fallback a JSON
            pass
    
    # Fallback: eliminar de JSON
    history = load_history()
    original_count = len(history)
    
    # Filtrar el registro con el ID especificado
    history = [r for r in history if r.get('id') != record_id]
    
    if len(history) < original_count:
        history_path = get_history_path()
        try:
            with open(history_path, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Error guardando historial: {e}")
    return False


def delete_month_from_history(month: str) -> int:
    """
    Elimina todos los registros de un mes específico
    
    Args:
        month: Mes en formato 'YYYY-MM'
        
    Returns:
        Número de registros eliminados
    """
    if USE_DATABASE:
        try:
            return delete_month_from_db_func(month)
        except Exception as e:
            print(f"Error eliminando mes de BD, usando JSON fallback: {e}")
            # Fallback a JSON
            pass
    
    # Fallback: eliminar de JSON
    history = load_history()
    original_count = len(history)
    
    # Filtrar registros del mes especificado
    history = [r for r in history if r.get('month') != month]
    
    deleted_count = original_count - len(history)
    if deleted_count > 0:
        history_path = get_history_path()
        try:
            with open(history_path, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error guardando historial: {e}")
    
    return deleted_count


def extract_invoice_number(invoice_number_str: str) -> Optional[int]:
    """
    Extrae el número de factura del formato T250263
    Ejemplo: T250263 -> 263
    
    Args:
        invoice_number_str: Número de factura en formato T{year}{number:04d}
        
    Returns:
        Número de factura (int) o None si no se puede parsear
    """
    # Patrón: T seguido de 2 dígitos (año) y 4 dígitos (número)
    match = re.match(r'T\d{2}(\d{4})', invoice_number_str)
    if match:
        return int(match.group(1))
    return None


def get_last_invoice_number(year: int) -> int:
    """
    Obtiene el último número de factura usado para un año específico.
    Busca en el historial y en la configuración.
    
    Args:
        year: Año (ej: 2025)
        
    Returns:
        Último número de factura usado, o 0 si no hay historial
    """
    import config
    
    # Primero, buscar en el historial
    history = load_history()
    last_number = 0
    
    # Buscar en todos los registros del historial
    for record in history:
        invoice_files = record.get('invoice_files', [])
        for inv_file in invoice_files:
            invoice_number = inv_file.get('number', '')
            # Extraer el año del número de factura (T250263 -> año 25 = 2025)
            match = re.match(r'T(\d{2})', invoice_number)
            if match:
                invoice_year = 2000 + int(match.group(1))
                if invoice_year == year:
                    number = extract_invoice_number(invoice_number)
                    if number and number > last_number:
                        last_number = number
    
    # Si no se encontró en el historial, usar la configuración
    if last_number == 0:
        last_number = config.LAST_INVOICE_NUMBERS.get(year, 0)
    
    return last_number


def get_last_year_with_invoices() -> Optional[int]:
    """
    Obtiene el último año que tiene facturas generadas (del historial o configuración).
    
    Returns:
        Año más reciente con facturas, o None si no hay ninguna
    """
    import config
    
    last_year = None
    last_number = 0
    
    # Buscar en el historial
    history = load_history()
    for record in history:
        invoice_files = record.get('invoice_files', [])
        for inv_file in invoice_files:
            invoice_number = inv_file.get('number', '')
            match = re.match(r'T(\d{2})', invoice_number)
            if match:
                invoice_year = 2000 + int(match.group(1))
                number = extract_invoice_number(invoice_number)
                if number and number > last_number:
                    last_number = number
                    last_year = invoice_year
    
    # Si no hay historial, buscar en la configuración
    if last_year is None and config.LAST_INVOICE_NUMBERS:
        last_year = max(config.LAST_INVOICE_NUMBERS.keys())
    
    return last_year

