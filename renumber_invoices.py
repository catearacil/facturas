"""
Script para renumerar facturas desde T2025026 en adelante
Ordena las facturas por fecha y las renumeración secuencialmente
"""

import psycopg2
import json
import re
from datetime import datetime
from typing import List, Dict, Tuple

DATABASE_URL = "postgresql://neondb_owner:npg_N0MdPby9RuTn@ep-square-hill-ahmpbcjq-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def get_db_connection():
    """Obtiene una conexión a la base de datos"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Error conectando a la base de datos: {e}")
        raise

def parse_date(fecha_str: str) -> datetime:
    """Parsea una fecha desde string"""
    try:
        if '/' in fecha_str:
            return datetime.strptime(fecha_str, '%d/%m/%Y')
        elif '-' in fecha_str:
            return datetime.strptime(fecha_str, '%Y-%m-%d')
    except:
        pass
    return datetime.now()

def extract_invoice_info(invoice_number_str: str) -> Tuple[int, int]:
    """Extrae año y número de factura"""
    # Formato: T2025026 o T20250264
    match = re.match(r'T(\d{4})(\d+)', invoice_number_str)
    if match:
        year = int(match.group(1))
        number = int(match.group(2))
        return year, number
    return None, None

def generate_correct_number(year: int, number: int) -> str:
    """Genera el número de factura correcto: T{year}{number:04d}"""
    return f"T{year}{number:04d}"

def get_all_invoices_from_26():
    """Obtiene todas las facturas desde el número 26 en adelante"""
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
                    number_str = inv_file.get('number', '')
                    year, num = extract_invoice_info(number_str)
                    
                    if year and num and num >= 26:
                        fecha = inv_file.get('fecha', '')
                        fecha_obj = parse_date(fecha) if fecha else datetime.now()
                        
                        all_invoices.append({
                            'old_number': number_str,
                            'year': year,
                            'old_num': num,
                            'fecha': fecha,
                            'fecha_obj': fecha_obj,
                            'record_id': record_id,
                            'invoice_data': inv_file
                        })
        
        return all_invoices
    finally:
        cur.close()
        conn.close()

def update_invoice_in_db(record_id: int, old_number: str, new_number: str, invoice_data: Dict):
    """Actualiza un número de factura en la base de datos"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Obtener el registro actual
        cur.execute("SELECT invoice_files FROM invoice_history WHERE id = %s", (record_id,))
        result = cur.fetchone()
        
        if not result:
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
                # Actualizar también el filename
                if 'filename' in inv_file:
                    inv_file['filename'] = f"{new_number}.pdf"
                # Actualizar también los datos del invoice si existen
                if 'invoice_data' in invoice_data:
                    inv_file.update(invoice_data)
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
            return False
    except Exception as e:
        print(f"  ❌ Error actualizando {old_number} -> {new_number}: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()

def main():
    import sys
    
    # Verificar si se pasa --yes para saltar confirmación
    auto_confirm = '--yes' in sys.argv or '-y' in sys.argv
    
    print("🔍 Conectando a la base de datos...")
    
    # Obtener todas las facturas desde el 26
    print("📋 Obteniendo todas las facturas desde el número 26...")
    all_invoices = get_all_invoices_from_26()
    print(f"   Encontradas {len(all_invoices)} facturas\n")
    
    if not all_invoices:
        print("✅ No hay facturas desde el número 26 para renumerar.")
        return
    
    # Ordenar por fecha (más antiguas primero)
    print("📅 Ordenando facturas por fecha...")
    sorted_invoices = sorted(all_invoices, key=lambda x: x['fecha_obj'])
    
    # Mostrar preview de las primeras y últimas
    print("\n📊 Preview del ordenamiento:")
    print("-" * 90)
    print("Primeras 10 facturas (más antiguas):")
    for inv in sorted_invoices[:10]:
        print(f"  {inv['old_number']:15} | Fecha: {inv['fecha']:12} | Número actual: {inv['old_num']}")
    
    if len(sorted_invoices) > 10:
        print("\nÚltimas 10 facturas (más recientes):")
        for inv in sorted_invoices[-10:]:
            print(f"  {inv['old_number']:15} | Fecha: {inv['fecha']:12} | Número actual: {inv['old_num']}")
    
    print("-" * 90)
    
    # Generar nueva numeración secuencial
    # Las facturas de octubre empiezan desde el 64
    print("\n🔄 Generando nueva numeración...")
    renumbering_map = []
    new_number = 64  # Empezar desde 64 para octubre
    
    # Separar facturas de octubre y otras
    october_invoices = []
    other_invoices = []
    
    for inv in sorted_invoices:
        fecha_obj = inv['fecha_obj']
        if fecha_obj.month == 10 and fecha_obj.year == 2025:
            october_invoices.append(inv)
        else:
            other_invoices.append(inv)
    
    # Primero numerar las de octubre (desde 64)
    print(f"   Facturas de octubre: {len(october_invoices)}")
    print(f"   Otras facturas: {len(other_invoices)}")
    
    # Ordenar octubre por fecha
    october_invoices.sort(key=lambda x: x['fecha_obj'])
    
    # Numerar facturas de octubre desde 64
    current_number = 64
    for inv in october_invoices:
        year = inv['year']
        new_number_str = generate_correct_number(year, current_number)
        
        renumbering_map.append({
            'old_number': inv['old_number'],
            'new_number': new_number_str,
            'old_num': inv['old_num'],
            'new_num': current_number,
            'fecha': inv['fecha'],
            'record_id': inv['record_id'],
            'invoice_data': inv['invoice_data']
        })
        
        current_number += 1
    
    # Luego numerar las demás (continuando desde donde quedó octubre)
    # Ordenar otras facturas por fecha
    other_invoices.sort(key=lambda x: x['fecha_obj'])
    
    for inv in other_invoices:
        year = inv['year']
        new_number_str = generate_correct_number(year, current_number)
        
        renumbering_map.append({
            'old_number': inv['old_number'],
            'new_number': new_number_str,
            'old_num': inv['old_num'],
            'new_num': current_number,
            'fecha': inv['fecha'],
            'record_id': inv['record_id'],
            'invoice_data': inv['invoice_data']
        })
        
        current_number += 1
    
    # Mostrar cambios
    print(f"\n📝 Cambios a realizar ({len(renumbering_map)} facturas):")
    print("-" * 90)
    
    changes_to_show = renumbering_map[:20] if len(renumbering_map) > 20 else renumbering_map
    for change in changes_to_show:
        if change['old_number'] != change['new_number']:
            print(f"  {change['old_number']:15} -> {change['new_number']:15} | Fecha: {change['fecha']:12}")
    
    if len(renumbering_map) > 20:
        print(f"  ... y {len(renumbering_map) - 20} facturas más")
    
    print("-" * 90)
    
    # Contar cuántas realmente necesitan cambio
    needs_change = [c for c in renumbering_map if c['old_number'] != c['new_number']]
    print(f"\n📊 Resumen:")
    print(f"   Total de facturas: {len(renumbering_map)}")
    print(f"   Facturas que necesitan cambio: {len(needs_change)}")
    
    if not needs_change:
        print("\n✅ Todas las facturas ya están correctamente numeradas.")
        return
    
    # Confirmar antes de hacer cambios
    print("\n" + "=" * 90)
    if auto_confirm:
        print("⚠️ Modo automático activado (--yes). Aplicando cambios...")
        response = 's'
    else:
        response = input("¿Deseas aplicar estos cambios? (s/n): ").strip().lower()
        if response != 's':
            print("❌ Operación cancelada.")
            return
    
    print("\n🔄 Aplicando cambios...")
    
    success_count = 0
    error_count = 0
    
    for change in renumbering_map:
        if change['old_number'] != change['new_number']:
            print(f"  {change['old_number']:15} -> {change['new_number']:15}...", end=" ")
            if update_invoice_in_db(
                change['record_id'], 
                change['old_number'], 
                change['new_number'],
                change['invoice_data']
            ):
                print("✅")
                success_count += 1
            else:
                print("❌")
                error_count += 1
    
    print("\n" + "=" * 90)
    print(f"✅ Actualizadas correctamente: {success_count}")
    if error_count > 0:
        print(f"❌ Errores: {error_count}")
    print("=" * 90)
    print("\n✅ Renumeración completada!")

if __name__ == "__main__":
    main()

