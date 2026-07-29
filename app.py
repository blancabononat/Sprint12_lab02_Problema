import streamlit as st
import pandas as pd
import plotly.express as px
import os
from google import genai

# -----------------------------------------------------------------------------
# 1. Configuración de la Página
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="IMDb Top 1000 Movies Analytics",
    page_icon="🎬",
    layout="wide"
)

# -----------------------------------------------------------------------------
# 2. Gestión, Carga y Limpieza de Datos (Fail-Safe)
# -----------------------------------------------------------------------------
@st.cache_data
def load_and_clean_data(file_path="imdb_top_1000.csv"):
    """
    Carga y limpia el dataset de IMDb Top 1000 de manera robusta a prueba de fallos.
    """
    if not os.path.exists(file_path):
        st.error(f"❌ Error crítico: El archivo de datos '{file_path}' no se encuentra en el directorio raíz.")
        return pd.DataFrame()

    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        st.error(f"❌ Error al intentar leer el CSV: {str(e)}")
        return pd.DataFrame()

    # Limpieza básica obligatoria de nombres de columnas
    df.columns = df.columns.str.strip()

    # Mapeo flexible de columnas por si varían minúsculas/mayúsculas o nombres
    col_mapping = {}
    for col in df.columns:
        c_lower = col.lower().replace(" ", "_")
        if c_lower in ['series_title', 'title', 'movie_title']:
            col_mapping[col] = 'Series_Title'
        elif c_lower in ['released_year', 'year']:
            col_mapping[col] = 'Released_Year'
        elif c_lower in ['imdb_rating', 'rating']:
            col_mapping[col] = 'IMDB_Rating'
        elif c_lower in ['meta_score', 'metascore']:
            col_mapping[col] = 'Meta_score'
        elif c_lower in ['gross', 'box_office']:
            col_mapping[col] = 'Gross'
        elif c_lower in ['genre', 'genres']:
            col_mapping[col] = 'Genre'
        elif c_lower in ['director']:
            col_mapping[col] = 'Director'

    df.rename(columns=col_mapping, inplace=True)

    # Validar presencia de columnas clave necesarias
    required_cols = ['Series_Title', 'Released_Year', 'IMDB_Rating', 'Gross', 'Genre', 'Director']
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        st.error(f"❌ Columnas clave no encontradas en el dataset: {missing_cols}")
        return pd.DataFrame()

    # Limpieza columna Gross (eliminar comas, convertir a float y NaNs a 0)
    if df['Gross'].dtype == object:
        df['Gross'] = df['Gross'].astype(str).str.replace(',', '').str.replace('$', '').str.strip()
        df['Gross'] = pd.to_numeric(df['Gross'], errors='coerce').fillna(0)
    else:
        df['Gross'] = pd.to_numeric(df['Gross'], errors='coerce').fillna(0)

    # Limpieza columna Released_Year (convertir a numérico, coercionar errores y pasar a int)
    df['Released_Year'] = pd.to_numeric(df['Released_Year'], errors='coerce')
    df.dropna(subset=['Released_Year'], inplace=True)
    df['Released_Year'] = df['Released_Year'].astype(int)

    # Limpieza Meta_score si existe
    if 'Meta_score' in df.columns:
        df['Meta_score'] = pd.to_numeric(df['Meta_score'], errors='coerce')

    # Limpieza IMDB_Rating
    df['IMDB_Rating'] = pd.to_numeric(df['IMDB_Rating'], errors='coerce').fillna(0)

    # Limpieza de textos básicos
    df['Director'] = df['Director'].fillna('Desconocido').astype(str).str.strip()
    df['Genre'] = df['Genre'].fillna('Desconocido').astype(str).str.strip()
    df['Series_Title'] = df['Series_Title'].fillna('Sin Título').astype(str).str.strip()

    return df

# Carga de datos con validación estricta
df_raw = load_and_clean_data()

