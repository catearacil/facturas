"""
Aplicación Streamlit para generar facturas desde extractos bancarios de Santander
"""

import streamlit as st
import pandas as pd
import zipfile
import os
import tempfile
import base64
import json
from datetime import datetime
from pathlib import Path

# Importar módulos del proyecto
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.santander_reader import process_santander_file
from src.invoice_splitter import process_transactions
from src.invoice_generator import generate_invoices
from src.history_manager import add_to_history, get_history_by_month, get_month_summary, delete_from_history, delete_month_from_history
import config


# Función para cargar configuración del usuario
def load_user_config():
    """Carga la configuración del usuario desde un archivo JSON"""
    config_path = os.path.join(os.path.dirname(__file__), 'output', 'user_config.json')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}


# Función para guardar configuración del usuario
def save_user_config(config_dict):
    """Guarda la configuración del usuario en un archivo JSON"""
    config_path = os.path.join(os.path.dirname(__file__), 'output', 'user_config.json')
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2)
    except Exception as e:
        st.warning(f"No se pudo guardar la configuración: {e}")


# Configuración de la página
st.set_page_config(
    page_title="Generador de Facturas - MallorCamp",
    page_icon="📄",
    layout="wide"
)

# Inicializar base de datos al inicio (si está disponible)
try:
    from src.db_manager import init_database
    init_database()
except Exception as e:
    # Si falla la inicialización, la app seguirá funcionando con JSON como fallback
    # No mostramos el warning aquí para no molestar al usuario, el sistema usará fallback automáticamente
    pass

# Título principal
st.title("📄 Generador de Facturas")
st.markdown("---")

# Pestañas
tab1, tab2 = st.tabs(["🔄 Generar Facturas", "📊 Historial"])

