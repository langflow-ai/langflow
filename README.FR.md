# [![Langflow](./docs/static/img/hero.png)](https://www.langflow.org)

<p align="center"><strong>
    Un Framework visuel pour créer des applications d'agent autonome et RAG
</strong></p>
<p align="center" style="font-size: 12px;">
    Open source, construit en Python, entièrement personnalisable, indépendant du modèle et de la base de données
</p>

<p align="center" style="font-size: 12px;">
    <a href="https://docs.langflow.org" style="text-decoration: underline;">Documentation</a> -
    <a href="https://discord.com/invite/EqksyE2EX9" style="text-decoration: underline;">Rejoignez notre Discord</a> -
    <a href="https://twitter.com/langflow_ai" style="text-decoration: underline;">Suivez-nous sur X</a> -
    <a href="https://huggingface.co/spaces/Langflow/Langflow" style="text-decoration: underline;">Démonstration</a>
</p>

<p align="center">
    <a href="https://github.com/langflow-ai/langflow">
        <img src="https://img.shields.io/github/stars/langflow-ai/langflow">
    </a>
    <a href="https://discord.com/invite/EqksyE2EX9">
        <img src="https://img.shields.io/discord/1116803230643527710?label=Discord">
    </a>
</p>

<div align="center">
  <a href="./README.md"><img alt="README en Anglais" src="https://img.shields.io/badge/English-d9d9d9"></a>
  <a href="./README.PT.md"><img alt="README en Portuguais" src="https://img.shields.io/badge/Português-d9d9d9"></a>
  <a href="./README.ES.md"><img alt="README en Espagnol" src="https://img.shields.io/badge/Español-d9d9d9"></a>
  <a href="./README.zh_CN.md"><img alt="README en Chinois Simplifié" src="https://img.shields.io/badge/简体中文-d9d9d9"></a>
  <a href="./README.ja.md"><img alt="README en Japonais" src="https://img.shields.io/badge/日本語-d9d9d9"></a>
  <a href="./README.KR.md"><img alt="README en Coréen" src="https://img.shields.io/badge/한국어-d9d9d9"></a>
  <a href="./README.FR.md"><img alt="README en Français" src="https://img.shields.io/badge/Français-d9d9d9"></a>
</div>

<!-- 
<p align="center">
  <img src="./docs/static/img/langflow_basic_howto.gif" alt="Tu GIF" style="border: 3px solid #211C43;">
</p> -->

# 📝 Contenu

