"""Gestion du parc automobile DGOER — registre des véhicules, affectation aux
entités/équipes, journal d'utilisation (carburant, vidange) et échéances de
réforme.

Ce qui est réel ici (fichier « gestionnaire_du_parc_auto_DGOER.xlsx » fourni
par l'utilisateur) :
  - Les 12 véhicules du parc (Direction/siège — y compris la sous-rubrique
    « Maîtrise d'œuvre publique » — + 4 antennes), avec leurs plaques, marques
    et années de mise en service recopiées telles quelles, y compris les
    4 plaques incomplètes (préfixe « CE » seul dans le fichier source) et les
    3 années de mise en service manquantes : rien n'est complété ou deviné.
  - Les 5 « entités propriétaires » du fichier parc auto et les 9 antennes de
    la feuille RH « Données - Équipes » proviennent de deux classeurs
    différents et ne se recouvrent pas exactement (ex. le fichier parc auto
    regroupe « Nord / Extrême-Nord / Adamaoua » en une seule entité, alors que
    la RH les distingue). Le champ « Entité propriétaire » reste donc fidèle
    au fichier parc auto ; le champ « Équipe affectée » est une affectation
    optionnelle et distincte, vers la vraie liste des antennes RH.

Ce qui est un outil à alimenter, pas une donnée déjà connue :
  - Le type de véhicule, la date d'acquisition précise, le chauffeur attitré,
    le statut opérationnel et le journal d'utilisation (carburant, vidanges,
    pannes) ne figurent dans aucun classeur : ce module fournit un registre
    pré-rempli avec les 12 véhicules réels mais à compléter, et un journal
    d'événements vide à alimenter au fil de l'eau.
  - La date de réforme est une ESTIMATION calculée à partir d'un seuil d'âge
    configurable (7 ans par défaut — aucune règle officielle de réforme, ni
    kilométrage, ne m'a été communiquée) : toujours affichée comme suggestion
    modifiable, jamais comme une date officielle. Elle reste éditable
    véhicule par véhicule dans le registre.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------
# Référentiels réels
# ---------------------------------------------------------------------
ENTITES_PARC = [
    "Direction (siège)",
    "Antenne Nord / Extrême-Nord / Adamaoua",
    "Antenne Akonolinga (Centre / Sud / Est)",
    "Antenne Nord-Ouest",
    "Antenne Limbé",
]

EQUIPE_NON_AFFECTEE = "(non affecté à une équipe)"

TYPE_NON_RENSEIGNE = "(non renseigné)"
TYPES_VEHICULE_SUGGERES = ["Pick-up / 4x4", "Berline", "Camion", "Bus / Minibus", "Moto", "Autre"]
TYPES_VEHICULE_OPTIONS = [TYPE_NON_RENSEIGNE] + TYPES_VEHICULE_SUGGERES

STATUTS_OPERATIONNELS = ["En service", "En panne", "En réforme", "Réformé / sorti du parc"]

SEUIL_AGE_REFORME_DEFAUT_ANS = 7
FENETRE_ALERTE_REFORME_DEFAUT_MOIS = 12
INTERVALLE_VIDANGE_DEFAUT_MOIS = 6

TYPES_EVENEMENT = ["Plein de carburant", "Vidange", "Entretien / réparation", "Panne", "Autre"]

REGISTER_COLUMNS = [
    "ID véhicule", "Entité propriétaire", "Rubrique source", "Équipe affectée",
    "N° de plaque", "Marque", "Type de véhicule", "Année de mise en service",
    "Date d'acquisition (précise)", "Chauffeur attitré", "Statut opérationnel",
    "Date de réforme (retenue)", "Notes",
]

JOURNAL_COLUMNS = [
    "ID véhicule", "Date", "Type d'événement", "Quantité carburant (L)",
    "Kilométrage au compteur (km)", "Coût (FCFA)", "Chauffeur", "Notes",
]

# ---------------------------------------------------------------------
# Données réelles du fichier source — recopiées telles quelles.
# ---------------------------------------------------------------------
_SEED_VEHICULES: list[dict] = [
    {"Entité propriétaire": ENTITES_PARC[0], "Rubrique source": "Parc courant", "N° (fichier source)": 1,
     "N° de plaque": "CE 747 NG", "Marque": "PEUGEOT", "Année de mise en service": None},
    {"Entité propriétaire": ENTITES_PARC[0], "Rubrique source": "Parc courant", "N° (fichier source)": 2,
     "N° de plaque": "CE 208 PL", "Marque": "HILUX", "Année de mise en service": None},
    {"Entité propriétaire": ENTITES_PARC[0], "Rubrique source": "Parc courant", "N° (fichier source)": 3,
     "N° de plaque": "CE 373 OX", "Marque": "HILUX", "Année de mise en service": None},
    {"Entité propriétaire": ENTITES_PARC[0], "Rubrique source": "Maîtrise d'œuvre publique", "N° (fichier source)": 1,
     "N° de plaque": "CE 748 PO", "Marque": "L200", "Année de mise en service": 2024},
    {"Entité propriétaire": ENTITES_PARC[0], "Rubrique source": "Maîtrise d'œuvre publique", "N° (fichier source)": 2,
     "N° de plaque": "CE", "Marque": "L200", "Année de mise en service": 2024},
    {"Entité propriétaire": ENTITES_PARC[0], "Rubrique source": "Maîtrise d'œuvre publique", "N° (fichier source)": 3,
     "N° de plaque": "CE", "Marque": "L200", "Année de mise en service": 2024},
    {"Entité propriétaire": ENTITES_PARC[0], "Rubrique source": "Maîtrise d'œuvre publique", "N° (fichier source)": 4,
     "N° de plaque": "CE", "Marque": "L200", "Année de mise en service": 2024},
    {"Entité propriétaire": ENTITES_PARC[0], "Rubrique source": "Maîtrise d'œuvre publique", "N° (fichier source)": 5,
     "N° de plaque": "CE", "Marque": "L200", "Année de mise en service": 2024},
    {"Entité propriétaire": ENTITES_PARC[1], "Rubrique source": "Parc courant", "N° (fichier source)": 1,
     "N° de plaque": "CE 742 NG", "Marque": "PEUGEOT", "Année de mise en service": 2023},
    {"Entité propriétaire": ENTITES_PARC[1], "Rubrique source": "Parc courant", "N° (fichier source)": 2,
     "N° de plaque": "CE 702 NZ", "Marque": "HILUX", "Année de mise en service": 2024},
    {"Entité propriétaire": ENTITES_PARC[2], "Rubrique source": "Parc courant", "N° (fichier source)": 1,
     "N° de plaque": "CE 705 NZ", "Marque": "HILUX", "Année de mise en service": 2024},
    {"Entité propriétaire": ENTITES_PARC[3], "Rubrique source": "Parc courant", "N° (fichier source)": 1,
     "N° de plaque": "CE 703 NZ", "Marque": "HILUX", "Année de mise en service": 2024},
]

PLAQUES_INCOMPLETES = {"CE"}  # plaques réduites au seul préfixe régional dans le fichier source


def _seed_dataframe() -> pd.DataFrame:
    rows = []
    for i, v in enumerate(_SEED_VEHICULES, start=1):
        rows.append({
            "ID véhicule": f"VH-{i:03d}",
            "Entité propriétaire": v["Entité propriétaire"],
            "Rubrique source": v["Rubrique source"],
            "Équipe affectée": EQUIPE_NON_AFFECTEE,
            "N° de plaque": v["N° de plaque"],
            "Marque": v["Marque"],
            "Type de véhicule": TYPE_NON_RENSEIGNE,
            "Année de mise en service": v["Année de mise en service"],
            "Date d'acquisition (précise)": pd.NaT,
            "Chauffeur attitré": "",
            "Statut opérationnel": "En service",
            "Date de réforme (retenue)": pd.NaT,
            "Notes": "",
        })
    df = pd.DataFrame(rows, columns=REGISTER_COLUMNS)
    df["Année de mise en service"] = pd.to_numeric(df["Année de mise en service"], errors="coerce").astype("Int64")
    df["Date d'acquisition (précise)"] = pd.to_datetime(df["Date d'acquisition (précise)"])
    df["Date de réforme (retenue)"] = pd.to_datetime(df["Date de réforme (retenue)"])
    return df


def get_register() -> pd.DataFrame:
    if "vehicules_register" not in st.session_state:
        st.session_state["vehicules_register"] = _seed_dataframe()
    return st.session_state["vehicules_register"]


def set_register(df: pd.DataFrame) -> None:
    st.session_state["vehicules_register"] = df


def next_vehicule_id(df: pd.DataFrame) -> str:
    existing = set(df["ID véhicule"].astype(str)) if "ID véhicule" in df.columns else set()
    n = len(df) + 1
    while f"VH-{n:03d}" in existing:
        n += 1
    return f"VH-{n:03d}"


def empty_journal() -> pd.DataFrame:
    df = pd.DataFrame(columns=JOURNAL_COLUMNS)
    df["Date"] = pd.to_datetime(df["Date"])
    for c in ["Quantité carburant (L)", "Kilométrage au compteur (km)", "Coût (FCFA)"]:
        df[c] = pd.to_numeric(df[c])
    return df


def get_journal() -> pd.DataFrame:
    if "vehicules_journal" not in st.session_state:
        st.session_state["vehicules_journal"] = empty_journal()
    return st.session_state["vehicules_journal"]


def set_journal(df: pd.DataFrame) -> None:
    st.session_state["vehicules_journal"] = df


def equipe_options(equipes_rows: pd.DataFrame | None) -> list[str]:
    opts = [EQUIPE_NON_AFFECTEE]
    if equipes_rows is not None and not equipes_rows.empty and "Antenne" in equipes_rows.columns:
        opts += sorted(equipes_rows["Antenne"].dropna().unique())
    return opts


CHAUFFEUR_NON_DEFINI = "(aucun chauffeur désigné)"


def chauffeurs_reels_antenne(antenne: str | None, equipes_rows: pd.DataFrame | None) -> list[str]:
    """Chauffeurs RÉELS (agents RH, rôle « Chauffeur », statut OK) rattachés à
    cette antenne précise — jamais un nom inventé ou tapé librement. Une
    antenne non choisie, ou sans aucun chauffeur réel en poste, renvoie une
    liste vide."""
    if not antenne or equipes_rows is None or equipes_rows.empty:
        return []
    needed = {"Antenne", "Rôle", "Statut", "Nom"}
    if not needed.issubset(equipes_rows.columns):
        return []
    subset = equipes_rows[
        (equipes_rows["Antenne"] == antenne)
        & (equipes_rows["Rôle"].astype(str).str.strip() == "Chauffeur")
        & (equipes_rows["Statut"] == "OK")
    ]
    noms = subset["Nom"].dropna().astype(str).str.strip()
    noms = noms[noms != ""]
    return sorted(noms.unique())


def chauffeurs_deja_affectes(register: pd.DataFrame, exclude_vehicule_id: str | None = None) -> dict:
    """Carte {nom du chauffeur: ID véhicule} pour tous les véhicules déjà
    dotés d'un chauffeur attitré (hors le véhicule en cours de ré-affectation,
    s'il y en a un) — sert à garantir qu'un même agent n'est jamais désigné
    responsable de deux véhicules à la fois (« un agent ne peut se retrouver
    dans deux antennes »)."""
    out = {}
    if register is None or register.empty or "Chauffeur attitré" not in register.columns:
        return out
    for _, row in register.iterrows():
        vid = row.get("ID véhicule")
        if exclude_vehicule_id is not None and vid == exclude_vehicule_id:
            continue
        nom = str(row.get("Chauffeur attitré") or "").strip()
        if nom:
            out[nom] = vid
    return out


def chauffeurs_disponibles(antenne: str | None, equipes_rows: pd.DataFrame | None, register: pd.DataFrame,
                            exclude_vehicule_id: str | None = None) -> tuple[list, dict]:
    """Options de chauffeur à proposer pour une antenne donnée : les agents
    RÉELS de cette antenne (rôle Chauffeur, statut OK) qui ne conduisent pas
    déjà un autre véhicule. Renvoie (options disponibles, {chauffeurs déjà
    pris ailleurs dans cette antenne: ID véhicule}) pour pouvoir expliquer à
    l'utilisateur pourquoi la liste peut être vide ou réduite."""
    reels = chauffeurs_reels_antenne(antenne, equipes_rows)
    deja_pris = chauffeurs_deja_affectes(register, exclude_vehicule_id)
    dispo = [c for c in reels if c not in deja_pris]
    pris_dans_cette_antenne = {c: v for c, v in deja_pris.items() if c in reels}
    return dispo, pris_dans_cette_antenne


