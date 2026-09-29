# Tableau de bord AER — Application Streamlit

Application de visualisation pour le classeur `Gestion_Parc_Solaire_AER2027_DASHBOARD.xlsx`
(parc solaire + ressources humaines terrain). Toutes les feuilles du classeur sont
exploitées : Dashboard, Antennes — Détail solaire, Données sites, Répartition par
antenne, Synthèse par région, Organigramme, Données - Équipes, Notes & méthodologie.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

## Lancement

```bash
streamlit run Home.py
```

L'application s'ouvre sur `http://localhost:8501`. Un fichier `data.xlsx` (le
tableau de bord AER) est fourni par défaut ; vous pouvez à tout moment charger un
autre classeur via le sélecteur de fichier dans la barre latérale, sur n'importe
quelle page.

## Structure du projet

```
Home.py                              Page d'accueil : KPI, grille des 16 équipes,
                                      plan d'action prioritaire, visualisations
pages/
  1_🗺️_Carte_électrification.py     Carte unique : sites, antennes, distances, charge de personnel
  2_🛰️_Parc_solaire.py              Dimensionnement par antenne + tableau des 499 sites
  3_👷_Équipes_terrain.py           Détail des équipes + personnel non affecté
  4_🌍_Répartition_régionale.py     Répartition par antenne / région / département
  5_🏢_Organigramme.py              Hiérarchie du réseau d'antennes (icicle chart)
  6_📝_Notes.py                     Notes & méthodologie (recherche plein texte)
utils/
  data.py                            Lecture et parsing du classeur (mise en cache)
  geo.py                             Distances (Haversine) et centroïdes d'antenne
  ui.py                              Composants d'interface & thème partagés
  loader.py                          Chargement du fichier, partagé entre les pages
data.xlsx                            Classeur AER fourni par défaut
```

## La carte d'électrification — ce qu'elle fait et ce qu'elle ne fait pas

C'est la page la plus riche de l'application, pensée pour rester honnête sur ce que
les données permettent réellement :

- **Sites** géolocalisés à leurs coordonnées GPS réelles, colorables par antenne,
  région ou phase, taille proportionnelle à la puissance, filtres combinables
  (antenne, région, phase, puissance, recherche par nom).
- **Antennes** affichées en losanges à leur **centroïde calculé** (barycentre des
  sites rattachés) — l'AER n'a pas fourni les coordonnées réelles du siège de
  chaque antenne dans ce classeur, donc l'application ne les invente pas et le
  dit explicitement dans l'encadré méthodologique de la page.
- **Hiérarchie du réseau** tracée entre antennes à partir de la colonne réelle
  « Rattachée à » de la feuille Antennes — Détail solaire.
- **Charge de personnel** : les antennes peuvent être colorées par leur ratio
  réel « sites / agent » pour repérer les zones les plus chargées.
- **Distances** : chaque site a sa distance orthodromique (Haversine, à vol
  d'oiseau — pas une distance routière) au centroïde de son antenne, plus un
  outil pour mesurer la distance entre deux sites choisis.
- **Ce qui n'est volontairement pas superposé** : le statut réel des 16 équipes
  terrain (feuille Données - Équipes) utilise un découpage par région qui ne
  correspond pas antenne pour antenne au découpage des sites — le mélanger sur
  la carte créerait un lien géographique faux. Cette donnée reste consultable
  sur la page « Équipes terrain », et la table de fréquence de visite du
  référentiel RH est quand même montrée en clair (non géolocalisée) sur la page
  carte, avec le même avertissement.

## Points de conception

- **Lecture robuste** : les tableaux sont localisés par recherche de titre de
  section plutôt que par numéro de ligne fixe — l'application continue de
  fonctionner si le classeur est régénéré avec quelques lignes en plus ou en moins.
- **Valeurs calculées** : le classeur est lu avec les valeurs mises en cache par
  Excel/LibreOffice (`data_only=True`). Si vous fournissez un fichier dont les
  formules n'ont jamais été recalculées (édité uniquement par un script sans
  ouverture dans Excel/LibreOffice), pensez à l'ouvrir et l'enregistrer une fois
  dans Excel, ou à le convertir via `soffice --headless --convert-to xlsx`.
- **Mise en cache** : `@st.cache_data` sur le parsing, `@st.cache_resource` sur le
  classeur ouvert — changer de fichier ou de filtre ne relit pas tout depuis zéro.
- **Couleurs** : la palette reprend celle du classeur Excel (navy / bleu / or /
  vert / rouge / ambre) pour une cohérence visuelle totale entre le fichier Excel
  et l'application.

## Déploiement

Le projet est prêt pour [Streamlit Community Cloud](https://streamlit.io/cloud) :
poussez ce dossier sur un dépôt Git et pointez le déploiement vers `Home.py`.
