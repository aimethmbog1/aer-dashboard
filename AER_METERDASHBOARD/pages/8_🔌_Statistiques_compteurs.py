from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.data import NAVY, BLUE, GOLD, RED, GREEN, AMBER, GREY
from utils.loader import get_data
from utils.ui import PAGE_ICON, inject_base_style, section_title, plotly_base_layout, kpi_row, render_sidebar_footer
from utils.compteurs import (
    generate_sample_data, read_excel_sheet_names, load_excel,
    est_format_holley, parse_date_from_filename, build_from_holley_files,
    apply_column_mapping, locality_cleanup_ui, lot_summary,
)

st.set_page_config(page_title="Statistiques des compteurs — AER", page_icon=PAGE_ICON, layout="wide")
inject_base_style()

data = get_data()  # gardé pour la cohérence de navigation ; non requis sur cette page
st.title("🔌 Statistiques des compteurs")
st.caption("Compteurs (abonnés) installés — répartition par localité et par période d'installation, à partir "
           "des exports du système de gestion des compteurs prépayés « Holley ».")

with st.expander("ℹ️ Ce que cette page représente exactement — à lire avant de l'utiliser", expanded=False):
    st.markdown(
        """
Le classeur Excel du tableau de bord (parc solaire + équipes terrain) **ne contient aucune donnée sur les
compteurs/abonnés installés** : cette page lit ses **propres fichiers**, déposés indépendamment ci-contre,
et les garde en mémoire pour la durée de la session — comme le registre du Fonds revolving.

**Format reconnu automatiquement — export « Holley » :**
- Détecté par la présence des colonnes `Full Address` / `Template Code`.
- La colonne `Opening Date` de ces exports est un **champ système figé à 01/01/2018** sur tous les fichiers
  observés : elle n'indique donc **pas** la vraie date d'installation.
- Chaque fichier correspond en réalité à un **lot d'abonnés** exporté à une date donnée, et c'est **la date
  présente dans le nom du fichier** (ex. `01-10-2024.xls`) qui sert de période d'installation pour toutes ses
  lignes — convention confirmée pour ces fichiers. Cette date est affichée et modifiable ci-contre avant de
  lancer les statistiques, et le détail par lot reste consultable dans l'onglet « Vue d'ensemble ».
- Si un fichier ne correspond pas à ce format, une correspondance manuelle des colonnes est proposée (un
  fichier à la fois).

**Qualité des données :** les noms de localités contiennent souvent des variantes d'orthographe (coquilles,
casse, espaces superflus). Un regroupement automatique est **suggéré** (par similarité de texte) dans la
barre latérale, mais rien n'est fusionné sans validation — modifie la proposition si besoin.

**Persistance :** comme pour le Fonds revolving, Streamlit ne conserve rien entre deux sessions — les
fichiers déposés ici sont à re-déposer à chaque ouverture. Les tableaux de cette page s'exportent en CSV.
        """
    )

# =============================================================================
# Barre latérale — dépôt des fichiers
# =============================================================================
st.sidebar.markdown("### 📥 Données compteurs")
jour_mois_annee = st.sidebar.toggle(
    "Dates de fichier au format JJ-MM-AAAA", value=True, key="cpt_jma",
    help="Le nom de chaque fichier doit contenir une date (ex. 01-10-2024.xls), qui sert de période "
         "d'installation pour toutes ses lignes. Désactive si tes fichiers sont nommés MM-JJ-AAAA.",
)
uploaded_files = st.sidebar.file_uploader(
    "Fichiers Excel des abonnés installés", type=["xlsx", "xls"], accept_multiple_files=True, key="cpt_upload",
    help="Dépose un ou plusieurs fichiers — le format export Holley (colonnes Full Address / Template Code) "
         "est reconnu automatiquement.",
)

