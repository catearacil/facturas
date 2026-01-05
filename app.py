"""
Aplicación Streamlit para generar facturas desde extractos bancarios de Santander
"""

import streamlit as st
import pandas as pd
import zipfile
import os
import tempfile
import base64
from datetime import datetime
from pathlib import Path

# Importar módulos del proyecto
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.santander_reader import process_santander_file
from src.invoice_splitter import process_transactions
from src.invoice_generator import generate_invoices
from src.history_manager import add_to_history, get_history_by_month, get_month_summary
import config


# Configuración de la página
st.set_page_config(
    page_title="Generador de Facturas - MallorCamp",
    page_icon="📄",
    layout="wide"
)

# Título principal
st.title("📄 Generador de Facturas")
st.markdown("---")

# Pestañas
tab1, tab2 = st.tabs(["🔄 Generar Facturas", "📊 Historial"])

# Sidebar para configuración
with st.sidebar:
    st.header("⚙️ Configuración")
    
    # IVA
    iva_rate = st.number_input(
        "IVA (%)",
        min_value=0.0,
        max_value=100.0,
        value=config.IVA_RATE * 100,
        step=0.1,
        help="Porcentaje de IVA a aplicar"
    )
    
    # Límite máximo por factura
    max_base = st.number_input(
        "Límite máximo base imponible (€)",
        min_value=0.0,
        value=config.MAX_INVOICE_BASE,
        step=10.0,
        help="Si una transacción supera este monto, se dividirá en múltiples facturas"
    )
    
    st.markdown("---")
    st.markdown("### 📋 Datos de la Empresa")
    st.text(f"Nombre: {config.COMPANY_DATA['name']}")
    st.text(f"CIF: {config.COMPANY_DATA['cif']}")
    st.text(f"Email: {config.COMPANY_DATA['email']}")