def chauffeurs_hors_antenne(register: pd.DataFrame, equipes_rows: pd.DataFrame | None) -> list:
    """Détecte les véhicules dont le chauffeur attitré n'est PAS un agent réel
    (rôle Chauffeur, statut OK) de l'équipe affectée du véhicule — typique
    d'une édition directe du tableau qui change l'équipe sans mettre à jour
    le chauffeur. Renvoie une liste de dicts {ID véhicule, Équipe affectée,
    Chauffeur attitré}."""
    out = []
    if register is None or register.empty:
        return out
    for _, row in register.iterrows():
        antenne = row.get("Équipe affectée")
        chauf = str(row.get("Chauffeur attitré") or "").strip()
        if not chauf or antenne == EQUIPE_NON_AFFECTEE:
            continue
        if chauf not in chauffeurs_reels_antenne(antenne, equipes_rows):
            out.append({"ID véhicule": row.get("ID véhicule"), "Équipe affectée": antenne,
                         "Chauffeur attitré": chauf})
    return out


def doublons_chauffeurs(register: pd.DataFrame) -> dict:
    """Détecte, dans le registre TEL QU'IL EST (y compris après une édition
    libre du tableau), tout chauffeur affecté à plusieurs véhicules à la fois
    — une incohérence à signaler, jamais à corriger silencieusement. Renvoie
    {nom du chauffeur: [ID véhicule, ...]} pour les seuls cas en doublon."""
    if register is None or register.empty or "Chauffeur attitré" not in register.columns:
        return {}
    par_chauffeur: dict = {}
    for _, row in register.iterrows():
        nom = str(row.get("Chauffeur attitré") or "").strip()
        if not nom:
            continue
        par_chauffeur.setdefault(nom, []).append(row.get("ID véhicule"))
    return {nom: vids for nom, vids in par_chauffeur.items() if len(vids) > 1}


