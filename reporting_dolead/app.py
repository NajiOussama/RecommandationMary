import pandas as pd
import ast
import streamlit as st
import altair as alt

# Charger les données
@st.cache_data
def load_data(file_path):
    df = pd.read_csv(file_path)
    df['discussiondate'] = pd.to_datetime(df['discussiondate'], format='%Y%m%d')
    df['call_duration'] = (pd.to_datetime(df['endtimestamp']) - pd.to_datetime(df['starttimestamp'])).dt.total_seconds()
    df['variables_dict'] = df['variables'].apply(lambda x: ast.literal_eval(x) if pd.notna(x) else {})
    df['note'] = df['variables_dict'].apply(lambda d: d.get('NOTE', None))
    df['transfer_status'] = df['variables_dict'].apply(lambda d: d.get('transfer', None))
    df['redirected_to'] = df['variables_dict'].apply(lambda d: d.get('RedirectedTo', None))
    df['zip_code_status'] = df['variables_dict'].apply(lambda d: d.get('check_zip_code', None))
    df['call_held'] = df['call_duration'] > 20
    df['is_transferred'] = df['transfer_status'] == 'done'
    return df

# Fonction pour filtrer les données
def filter_data(df):
    return df[(df['agent'] == 'dolead_att') & (df['variables'].apply(lambda d: 'amd' not in d))]

# Fonction pour générer le reporting
def generate_reporting(df, freq):
    aggregated = df.resample(freq, on='discussiondate').agg({
        'discussionid': 'count',
        'call_duration': 'sum',
        'call_held': 'mean',
        'is_transferred': 'mean',
        'callfrom': lambda x: x.nunique(),
        'note': 'mean'
    }).rename(columns={
        'discussionid': 'total_calls',
        'call_duration': 'total_call_duration',
        'call_held': 'percent_held_calls',
        'is_transferred': 'percent_transferred_calls',
        'callfrom': 'unique_transferred_numbers',
        'note': 'average_note'
    })
    aggregated['percent_held_calls'] *= 100
    aggregated['percent_transferred_calls'] *= 100
    return aggregated

# Streamlit App
st.title("Reporting des appels - Agent dolead_att")
file_path = st.file_uploader("Uploader le fichier CSV :", type=["csv"])

if file_path:
    # Charger et filtrer les données
    df = load_data(file_path)
    df = filter_data(df)

    if df.empty:
        st.warning("Aucune donnée disponible après application des filtres.")
    else:
        # Sélection de la période
        st.sidebar.header("Options de reporting")
        period = st.sidebar.selectbox("Période de reporting :", ['daily', 'weekly', 'monthly'])
        freq_map = {'daily': 'D', 'weekly': 'W', 'monthly': 'M'}

        # Générer le reporting
        reporting_df = generate_reporting(df, freq_map[period])

        # Afficher le tableau
        st.header(f"Rapport {period.capitalize()}")
        st.dataframe(reporting_df)

        # Sélection de métriques pour visualisation
        st.sidebar.header("Options de visualisation")
        metric = st.sidebar.selectbox("Métrique à visualiser :", reporting_df.columns)

        # Créer un graphique interactif
        chart = alt.Chart(reporting_df.reset_index()).mark_line(point=True).encode(
            x='discussiondate:T',
            y=metric,
            tooltip=['discussiondate', metric]
        ).properties(title=f"Évolution de {metric}")
        st.altair_chart(chart, use_container_width=True)

        # Télécharger les données
        st.sidebar.header("Téléchargement")
        csv = reporting_df.to_csv(index=True)
        st.sidebar.download_button(label="Télécharger le rapport CSV", data=csv, file_name=f'report_{period}.csv')