df = None
if uploaded_files:
    lus, erreurs = [], []
    for uf in uploaded_files:
        try:
            feuilles = read_excel_sheet_names(uf)
            raw = load_excel(uf, sheet_name=feuilles[0] if feuilles else 0)
        except Exception as e:  # noqa: BLE001
            erreurs.append(f"{uf.name} : {e}")
            continue
        lus.append({"nom": uf.name, "df": raw})
    for e in erreurs:
        st.sidebar.error(e)

    df_brut = None
    if lus:
        if all(est_format_holley(l["df"]) for l in lus):
            st.sidebar.markdown("**Période de chaque lot** (détectée depuis le nom du fichier — à corriger si besoin)")
            fichiers_avec_periode = []
            for l in lus:
                devinee = parse_date_from_filename(l["nom"], jour_mois_annee) or date.today()
                choisie = st.sidebar.date_input(l["nom"], value=devinee, key=f"cpt_periode_{l['nom']}")
                fichiers_avec_periode.append({"nom": l["nom"], "df": l["df"], "periode": choisie})
            df_brut = build_from_holley_files(fichiers_avec_periode)
            st.sidebar.success(f"{len(df_brut)} lignes chargées depuis {len(lus)} fichier(s) — format Holley détecté.")
        elif len(lus) == 1:
            brut = lus[0]["df"]
            st.sidebar.markdown("**Correspondance des colonnes** (format non reconnu automatiquement)")
            colonnes = list(brut.columns)
            col_localite = st.sidebar.selectbox("Colonne → Localité", colonnes, key="cpt_map_localite")
            col_date = st.sidebar.selectbox("Colonne → Date d'installation", colonnes, key="cpt_map_date")
            col_site = st.sidebar.selectbox("Colonne → Site/Région (optionnel)", ["(aucune)"] + colonnes, key="cpt_map_site")
            col_type = st.sidebar.selectbox("Colonne → Type de compteur (optionnel)", ["(aucune)"] + colonnes, key="cpt_map_type")
            mapping = {
                "localite": col_localite, "date_installation": col_date,
                "site": None if col_site == "(aucune)" else col_site,
                "type_compteur": None if col_type == "(aucune)" else col_type,
            }
            df_brut, n_rejetees = apply_column_mapping(brut, mapping)
            st.sidebar.success(f"{len(df_brut)} lignes chargées.")
            if n_rejetees:
                st.sidebar.warning(f"{n_rejetees} ligne(s) ignorée(s) (date d'installation illisible).")
        else:
            st.sidebar.warning(
                "Plusieurs fichiers chargés mais tous ne correspondent pas au format Holley reconnu "
                "automatiquement — dépose-les un par un pour une correspondance manuelle des colonnes."
            )

    if df_brut is not None and not df_brut.empty:
        df = locality_cleanup_ui(df_brut)

donnees_exemple = df is None
if donnees_exemple:
    st.sidebar.info(
        "Aucun fichier chargé — cette page tourne pour l'instant sur un **jeu de données d'exemple** "
        "(localités et dates fictives), juste pour montrer le fonctionnement. Dépose tes fichiers Excel "
        "ci-dessus dès qu'ils sont prêts."
    )
    df = generate_sample_data()
    st.caption("ℹ️ Statistiques construites sur le **jeu de données d'exemple** — dépose tes fichiers Excel "
               "dans la barre latérale pour voir tes vrais chiffres.")

if df.empty:
    st.info("Aucune donnée à afficher.")
    st.stop()

# =============================================================================
# KPI globaux
# =============================================================================
total = len(df)
nb_localites = df["localite"].nunique()
nb_sites = df["site"].nunique() if "site" in df else None
derniere_periode = df["periode"].max()
nb_solaire = int(df["solaire"].sum()) if "solaire" in df else 0
taux_solaire = f"{nb_solaire / total * 100:.0f} %" if total else "—"

kpi_row([
    ("🔌 Compteurs installés", f"{total:,}".replace(",", " "), None),
    ("📍 Localités couvertes", f"{nb_localites}", None),
    ("🗺️ Sites couverts", f"{nb_sites}" if nb_sites else "—", None),
    ("📅 Dernière période", derniere_periode.strftime("%m/%Y") if pd.notna(derniere_periode) else "—", None),
    ("☀️ Compteurs solaires", taux_solaire, None),
])

st.write("")

tab_vue, tab_localite, tab_periode, tab_croisement = st.tabs([
    "📊 Vue d'ensemble", "📍 Par localité", "📅 Par période", "🧭 Localité × période",
])

