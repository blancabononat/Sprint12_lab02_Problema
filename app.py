import os
import pandas as pd
import plotly.express as px
import streamlit as st
from google import genai

# -----------------------------------------------------------------------------
# 1. Configuración de la Aplicación
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="IMDb Top 1000 Analytics",
    page_icon="🎬",
    layout="wide"
)

# -----------------------------------------------------------------------------
# 2. Carga, Limpieza y Mapeo Robustos (Fail-Safe Data Engineering)
# -----------------------------------------------------------------------------
@st.cache_data
def load_and_clean_data(file_path="imdb_top_1000.csv"):
    """
    Carga y limpia el dataset con estrategias defensivas ante nombres de columnas
    variables, espacios invisibles y tipos de datos erróneos.
    """
    
    if not os.path.exists(file_path):
        st.error(f"❌ Error Crítico: No se encuentra el archivo '{file_path}' en la raíz del repositorio.")
        return pd.DataFrame()

    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        st.error(f"❌ Error de lectura en el archivo CSV: {str(e)}")
        return pd.DataFrame()

    # 1. Limpieza inmediata de nombres de columnas (eliminar espacios en blanco invisibles)
    df.columns = df.columns.str.strip()

    # 2. Normalización de nombres de columnas (mapeo flexible para evitar KeyErrors)
    col_mapping = {}
    for col in df.columns:
        c_clean = col.lower().replace(" ", "_")
        if c_clean in ['movie_name', 'series_title', 'title']:
            col_mapping[col] = 'Movie Name'
        elif c_clean in ['year_of_release', 'released_year', 'year']:
            col_mapping[col] = 'Year of Release'
        elif c_clean in ['movie_rating', 'imdb_rating', 'rating']:
            col_mapping[col] = 'Movie Rating'
        elif c_clean in ['metascore_of_movie', 'meta_score', 'metascore']:
            col_mapping[col] = 'Metascore of movie'
        elif c_clean in ['gross', 'box_office']:
            col_mapping[col] = 'Gross'
        elif c_clean in ['director']:
            col_mapping[col] = 'Director'

    df.rename(columns=col_mapping, inplace=True)

    # Validar presencia de columnas críticas mínimas
    required_cols = ['Movie Name', 'Year of Release', 'Movie Rating', 'Gross']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        st.error(f"❌ El dataset no contiene las columnas necesarias: {missing}")
        return pd.DataFrame()

    # 3. Limpieza de columna Gross (Texto con comas/símbolos -> Float -> fillna 0)
    #if df['Gross'].dtype == object:
    #    df['Gross'] = df['Gross'].astype(str).str.replace(',', '').str.replace('$', '').str.strip()
    #    df['Gross'] = pd.to_numeric(df['Gross'], errors='coerce')
    #    df['Gross'] = df['Gross'].fillna(0)
    #-----------------------------------------------------------PRUEBA ERROR
    df["Gross"] = (
        df["Gross"]
        .astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.strip()
    )

    df["Gross"] = pd.to_numeric(df["Gross"], errors="coerce")
    df["Gross"] = df["Gross"].fillna(0).astype(float)

    #st.write("Después de to_numeric")
    #st.write(df["Gross"].dtype)
    #-----------------------------------------------------------FIN PRUEBA ERROR
    

    # 4. Limpieza de columna Year of Release (errors='coerce', drop NaNs -> Int)
    df['Year of Release'] = pd.to_numeric(df['Year of Release'], errors='coerce')
    df.dropna(subset=['Year of Release'], inplace=True)
    df['Year of Release'] = df['Year of Release'].astype(int)

    # 5. Limpieza de Ratings
    df['Movie Rating'] = pd.to_numeric(df['Movie Rating'], errors='coerce').fillna(0)
    
    if 'Metascore of movie' in df.columns:
        df['Metascore of movie'] = pd.to_numeric(df['Metascore of movie'], errors='coerce')
#-----------------------------------------------------------PRUEBA ERROR
    #st.write(df["Gross"].iloc[:5].tolist())
    #st.write([type(x) for x in df["Gross"].iloc[:5]])
#-----------------------------------------------------------FIN PRUEBA ERROR
    return df


# Carga de datos
df_raw = load_and_clean_data()
#-----------------------------------------PRUEBA ERROR
#st.write(df_raw.dtypes)
#st.write(df_raw["Gross"].dtype)
#st.write(df_raw["Gross"].head())
#-----------------------------------------FIN PRUEBA ERROR

# Validación estricta: Si el DataFrame está vacío tras la limpieza, frena la app
if df_raw.empty:
    st.error("⚠️ El DataFrame está vacío o no pudo ser procesado correctamente.")
    st.stop()

# -----------------------------------------------------------------------------
# 3. Interfaz y Filtros (Sidebar & UX)
# -----------------------------------------------------------------------------
st.sidebar.title("🎬 Filtros & Configuración")

# Input para Gemini API Key
api_key = st.sidebar.text_input(
    "🔑 Google GenAI API Key", 
    type="password", 
    help="Introduce tu API key para habilitar el análisis conversacional"
)

st.sidebar.markdown("---")

# Filtro de Año con opción 'Todos'
years_available = ['Todos'] + sorted(df_raw['Year of Release'].unique().tolist(), reverse=True)
selected_year = st.sidebar.selectbox("Filtrar por Año de Estreno", years_available, index=0)

# Aplicar filtrado por Año
if selected_year == 'Todos':
    df_filtered = df_raw.copy()
else:
    df_filtered = df_raw[df_raw['Year of Release'] == selected_year]