def with_age_and_reforme(df: pd.DataFrame, seuil_age_ans: int) -> pd.DataFrame:
    """Ajoute les colonnes calculées : âge, date de réforme suggérée (à partir
    du seuil d'âge choisi dans l'appli) et statut de réforme. La date retenue
    manuellement par l'utilisateur prime toujours sur la suggestion."""
    out = df.copy()
    if out.empty:
        out["Âge (ans)"] = pd.Series(dtype="float64")
        out["Date de réforme suggérée (seuil actuel)"] = pd.Series(dtype="datetime64[ns]")
        out["Date de réforme (retenue ou suggérée)"] = pd.Series(dtype="datetime64[ns]")
        out["Statut réforme"] = pd.Series(dtype="object")
        return out

    annee_actuelle = date.today().year
    annee = pd.to_numeric(out["Année de mise en service"], errors="coerce")
    out["Âge (ans)"] = annee_actuelle - annee

    def _suggestion(a):
        if pd.isna(a):
            return pd.NaT
        return pd.Timestamp(year=int(a) + seuil_age_ans, month=1, day=1)

    out["Date de réforme suggérée (seuil actuel)"] = annee.apply(_suggestion)

    retenue = pd.to_datetime(out["Date de réforme (retenue)"], errors="coerce")
    suggeree = out["Date de réforme suggérée (seuil actuel)"]
    date_ref = retenue.where(retenue.notna(), suggeree)
    today_ts = pd.Timestamp(date.today())

    def _statut(d):
        if pd.isna(d):
            return "Non calculable (année inconnue)"
        delta_mois = (d.year - today_ts.year) * 12 + (d.month - today_ts.month)
        if delta_mois < 0:
            return "Échéance dépassée"
        if delta_mois <= FENETRE_ALERTE_REFORME_DEFAUT_MOIS:
            return "À surveiller (≤ 12 mois)"
        return "OK"

    out["Date de réforme (retenue ou suggérée)"] = date_ref
    out["Statut réforme"] = date_ref.apply(_statut)
    return out


