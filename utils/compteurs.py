"""Données et logique de la page « Statistiques des compteurs ».

Important — comme pour le Fonds revolving (voir `utils/revolving.py`), le
classeur Excel du tableau de bord AER (Gestion_Parc_Solaire...) ne contient
AUCUNE donnée sur les compteurs/abonnés installés : cette page lit ses
propres fichiers, déposés indépendamment par l'utilisateur dans la barre
latérale, et les garde en mémoire de session (comme le registre du Fonds
revolving) le temps de la session.

Deux formats de fichier sont pris en charge :

1. **Export Holley** (le format réel des fichiers fournis par l'AER — export
   du système de gestion des compteurs prépayés « Holley ») : détecté
   automatiquement par la présence des colonnes `Full Address` / `Template
   Code`. Particularité importante, constatée sur les fichiers d'exemple :
   la colonne `Opening Date` de ces exports est un champ système toujours
   égal à 01/01/2018 — elle n'indique donc PAS la vraie date d'installation.
   Chaque fichier correspond en réalité à un **lot d'abonnés** exporté à une
   date donnée (le nom du fichier est lui-même une date, ex.
   « 01-10-2024.xls ») : c'est CETTE date de lot qui sert de période
   d'installation pour toutes ses lignes — convention confirmée par l'AER.

2. **Format générique** (si les colonnes ci-dessus sont absentes) : on
   retombe sur une correspondance manuelle des colonnes, l'utilisateur
   indiquant lui-même quelle colonne est la localité / la date.

Les données réelles contiennent aussi beaucoup de variantes d'orthographe sur
les noms de localités (ex. « DJIGBAMAFOU » / « DJIGBAMAFOUS », ou des
coquilles comme « DOUKOUR0Y » pour « DOUKOUROY ») : `suggest_locality_groups`
propose un regroupement automatique (par similarité de texte) que
l'utilisateur valide ou corrige avant de lancer les statistiques — rien
n'est fusionné silencieusement, dans le même esprit de rigueur des données
que le reste de l'application (voir la carte d'électrification et le Fonds
revolving)."""
from __future__ import annotations

import difflib
import random
import re
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Jeu de données d'exemple (utilisé uniquement si aucun fichier n'est fourni)
# ---------------------------------------------------------------------------
LOCALITES_EXEMPLE = {
    "Adamaoua": ["Ngaoundéré", "Tibati", "Meiganga"],
    "Centre": ["Obala", "Mfou", "Bafia", "Monatélé"],
    "Est": ["Bertoua", "Abong-Mbang", "Batouri"],
    "Extrême-Nord": ["Maroua", "Kousseri", "Mokolo"],
    "Littoral": ["Nkongsamba", "Yabassi"],
    "Nord": ["Garoua", "Guider", "Poli"],
    "Nord-Ouest": ["Bamenda", "Wum"],
    "Ouest": ["Bafoussam", "Dschang", "Bangangté"],
    "Sud": ["Ebolowa", "Sangmélima"],
    "Sud-Ouest": ["Buea", "Kumba"],
}
TYPES_COMPTEUR_EXEMPLE = ["RESEAU", "RESEAU", "RESEAU", "SOLAR"]