# -----------------------------------------------------------------------
# Vue d'ensemble
# -----------------------------------------------------------------------
with tab_vue:
    section_title("TOP 10 DES LOCALITÉS")
    top10 = df["localite"].value_counts().head(10).reset_index()
    top10.columns = ["Localité", "Compteurs installés"]
    fig = px.bar(top10.sort_values("Compteurs installés"), x="Compteurs installés", y="Localité",
                 orientation="h", color_discrete_sequence=[NAVY])
    fig = plotly_base_layout(fig, height=360, legend=False)
    st.plotly_chart(fig, use_container_width=True)

    section_title("RYTHME D'INSTALLATION — PÉRIODES LES PLUS RÉCENTES")
    par_periode_apercu = df.groupby("periode").size().reset_index(name="Installations")
    par_periode_apercu = par_periode_apercu.sort_values("periode").tail(12)
    fig2 = px.bar(par_periode_apercu, x="periode", y="Installations", color_discrete_sequence=[BLUE])
    fig2 = plotly_base_layout(fig2, height=300, legend=False)
    fig2.update_xaxes(title=None)
    st.plotly_chart(fig2, use_container_width=True)

    if not donnees_exemple and "nom_fichier" in df.columns and df["nom_fichier"].nunique() > 0:
        section_title("TRAÇABILITÉ PAR LOT — UN FICHIER DÉPOSÉ = UN LOT D'ABONNÉS")
        st.caption("Vérifie ici que la période détectée depuis le nom de chaque fichier est cohérente avec "
                   "le lot qu'il contient.")
        resume_lots = lot_summary(df)
        st.dataframe(
            resume_lots, use_container_width=True, hide_index=True,
            column_config={"Période": st.column_config.DateColumn("Période", format="MM/YYYY")},
        )

# -----------------------------------------------------------------------
# Par localité
# -----------------------------------------------------------------------
with tab_localite:
    df_loc = df
    if "site" in df_loc and df_loc["site"].nunique() > 1:
        sites = sorted(df_loc["site"].dropna().unique().tolist())
        # La clé inclut la liste des sites : si le jeu de données change (nouveaux fichiers
        # déposés, ou bascule exemple → réel), Streamlit traite le filtre comme un nouveau
        # widget et resélectionne tout par défaut, au lieu de garder une ancienne sélection
        # devenue invalide (qui se traduirait par un filtre vide et silencieux).
        cle_filtre = "cpt_site_filter_" + str(abs(hash(tuple(sites))))
        choix_sites = st.multiselect("Filtrer par site", sites, default=sites, key=cle_filtre)
        df_loc = df_loc[df_loc["site"].isin(choix_sites)]

    if df_loc.empty:
        st.warning("Aucune localité ne correspond au filtre choisi.")
    else:
        par_loc = df_loc["localite"].value_counts().reset_index()
        par_loc.columns = ["Localité", "Compteurs installés"]
        localite_top = par_loc.iloc[0]

        kpi_row([
            ("📍 Localités couvertes", str(df_loc["localite"].nunique()), None),
            ("🥇 Localité la plus équipée", localite_top["Localité"], None),
            (f"🔌 Compteurs à {localite_top['Localité']}", str(int(localite_top["Compteurs installés"])), None),
            ("📊 Compteurs / localité (moy.)", f"{len(df_loc) / df_loc['localite'].nunique():.0f}", None),
        ])

        st.write("")
        section_title("COMPTEURS INSTALLÉS PAR LOCALITÉ")
        NB_AFFICHEES = 15
        if len(par_loc) > NB_AFFICHEES:
            tete = par_loc.head(NB_AFFICHEES)
            reste = par_loc.iloc[NB_AFFICHEES:]["Compteurs installés"].sum()
            affichage = pd.concat([tete, pd.DataFrame([{"Localité": "Autres localités", "Compteurs installés": reste}])])
            st.caption(f"{len(par_loc)} localités au total — les {NB_AFFICHEES} premières sont détaillées, le "
                       "reste est regroupé sous « Autres localités ».")
        else:
            affichage = par_loc
        affichage = affichage.sort_values("Compteurs installés")
        couleurs = [GREY if loc == "Autres localités" else NAVY for loc in affichage["Localité"]]
        fig = px.bar(affichage, x="Compteurs installés", y="Localité", orientation="h", text="Compteurs installés")
        fig.update_traces(marker_color=couleurs, textposition="outside")
        fig = plotly_base_layout(fig, height=max(360, 28 * len(affichage)), legend=False)
        st.plotly_chart(fig, use_container_width=True)

        if "site" in df_loc and df_loc["site"].nunique() > 1:
            section_title("RÉPARTITION PAR SITE")
            par_site = df_loc["site"].value_counts().reset_index()
            par_site.columns = ["Site", "Compteurs installés"]
            fig_r = px.bar(par_site.sort_values("Compteurs installés"), x="Compteurs installés", y="Site",
                           orientation="h", color_discrete_sequence=[BLUE])
            fig_r = plotly_base_layout(fig_r, height=max(280, 32 * len(par_site)), legend=False)
            st.plotly_chart(fig_r, use_container_width=True)

        if "type_compteur" in df_loc and df_loc["type_compteur"].nunique() > 1:
            section_title("RÉPARTITION PAR TYPE DE COMPTEUR")
            par_type = df_loc["type_compteur"].value_counts().reset_index()
            par_type.columns = ["Type de compteur", "Compteurs installés"]
            couleurs_type = [GOLD if ("SOLAR" in t or "SOLAIRE" in t) else BLUE for t in par_type["Type de compteur"]]
            fig_t = px.bar(par_type.sort_values("Compteurs installés"), x="Compteurs installés", y="Type de compteur",
                           orientation="h", text="Compteurs installés")
            fig_t.update_traces(marker_color=couleurs_type, textposition="outside")
            fig_t = plotly_base_layout(fig_t, height=max(220, 40 * len(par_type)), legend=False)
            st.plotly_chart(fig_t, use_container_width=True)

        st.write("")
        section_title("TABLEAU DÉTAILLÉ")
        tableau = df_loc.groupby("localite").agg(Compteurs=("localite", "size"), Dernière_période=("periode", "max"))
        if "solaire" in df_loc:
            tableau["Compteurs solaires"] = df_loc[df_loc["solaire"]].groupby("localite").size()
            tableau["Compteurs solaires"] = tableau["Compteurs solaires"].fillna(0).astype(int)
        tableau = tableau.sort_values("Compteurs", ascending=False).reset_index()
        tableau.columns = ["Localité"] + list(tableau.columns[1:])
        st.dataframe(
            tableau, use_container_width=True, hide_index=True,
            column_config={"Dernière_période": st.column_config.DateColumn("Dernière période", format="MM/YYYY")},
        )
        st.download_button("⬇️ Télécharger ce tableau (CSV)", tableau.to_csv(index=False).encode("utf-8"),
                            "compteurs_par_localite.csv", "text/csv", key="cpt_dl_localite")