if df_raw.empty:
    st.error("⚠️ El proceso de carga y limpieza devolvió un DataFrame vacío o inválido. Por favor revisa el archivo 'imdb_top_1000.csv'.")
    st.stop()

# -----------------------------------------------------------------------------
# 3. Interfaz de Usuario y Filtros (Sidebar Cascading Filter)
# -----------------------------------------------------------------------------
st.sidebar.title("🎬 Filtros & Configuración")

# Input para API Key de Gemini
api_key = st.sidebar.text_input("🔑 Gemini API Key", type="password", help="Introduce tu Google GenAI API Key para habilitar la IA")

st.sidebar.markdown("---")

# Filtro 1: Director ('Todos' por defecto)
directores = ['Todos'] + sorted(list(df_raw['Director'].unique()))
selected_director = st.sidebar.selectbox("Filtrar por Director", directores, index=0)

# Filtrado dinámico previo para Género en Cascada
if selected_director == 'Todos':
    df_step1 = df_raw.copy()
else:
    df_step1 = df_raw[df_raw['Director'] == selected_director]

# Obtener lista de géneros únicos disponibles en la selección actual del director
generos_set = set()
for g_str in df_step1['Genre'].dropna():
    parts = [g.strip() for g in g_str.split(',')]
    generos_set.update(parts)
generos_disponibles = sorted(list(generos_set))

# Filtro 2: Género (Multiselect)
selected_genres = st.sidebar.multiselect("Filtrar por Género(s)", generos_disponibles)

# Aplicar filtro de Género con búsqueda flexible de texto
if selected_genres:
    pattern = '|'.join([rf'\b{g}\b' for g in selected_genres])
    df_filtered = df_step1[df_step1['Genre'].str.contains(pattern, case=False, regex=True, na=False)]
else:
    df_filtered = df_step1.copy()

# Validar que el subset filtrado no esté vacío
if df_filtered.empty:
    st.warning("⚠️ No se encontraron películas que coincidan con los filtros seleccionados.")
    st.stop()

# -----------------------------------------------------------------------------
# 4. Título Dinámico y KPIs
# -----------------------------------------------------------------------------
if selected_director != 'Todos':
    title_text = f"🎬 Análisis de Películas: Director {selected_director}"
else:
    title_text = "🎬 Análisis Global del Top 1000 de IMDb"

if selected_genres:
    title_text += f" | Género(s): {', '.join(selected_genres)}"

st.title(title_text)

col1, col2, col3, col4 = st.columns(4)

# 1. Recaudación Total
recaudacion_total = df_filtered['Gross'].sum()
col1.metric("Recaudación Total", f"${recaudacion_total:,.0f}")

# 2. Rating Promedio IMDb
rating_promedio = df_filtered['IMDB_Rating'].mean()
col2.metric("Rating IMDb Promedio", f"{rating_promedio:.2f} / 10")

# 3. Meta Score Promedio
if 'Meta_score' in df_filtered.columns and not df_filtered['Meta_score'].dropna().empty:
    meta_promedio = df_filtered['Meta_score'].mean()
    col3.metric("Meta Score Promedio", f"{meta_promedio:.1f} / 100")
else:
    col3.metric("Meta Score Promedio", "N/A")

# 4. Película Top por Recaudación
top_movie_row = df_filtered.loc[df_filtered['Gross'].idxmax()]
top_movie_name = top_movie_row['Series_Title']
top_movie_gross = top_movie_row['Gross']
col4.metric("Película Top Recaudación", f"{top_movie_name}", f"${top_movie_gross:,.0f}")

st.markdown("---")

# -----------------------------------------------------------------------------
# 5. Visualizaciones (Plotly Express)
# -----------------------------------------------------------------------------
g_col1, g_col2 = st.columns(2)

