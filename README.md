# Analyse de Parties d'Échecs Amateurs

Ce projet vise à analyser les moments de "craquage" dans les parties d'échecs amateurs (Elo < 1500) en utilisant les données de Lichess.

## Fonctionnalités
- **Environnement Docker** : Tout le projet tourne dans un conteneur isolé avec Python 3.10 et les librairies de Data Science nécessaires.
- **Streaming de Données** : Script `fetch_data.py` capable de lire les dumps massifs de Lichess en streaming (sans téléchargement complet) pour extraire uniquement les parties pertinentes.
- **Filtres** : Sélection des parties selon l'Elo (< 1500) et présence d'analyse machine (`%eval`).

## Utilisation

### Pré-requis
- Docker & Docker Compose

### Lancement
1.  Construire l'image :
    ```bash
    docker compose build
    ```
2.  Lancer le conteneur :
    ```bash
    docker compose up -d
    ```
3.  Lancer le script de récupération :
    ```bash
    docker compose run app python src/fetch_data.py
    ```
