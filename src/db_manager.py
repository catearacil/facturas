"""
Módulo para gestionar la conexión a la base de datos PostgreSQL (Neon)
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Optional
import json

# Cargar variables de entorno desde .env si existe
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Si python-dotenv no está instalado, continuar sin él
    pass


def get_db_connection():
    """
    Obtiene una conexión a la base de datos PostgreSQL.
    Prioridad de búsqueda:
    1. Streamlit secrets (para Streamlit Cloud)
    2. Variable de entorno DATABASE_URL (desde .env o sistema)
    3. Cadena de conexión por defecto (hardcodeada como último recurso)
    
    Returns:
        Conexión a la base de datos
    """
    database_url = None
    
    # 1. Intentar desde Streamlit secrets (para Streamlit Cloud)
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and 'DATABASE_URL' in st.secrets:
            database_url = st.secrets['DATABASE_URL']
    except:
        pass
    
    # 2. Intentar desde variable de entorno (desde .env o sistema)
    if not database_url:
        database_url = os.environ.get('DATABASE_URL')
    
    # 3. Si no está en ninguna parte, usar la cadena de conexión por defecto
    # (último recurso, no recomendado para producción)
    if not database_url:
        database_url = "postgresql://neondb_owner:npg_N0MdPby9RuTn@ep-square-hill-ahmpbcjq-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    
    try:
        conn = psycopg2.connect(database_url)
        return conn
    except Exception as e:
        print(f"Error conectando a la base de datos: {e}")
        raise


def init_database():
    """
    Inicializa las tablas necesarias en la base de datos si no existen.
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Crear tabla de historial
        cur.execute("""
            CREATE TABLE IF NOT EXISTS invoice_history (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                date VARCHAR(10),
                month VARCHAR(7),
                invoice_count INTEGER,
                total_base NUMERIC(10, 2),
                total_iva NUMERIC(10, 2),
                total_amount NUMERIC(10, 2),
                invoice_files JSONB,
                output_dir TEXT,
                excluded_transactions JSONB,
                split_transactions JSONB,
                processing_info JSONB,
                iva_rate NUMERIC(5, 4)
            )
        """)
        
        # Crear índices para búsquedas rápidas
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_invoice_history_month 
            ON invoice_history(month)
        """)
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_invoice_history_date 
            ON invoice_history(date)
        """)
        
        conn.commit()
        cur.close()
        
    except Exception as e:
        print(f"Error inicializando base de datos: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def load_history_from_db() -> List[Dict]:
    """
    Carga el historial desde la base de datos PostgreSQL.
    
    Returns:
        Lista de registros del historial
    """
    try:
        init_database()  # Asegurar que las tablas existen
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT * FROM invoice_history 
            ORDER BY timestamp DESC
        """)
        
        records = cur.fetchall()
        
        # Convertir a lista de diccionarios y convertir JSONB a dict
        history = []
        for record in records:
            record_dict = dict(record)
            # Convertir JSONB a dict si es necesario
            if isinstance(record_dict.get('invoice_files'), str):
                record_dict['invoice_files'] = json.loads(record_dict['invoice_files'])
            if isinstance(record_dict.get('excluded_transactions'), str):
                record_dict['excluded_transactions'] = json.loads(record_dict['excluded_transactions'])
            if isinstance(record_dict.get('split_transactions'), str):
                record_dict['split_transactions'] = json.loads(record_dict['split_transactions'])
            if isinstance(record_dict.get('processing_info'), str):
                record_dict['processing_info'] = json.loads(record_dict['processing_info'])
            
            # Convertir timestamp a string ISO
            if record_dict.get('timestamp'):
                record_dict['timestamp'] = record_dict['timestamp'].isoformat()
            
            history.append(record_dict)
        
        cur.close()
        conn.close()
        
        return history
        
    except Exception as e:
        print(f"Error cargando historial desde BD: {e}")
        # Si falla la BD, retornar lista vacía
        return []


def save_history_to_db(record: Dict) -> int:
    """
    Guarda un registro en la base de datos PostgreSQL.
    
    Args:
        record: Diccionario con los datos del registro
        
    Returns:
        ID del registro insertado
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO invoice_history 
            (date, month, invoice_count, total_base, total_iva, total_amount, 
             invoice_files, output_dir, excluded_transactions, split_transactions, 
             processing_info, iva_rate)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            record.get('date'),
            record.get('month'),
            record.get('invoice_count'),
            record.get('total_base'),
            record.get('total_iva'),
            record.get('total_amount'),
            json.dumps(record.get('invoice_files', [])),
            record.get('output_dir'),
            json.dumps(record.get('excluded_transactions', [])),
            json.dumps(record.get('split_transactions', [])),
            json.dumps(record.get('processing_info', {})),
            record.get('iva_rate', 0.21)
        ))
        
        record_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return record_id
        
    except Exception as e:
        print(f"Error guardando historial en BD: {e}")
        if conn:
            conn.rollback()
            conn.close()
        raise


def delete_from_db(record_id: int) -> bool:
    """
    Elimina un registro del historial por su ID.
    
    Args:
        record_id: ID del registro a eliminar
        
    Returns:
        True si se eliminó correctamente, False si no se encontró
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("DELETE FROM invoice_history WHERE id = %s", (record_id,))
        deleted = cur.rowcount > 0
        
        conn.commit()
        cur.close()
        conn.close()
        
        return deleted
        
    except Exception as e:
        print(f"Error eliminando registro de BD: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False


def delete_month_from_db(month: str) -> int:
    """
    Elimina todos los registros de un mes específico.
    
    Args:
        month: Mes en formato 'YYYY-MM'
        
    Returns:
        Número de registros eliminados
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("DELETE FROM invoice_history WHERE month = %s", (month,))
        deleted_count = cur.rowcount
        
        conn.commit()
        cur.close()
        conn.close()
        
        return deleted_count
        
    except Exception as e:
        print(f"Error eliminando mes de BD: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return 0