# Verificación post-filtro
if df_filtered.empty:
    st.warning("⚠️ No se encontraron películas que coincidan con los criterios seleccionados.")
    st.stop()

# -----------------------------------------------------------------------------
# 4. Título Dinámico y KPIs
# -----------------------------------------------------------------------------
if selected_year != 'Todos':
    st.title(f"🎬 Análisis de Películas: Año {selected_year}")
else:
    st.title("🎬 Análisis Global de Películas (Top IMDb)")

kpi1, kpi2, kpi3, kpi4 = st.columns(4)

# 1. Recaudación Total (Gross)
recaudacion_total = df_filtered['Gross'].sum()
kpi1.metric("Recaudación Total", f"${recaudacion_total:,.0f}")

# 2. Rating Promedio (Movie Rating)
rating_promedio = df_filtered['Movie Rating'].mean()
kpi2.metric("Rating Promedio", f"{rating_promedio:.2f} / 10")

# 3. Meta Score Promedio (Metascore of movie)
if 'Metascore of movie' in df_filtered.columns and not df_filtered['Metascore of movie'].dropna().empty:
    metascore_prom = df_filtered['Metascore of movie'].mean()
    kpi3.metric("Meta Score Promedio", f"{metascore_prom:.1f} / 100")
else:
    kpi3.metric("Meta Score Promedio", "N/A")

# 4. Película Top por Recaudación
top_movie_idx = df_filtered['Gross'].idxmax()
top_movie_row = df_filtered.loc[top_movie_idx]
kpi4.metric(
    "Película Taquillera Top", 
    f"{top_movie_row['Movie Name']}", 
    f"${top_movie_row['Gross']:,.0f}"
)

st.markdown("---")

# -----------------------------------------------------------------------------
# 5. Visualizaciones (Plotly Express)
# -----------------------------------------------------------------------------
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.subheader("🏆 Top 10 Películas por Recaudación (Gross)")
    top10_gross = df_filtered.nlargest(10, 'Gross').sort_values('Gross', ascending=True)
    
    fig_bar = px.bar(
        top10_gross,
        x='Gross',
        y='Movie Name',
        orientation='h',
        labels={'Gross': 'Recaudación ($)', 'Movie Name': 'Película'},
        color='Gross',
        color_continuous_scale='Viridis'
    )
    fig_bar.update_layout(showlegend=False, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig_bar, use_container_width=True)

with chart_col2:
    st.subheader("⭐ Rating vs Recaudación (Gross)")
    fig_scatter = px.scatter(
        df_filtered,
        x='Movie Rating',
        y='Gross',
        hover_name='Movie Name',
        color='Year of Release' if selected_year == 'Todos' else None,
        size='Gross' if df_filtered['Gross'].max() > 0 else None,
        labels={'Movie Rating': 'Rating IMDb', 'Gross': 'Recaudación ($)'},
    )
    fig_scatter.update_layout(margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig_scatter, use_container_width=True)

st.markdown("---")

# -----------------------------------------------------------------------------
# 6. Integración de IA (Google GenAI - SDK Moderno & Smart Context)
# -----------------------------------------------------------------------------
st.header("🤖 Insights Inteligentes con Gemini AI")

if not api_key:
    st.info("💡 Proporciona tu Google GenAI API Key en la barra lateral para generar un análisis automatizado.")
else:
    # Selección estricta de columnas para el contexto
    smart_cols = ['Movie Name', 'Year of Release', 'Movie Rating', 'Gross']
    df_ai_subset = df_filtered[smart_cols]

    # Regla de Límite (Smart Context): Si > 60 filas, enviar Muestra Representativa
    if len(df_ai_subset) > 60:
        top_gross_30 = df_ai_subset.nlargest(30, 'Gross')
        top_rating_30 = df_ai_subset.nlargest(30, 'Movie Rating')
        df_context = pd.concat([top_gross_30, top_rating_30]).drop_duplicates()
        limit_note = f"(Muestra representativa de {len(df_context)} películas clave por recaudación y rating)"
    else:
        df_context = df_ai_subset
        limit_note = f"(Contexto completo con {len(df_context)} películas)"

    csv_data = df_context.to_csv(index=False)

    col_btn, _ = st.columns([1, 2])
    with col_btn:
        generate_ai = st.button("✨ Generar Diagnóstico de Cine", type="primary")

    if generate_ai:
        prompt = f"""
        Actúa como un Analista Senior de la Industria Cinematográfica.
        Analiza la siguiente selección de datos de películas {limit_note}:

        ```csv
        {csv_data}
        ```

        Proporciona un reporte ejecutivo estructurado en:
        1. **Patrones de Taquilla y Recepción**: Relación entre el rating y los ingresos.
        2. **Análisis de Desempeño**: Observaciones sobre las películas más exitosas frente al promedio.
        3. **3 Insights Estratégicos**: Lecciones clave para la producción y comercialización de cine.
        """

        try:
            client = genai.Client(api_key=api_key)

            with st.status("Analizando...", expanded=True) as status:
                st.write("🧠 Conectando con el modelo Gemini 2.5 Flash...")

                def response_generator():
                    response_stream = client.models.generate_content_stream(
                        model='gemini-3.6-flash',
                        contents=prompt
                    )
                    for chunk in response_stream:
                        yield chunk.text

                # Streaming en tiempo real con efecto máquina de escribir
                st.write_stream(response_generator)
                status.update(label="✅ Análisis finalizado", state="complete", expanded=False)

        except Exception as e:
            st.error(f"❌ Ocurrió un error al comunicarse con la API de Gemini: {str(e)}")
