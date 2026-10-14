import plotly.graph_objects as go
import streamlit as st

from utils.data import NAVY, BLUE, GOLD
from utils.loader import get_data
from utils.ui import PAGE_ICON, inject_base_style, section_title, plotly_base_layout, render_sidebar_footer

st.set_page_config(page_title="Organigramme — AER", page_icon=PAGE_ICON, layout="wide")
inject_base_style()

data = get_data()
if data is None:
    st.stop()

st.title("🏢 Organigramme du réseau d'antennes")
st.caption("Reconstruit dynamiquement à partir de la feuille « Antennes — Détail solaire » "
           "(colonnes Antenne / Type / Rattachée à / Effectif total) — aucune dépendance système "
           "requise (rendu 100% Plotly, contrairement à Graphviz).")

det = data.antennes_detail
if det is None or det.empty or "Rattachée à" not in det.columns:
    st.warning("Impossible de reconstruire l'organigramme : colonnes attendues introuvables.")
    st.stop()

section_title("SIÈGE & ANTENNES — VUE HIÉRARCHIQUE")

SIEGE_LABEL = "AGENCE D'ÉLECTRIFICATION RURALE — Siège Yaoundé"
ids, labels, parents, values, colors, custom = [], [], [], [], [], []

ids.append("SIEGE"); labels.append(SIEGE_LABEL); parents.append("")
values.append(0); colors.append(NAVY); custom.append("")

for _, row in det.iterrows():
    antenne = str(row.get("Antenne") or "").strip()
    if not antenne:
        continue
    typ = row.get("Type") or ""
    effectif = row.get("Effectif total") or 0
    sites = row.get("Nb sites") or 0
    parent = row.get("Rattachée à")
    parent_id = str(parent).strip() if parent and str(parent).strip() not in ("—", "None", "") else "SIEGE"
    ids.append(antenne)
    labels.append(antenne)
    parents.append(parent_id)
    values.append(max(effectif, 1))
    colors.append(BLUE if typ == "Principale" else GOLD)
    custom.append(f"{typ} · {int(sites)} sites · {int(effectif)} agents")

fig = go.Figure(go.Icicle(
    ids=ids, labels=labels, parents=parents, values=values,
    marker=dict(colors=colors, line=dict(width=1, color="white")),
    customdata=custom,
    hovertemplate="<b>%{label}</b><br>%{customdata}<extra></extra>",
    tiling=dict(orientation="v"),
    root_color="lightgrey",
))
fig = plotly_base_layout(fig, height=520, legend=False)
fig.update_layout(margin=dict(t=10, l=10, r=10, b=10))
st.plotly_chart(fig, use_container_width=True)

st.caption("🔵 Antenne principale &nbsp;&nbsp; 🟡 Annexe rattachée &nbsp;&nbsp;"
           " — la taille de chaque bloc est proportionnelle à son effectif recommandé.")

with st.expander("Voir le tableau source"):
    st.dataframe(det[["Antenne", "Type", "Rattachée à", "Nb sites", "Effectif total"]],
                 use_container_width=True, hide_index=True)

render_sidebar_footer(data.generated_on)
