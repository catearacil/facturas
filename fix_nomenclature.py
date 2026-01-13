"""
Script para corregir la nomenclatura de las facturas en la base de datos
Renombra facturas desde T2025026 en adelante al formato correcto T{year}{number:04d}
"""

import psycopg2
import json
import re
from typing import List, Dict

DATABASE_URL = "postgresql://neondb_owner:npg_N0MdPby9RuTn@ep-square-hill-ahmpbcjq-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def get_db_connection():
    """Obtiene una conexión a la base de datos"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Error conectando a la base de datos: {e}")
        raise

def extract_invoice_info(invoice_number_str: str) -> tuple:
    """
    Extrae año y número de factura del formato actual
    Ejemplos:
    - T2025026 -> (2025, 26)
    - T20250264 -> (2025, 264)
    - T250264 -> (2025, 264)  # formato antiguo con año de 2 dígitos
    """
    # Intentar formato nuevo: T2025026 (año de 4 dígitos)
    match = re.match(r'T(\d{4})(\d+)', invoice_number_str)
    if match:
        year = int(match.group(1))
        number = int(match.group(2))
        return year, number
    
    # Intentar formato antiguo: T250264 (año de 2 dígitos)
    match = re.match(r'T(\d{2})(\d{4})', invoice_number_str)
    if match:
        year = 2000 + int(match.group(1))
        number = int(match.group(2))
        return year, number
    
    return None, None

def generate_correct_number(year: int, number: int) -> str:
    """Genera el número de factura correcto: T{year}{number:04d}"""
    return f"T{year}{number:04d}"

def get_all_invoices():
    """Obtiene todas las facturas de la base de datos"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT id, invoice_files 
            FROM invoice_history 
            ORDER BY id
        """)
        
        records = cur.fetchall()
        all_invoices = []
        
        for record_id, invoice_files_json in records:
            if invoice_files_json:
                if isinstance(invoice_files_json, str):
                    invoice_files = json.loads(invoice_files_json)
                else:
                    invoice_files = invoice_files_json
                
                for inv_file in invoice_files:
                    inv_file['record_id'] = record_id
                    all_invoices.append(inv_file)
        
        return all_invoices
    finally:
        cur.close()
        conn.close()

def update_invoice_in_db(record_id: int, old_number: str, new_number: str):
    """Actualiza un número de factura en la base de datos"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Obtener el registro actual
        cur.execute("SELECT invoice_files FROM invoice_history WHERE id = %s", (record_id,))
        result = cur.fetchone()
        
        if not result:
            print(f"  ⚠️ No se encontró el registro {record_id}")
            return False
        
        invoice_files_json = result[0]
        if isinstance(invoice_files_json, str):
            invoice_files = json.loads(invoice_files_json)
        else:
            invoice_files = invoice_files_json
        
        # Actualizar el número de factura en la lista
        updated = False
        for inv_file in invoice_files:
            if inv_file.get('number') == old_number:
                inv_file['number'] = new_number
                # Actualizar también el filename si existe
                if 'filename' in inv_file:
                    # Extraer la extensión
                    if inv_file['filename'].endswith('.pdf'):
                        inv_file['filename'] = f"{new_number}.pdf"
                    else:
                        inv_file['filename'] = f"{new_number}.pdf"
                updated = True
                break
        
        if updated:
            # Guardar de vuelta en la BD
            cur.execute("""
                UPDATE invoice_history 
                SET invoice_files = %s 
                WHERE id = %s
            """, (json.dumps(invoice_files), record_id))
            conn.commit()
            return True
        else:
            print(f"  ⚠️ No se encontró la factura {old_number} en el registro {record_id}")
            return False
    except Exception as e:
        print(f"  ❌ Error actualizando {old_number} -> {new_number}: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()

def main():
    print("🔍 Conectando a la base de datos...")
    
    # Obtener todas las facturas
    print("📋 Obteniendo todas las facturas...")
    all_invoices = get_all_invoices()
    print(f"   Encontradas {len(all_invoices)} facturas en total\n")
    
    # Mostrar todas las facturas para diagnóstico
    print("📊 Revisando formato de todas las facturas (>= 26):")
    print("-" * 80)
    
    invoices_to_fix = []
    invoices_by_number = {}
    
    for inv in all_invoices:
        number = inv.get('number', '')
        year, num = extract_invoice_info(number)
        
        if year and num:
            correct_number = generate_correct_number(year, num)
            status = "✅" if number == correct_number else "❌"
            
            # Agrupar por número para evitar duplicados
            key = (year, num)
            if key not in invoices_by_number:
                invoices_by_number[key] = {
                    'old_number': number,
                    'new_number': correct_number,
                    'year': year,
                    'num': num,
                    'record_id': inv.get('record_id'),
                    'needs_fix': number != correct_number
                }
            
            # Mostrar todas las facturas >= 26
            if num >= 26:
                if number != correct_number:
                    print(f"  {status} {number:15} -> {correct_number:15} (año {year}, número {num})")
        else:
            if number and number.startswith('T'):
                print(f"  ⚠️  {number:15} (formato no reconocido)")
    
    print("-" * 80)
    
    # Filtrar facturas desde T2025026 en adelante que necesitan corrección
    for key, inv_info in invoices_by_number.items():
        if inv_info['num'] >= 26 and inv_info['needs_fix']:
            invoices_to_fix.append(inv_info)
    
    if not invoices_to_fix:
        print("\n✅ No hay facturas que corregir desde T2025026 en adelante.")
        print("   Todas las facturas ya tienen el formato correcto T{year}{number:04d}")
        return
    
    print(f"📝 Facturas a corregir: {len(invoices_to_fix)}\n")
    print("Lista de cambios:")
    print("-" * 60)
    
    for inv in invoices_to_fix:
        print(f"  {inv['old_number']} -> {inv['new_number']} (año {inv['year']}, número {inv['num']})")
    
    print("-" * 60)
    
    # Confirmar antes de hacer cambios
    response = input("\n¿Deseas aplicar estos cambios? (s/n): ").strip().lower()
    if response != 's':
        print("❌ Operación cancelada.")
        return
    
    print("\n🔄 Aplicando cambios...")
    
    success_count = 0
    error_count = 0
    
    for inv in invoices_to_fix:
        print(f"  Actualizando {inv['old_number']} -> {inv['new_number']}...", end=" ")
        if update_invoice_in_db(inv['record_id'], inv['old_number'], inv['new_number']):
            print("✅")
            success_count += 1
        else:
            print("❌")
            error_count += 1
    
    print("\n" + "=" * 60)
    print(f"✅ Actualizadas correctamente: {success_count}")
    if error_count > 0:
        print(f"❌ Errores: {error_count}")
    print("=" * 60)

if __name__ == "__main__":
    main()