- [](#)
- [📝 Contenu](#-contenu)
- [📦 Démarrage](#-démarrage)
- [🎨 Créer des flux](#-créer-des-flux)
- [Déploiement](#déploiement)
  - [Déploiement à l'aide de Google Cloud Platform](#déploiement-à-laide-de-google-cloudplatform)
  - [Déploiement sur Railway](#déploiement-sur-railway)
  - [Déployer sur Render](#déployer-sur-render)
- [🖥️ Interface de Ligne de Commandes (CLI)](#️-interface-de-ligne-de-commandes-cli)
  - [Usage](#usage)
    - [Variables d'environnement](#variables-denvironnement)
- [👋 Contribuer](#-contribuer)
- [🌟 Contributeurs](#-contributeurs)
- [📄 Licence](#-licence)

# 📦 Démarrage

Vous pouvez installer Langflow avec pip:

```shell
# Assurez-vous que >=Python 3.10 est installé sur votre système.
# Installez la version préliminaire (recommandée pour les mises à jour les plus récentes)
python -m pip install langflow --pre --force-reinstall

# ou version stable
python -m pip install langflow -U
```

Ensuite, exécutez Langflow avec:

```shell
python -m langflow run
```

Vous pouvez également voir Langflow sur [HuggingFace Spaces](https://huggingface.co/spaces/Langflow/Langflow). [Clonez le 'Space' en utilisant ce lien](https://huggingface.co/spaces/Langflow/Langflow?duplicate=true) pour créer votre propre espace de travail Langflow en quelques minutes.

# 🎨 Créer des flux

Créer des flux avec Langflow est simple. Faites simplement glisser les composants de la barre latérale vers l'espace de travail et connectez-les pour commencer à créer votre application.

Explorez en modifiant les paramètres d'invite, en regroupant les composants et en créant vos propres composants personnalisés.

Lorsque vous avez terminé, vous pouvez exporter votre flux sous forme de fichier JSON.

Charger le flux avec:

```python
from langflow.load import run_flow_from_json

results = run_flow_from_json("chemin/vers/fichier.json", input_value="Hello, World!")
```

# Déploiement

## Déploiement à l'aide de Google Cloud Platform

Suivez notre guide étape par étape pour déployer Langflow sur Google Cloud Platform (GCP) à l'aide de Google Cloud Shell. Le guide est disponible dans le document [**Langflow sur Google Cloud Platform**](https://github.com/langflow-ai/langflow/blob/dev/docs/docs/deployment/gcp-deployment.md).

Vous pouvez également cliquer sur le bouton **"Ouvrir dans Cloud Shell"** ci-dessous pour lancer Google Cloud Shell, cloner le dépôt Langflow et commencer un **tutoriel interactif** qui vous guidera tout au long du processus de configuration des ressources et du déploiement de Langflow dans votre projet GCP.

[![Ouvrir dans Cloud Shell](https://gstatic.com/cloudssh/images/open-btn.svg)](https://console.cloud.google.com/cloudshell/open?git_repo=https://github.com/langflow-ai/langflow&working_dir=scripts/gcp&shellonly=true&tutorial=walkthroughtutorial_spot.md)

## Déploiement sur Railway

Utilisez ce modèle pour déployer Langflow 1.0 Preview sur Railway:

[![Déployer la version préliminaire 1.0 sur sur Railway](https://railway.app/button.svg)](https://railway.app/template/UsJ1uB?referralCode=MnPSdg)

Ou ceci pour déployer Langflow 0.6.x:

[![Déployer sur Railway](https://railway.app/button.svg)](https://railway.app/template/JMXEWp?referralCode=MnPSdg)

## Déployer sur Render

<a href="https://render.com/deploy?repo=https://github.com/langflow-ai/langflow/tree/dev">
<img src="https://render.com/images/deploy-to-render-button.svg" alt="Déployer sur Render" />
</a>

# 🖥️ Interface de Ligne de Commandes (CLI)

Langflow fournit une interface de ligne de commandes (CLI) pour une gestion et une configuration faciles.

## Usage

Vous pouvez exécuter Langflow à l'aide de la commande suivante :

```shell
langflow run [OPTIONS]
```

Chaque option est détaillée ci-dessous :

- `--help`: affiche toutes les options disponibles.
- `--host`: définit l'hôte auquel lier le serveur. Il peut être défini à l'aide de la variable d'environnement `LANGFLOW_HOST`. La valeur par défaut est `127.0.0.1`.
- `--workers`: définit le nombre de processus. Il peut être défini à l'aide de la variable d'environnement `LANGFLOW_WORKERS`. La valeur par défaut est `1`.
- `--worker-timeout`: définit le délai d'expiration du travailleur en secondes. La valeur par défaut est `60`.
- `--port`: Définit le port sur lequel écouter. Il peut être défini à l'aide de la variable d'environnement `LANGFLOW_PORT`. La valeur par défaut est `7860`.
- `--env-file`: Spécifie le chemin d'accès au fichier .env contenant les variables d'environnement. La valeur par défaut est `.env`.
- `--log-level`: définit le niveau de journalisation. Il peut être défini à l'aide de la variable d'environnement `LANGFLOW_LOG_LEVEL`. La valeur par défaut est `critique`.
- `--components-path`: Spécifie le chemin d'accès au répertoire contenant les composants personnalisés. Il peut être défini à l'aide de la variable d'environnement `LANGFLOW_COMPONENTS_PATH`. La valeur par défaut est `langflow/components`.
- `--log-file`: Spécifie le chemin d'accès au fichier journal. Il peut être défini à l'aide de la variable d'environnement `LANGFLOW_LOG_FILE`. La valeur par défaut est `logs/langflow.log`.
- `--cache`: Sélectionnez le type de cache à utiliser. Les options sont `InMemoryCache` et `SQLiteCache`. Il peut être défini à l'aide de la variable d'environnement `LANGFLOW_LANGCHAIN_CACHE`. La valeur par défaut est `SQLiteCache`.
- `--dev/--no-dev`: basculer en mode développement. La valeur par défaut est `no-dev`.
- `--path`: Spécifie le chemin d'accès au répertoire frontend contenant les fichiers de build. Cette option est uniquement destinée à des fins de développement. Il peut être défini à l'aide de la variable d'environnement `LANGFLOW_FRONTEND_PATH`.
- `--open-browser/--no-open-browser`: activez l'option permettant d'ouvrir le navigateur après le démarrage du serveur. Il peut être défini à l'aide de la variable d'environnement `LANGFLOW_OPEN_BROWSER`. La valeur par défaut est `open-browser`.
- `--remove-api-keys/--no-remove-api-keys`: active l'option permettant de supprimer les clés API des projets enregistrés dans la base de données. Il peut être défini à l'aide de la variable d'environnement `LANGFLOW_REMOVE_API_KEYS`. La valeur par défaut est `no-remove-api-keys`.
- `--install-completion [bash|zsh|fish|powershell|pwsh]`: installe l'auto-complétion pour le shell spécifié.
- `--show-completion [bash|zsh|fish|powershell|pwsh]`: affiche le code d'auto-complétion pour le shell spécifié, vous permettant de copier ou de personnaliser l'installation.
- `--backend-only`: Ce paramètre, avec la valeur par défaut `False`, permet d'exécuter uniquement le serveur backend sans le frontend. Il peut également être défini à l'aide de la variable d'environnement `LANGFLOW_BACKEND_ONLY`.
- `--store`: Ce paramètre, avec la valeur par défaut `True`, active les fonctions de magasin, utilisez `--no-store` pour les désactiver. Il peut être défini à l'aide de la variable d'environnement `LANGFLOW_STORE`.

Ces paramètres sont importants pour les utilisateurs qui ont besoin de personnaliser le comportement de Langflow, en particulier dans des scénarios de développement ou de déploiement spécialisés.

### Variables d'environnement

Vous pouvez configurer de nombreuses options du CLI à l'aide de variables d'environnement. Ceux-ci peuvent être exportés dans votre système d'exploitation ou ajoutés à un fichier `.env` et chargés à l'aide de l'option `--env-file`.

Un exemple de fichier `.env` appelé `.env.example` est inclus dans le projet. Copiez ce fichier dans un nouveau fichier appelé `.env` et remplacez les exemples de valeurs par vos paramètres réels. Si vous définissez des valeurs à la fois dans votre système d'exploitation et dans le fichier `.env`, les paramètres `.env` auront la priorité.

# 👋 Contribuer

Nous acceptons les contributions de développeurs de tous niveaux pour notre projet open source sur GitHub. Si vous souhaitez contribuer, veuillez consulter nos [directives de contribution](./CONTRIBUTING.md) et contribuer à rendre Langflow plus accessible.

---

[![Historique des étoiles](https://api.star-history.com/svg?repos=langflow-ai/langflow&type=Timeline)](https://star-history.com/#langflow-ai/langflow&Date)

# 🌟 Contributeurs

[![contributeurs de langflow](https://contrib.rocks/image?repo=langflow-ai/langflow)](https://github.com/langflow-ai/langflow/graphs/contributors)

# 📄 Licence

Langflow est publié sous licence MIT. Consultez le fichier [LICENSE](LICENSE) pour plus de détails.