@st.cache_data(show_spinner=False)
def generate_sample_data(n: int = 650, seed: int = 42) -> pd.DataFrame:
    """Jeu de données fictif (localités et dates imaginaires), affiché
    uniquement tant qu'aucun fichier réel n'est déposé — jamais présenté
    comme une vraie mesure, exactement comme le registre vide du Fonds
    revolving avant toute saisie."""
    rng = random.Random(seed)
    debut, fin = date(2022, 1, 1), date(2026, 10, 1)
    jours_total = (fin - debut).days
    rows = []
    for i in range(n):
        site = rng.choice(list(LOCALITES_EXEMPLE.keys()))
        localite = rng.choice(LOCALITES_EXEMPLE[site])
        jours_offset = (rng.randint(max(0, jours_total - 540), jours_total) if rng.random() < 0.55
                        else rng.randint(0, jours_total))
        d = debut + timedelta(days=jours_offset)
        type_compteur = rng.choice(TYPES_COMPTEUR_EXEMPLE)
        rows.append({
            "numero_compteur": f"CPT-{10000 + i}",
            "localite_brute": localite.upper(),
            "localite": localite.upper(),
            "site": site,
            "categorie": "MENAGES",
            "type_compteur": type_compteur,
            "solaire": type_compteur == "SOLAR",
            "periode": pd.Timestamp(d).to_period("M").to_timestamp(),
            "nom_fichier": "(jeu d'exemple)",
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Format Holley (format réel des fichiers fournis par l'AER)
# ---------------------------------------------------------------------------
COLONNES_HOLLEY_ATTENDUES = {"Full Address", "Template Code"}


def est_format_holley(raw: pd.DataFrame) -> bool:
    return COLONNES_HOLLEY_ATTENDUES.issubset(set(raw.columns))


def read_excel_sheet_names(uploaded_file) -> list[str]:
    try:
        return pd.ExcelFile(uploaded_file).sheet_names
    except Exception:  # noqa: BLE001
        return []


def load_excel(uploaded_file, sheet_name=0) -> pd.DataFrame:
    return pd.read_excel(uploaded_file, sheet_name=sheet_name)


_MOTIF_DATE_NOM_FICHIER = re.compile(r"(\d{1,2})[-_](\d{1,2})[-_](\d{4})")


def parse_date_from_filename(nom_fichier: str, jour_mois_annee: bool = True) -> date | None:
    """Extrait la date de lot encodée dans le nom du fichier (ex.
    « 01-10-2024.xls »). `jour_mois_annee=True` suppose le format JJ-MM-AAAA
    (convention camerounaise/française) ; sinon MM-JJ-AAAA."""
    m = _MOTIF_DATE_NOM_FICHIER.search(nom_fichier)
    if not m:
        return None
    a, b, annee = int(m.group(1)), int(m.group(2)), int(m.group(3))
    jour, mois = (a, b) if jour_mois_annee else (b, a)
    try:
        return date(annee, mois, jour)
    except ValueError:
        try:  # au cas où l'hypothèse jour/mois serait inversée pour CE fichier précis
            return date(annee, jour, mois)
        except ValueError:
            return None


_MOTIF_MOT_DOUBLE = re.compile(r"^(.+?) \1$")


def _normaliser_localite(brut: str) -> str:
    """Nettoyage léger avant le regroupement par similarité : espaces
    multiples, et le cas fréquent d'un nom de localité dupliqué deux fois
    de suite (« DJIGBAMAFOUS DJIGBAMAFOUS »), que la seule similarité de
    texte ne détecte pas bien (la répétition fait baisser le score de
    ressemblance avec la version simple)."""
    s = re.sub(r"\s+", " ", brut).strip()
    m = _MOTIF_MOT_DOUBLE.match(s)
    return m.group(1) if m else s


def build_from_holley_files(fichiers: list[dict]) -> pd.DataFrame:
    """`fichiers` = [{"nom": str, "df": DataFrame brut, "periode": date}, ...]
    Renvoie un DataFrame normalisé, une ligne par compteur/abonné."""
    blocs = []
    for f in fichiers:
        raw, n = f["df"], len(f["df"])
        bloc = pd.DataFrame()
        bloc["localite_brute"] = (raw.get("Full Address", pd.Series(["(non renseigné)"] * n)).astype(str)
                                   .str.strip().str.upper().map(_normaliser_localite))
        bloc["site"] = raw.get("Holley System ID", pd.Series(["(non renseigné)"] * n)).astype(str).str.strip()
        template = raw.get("Template Code", pd.Series(["(non renseigné)"] * n)).astype(str)
        parties = template.str.split("|", n=1, expand=True)
        bloc["categorie"] = parties[0].str.strip() if 0 in parties else "(non renseigné)"
        bloc["type_compteur"] = (parties[1].str.strip().str.upper() if parties.shape[1] > 1 and 1 in parties
                                  else "(non renseigné)")
        bloc["solaire"] = bloc["type_compteur"].str.contains("SOLAR|SOLAIRE", regex=True, na=False)
        bloc["numero_compteur"] = raw.get("Old Consumer No.", raw.get("Holley Meter ID", pd.Series(range(n))))
        bloc["periode"] = pd.Timestamp(f["periode"]).to_period("M").to_timestamp()
        bloc["nom_fichier"] = f["nom"]
        blocs.append(bloc)
    out = pd.concat(blocs, ignore_index=True)
    out.loc[out["localite_brute"].isin(["0", "", "NAN", "NONE"]), "localite_brute"] = "(localité non renseignée)"
    out["localite"] = out["localite_brute"]  # remplacé par la version nettoyée une fois validée par l'utilisateur
    return out


def suggest_locality_groups(localites_brutes: list[str], seuil: float = 0.82) -> dict[str, str]:
    """Regroupe les noms de localités très similaires (coquilles, variantes
    d'orthographe) sous le nom le plus fréquent du groupe. Ne fusionne
    JAMAIS automatiquement deux noms franchement différents : c'est une
    suggestion à valider, pas une correction silencieuse."""
    comptes = pd.Series(localites_brutes).value_counts()
    noms = list(comptes.index)
    mapping: dict[str, str] = {}
    deja_groupes: set[str] = set()
    for nom in noms:
        if nom in deja_groupes or nom == "(localité non renseignée)":
            continue
        groupe = [nom]
        for autre in noms:
            if autre == nom or autre in deja_groupes or autre == "(localité non renseignée)":
                continue
            if difflib.SequenceMatcher(None, nom, autre).ratio() >= seuil:
                groupe.append(autre)
        if len(groupe) > 1:
            canonique = max(groupe, key=lambda g: comptes[g])
            for g in groupe:
                mapping[g] = canonique
                deja_groupes.add(g)
        else:
            mapping[nom] = nom
            deja_groupes.add(nom)
    return mapping


def apply_locality_mapping(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    df = df.copy()
    df["localite"] = df["localite_brute"].map(mapping).fillna(df["localite_brute"])
    return df


def locality_cleanup_ui(df: pd.DataFrame) -> pd.DataFrame:
    """Tableau éditable (barre latérale) proposant un regroupement des
    variantes d'orthographe détectées parmi les localités brutes ; renvoie
    `df` avec sa colonne `localite` mise à jour selon les corrections
    validées par l'utilisateur. Rien n'est fusionné sans validation."""
    comptes = df["localite_brute"].value_counts()
    suggestion = suggest_locality_groups(df["localite_brute"].tolist())
    table_initiale = pd.DataFrame({
        "Localité (brute)": comptes.index,
        "Occurrences": comptes.values,
        "Localité retenue": [suggestion.get(n, n) for n in comptes.index],
    })
    cle = "cpt_localite_cleanup_" + str(abs(hash(tuple(sorted(comptes.index)))))
    with st.sidebar.expander(f"🧹 Vérifier les localités ({len(comptes)} valeurs brutes)", expanded=False):
        st.caption(
            "Les fichiers réels contiennent souvent des variantes d'orthographe pour une même "
            "localité (coquilles, casse, espaces). Une proposition de regroupement est déjà "
            "pré-remplie ci-dessous — corrige-la si besoin : deux lignes avec la même valeur "
            "retenue seront comptées ensemble."
        )
        edite = st.data_editor(
            table_initiale, hide_index=True, use_container_width=True, key=cle,
            disabled=["Localité (brute)", "Occurrences"], height=min(60 + 36 * len(table_initiale), 400),
        )
    mapping = dict(zip(edite["Localité (brute)"], edite["Localité retenue"]))
    return apply_locality_mapping(df, mapping)


# ---------------------------------------------------------------------------
# Format générique (correspondance manuelle des colonnes)
# ---------------------------------------------------------------------------
def apply_column_mapping(raw: pd.DataFrame, mapping: dict) -> tuple[pd.DataFrame, int]:
    """mapping = {"localite": "<nom de colonne réel>", "date_installation": "...",
    "site": "..." | None, "type_compteur": "..." | None}."""
    out = pd.DataFrame()
    out["localite_brute"] = raw[mapping["localite"]].astype(str).str.strip().str.upper().map(_normaliser_localite)
    out["date_installation"] = pd.to_datetime(raw[mapping["date_installation"]], errors="coerce")
    out["site"] = raw[mapping["site"]].astype(str).str.strip() if mapping.get("site") else "(non précisé)"
    out["type_compteur"] = (raw[mapping["type_compteur"]].astype(str).str.strip().str.upper()
                             if mapping.get("type_compteur") else "(non précisé)")
    out["solaire"] = out["type_compteur"].str.contains("SOLAR|SOLAIRE", regex=True, na=False)
    out["localite"] = out["localite_brute"]
    out["nom_fichier"] = "(fichier unique)"
    n_avant = len(out)
    out = out.dropna(subset=["date_installation"])
    out["periode"] = out["date_installation"].dt.to_period("M").dt.to_timestamp()
    n_rejetees = n_avant - len(out)
    return out, n_rejetees


# ---------------------------------------------------------------------------
# Traçabilité des lots — un fichier Holley = un lot d'abonnés exporté à une
# date donnée (voir docstring du module). Permet de vérifier, lot par lot,
# que la période détectée depuis le nom de fichier est cohérente.
# ---------------------------------------------------------------------------
def lot_summary(df: pd.DataFrame) -> pd.DataFrame:
    if "nom_fichier" not in df.columns:
        return pd.DataFrame()
    g = df.groupby("nom_fichier", dropna=False)
    out = g.agg(
        Compteurs=("nom_fichier", "size"),
        Période=("periode", "max"),
        Localités=("localite", "nunique"),
    )
    if "solaire" in df.columns:
        out["Compteurs solaires"] = g["solaire"].sum().astype(int)
    out = out.reset_index().rename(columns={"nom_fichier": "Fichier (lot)"})
    return out.sort_values("Période")