with g_col1:
    st.subheader("🏆 Top 10 Películas por Recaudación (Gross)")
    top10_gross = df_filtered.nlargest(10, 'Gross').sort_values('Gross', ascending=True)
    fig_bar = px.bar(
        top10_gross,
        x='Gross',
        y='Series_Title',
        orientation='h',
        labels={'Gross': 'Recaudación ($)', 'Series_Title': 'Película'},
        title="Top Recaudación",
        color='Gross',
        color_continuous_scale='Viridis'
    )
    fig_bar.update_layout(showlegend=False, margin=dict(l=20, r=20, t=40, b=20))
    st.plotly_chart(fig_bar, use_container_width=True)

with g_col2:
    st.subheader("⭐ IMDb Rating vs Recaudación (Gross)")
    fig_scatter = px.scatter(
        df_filtered,
        x='IMDB_Rating',
        y='Gross',
        hover_name='Series_Title',
        color='Director' if selected_director == 'Todos' else 'Released_Year',
        size='Gross' if df_filtered['Gross'].max() > 0 else None,
        labels={'IMDB_Rating': 'Rating IMDb', 'Gross': 'Recaudación ($)'},
        title="Relación Rating vs Taquilla"
    )
    fig_scatter.update_layout(margin=dict(l=20, r=20, t=40, b=20))
    st.plotly_chart(fig_scatter, use_container_width=True)

st.markdown("---")

# -----------------------------------------------------------------------------
# 6. Integración de IA Avanzada (Google GenAI - Smart Context & Streaming)
# -----------------------------------------------------------------------------
st.header("🤖 Análisis Inteligente con Gemini AI")

if not api_key:
    st.info("💡 Ingresa tu Google GenAI API Key en la barra lateral para desbloquear el análisis inteligente de películas.")
else:
    # Preparación de Smart Context (Optimización del Prompt)
    cols_ai = ['Series_Title', 'Released_Year', 'IMDB_Rating', 'Gross', 'Director']
    df_ai_subset = df_filtered[cols_ai]

    # Regla de Límite (> 60 filas -> muestra representativa Top 30 Gross + Top 30 Rating)
    if len(df_ai_subset) > 60:
        top_gross_30 = df_ai_subset.nlargest(30, 'Gross')
        top_rating_30 = df_ai_subset.nlargest(30, 'IMDB_Rating')
        df_context = pd.concat([top_gross_30, top_rating_30]).drop_duplicates()
        limit_info_note = f"(Muestra optimizada de {len(df_context)} películas representativas: Top por Taquilla y Rating)"
    else:
        df_context = df_ai_subset
        limit_info_note = f"(Contexto completo con {len(df_context)} películas)"

    csv_context = df_context.to_csv(index=False)

    col_btn, col_blank = st.columns([1, 2])
    with col_btn:
        generate_analysis = st.button("✨ Generar Diagnóstico IA", type="primary")

    if generate_analysis:
        prompt = f"""
        Actúa como un Experto Senior en Cine y Analista de Industria Cinematográfica.
        Analiza el conjunto de datos de películas filtradas {limit_info_note}:

        ```csv
        {csv_context}
        ```

        Por favor provee un informe ejecutivo detallado estructurado en:
        1. **Resumen y Tendencias Clave**: Patrones entre recaudación, ratings y directores.
        2. **Relación Calidad vs Taquilla**: Análisis de si las mejor valoradas son las que más recaudan.
        3. **3 Recomendaciones Estratégicas / Insights de Negocio**: Lecciones de producción para la industria.
        """

        try:
            client = genai.Client(api_key=api_key)

            with st.status("Analizando...", expanded=True) as status:
                st.write("🧠 Conectando con Gemini 2.5 Flash y analizando el contexto de películas...")

                def stream_response():
                    response = client.models.generate_content_stream(
                        model='gemini-2.5-flash',
                        contents=prompt
                    )
                    for chunk in response:
                        yield chunk.text

                st.write_stream(stream_response)
                status.update(label="✅ Análisis completado con éxito", state="complete", expanded=False)

        except Exception as e:
            st.error(f"❌ Ocurrió un error al comunicarse con la API de Gemini: {str(e)}")