def journal_summary(journal: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par véhicule ayant au moins un événement : carburant total,
    coût total, nombre de vidanges, dernière vidange, dernier kilométrage
    relevé — calculés uniquement à partir des événements saisis."""
    cols = ["ID véhicule", "Carburant total (L)", "Coût total (FCFA)",
            "Nb vidanges", "Dernière vidange", "Dernier kilométrage relevé"]
    if journal.empty:
        return pd.DataFrame(columns=cols)

    j = journal.copy()
    j["Date"] = pd.to_datetime(j["Date"], errors="coerce")

    carburant = j.groupby("ID véhicule")["Quantité carburant (L)"].sum(min_count=1)
    cout = j.groupby("ID véhicule")["Coût (FCFA)"].sum(min_count=1)
    vidanges = j[j["Type d'événement"] == "Vidange"]
    nb_vidanges = vidanges.groupby("ID véhicule").size()
    derniere_vidange = vidanges.groupby("ID véhicule")["Date"].max()
    km = j.dropna(subset=["Kilométrage au compteur (km)"]).sort_values("Date")
    dernier_km = km.groupby("ID véhicule")["Kilométrage au compteur (km)"].last()

    out = pd.DataFrame({
        "Carburant total (L)": carburant,
        "Coût total (FCFA)": cout,
        "Nb vidanges": nb_vidanges,
        "Dernière vidange": derniere_vidange,
        "Dernier kilométrage relevé": dernier_km,
    })
    out.index.name = "ID véhicule"
    return out.reset_index()


def besoins_par_equipe(register_view: pd.DataFrame, equipes_rows: pd.DataFrame | None) -> pd.DataFrame:
    """Compare, pour chaque antenne RÉELLE de la feuille RH, le nombre de
    véhicules qui lui sont affectés. Un simple repère de couverture (0 véhicule
    affecté = besoin potentiel à vérifier), PAS un calcul de dotation
    officielle — aucun ratio véhicules/agents officiel ne m'a été communiqué."""
    if equipes_rows is None or equipes_rows.empty or "Antenne" not in equipes_rows.columns:
        return pd.DataFrame(columns=["Antenne (RH)", "Véhicules affectés", "Agents (équipe)", "Repère"])

    antennes = sorted(equipes_rows["Antenne"].dropna().unique())
    agents_par_antenne = equipes_rows.groupby("Antenne").size()

    if register_view.empty:
        compte = pd.Series(dtype="int64")
    else:
        affectes = register_view[register_view["Équipe affectée"] != EQUIPE_NON_AFFECTEE]
        compte = affectes.groupby("Équipe affectée").size()

    rows = []
    for a in antennes:
        n_veh = int(compte.get(a, 0))
        n_agents = int(agents_par_antenne.get(a, 0))
        repere = "🔴 Aucun véhicule affecté" if n_veh == 0 else ("🟡 1 seul véhicule" if n_veh == 1 else "🟢 OK")
        rows.append({"Antenne (RH)": a, "Véhicules affectés": n_veh, "Agents (équipe)": n_agents, "Repère": repere})
    return pd.DataFrame(rows)
