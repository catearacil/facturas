"""
Módulo para leer y procesar extractos bancarios de Santander
"""

import pandas as pd
from typing import List, Dict, Optional
import re


def find_header_row(file_path: str, max_rows: int = 20) -> int:
    """
    Busca la fila que contiene los encabezados de las columnas.
    
    Args:
        file_path: Ruta al archivo Excel
        max_rows: Número máximo de filas a revisar
        
    Returns:
        Número de fila donde están los encabezados (0-indexed), o -1 si no se encuentra
    """
    # Patrones para identificar encabezados
    fecha_keywords = ['fecha', 'operación', 'operacion', 'valor', 'date']
    concepto_keywords = ['concepto', 'descripción', 'descripcion', 'detalle', 'motivo']
    importe_keywords = ['importe', 'cantidad', 'monto', 'valor', 'euros', 'eur']
    
    for row_idx in range(max_rows):
        try:
            # Leer solo esa fila
            df_test = pd.read_excel(file_path, engine='openpyxl', nrows=1, skiprows=row_idx, header=None)
            if df_test.empty:
                continue
            
            # Convertir la fila a lista de strings (lowercase)
            row_values = [str(val).lower().strip() if pd.notna(val) else '' for val in df_test.iloc[0].values]
            
            # Contar coincidencias con patrones
            fecha_count = sum(1 for val in row_values for kw in fecha_keywords if kw in val)
            concepto_count = sum(1 for val in row_values for kw in concepto_keywords if kw in val)
            importe_count = sum(1 for val in row_values for kw in importe_keywords if kw in val)
            
            # Si encontramos al menos 2 de los 3 tipos de columnas, probablemente es el header
            if (fecha_count > 0 and concepto_count > 0) or (fecha_count > 0 and importe_count > 0) or (concepto_count > 0 and importe_count > 0):
                return row_idx
        except:
            continue
    
    return -1


def read_santander_excel(file_path: str) -> pd.DataFrame:
    """
    Lee un archivo Excel de extracto bancario de Santander.
    
    Args:
        file_path: Ruta al archivo Excel
        
    Returns:
        DataFrame con los datos del extracto
    """
    try:
        # Primero intentar encontrar la fila de encabezados
        header_row = find_header_row(file_path)
        
        if header_row >= 0:
            # Leer usando la fila encontrada como header
            df = pd.read_excel(file_path, engine='openpyxl', header=header_row)
            df.columns = df.columns.str.strip()
            return df
        
        # Si no se encuentra, intentar leer normalmente
        df = pd.read_excel(file_path, engine='openpyxl')
        df.columns = df.columns.str.strip()
        
        # Si las columnas son "Unnamed", intentar diferentes estrategias
        if all('unnamed' in str(col).lower() for col in df.columns[:3]) and df.shape[0] > 0:
            # Buscar en las primeras filas
            for skip in range(1, 15):
                try:
                    df_test = pd.read_excel(file_path, engine='openpyxl', skiprows=skip, nrows=1, header=None)
                    if df_test.empty:
                        continue
                    
                    # Verificar si esta fila parece tener encabezados
                    row_values = [str(val).lower().strip() if pd.notna(val) else '' for val in df_test.iloc[0].values]
                    has_fecha = any('fecha' in val or 'operación' in val or 'operacion' in val for val in row_values)
                    has_concepto = any('concepto' in val or 'descripción' in val or 'descripcion' in val for val in row_values)
                    has_importe = any('importe' in val or 'cantidad' in val or 'monto' in val for val in row_values)
                    
                    if (has_fecha and has_concepto) or (has_fecha and has_importe) or (has_concepto and has_importe):
                        # Esta es probablemente la fila de encabezados
                        df = pd.read_excel(file_path, engine='openpyxl', header=skip)
                        df.columns = df.columns.str.strip()
                        return df
                except:
                    continue
        
        return df
    except Exception as e:
        raise ValueError(f"Error al leer el archivo Excel: {str(e)}")