# Pestaña 1: Generar Facturas
with tab1:
    # Área principal
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📤 Subir Extracto Bancario")
        
        uploaded_file = st.file_uploader(
            "Selecciona el archivo Excel del extracto de Santander",
            type=['xlsx', 'xls'],
            help="El archivo debe contener columnas: Fecha Operación, Concepto, Importe"
        )
        
        # Mostrar preview del archivo si está cargado (opcional, más discreto)
        if uploaded_file is not None:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_path = tmp_file.name
                
                # Leer solo para preview
                df_preview = pd.read_excel(tmp_path, engine='openpyxl', nrows=5)
                
                # Mostrar preview de forma más discreta
                with st.expander("👁️ Vista previa del archivo", expanded=False):
                    st.dataframe(df_preview.head(), use_container_width=True)
                
                # Limpiar archivo temporal del preview
                os.unlink(tmp_path)
            except Exception as e:
                # Silenciar errores de preview, no es crítico
                pass

    # Inicializar variables de sesión
    if 'invoices_generated' not in st.session_state:
        st.session_state.invoices_generated = None
    if 'summary_data' not in st.session_state:
        st.session_state.summary_data = None

    # Procesar archivo si se subió
    if uploaded_file is not None:
        with col1:
            if st.button("🔄 Procesar Extracto", type="primary", use_container_width=True):
                try:
                    with st.spinner("Procesando extracto..."):
                        # Guardar archivo temporalmente
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
                            tmp_file.write(uploaded_file.getvalue())
                            tmp_path = tmp_file.name
                        
                        # Procesar extracto
                        transactions = process_santander_file(tmp_path)
                        
                        if not transactions:
                            st.warning("⚠️ No se encontraron transacciones de ingreso en el extracto.")
                        else:
                            # Actualizar configuración temporal
                            original_iva = config.IVA_RATE
                            original_max = config.MAX_INVOICE_BASE
                            config.IVA_RATE = iva_rate / 100
                            config.MAX_INVOICE_BASE = max_base
                            
                            # Dividir transacciones en facturas
                            invoices = process_transactions(transactions, max_base)
                            
                            # Crear directorio de salida temporal
                            output_dir = tempfile.mkdtemp()
                            
                            # Generar facturas
                            generated = generate_invoices(invoices, output_dir, start_number=1)
                            
                            # Restaurar configuración original
                            config.IVA_RATE = original_iva
                            config.MAX_INVOICE_BASE = original_max
                            
                            # Calcular resumen
                            total_base = sum(inv['base_imponible'] for inv in invoices)
                            total_iva = sum(inv['base_imponible'] * (iva_rate / 100) for inv in invoices)
                            total_amount = total_base + total_iva
                            
                            # Guardar en sesión
                            st.session_state.invoices_generated = generated
                            st.session_state.summary_data = {
                                'total_transactions': len(transactions),
                                'total_invoices': len(invoices),
                                'total_base': total_base,
                                'total_iva': total_iva,
                                'total_amount': total_amount,
                                'output_dir': output_dir
                            }
                            
                            # Guardar en historial
                            add_to_history(
                                invoice_count=len(invoices),
                                total_base=total_base,
                                total_iva=total_iva,
                                total_amount=total_amount,
                                invoice_files=generated,
                                output_dir=output_dir,
                                iva_rate=iva_rate / 100
                            )
                            
                            # Limpiar archivo temporal
                            os.unlink(tmp_path)
                            
                            st.success(f"✅ Se generaron {len(invoices)} facturas correctamente!")
                            
                except ValueError as e:
                    # Error de columnas no encontradas - mostrar información detallada
                    error_msg = str(e)
                    st.error(f"❌ Error al procesar el archivo: {error_msg}")
                    
                    # Intentar mostrar las columnas del archivo
                    try:
                        df_debug = pd.read_excel(tmp_path, engine='openpyxl', nrows=1)
                        st.info(f"**Columnas en el archivo:** {', '.join(df_debug.columns.tolist())}")
                        st.info("💡 **Sugerencia:** Asegúrate de que el archivo tenga columnas con nombres como 'Fecha Operación', 'Concepto' o 'Importe' (pueden tener variaciones)")
                    except:
                        pass
                        
                except Exception as e:
                    st.error(f"❌ Error al procesar el archivo: {str(e)}")
                    with st.expander("🔍 Detalles del error"):
                        st.exception(e)

    # Mostrar resultados si hay facturas generadas
    if st.session_state.invoices_generated is not None:
        st.markdown("---")
        st.subheader("📊 Resumen de Facturas Generadas")
        
        summary = st.session_state.summary_data
        
        # Métricas
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Transacciones", summary['total_transactions'])
        with col2:
            st.metric("Facturas Generadas", summary['total_invoices'])
        with col3:
            st.metric("Base Imponible Total", f"{summary['total_base']:,.2f} €")
        with col4:
            st.metric("Total con IVA", f"{summary['total_amount']:,.2f} €")
        
        st.markdown("---")
        
        # Tabla de facturas
        st.subheader("📋 Lista de Facturas")
        
        invoices_data = []
        for inv in st.session_state.invoices_generated:
            base = inv['invoice']['base_imponible']
            iva = base * (iva_rate / 100)
            total = base + iva
            invoices_data.append({
                'Número': inv['number'],
                'Fecha': inv['invoice']['fecha'],
                'Concepto': inv['invoice']['concepto'][:50] + '...' if len(inv['invoice']['concepto']) > 50 else inv['invoice']['concepto'],
                'Base': f"{base:,.2f} €",
                'IVA': f"{iva:,.2f} €",
                'Total': f"{total:,.2f} €"
            })
        
        df_invoices = pd.DataFrame(invoices_data)
        st.dataframe(df_invoices, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Preview y descarga
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("👁️ Vista Previa")
            if st.session_state.invoices_generated:
                first_invoice = st.session_state.invoices_generated[0]
                # Leer PDF una vez
                with open(first_invoice['path'], 'rb') as pdf_file:
                    pdf_data = pdf_file.read()
                
                # Botón de descarga
                st.download_button(
                    label="📥 Descargar Primera Factura",
                    data=pdf_data,
                    file_name=first_invoice['filename'],
                    mime="application/pdf"
                )
                
                # Mostrar PDF embebido
                base64_pdf = base64.b64encode(pdf_data).decode('utf-8')
                pdf_display = f'''
                <iframe 
                    src="data:application/pdf;base64,{base64_pdf}" 
                    width="100%" 
                    height="600px" 
                    type="application/pdf"
                    style="border: 1px solid #ddd;">
                </iframe>
                '''
                st.markdown(pdf_display, unsafe_allow_html=True)
        
        with col2:
            st.subheader("📦 Descargar Todas las Facturas")
            
            # Crear ZIP con todas las facturas
            if st.button("📥 Descargar ZIP con todas las facturas", use_container_width=True):
                zip_path = os.path.join(summary['output_dir'], 'facturas.zip')
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for inv in st.session_state.invoices_generated:
                        zipf.write(inv['path'], inv['filename'])
                
                with open(zip_path, 'rb') as zip_file:
                    st.download_button(
                        label="⬇️ Descargar ZIP",
                        data=zip_file.read(),
                        file_name=f"facturas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
            
            # Descargas individuales
            st.markdown("### 📄 Descargas Individuales")
            for inv in st.session_state.invoices_generated[:10]:  # Mostrar solo las primeras 10
                with open(inv['path'], 'rb') as pdf_file:
                    st.download_button(
                        label=f"📥 {inv['number']}",
                        data=pdf_file.read(),
                        file_name=inv['filename'],
                        mime="application/pdf",
                        key=f"download_{inv['number']}"
                    )
            
            if len(st.session_state.invoices_generated) > 10:
                st.info(f"Mostrando las primeras 10 facturas. El ZIP contiene todas las {len(st.session_state.invoices_generated)} facturas.")

        # Footer
        st.markdown("---")
        st.markdown(
            """
            <div style='text-align: center; color: #666;'>
                <p>Generador de Facturas - MallorCamp Sport SL</p>
            </div>
            """,
            unsafe_allow_html=True
        )

# Pestaña 2: Historial
with tab2:
    st.subheader("📊 Historial de Facturas por Mes")
    
    # Cargar historial
    history_by_month = get_history_by_month()
    
    if not history_by_month:
        st.info("📭 No hay historial de facturas generadas aún. Genera facturas en la pestaña 'Generar Facturas' para ver el historial aquí.")
    else:
        # Resumen general
        all_records = []
        for records in history_by_month.values():
            all_records.extend(records)
        
        if all_records:
            general_summary = get_month_summary(all_records)
            
            st.markdown("### 📈 Resumen General")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Facturas", general_summary['total_invoices'])
            with col2:
                st.metric("Base Imponible Total", f"{general_summary['total_base']:,.2f} €")
            with col3:
                st.metric("IVA Total", f"{general_summary['total_iva']:,.2f} €")
            with col4:
                st.metric("Total General", f"{general_summary['total_amount']:,.2f} €")
            
            st.markdown(f"**Total de procesamientos:** {general_summary['processing_count']}")
            st.markdown("---")
        
        # Mostrar historial por mes
        for month, records in history_by_month.items():
            # Formatear nombre del mes en español
            try:
                month_date = datetime.strptime(month, '%Y-%m')
                months_es = {
                    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
                    5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
                    9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
                }
                month_name = f"{months_es[month_date.month]} {month_date.year}"
            except:
                month_name = month
            
            with st.expander(f"📅 {month_name} ({len(records)} procesamiento{'s' if len(records) > 1 else ''})", expanded=True):
                # Resumen del mes
                summary = get_month_summary(records)
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Facturas", summary['total_invoices'])
                with col2:
                    st.metric("Base Imponible", f"{summary['total_base']:,.2f} €")
                with col3:
                    st.metric("IVA", f"{summary['total_iva']:,.2f} €")
                with col4:
                    st.metric("Total", f"{summary['total_amount']:,.2f} €")
                
                st.markdown("---")
                
                # Detalles de cada procesamiento
                for idx, record in enumerate(records):
                    # Formatear fecha en español
                    try:
                        record_date = datetime.strptime(record['date'], '%Y-%m-%d')
                        date_formatted = record_date.strftime('%d/%m/%Y')
                    except:
                        date_formatted = record['date']
                    
                    st.markdown(f"**📄 Procesamiento del {date_formatted}**")
                    
                    # Mostrar información en columnas
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Facturas", record['invoice_count'])
                    with col2:
                        st.metric("Base Imponible", f"{record['total_base']:,.2f} €")
                    with col3:
                        st.metric("IVA", f"{record['total_iva']:,.2f} €")
                    with col4:
                        st.metric("Total", f"{record['total_amount']:,.2f} €")
                    
                    # Lista de facturas
                    if record['invoice_files']:
                        with st.expander(f"📋 Ver {len(record['invoice_files'])} factura{'s' if len(record['invoice_files']) > 1 else ''} de este procesamiento"):
                            # Crear tabla de facturas
                            invoices_table_data = []
                            for inv_file in record['invoice_files']:
                                invoices_table_data.append({
                                    'Número': inv_file['number'],
                                    'Base': f"{inv_file['base']:,.2f} €",
                                    'Total': f"{inv_file['total']:,.2f} €",
                                    'Archivo': inv_file['filename']
                                })
                            
                            df_invoices = pd.DataFrame(invoices_table_data)
                            st.dataframe(df_invoices, use_container_width=True, hide_index=True)
                            
                            st.markdown("**Descargar facturas:**")
                            # Botones de descarga
                            cols = st.columns(min(3, len(record['invoice_files'])))
                            for i, inv_file in enumerate(record['invoice_files']):
                                col_idx = i % 3
                                with cols[col_idx]:
                                    if os.path.exists(inv_file['path']):
                                        with open(inv_file['path'], 'rb') as pdf_file:
                                            st.download_button(
                                                label=f"📥 {inv_file['number']}",
                                                data=pdf_file.read(),
                                                file_name=inv_file['filename'],
                                                mime="application/pdf",
                                                key=f"hist_{record['id']}_{inv_file['number']}_{idx}",
                                                use_container_width=True
                                            )
                                    else:
                                        st.warning(f"⚠️ {inv_file['number']}")
                    
                    if idx < len(records) - 1:
                        st.markdown("---")

