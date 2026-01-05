# Guía de Deploy - Streamlit Cloud

## Opción 1: Streamlit Cloud (Recomendado - Gratis)

### Pasos:

1. **Asegúrate de que tu repositorio esté en GitHub**
   - Si aún no lo has subido, haz commit y push:
   ```bash
   git add .
   git commit -m "Preparado para deploy"
   git push origin main
   ```

2. **Ve a [share.streamlit.io](https://share.streamlit.io)**
   - Inicia sesión con tu cuenta de GitHub

3. **Conecta tu repositorio**
   - Haz clic en "New app"
   - Selecciona tu repositorio de GitHub
   - Selecciona la rama (main/master)
   - **Main file path**: `app.py`
   - Haz clic en "Deploy!"

4. **Espera a que se despliegue**
   - Streamlit Cloud instalará las dependencias automáticamente
   - Tu app estará disponible en: `https://tu-app-name.streamlit.app`

### Notas importantes:
- ✅ El archivo `requirements.txt` ya está configurado
- ✅ La configuración de Streamlit está en `.streamlit/config.toml`
- ✅ El logo en `assets/logo.png` se incluirá automáticamente
- ⚠️ Los archivos en `output/` no se persisten entre sesiones (se regeneran)

---

## Opción 2: Railway (Alternativa)

1. Ve a [railway.app](https://railway.app)
2. Inicia sesión con GitHub
3. Crea un nuevo proyecto desde GitHub
4. Añade las variables de entorno si es necesario
5. Railway detectará automáticamente que es una app Python

### Railway necesita un archivo adicional:

Crea `Procfile`:
```
web: streamlit run app.py --server.port $PORT --server.address 0.0.0.0
```

---

## Opción 3: Render (Alternativa)

1. Ve a [render.com](https://render.com)
2. Crea una nueva "Web Service"
3. Conecta tu repositorio de GitHub
4. Configuración:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`

---

## Verificación Pre-Deploy

Antes de hacer deploy, verifica:

- [x] `requirements.txt` incluye todas las dependencias
- [x] `app.py` es el archivo principal
- [x] Los archivos necesarios están en el repositorio (logo, etc.)
- [x] No hay rutas absolutas en el código
- [x] `.gitignore` está configurado correctamente

## Solución de Problemas

### Si el deploy falla:
1. Revisa los logs en Streamlit Cloud
2. Verifica que todas las dependencias estén en `requirements.txt`
3. Asegúrate de que `app.py` esté en la raíz del repositorio

### Si hay errores de importación:
- Verifica que todos los módulos en `src/` estén incluidos
- Asegúrate de que `__init__.py` exista en `src/`