def identify_columns(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    """
    Identifica automáticamente las columnas relevantes del extracto.
    Columnas esperadas de Santander:
    - Fecha Operación
    - Fecha Valor
    - Concepto
    - Importe
    - Divisa
    - Saldo
    - Código
    - Número de docum Referencia 1
    - Referencia 2
    - Información adicional
    
    Args:
        df: DataFrame con los datos
        
    Returns:
        Diccionario con las columnas identificadas
    """
    columns = {
        'fecha_operacion': None,
        'concepto': None,
        'importe': None
    }
    
    # Buscar columnas por nombre exacto o similar (case insensitive)
    df_columns_lower = [col.lower().strip() for col in df.columns]
    
    # Buscar "Fecha Operación" (prioridad) o "Fecha Operacion"
    fecha_patterns = ['fecha operación', 'fecha operacion', 'fechaoperación', 'fechaoperacion']
    for pattern in fecha_patterns:
        if pattern in df_columns_lower:
            idx = df_columns_lower.index(pattern)
            columns['fecha_operacion'] = df.columns[idx]
            break
    
    # Si no se encuentra, buscar solo "fecha" (puede ser "Fecha Valor" pero usamos la primera)
    if columns['fecha_operacion'] is None:
        for i, col_lower in enumerate(df_columns_lower):
            if 'fecha' in col_lower:
                columns['fecha_operacion'] = df.columns[i]
                break
    
    # Buscar "Concepto" (exacto)
    concepto_patterns = ['concepto']
    for pattern in concepto_patterns:
        if pattern in df_columns_lower:
            idx = df_columns_lower.index(pattern)
            columns['concepto'] = df.columns[idx]
            break
    
    # Si no se encuentra, buscar alternativas
    if columns['concepto'] is None:
        concepto_alt_patterns = ['descripción', 'descripcion', 'detalle', 'descrip']
        for pattern in concepto_alt_patterns:
            if pattern in df_columns_lower:
                idx = df_columns_lower.index(pattern)
                columns['concepto'] = df.columns[idx]
                break
    
    # Buscar "Importe" (exacto, es la columna clave)
    importe_patterns = ['importe']
    for pattern in importe_patterns:
        if pattern in df_columns_lower:
            idx = df_columns_lower.index(pattern)
            columns['importe'] = df.columns[idx]
            break
    
    # Si no se encuentra, buscar alternativas
    if columns['importe'] is None:
        importe_alt_patterns = ['cantidad', 'monto', 'valor', 'amount']
        for pattern in importe_alt_patterns:
            if pattern in df_columns_lower:
                idx = df_columns_lower.index(pattern)
                columns['importe'] = df.columns[idx]
                break
    
    # Si no se encontraron por nombre y las columnas son "Unnamed", 
    # intentar inferir por el contenido de los datos
    if not all(columns.values()) and df.shape[0] > 0:
        # Analizar las primeras filas para inferir tipos
        sample_size = min(10, df.shape[0])
        df_sample = df.head(sample_size)
        
        # Buscar columna de fecha (debe tener fechas o fechas parseables)
        if not columns['fecha_operacion']:
            for col in df.columns:
                if columns['fecha_operacion']:
                    break
                # Verificar si la columna contiene fechas
                date_count = 0
                for val in df_sample[col].dropna():
                    val_str = str(val).lower()
                    # Patrones de fecha
                    if (re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', val_str) or
                        re.search(r'\d{4}[/-]\d{1,2}[/-]\d{1,2}', val_str) or
                        pd.api.types.is_datetime64_any_dtype(df[col])):
                        date_count += 1
                if date_count >= sample_size * 0.5:  # Al menos 50% son fechas
                    columns['fecha_operacion'] = col
                    break
        
        # Buscar columna de importe (debe tener números)
        if not columns['importe']:
            for col in df.columns:
                if columns['importe']:
                    break
                # Verificar si la columna contiene números
                numeric_count = 0
                for val in df_sample[col].dropna():
                    try:
                        amount = clean_amount(val)
                        if amount != 0:  # Solo contar si es un número válido
                            numeric_count += 1
                    except:
                        pass
                if numeric_count >= sample_size * 0.5:  # Al menos 50% son numéricos
                    columns['importe'] = col
                    break
        
        # Buscar columna de concepto (texto largo, no numérico)
        if not columns['concepto']:
            for col in df.columns:
                if col in [columns['fecha_operacion'], columns['importe']]:
                    continue
                if columns['concepto']:
                    break
                # Verificar si la columna contiene texto
                text_count = 0
                for val in df_sample[col].dropna():
                    val_str = str(val)
                    # Si es texto largo (más de 5 caracteres) y no es principalmente numérico
                    if len(val_str) > 5 and not re.match(r'^[\d\s,.\-]+$', val_str):
                        text_count += 1
                if text_count >= sample_size * 0.3:  # Al menos 30% son texto
                    columns['concepto'] = col
                    break
    
    return columns


def clean_amount(amount: any) -> float:
    """
    Limpia y convierte un importe a float.
    
    Args:
        amount: Valor del importe (puede ser string con formato europeo)
        
    Returns:
        Importe como float
    """
    if pd.isna(amount):
        return 0.0
    
    # Si ya es numérico
    if isinstance(amount, (int, float)):
        return float(amount)
    
    # Si es string, limpiar
    if isinstance(amount, str):
        # Remover espacios y caracteres especiales excepto punto, coma y signo menos
        cleaned = re.sub(r'[^\d,.\-]', '', amount)
        # Reemplazar coma por punto para conversión
        cleaned = cleaned.replace(',', '.')
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
    
    return 0.0


def filter_income_transactions(df: pd.DataFrame, columns: Dict[str, Optional[str]]) -> tuple:
    """
    Filtra solo las transacciones de ingreso (valores positivos).
    
    Args:
        df: DataFrame con los datos
        columns: Diccionario con las columnas identificadas
        
    Returns:
        Tupla: (transacciones_incluidas, transacciones_excluidas)
        donde transacciones_excluidas es una lista de dicts con 'fecha', 'concepto', 'importe', 'razon'
    """
    if not all(columns.values()):
        missing = [k for k, v in columns.items() if v is None]
        found = {k: v for k, v in columns.items() if v is not None}
        
        # Crear mensaje de error más informativo
        error_msg = f"Columnas no encontradas: {', '.join(missing)}\n\n"
        error_msg += f"Columnas encontradas en el archivo:\n"
        for col in df.columns:
            error_msg += f"  - {col}\n"
        if found:
            error_msg += f"\nColumnas identificadas:\n"
            for key, value in found.items():
                error_msg += f"  - {key}: {value}\n"
        error_msg += f"\nSugerencia: Verifica que el archivo Excel tenga las columnas correctas."
        
        raise ValueError(error_msg)
    
    transactions = []
    excluded = []
    
    for idx, row in df.iterrows():
        try:
            # Obtener importe
            importe = clean_amount(row[columns['importe']])
            
            # Obtener fecha
            fecha = row[columns['fecha_operacion']]
            if pd.isna(fecha):
                fecha = None
            else:
                # Convertir a string si es fecha
                if hasattr(fecha, 'strftime'):
                    fecha = fecha.strftime('%d/%m/%Y')
                else:
                    fecha = str(fecha)
            
            # Obtener concepto
            concepto = str(row[columns['concepto']]) if not pd.isna(row[columns['concepto']]) else "Sin concepto"
            
            # Solo procesar ingresos (valores positivos)
            if importe > 0:
                transactions.append({
                    'fecha': fecha,
                    'concepto': concepto,
                    'importe': importe  # Este es la base imponible (sin IVA)
                })
            else:
                # Registrar transacción excluida
                razon = "Gasto o importe cero" if importe < 0 else "Importe cero"
                excluded.append({
                    'fecha': fecha,
                    'concepto': concepto,
                    'importe': importe,
                    'razon': razon
                })
        except Exception as e:
            # Registrar transacción con error
            try:
                concepto = str(row[columns['concepto']]) if columns['concepto'] and not pd.isna(row[columns['concepto']]) else "Sin concepto"
                fecha = None
                try:
                    fecha_val = row[columns['fecha_operacion']]
                    if not pd.isna(fecha_val):
                        if hasattr(fecha_val, 'strftime'):
                            fecha = fecha_val.strftime('%d/%m/%Y')
                        else:
                            fecha = str(fecha_val)
                except:
                    pass
            except:
                concepto = "Error al leer concepto"
                fecha = None
            
            excluded.append({
                'fecha': fecha,
                'concepto': concepto,
                'importe': 0.0,
                'razon': f"Error al procesar: {str(e)}"
            })
    
    return transactions, excluded


def process_santander_file(file_path: str) -> tuple:
    """
    Procesa un archivo Excel de Santander y retorna las transacciones de ingreso y excluidas.
    
    Args:
        file_path: Ruta al archivo Excel
        
    Returns:
        Tupla: (transacciones_incluidas, transacciones_excluidas, info_procesamiento)
        donde info_procesamiento es un dict con información del procesamiento
    """
    # Leer el Excel
    df = read_santander_excel(file_path)
    
    # Identificar columnas
    columns = identify_columns(df)
    
    # Filtrar transacciones de ingreso
    transactions, excluded = filter_income_transactions(df, columns)
    
    info = {
        'total_filas': len(df),
        'transacciones_incluidas': len(transactions),
        'transacciones_excluidas': len(excluded),
        'columnas_identificadas': columns
    }
    
    return transactions, excluded, info