# -----------------------------------------------------------------------
# Par période
# -----------------------------------------------------------------------
with tab_periode:
    date_min, date_max = df["periode"].min().date(), df["periode"].max().date()
    c1, c2 = st.columns([2, 1])
    with c1:
        if date_min == date_max:
            st.markdown(f"**Période disponible :** {date_min.strftime('%m/%Y')} (un seul lot chargé)")
            debut, fin = date_min, date_max
        else:
            plage = st.date_input("Période à afficher", value=(date_min, date_max),
                                   min_value=date_min, max_value=date_max, key="cpt_plage")
            debut, fin = plage if isinstance(plage, tuple) and len(plage) == 2 else (date_min, date_max)
    with c2:
        granularite = st.radio("Granularité", ["Mois", "Trimestre", "Année"], horizontal=True, index=0, key="cpt_gran")

    masque = (df["periode"].dt.date >= debut) & (df["periode"].dt.date <= fin)
    periode_df = df[masque]

    if periode_df.empty:
        st.warning("Aucune installation sur la période choisie.")
    else:
        code_periode = {"Mois": "M", "Trimestre": "Q", "Année": "Y"}[granularite]
        periode_df = periode_df.copy()
        periode_df["bucket"] = periode_df["periode"].dt.to_period(code_periode).dt.to_timestamp()

        par_bucket = periode_df.groupby("bucket").size().reset_index(name="Nouvelles installations").sort_values("bucket")
        par_bucket["Cumul"] = par_bucket["Nouvelles installations"].cumsum()

        moyenne = par_bucket["Nouvelles installations"].mean()
        meilleure = par_bucket.loc[par_bucket["Nouvelles installations"].idxmax()]
        kpi_row([
            ("🔌 Installations sur la période", f"{len(periode_df):,}".replace(",", " "), None),
            (f"📈 Moyenne par {granularite.lower()}", f"{moyenne:.0f}", None),
            (f"🏆 Meilleur(e) {granularite.lower()}",
             meilleure["bucket"].strftime("%m/%Y") if granularite != "Année" else meilleure["bucket"].strftime("%Y"),
             f"{int(meilleure['Nouvelles installations'])} installations"),
        ])

        st.write("")
        section_title(f"NOUVELLES INSTALLATIONS PAR {granularite.upper()}")
        fig = px.bar(par_bucket, x="bucket", y="Nouvelles installations", color_discrete_sequence=[NAVY])
        fig = plotly_base_layout(fig, height=340, legend=False)
        fig.update_xaxes(title=None)
        st.plotly_chart(fig, use_container_width=True)

        section_title("CUMUL DES INSTALLATIONS DANS LE TEMPS")
        fig2 = px.line(par_bucket, x="bucket", y="Cumul", markers=True, color_discrete_sequence=[BLUE])
        fig2 = plotly_base_layout(fig2, height=300, legend=False)
        fig2.update_xaxes(title=None)
        fig2.update_traces(line=dict(width=2.5))
        st.plotly_chart(fig2, use_container_width=True)

        st.write("")
        section_title("TABLEAU DÉTAILLÉ")
        tableau_p = par_bucket.rename(columns={"bucket": "Période"})
        st.dataframe(tableau_p, use_container_width=True, hide_index=True)
        st.download_button("⬇️ Télécharger ce tableau (CSV)", tableau_p.to_csv(index=False).encode("utf-8"),
                            "compteurs_par_periode.csv", "text/csv", key="cpt_dl_periode")

