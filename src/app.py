import os
import sys
import time

import pandas as pd
import plotly.express as px
import streamlit as st

# Add project root to sys.path to allow imports from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.export_analytics import process_and_export_games

# Page config
st.set_page_config(page_title="Chess Tilt Detector", layout="wide")

st.title("♟️ Chess Tilt Detector - Analytics Dashboard")

# --- Sidebar Configuration ---
st.sidebar.header("🔧 Configuration de l'analyse")

# Date Selector
years = [2023, 2024, 2025]
months = [f"{i:02d}" for i in range(1, 13)]
selected_year = st.sidebar.selectbox("Année", years, index=2)
selected_month = st.sidebar.selectbox("Mois", months, index=10)  # Default Nov

# Format Selector
time_control_mode = st.sidebar.selectbox(
    "Cadence", ["Blitz", "Rapid", "Bullet", "Classical"]
)

# Max Games Slider
max_games = st.sidebar.slider(
    "Nombre de parties à analyser", 100, 10000, 1000, step=100
)

# Run Button
if st.sidebar.button("🚀 Lancer une nouvelle analyse"):
    # Construct URL
    url = f"https://database.lichess.org/standard/lichess_db_standard_rated_{selected_year}-{selected_month}.pgn.zst"

    # Progress Bar
    progress_bar = st.sidebar.progress(0)
    status_text = st.sidebar.empty()

    def update_progress(progress, message):
        progress_bar.progress(progress)
        status_text.text(message)

    with st.spinner("Analyse en cours... Cela peut prendre du temps ⏳"):
        try:
            process_and_export_games(
                url=url,
                max_games=max_games,
                time_control_mode=time_control_mode,
                progress_callback=update_progress,
            )
            st.success("Analyse terminée ! 🎉")
            st.cache_data.clear()  # Clear cache to reload new data
            time.sleep(1)  # Give time to see the success message
            st.rerun()
        except Exception as e:
            st.error(f"Une erreur est survenue : {e}")


# --- Load Data ---
@st.cache_data
def load_data():
    try:
        games_df = pd.read_csv("data/processed/games_metadata.csv")
        tilts_df = pd.read_csv("data/processed/tilt_events.csv")
        return games_df, tilts_df
    except FileNotFoundError:
        return pd.DataFrame(), pd.DataFrame()


games_df, tilts_df = load_data()

if games_df.empty:
    st.info("👋 Bienvenue ! Aucune donnée n'est disponible pour le moment.")
    st.info(
        "Utilisez le menu à gauche pour configurer et lancer votre première analyse."
    )
    st.stop()

# --- Preprocessing ---


# Create Elo Bins (200 pts)
def create_elo_bins(df, elo_col):
    bins = range(0, 3200, 200)
    labels = [f"{i}-{i+200}" for i in bins[:-1]]
    df["elo_bin"] = pd.cut(df[elo_col], bins=bins, labels=labels, right=False)
    return df


# For games_df, we have white_elo and black_elo. We need to count PLAYERS, not games.
# So we stack them.
players_df = pd.concat(
    [
        games_df[["white_elo"]].rename(columns={"white_elo": "elo"}),
        games_df[["black_elo"]].rename(columns={"black_elo": "elo"}),
    ]
)
players_df = create_elo_bins(players_df, "elo")

# For tilts_df
tilts_df = create_elo_bins(tilts_df, "player_elo")

# --- Sidebar Filters ---
st.sidebar.header("Filters")
min_elo = int(players_df["elo"].min())
max_elo = int(players_df["elo"].max())
elo_range = st.sidebar.slider("Elo Range", min_elo, max_elo, (min_elo, max_elo))

# Filter Data
filtered_players = players_df[
    (players_df["elo"] >= elo_range[0]) & (players_df["elo"] <= elo_range[1])
]
filtered_tilts = tilts_df[
    (tilts_df["player_elo"] >= elo_range[0]) & (tilts_df["player_elo"] <= elo_range[1])
]

# --- Metrics ---
total_games = len(games_df)
total_players = len(filtered_players)  # Approximate if filtered
total_tilts = len(filtered_tilts)
global_rate = (total_tilts / total_players) * 100 if total_players > 0 else 0

col1, col2, col3 = st.columns(3)
col1.metric("Total Games Analyzed", total_games)
col2.metric("Total Tilt Events", total_tilts)
col3.metric("Global Tilt Rate", f"{global_rate:.2f}%")

# --- Visualizations ---

# 1. Tilt Rate by Elo Bin
st.subheader("1. Probabilité de craquer selon le niveau")

# Count players per bin
players_per_bin = filtered_players["elo_bin"].value_counts().sort_index()
# Count tilts per bin
tilts_per_bin = filtered_tilts["elo_bin"].value_counts().sort_index()

# Calculate rate
tilt_rate_df = pd.DataFrame(
    {"Players": players_per_bin, "Tilts": tilts_per_bin}
).fillna(0)
tilt_rate_df["Tilt Rate (%)"] = (tilt_rate_df["Tilts"] / tilt_rate_df["Players"]) * 100

fig1 = px.bar(
    tilt_rate_df,
    x=tilt_rate_df.index,
    y="Tilt Rate (%)",
    title="Pourcentage de joueurs qui tiltent par tranche d'Elo",
    labels={"index": "Elo Bin", "Tilt Rate (%)": "Taux de Tilt (%)"},
)

col_chart1, _ = st.columns([0.5, 0.5])  # Use 50% width
with col_chart1:
    st.plotly_chart(fig1, use_container_width=True)

# 2. Tilt Start Move vs Elo
st.subheader("2. Le moment fatidique (Move Number vs Elo)")
fig2 = px.scatter(
    filtered_tilts,
    x="player_elo",
    y="tilt_start_move",
    color="has_lost",
    title="A quel moment le tilt arrive-t-il ?",
    labels={
        "tilt_start_move": "Numéro du coup du début du tilt",
        "player_elo": "Elo du Joueur",
    },
    opacity=0.7,
)

col_chart2, _ = st.columns([0.5, 0.5])
with col_chart2:
    st.plotly_chart(fig2, use_container_width=True)

# 3. Moves Survived Distribution
st.subheader("3. La survie après le Tilt")
fig3 = px.histogram(
    filtered_tilts,
    x="moves_survived",
    nbins=20,
    title="Combien de temps le joueur survit-il après le tilt ?",
    labels={"moves_survived": "Coups joués après le tilt"},
)

col_chart3, _ = st.columns([0.5, 0.5])
with col_chart3:
    st.plotly_chart(fig3, use_container_width=True)
