"""
Script CLI para procesar extractos bancarios y generar facturas
"""

import sys
import argparse
import os
from pathlib import Path

# Agregar el directorio padre al path para importar config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.santander_reader import process_santander_file
from src.invoice_splitter import process_transactions
from src.invoice_generator import generate_invoices
import config


def main():
    parser = argparse.ArgumentParser(
        description='Genera facturas desde extractos bancarios de Santander'
    )
    parser.add_argument(
        'input_file',
        type=str,
        help='Ruta al archivo Excel del extracto de Santander'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default='output',
        help='Directorio de salida para las facturas (default: output)'
    )
    parser.add_argument(
        '--iva',
        type=float,
        default=config.IVA_RATE * 100,
        help=f'Porcentaje de IVA (default: {config.IVA_RATE * 100}%%)'
    )
    parser.add_argument(
        '--max-base',
        type=float,
        default=config.MAX_INVOICE_BASE,
        help=f'Límite máximo de base imponible por factura (default: {config.MAX_INVOICE_BASE}€)'
    )
    parser.add_argument(
        '--start-number',
        type=int,
        default=1,
        help='Número inicial para la numeración de facturas (default: 1)'
    )
    
    args = parser.parse_args()
    
    # Validar archivo de entrada
    if not os.path.exists(args.input_file):
        print(f"❌ Error: El archivo {args.input_file} no existe.")
        sys.exit(1)
    
    # Actualizar configuración
    original_iva = config.IVA_RATE
    original_max = config.MAX_INVOICE_BASE
    config.IVA_RATE = args.iva / 100
    config.MAX_INVOICE_BASE = args.max_base
    
    try:
        print(f"📖 Leyendo extracto: {args.input_file}")
        transactions, excluded, info = process_santander_file(args.input_file)
        
        if not transactions:
            print("⚠️  No se encontraron transacciones de ingreso en el extracto.")
            if excluded:
                print(f"\n📋 Se encontraron {len(excluded)} transacciones excluidas:")
                for trans in excluded[:5]:  # Mostrar primeras 5
                    print(f"  - {trans.get('concepto', 'Sin concepto')}: {trans.get('razon', 'Sin razón')}")
                if len(excluded) > 5:
                    print(f"  ... y {len(excluded) - 5} más")
            sys.exit(0)
        
        print(f"✅ Se encontraron {len(transactions)} transacciones de ingreso")
        if excluded:
            print(f"⚠️  Se excluyeron {len(excluded)} transacciones (gastos o errores)")
        
        print(f"🔄 Procesando transacciones (IVA: {args.iva}%, Límite: {args.max_base}€)...")
        invoices, split_transactions = process_transactions(transactions, args.max_base)
        
        if split_transactions:
            print(f"\n✂️  Se dividieron {len(split_transactions)} transacciones grandes:")
            for trans in split_transactions:
                print(f"  - {trans.get('concepto', 'Sin concepto')[:50]}: "
                      f"{trans.get('importe_original', 0):,.2f} € → {trans.get('num_facturas', 0)} facturas")
        
        print(f"📄 Generando {len(invoices)} facturas...")
        
        # Crear directorio de salida si no existe
        os.makedirs(args.output, exist_ok=True)
        
        # Generar facturas
        generated = generate_invoices(invoices, args.output, args.start_number)
        
        # Calcular resumen
        total_base = sum(inv['base_imponible'] for inv in invoices)
        total_iva = sum(inv['base_imponible'] * config.IVA_RATE for inv in invoices)
        total_amount = total_base + total_iva
        
        print("\n" + "="*50)
        print("📊 RESUMEN")
        print("="*50)
        print(f"Transacciones procesadas: {len(transactions)}")
        print(f"Facturas generadas: {len(invoices)}")
        print(f"Base imponible total: {total_base:,.2f} €")
        print(f"IVA total: {total_iva:,.2f} €")
        print(f"Total con IVA: {total_amount:,.2f} €")
        print("="*50)
        print(f"\n✅ Facturas guardadas en: {args.output}")
        
        # Restaurar configuración
        config.IVA_RATE = original_iva
        config.MAX_INVOICE_BASE = original_max
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