# Sidebar para configuración
with st.sidebar:
    st.header("⚙️ Configuración")
    
    # Cargar configuración guardada del usuario
    user_config = load_user_config()
    
    # Inicializar valores: primero desde archivo guardado, luego session_state, luego default
    default_iva = user_config.get('iva_rate', config.IVA_RATE * 100)
    default_max_base = user_config.get('max_base', config.MAX_INVOICE_BASE)
    
    # Inicializar session_state SIEMPRE desde el archivo guardado (para que persista entre recargas)
    # Esto asegura que si el usuario cambió el valor y se guardó, se cargue al recargar
    st.session_state.iva_rate_input = default_iva
    st.session_state.max_base_input = default_max_base
    
    # Callback para guardar IVA cuando cambia
    def save_iva():
        user_config = load_user_config()
        user_config['iva_rate'] = st.session_state.iva_rate_input
        save_user_config(user_config)
    
    # IVA - cuando usas key, Streamlit usa automáticamente el valor de session_state
    iva_rate = st.number_input(
        "IVA (%)",
        min_value=0.0,
        max_value=100.0,
        step=0.1,
        help="Porcentaje de IVA a aplicar",
        key='iva_rate_input',
        on_change=save_iva
    )
    
    # Callback para guardar max_base cuando cambia
    def save_max_base():
        user_config = load_user_config()
        user_config['max_base'] = st.session_state.max_base_input
        save_user_config(user_config)
    
    # Límite máximo por factura
    max_base = st.number_input(
        "Límite máximo base imponible (€)",
        min_value=0.0,
        step=10.0,
        help="Si una transacción supera este monto, se dividirá en múltiples facturas",
        key='max_base_input',
        on_change=save_max_base
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
                        
                        # Procesar extracto - ahora devuelve tupla (transactions, excluded, info)
                        transactions, excluded_transactions, processing_info = process_santander_file(tmp_path)
                        
                        if not transactions:
                            st.warning("⚠️ No se encontraron transacciones de ingreso en el extracto.")
                        else:
                            # Actualizar configuración temporal
                            original_iva = config.IVA_RATE
                            original_max = config.MAX_INVOICE_BASE
                            config.IVA_RATE = iva_rate / 100
                            config.MAX_INVOICE_BASE = max_base
                            
                            # Dividir transacciones en facturas
                            invoices, split_transactions = process_transactions(transactions, max_base)
                            
                            # Crear directorio de salida temporal
                            output_dir = tempfile.mkdtemp()
                            
                            # Obtener el último año con facturas y continuar desde ahí
                            from src.history_manager import get_last_invoice_number, get_last_year_with_invoices
                            
                            # Buscar el último año que tiene facturas
                            last_year = get_last_year_with_invoices()
                            if last_year is None:
                                # Si no hay historial, usar el año actual
                                last_year = datetime.now().year
                            
                            # Obtener el último número usado para ese año
                            last_number = get_last_invoice_number(last_year)
                            
                            # Si no hay número para ese año, empezar desde 1
                            if last_number == 0:
                                last_number = 0
                            
                            start_number = last_number + 1  # Continuar desde el siguiente
                            
                            # Generar facturas usando el último año encontrado
                            generated = generate_invoices(invoices, output_dir, start_number=start_number, year=last_year)
                            
                            # Restaurar configuración original
                            config.IVA_RATE = original_iva
                            config.MAX_INVOICE_BASE = original_max
                            
                            # Calcular resumen
                            total_base = sum(inv['base_imponible'] for inv in invoices)
                            # El IVA ya está incluido en el importe original, así que calculamos el IVA desde la base
                            total_iva = sum(inv['base_imponible'] * (iva_rate / 100) for inv in invoices)
                            # Si las facturas tienen importe_con_iva, usarlo; si no, calcularlo
                            total_amount = sum(inv.get('importe_con_iva', inv['base_imponible'] * (1 + iva_rate / 100)) for inv in invoices)
                            
                            # Guardar en sesión
                            st.session_state.invoices_generated = generated
                            st.session_state.excluded_transactions = excluded_transactions
                            st.session_state.split_transactions = split_transactions
                            st.session_state.processing_info = processing_info
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
                                iva_rate=iva_rate / 100,
                                excluded_transactions=excluded_transactions,
                                split_transactions=split_transactions,
                                processing_info=processing_info
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
            # El IVA se calcula desde la base imponible
            iva = base * (iva_rate / 100)
            # El total debe usar importe_con_iva si existe (ya incluye IVA), si no calcularlo
            total = inv['invoice'].get('importe_con_iva', base + iva)
            invoices_data.append({
                'Número': inv['number'],
                'Fecha': inv['invoice']['fecha'],
                'Concepto': inv['invoice'].get('concepto', 'Consultoría de Tenis')[:50] + '...' if len(inv['invoice'].get('concepto', 'Consultoría de Tenis')) > 50 else inv['invoice'].get('concepto', 'Consultoría de Tenis'),
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

        # Mostrar transacciones excluidas si existen
        if st.session_state.invoices_generated and 'excluded_transactions' in st.session_state:
            excluded = st.session_state.excluded_transactions
            info = st.session_state.get('processing_info', {})
            
            if excluded:
                st.markdown("---")
                st.subheader("📋 Transacciones Excluidas")
                
                # Resumen
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Total Excluidas", len(excluded))
                with col2:
                    total_excluido = sum(t.get('importe', 0) for t in excluded)
                    st.metric("Importe Total Excluido", f"{abs(total_excluido):,.2f} €")
                
                # Agrupar por razón
                razones = {}
                for trans in excluded:
                    razon = trans.get('razon', 'Sin razón especificada')
                    if razon not in razones:
                        razones[razon] = []
                    razones[razon].append(trans)
                
                # Mostrar por categorías
                for razon, trans_list in razones.items():
                    with st.expander(f"❌ {razon} ({len(trans_list)} transacciones)", expanded=False):
                        # Crear DataFrame para mostrar
                        df_excluded = pd.DataFrame(trans_list)
                        # Reordenar columnas si existe 'razon'
                        if 'razon' in df_excluded.columns:
                            # Mostrar sin la columna razon en la tabla (ya está en el título)
                            df_display = df_excluded[['fecha', 'concepto', 'importe']].copy()
                        else:
                            df_display = df_excluded.copy()
                        
                        st.dataframe(df_display, use_container_width=True, hide_index=True)
                        
                        # Botón para descargar CSV de esta categoría
                        # Asegurar que la fecha esté presente y en el orden correcto
                        if 'fecha' in df_excluded.columns:
                            # Reordenar columnas para que fecha esté primero
                            column_order = ['fecha', 'concepto', 'importe']
                            # Agregar otras columnas que puedan existir
                            for col in df_excluded.columns:
                                if col not in column_order:
                                    column_order.append(col)
                            # Filtrar solo las columnas que existen
                            column_order = [col for col in column_order if col in df_excluded.columns]
                            df_excluded_ordered = df_excluded[column_order]
                        else:
                            df_excluded_ordered = df_excluded
                        csv = df_excluded_ordered.to_csv(index=False, encoding='utf-8-sig')
                        st.download_button(
                            label=f"📥 Descargar {razon} (CSV)",
                            data=csv,
                            file_name=f"transacciones_excluidas_{razon.replace(' ', '_').replace('/', '_')}.csv",
                            mime="text/csv",
                            key=f"download_excluded_{hash(razon)}"
                        )
                
                # Botón para descargar todas las excluidas
                df_all_excluded = pd.DataFrame(excluded)
                # Asegurar que la fecha esté presente y en el orden correcto
                if 'fecha' in df_all_excluded.columns:
                    # Reordenar columnas para que fecha esté primero
                    column_order = ['fecha', 'concepto', 'importe', 'razon']
                    # Agregar otras columnas que puedan existir
                    for col in df_all_excluded.columns:
                        if col not in column_order:
                            column_order.append(col)
                    # Filtrar solo las columnas que existen
                    column_order = [col for col in column_order if col in df_all_excluded.columns]
                    df_all_excluded_ordered = df_all_excluded[column_order]
                else:
                    df_all_excluded_ordered = df_all_excluded
                csv_all = df_all_excluded_ordered.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📥 Descargar Todas las Transacciones Excluidas (CSV)",
                    data=csv_all,
                    file_name=f"todas_transacciones_excluidas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="download_all_excluded"
                )
                
                # Información adicional
                st.info(f"""
                **ℹ️ Información del procesamiento:**
                - Total de filas en el archivo: {info.get('total_filas', 'N/A')}
                - Transacciones incluidas: {info.get('transacciones_incluidas', 0)}
                - Transacciones excluidas: {info.get('transacciones_excluidas', 0)}
                """)
        
        # Mostrar transacciones divididas si existen
        if st.session_state.invoices_generated and 'split_transactions' in st.session_state:
            split_trans = st.session_state.split_transactions
            
            if split_trans:
                st.markdown("---")
                st.subheader("✂️ Transacciones Divididas en Múltiples Facturas")
                
                # Resumen
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Transacciones Divididas", len(split_trans))
                with col2:
                    total_original = sum(t.get('importe_original', 0) for t in split_trans)
                    st.metric("Importe Total Original", f"{total_original:,.2f} €")
                with col3:
                    total_facturas = sum(t.get('num_facturas', 0) for t in split_trans)
                    st.metric("Total Facturas Generadas", total_facturas)
                
                # Crear DataFrame para mostrar
                df_split = pd.DataFrame(split_trans)
                # Formatear importe para mostrar
                df_split['importe_original'] = df_split['importe_original'].apply(lambda x: f"{x:,.2f} €")
                df_split['limite_aplicado'] = df_split['limite_aplicado'].apply(lambda x: f"{x:,.2f} €")
                
                # Renombrar columnas para mejor visualización
                df_split_display = df_split.rename(columns={
                    'fecha': 'Fecha',
                    'concepto': 'Concepto',
                    'importe_original': 'Importe Original',
                    'num_facturas': 'Nº Facturas',
                    'limite_aplicado': 'Límite Aplicado'
                })
                
                # Mostrar tabla
                st.dataframe(df_split_display[['Fecha', 'Concepto', 'Importe Original', 'Nº Facturas', 'Límite Aplicado']], 
                           use_container_width=True, hide_index=True)
                
                # Botón para descargar CSV
                # Restaurar valores numéricos para el CSV
                df_split_csv = pd.DataFrame(split_trans)
                # Asegurar que la fecha esté presente y en el orden correcto
                if 'fecha' in df_split_csv.columns:
                    # Reordenar columnas para que fecha esté primero
                    column_order = ['fecha', 'concepto', 'importe_original', 'num_facturas', 'limite_aplicado']
                    # Agregar otras columnas que puedan existir
                    for col in df_split_csv.columns:
                        if col not in column_order:
                            column_order.append(col)
                    # Filtrar solo las columnas que existen
                    column_order = [col for col in column_order if col in df_split_csv.columns]
                    df_split_csv_ordered = df_split_csv[column_order]
                else:
                    df_split_csv_ordered = df_split_csv
                csv_split = df_split_csv_ordered.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📥 Descargar Transacciones Divididas (CSV)",
                    data=csv_split,
                    file_name=f"transacciones_divididas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="download_split_transactions"
                )
                
                st.info(f"""
                **💡 Nota:** Estas transacciones fueron divididas porque su importe superó el límite máximo 
                de {max_base:,.2f} € por factura. Cada transacción se dividió en múltiples facturas 
                para cumplir con este límite.
                """)

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
                # Botón para eliminar todo el mes
                col_header1, col_header2 = st.columns([4, 1])
                with col_header1:
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
                
                with col_header2:
                    if st.button("🗑️ Eliminar Mes", key=f"delete_month_{month}", use_container_width=True, type="secondary"):
                        deleted = delete_month_from_history(month)
                        if deleted > 0:
                            st.success(f"✅ Se eliminaron {deleted} registro(s) del mes {month_name}")
                            st.rerun()
                        else:
                            st.error("❌ No se pudo eliminar el mes")
                
                st.markdown("---")
                
                # Detalles de cada procesamiento
                for idx, record in enumerate(records):
                    # Formatear fecha en español
                    try:
                        record_date = datetime.strptime(record['date'], '%Y-%m-%d')
                        date_formatted = record_date.strftime('%d/%m/%Y')
                    except:
                        date_formatted = record['date']
                    
                    # Header del procesamiento con botón de eliminar
                    col_proc1, col_proc2 = st.columns([4, 1])
                    with col_proc1:
                        st.markdown(f"**📄 Procesamiento del {date_formatted}**")
                    with col_proc2:
                        if st.button("🗑️ Eliminar", key=f"delete_{record['id']}", use_container_width=True, type="secondary"):
                            if delete_from_history(record['id']):
                                st.success(f"✅ Procesamiento del {date_formatted} eliminado")
                                st.rerun()
                            else:
                                st.error("❌ No se pudo eliminar el procesamiento")
                    
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
                    
                    # Mostrar transacciones excluidas si existen
                    excluded = record.get('excluded_transactions', [])
                    if excluded:
                        st.markdown("---")
                        with st.expander(f"📋 Transacciones Excluidas ({len(excluded)} transacciones)", expanded=False):
                            # Resumen
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("Total Excluidas", len(excluded))
                            with col2:
                                total_excluido = sum(t.get('importe', 0) for t in excluded)
                                st.metric("Importe Total Excluido", f"{abs(total_excluido):,.2f} €")
                            
                            # Agrupar por razón
                            razones = {}
                            for trans in excluded:
                                razon = trans.get('razon', 'Sin razón especificada')
                                if razon not in razones:
                                    razones[razon] = []
                                razones[razon].append(trans)
                            
                            # Mostrar por categorías
                            for razon, trans_list in razones.items():
                                with st.expander(f"❌ {razon} ({len(trans_list)} transacciones)", expanded=False):
                                    df_excluded = pd.DataFrame(trans_list)
                                    if 'razon' in df_excluded.columns:
                                        df_display = df_excluded[['fecha', 'concepto', 'importe']].copy()
                                    else:
                                        df_display = df_excluded.copy()
                                    st.dataframe(df_display, use_container_width=True, hide_index=True)
                            
                            # Información del procesamiento
                            info = record.get('processing_info', {})
                            if info:
                                st.info(f"""
                                **ℹ️ Información del procesamiento:**
                                - Total de filas en el archivo: {info.get('total_filas', 'N/A')}
                                - Transacciones incluidas: {info.get('transacciones_incluidas', 0)}
                                - Transacciones excluidas: {info.get('transacciones_excluidas', 0)}
                                """)
                    
                    # Mostrar transacciones divididas si existen
                    split_trans = record.get('split_transactions', [])
                    if split_trans:
                        st.markdown("---")
                        with st.expander(f"✂️ Transacciones Divididas ({len(split_trans)} transacciones)", expanded=False):
                            # Resumen
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Transacciones Divididas", len(split_trans))
                            with col2:
                                total_original = sum(t.get('importe_original', 0) for t in split_trans)
                                st.metric("Importe Total Original", f"{total_original:,.2f} €")
                            with col3:
                                total_facturas = sum(t.get('num_facturas', 0) for t in split_trans)
                                st.metric("Total Facturas Generadas", total_facturas)
                            
                            # Crear DataFrame para mostrar
                            df_split = pd.DataFrame(split_trans)
                            # Formatear importe para mostrar
                            df_split['importe_original'] = df_split['importe_original'].apply(lambda x: f"{x:,.2f} €")
                            df_split['limite_aplicado'] = df_split['limite_aplicado'].apply(lambda x: f"{x:,.2f} €")
                            
                            # Renombrar columnas
                            df_split_display = df_split.rename(columns={
                                'fecha': 'Fecha',
                                'concepto': 'Concepto',
                                'importe_original': 'Importe Original',
                                'num_facturas': 'Nº Facturas',
                                'limite_aplicado': 'Límite Aplicado'
                            })
                            
                            st.dataframe(df_split_display[['Fecha', 'Concepto', 'Importe Original', 'Nº Facturas', 'Límite Aplicado']], 
                                       use_container_width=True, hide_index=True)
                            
                            st.info(f"""
                            **💡 Nota:** Estas transacciones fueron divididas porque su importe superó el límite máximo 
                            por factura. Cada transacción se dividió en múltiples facturas para cumplir con este límite.
                            """)
                    
                    if idx < len(records) - 1:
                        st.markdown("---")