# -----------------------------------------------------------------------
# Croisement localité × période
# -----------------------------------------------------------------------
with tab_croisement:
    section_title("INSTALLATIONS PAR LOCALITÉ ET PAR PÉRIODE")
    st.caption("Les 12 localités les plus équipées, mois par mois — pour repérer d'un coup d'œil où et quand "
               "l'effort d'installation s'est concentré.")
    NB_LOC_CROISEMENT = 12
    top_localites = df["localite"].value_counts().head(NB_LOC_CROISEMENT).index.tolist()
    df_crois = df[df["localite"].isin(top_localites)]
    if df_crois.empty:
        st.info("Pas assez de données pour un croisement.")
    else:
        pivot = (df_crois.groupby(["localite", "periode"]).size().reset_index(name="Compteurs")
                 .pivot(index="localite", columns="periode", values="Compteurs").fillna(0))
        pivot = pivot.reindex(top_localites)
        pivot.columns = [c.strftime("%m/%Y") for c in pivot.columns]
        fig = go.Figure(data=go.Heatmap(
            z=pivot.values, x=pivot.columns, y=pivot.index,
            colorscale=[[0, "#F2F2F2"], [1, NAVY]], hoverongaps=False,
            colorbar=dict(title="Compteurs"),
        ))
        fig = plotly_base_layout(fig, height=max(360, 34 * len(pivot)), legend=False)
        st.plotly_chart(fig, use_container_width=True)
        with st.expander("📋 Voir le tableau croisé"):
            st.dataframe(pivot.astype(int), use_container_width=True)
            st.download_button("⬇️ Télécharger ce tableau croisé (CSV)", pivot.astype(int).to_csv().encode("utf-8"),
                                "compteurs_localite_x_periode.csv", "text/csv", key="cpt_dl_croisement")

st.write("")
if not donnees_exemple:
    with st.expander("📄 Export complet des compteurs (toutes colonnes nettoyées)"):
        colonnes_export = [c for c in ["numero_compteur", "localite", "site", "categorie", "type_compteur",
                                        "solaire", "periode", "nom_fichier"] if c in df.columns]
        st.dataframe(df[colonnes_export], use_container_width=True, hide_index=True, height=400)
        st.download_button("⬇️ Télécharger toutes les lignes (CSV)", df[colonnes_export].to_csv(index=False).encode("utf-8"),
                            f"compteurs_export_{date.today().isoformat()}.csv", "text/csv", key="cpt_dl_export")

render_sidebar_footer(data.generated_on if data else "")
