"""Composants d'interface et thème partagés par toutes les pages."""
from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go
import plotly.io as pio

from .data import NAVY, BLUE, GOLD, RED, GREEN, AMBER, GREY, CATEGORICAL, STATUS_COLORS

PAGE_ICON = "☀️"
APP_TITLE = "Tableau de bord AER — Parc solaire & Ressources humaines"


def inject_base_style():
    st.markdown(
        f"""
        <style>
        .block-container {{ padding-top: 1.6rem; padding-bottom: 3rem; }}
        [data-testid="stMetricValue"] {{ font-size: 1.6rem; color: {NAVY}; }}
        [data-testid="stMetricLabel"] {{ font-weight: 600; letter-spacing: .02em; }}
        .aer-kpi {{
            background: var(--background-color, #fff);
            border: 1px solid rgba(31,56,100,0.12);
            border-radius: 10px;
            padding: 0.9rem 1rem 0.7rem 1rem;
        }}
        .aer-badge {{
            display: inline-block; padding: 0.15rem 0.6rem; border-radius: 999px;
            font-size: 0.78rem; font-weight: 700; color: white;
        }}
        .aer-section-title {{
            background: #DCE6F1; color: {NAVY}; font-weight: 700; font-size: 1.02rem;
            padding: 0.5rem 0.8rem; border-radius: 6px; margin: 0.6rem 0 0.8rem 0;
        }}
        div[data-baseweb="tab-list"] {{ gap: 4px; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def section_title(text: str):
    st.markdown(f'<div class="aer-section-title">{text}</div>', unsafe_allow_html=True)


def status_badge(status: str) -> str:
    color = STATUS_COLORS.get(status, GREY)
    return f'<span class="aer-badge" style="background:{color}">{status}</span>'


def plotly_base_layout(fig: go.Figure, height: int = 380, legend: bool = True) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=48, b=10),
        font=dict(family="Segoe UI, Arial, sans-serif", size=13, color="#2B2B2B"),
        title_font=dict(size=15, color=NAVY),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hoverlabel=dict(bgcolor="white", font_size=12),
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor="rgba(31,56,100,0.08)", zeroline=False)
    return fig


def style_map(styler, func, subset=None):
    """Wrapper compatible pandas < 2.1 (Styler.applymap) et >= 2.1 / 3.x
    (Styler.map, applymap étant supprimé en pandas 3.0)."""
    if hasattr(styler, "map"):
        return styler.map(func, subset=subset)
    return styler.applymap(func, subset=subset)


def kpi_row(items: list[tuple[str, str, str | None]]):
    """items: liste de (label, valeur, delta_ou_None)."""
    cols = st.columns(len(items))
    for col, (label, value, delta) in zip(cols, items):
        with col:
            st.metric(label, value, delta=delta)


def gauge_indicator(
    value: float, title: str, max_value: float = 100, suffix: str = "%",
    low_threshold: float = 40, high_threshold: float = 75,
    low_color: str = RED, mid_color: str = AMBER, high_color: str = GREEN,
    height: int = 320,
) -> go.Figure:
    """Jauge (« meter ») pour un ratio lu contre une limite (taux de
    couverture, taux de recouvrement, part solaire...) — plus lisible qu'un
    simple pourcentage en texte pour ce type de métrique. Les seuils bas/haut
    sont exprimés sur la même échelle que `value` (ex. en %)."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={"suffix": suffix, "font": {"size": 22, "color": NAVY}},
        title={"text": title, "font": {"size": 13, "color": NAVY}},
        gauge={
            "axis": {"range": [0, max_value], "tickwidth": 1, "tickcolor": GREY},
            "bar": {"color": NAVY, "thickness": 0.32},
            "bgcolor": "white",
            "borderwidth": 0,
            "steps": [
                {"range": [0, low_threshold], "color": f"{low_color}26"},
                {"range": [low_threshold, high_threshold], "color": f"{mid_color}26"},
                {"range": [high_threshold, max_value], "color": f"{high_color}26"},
            ],
        },
    ))
    fig.update_layout(
        height=height, margin=dict(l=30, r=30, t=60, b=50),
        font=dict(family="Segoe UI, Arial, sans-serif", color="#2B2B2B"),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def render_sidebar_footer(generated_on: str):
    st.sidebar.markdown("---")
    if generated_on:
        st.sidebar.caption(generated_on)
    st.sidebar.caption("AER · Application de visualisation — construite avec Streamlit & Plotly.")
