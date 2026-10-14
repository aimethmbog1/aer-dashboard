import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.data import NAVY, BLUE, GOLD, RED, GREEN, AMBER, CATEGORICAL, STATUS_COLORS
from utils.loader import get_data
from utils.ui import (
    APP_TITLE, PAGE_ICON, inject_base_style, section_title, plotly_base_layout,
    kpi_row, render_sidebar_footer, status_badge, style_map,
)

st.set_page_config(page_title="Vue d'ensemble — AER", page_icon=PAGE_ICON, layout="wide")
inject_base_style()

data = get_data()
if data is None:
    st.stop()

st.title(APP_TITLE)
st.caption(data.generated_on or "")

# =====================================================================
# KPI — Parc solaire
# =====================================================================
section_title("VUE D'ENSEMBLE — PARC SOLAIRE")
ks = data.kpis_solar
kpi_row([
    ("Sites installés", f"{int(ks.get('SITES INSTALLÉS', 0)):,}".replace(",", " "), None),
    ("Puissance totale (kWc)", f"{ks.get('PUISSANCE TOTALE (kWc)', 0):,.1f}".replace(",", " "), None),
    ("Antennes réseau solaire", str(ks.get("ANTENNES RÉSEAU SOLAIRE", "—")), None),
    ("Effectif recommandé", str(ks.get("EFFECTIF RECOMMANDÉ (total)", "—")), None),
    ("Sites / agent (moy.)", f"{ks.get('SITES / AGENT (moy.)', 0):,.1f}", None),
])

st.write("")

# =====================================================================
# KPI — Ressources humaines terrain
# =====================================================================
section_title("VUE D'ENSEMBLE — DÉPLOIEMENT DU PERSONNEL TERRAIN (16 équipes)")
kr = data.kpis_rh
manque_ing = str(kr.get("MANQUE INGÉNIEURS", "—"))
manque_tc = str(kr.get("MANQUE TECH. / CHAUFF.", "—"))
kpi_row([
    ("Équipes constituées", str(kr.get("ÉQUIPES CONSTITUÉES", "—")), None),
    ("Postes pourvus / requis", str(kr.get("POSTES POURVUS / REQUIS", "—")), None),
    ("Total manques", str(kr.get("TOTAL MANQUES", "—")), None),
    ("Personnel disponible (non affecté)", str(kr.get("PERSONNEL DISPONIBLE (non affecté)", "—")), None),
])
c1, c2 = st.columns(2)
c1.info(f"**Manque Ingénieurs :** {manque_ing}")
c2.info(f"**Manque Technicien / Chauffeur :** {manque_tc}")

st.write("")

# =====================================================================
# Grille de statut des 16 équipes + Plan d'action
# =====================================================================
col_grid, col_donut = st.columns([2.1, 1])

with col_grid:
    section_title("STATUT DES 16 ÉQUIPES")
    grid = data.grid.copy()
    if not grid.empty:
        role_cols = [c for c in grid.columns if c not in ("Équipe (antenne — zone)", "Statut équipe")]
        filt_statut = st.multiselect(
            "Filtrer par statut d'équipe", options=["Complète", "Partielle", "Critique"],
            default=["Complète", "Partielle", "Critique"], key="grid_filter",
        )
        view = grid[grid["Statut équipe"].isin(filt_statut)] if "Statut équipe" in grid else grid

        def style_ok(v):
            if v == "OK":
                return f"background-color:#D9EAD3;color:{GREEN};font-weight:600;text-align:center"
            if v == "—":
                return f"background-color:#F8D7DA;color:{RED};font-weight:600;text-align:center"
            return "text-align:center"

        def style_statut(v):
            color = STATUS_COLORS.get(v, "#666")
            return f"background-color:{color}22;color:{color};font-weight:700;text-align:center"

        styler = style_map(view.style, style_ok, subset=[c for c in role_cols if c != "Statut équipe"])
        if "Statut équipe" in view.columns:
            styler = style_map(styler, style_statut, subset=["Statut équipe"])
        st.dataframe(styler, use_container_width=True, hide_index=True, height=420)
    else:
        st.warning("Grille introuvable dans ce classeur.")

with col_donut:
    section_title("TAUX DE COMPLÉTUDE")
    if not grid.empty and "Statut équipe" in grid.columns:
        counts = grid["Statut équipe"].value_counts().reindex(["Complète", "Partielle", "Critique"]).fillna(0)
        fig = go.Figure(data=[go.Pie(
            labels=counts.index, values=counts.values, hole=0.55,
            marker=dict(colors=[STATUS_COLORS[k] for k in counts.index]),
            textinfo="label+percent", sort=False,
        )])
        fig = plotly_base_layout(fig, height=300, legend=False)
        fig.update_layout(title="16 équipes")
        st.plotly_chart(fig, use_container_width=True)
        for label, val in counts.items():
            st.markdown(f"{status_badge(label)} &nbsp; **{int(val)}** équipe(s)", unsafe_allow_html=True)

st.write("")
section_title("PLAN D'ACTION PRIORITAIRE — RECRUTEMENT / REDÉPLOIEMENT")
ap = data.action_plan
if ap is not None and not ap.empty:
    min_manques = st.slider("Afficher les équipes avec au moins N postes manquants",
                             0, int(ap["Postes manquants"].max()), 0)
    ap_view = ap[ap["Postes manquants"] >= min_manques]
    st.dataframe(ap_view, use_container_width=True, hide_index=True, height=380)
else:
    st.info("Plan d'action non trouvé dans ce classeur (ajouté dans les versions récentes).")

st.write("")

# =====================================================================
# Visualisations de synthèse
# =====================================================================
section_title("VISUALISATIONS")
v1, v2 = st.columns(2)

with v1:
    st.subheader("Manques par profil (RH terrain)")
    pt = data.profil_table
    if pt is not None and not pt.empty and "Profil" in pt.columns:
        pt2 = pt[pt["Profil"] != "TOTAL"]
        fig = px.pie(pt2, names="Profil", values="Manque", hole=0.35,
                     color="Profil", color_discrete_sequence=CATEGORICAL)
        fig.update_traces(textinfo="label+percent")
        fig = plotly_base_layout(fig, legend=False)
        st.plotly_chart(fig, use_container_width=True)

with v2:
    st.subheader("Manques par antenne, par profil")
    rh = data.rh_table
    if rh is not None and not rh.empty:
        rh2 = rh[rh.iloc[:, 0] != "TOTAL (9 antennes / 16 équipes)"]
        fig = go.Figure()
        for col, color in zip(["Ingénieur manquant", "Technicien manquant", "Chauffeur manquant"],
                               [RED, AMBER, BLUE]):
            if col in rh2.columns:
                fig.add_bar(name=col.replace(" manquant", ""), x=rh2.iloc[:, 0], y=rh2[col],
                            marker_color=color)
        fig.update_layout(barmode="stack")
        fig = plotly_base_layout(fig)
        st.plotly_chart(fig, use_container_width=True)

render_sidebar_footer(data.generated_on)
