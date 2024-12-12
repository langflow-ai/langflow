> [!WARNING]
> Tout les liens externes sont susceptibles d'être en anglais.

# Contribuer à Langflow

Ce guide est destiné à vous aider à commencer à contribuer à Langflow.
En tant que projet open source dans un domaine en développement rapide, nous sommes extrêmement ouverts aux contributions, que ce soit sous la forme d'une nouvelle fonctionnalité, d'une infrastructure améliorée ou d'une meilleure documentation.

Pour contribuer à ce projet, veuillez suivre le flux de travail [fork et pull request](https://docs.github.com/en/get-started/quickstart/contributing-to-projects).

## Signaler des bugs ou suggérer des améliorations

Notre page [GitHub issues](https://github.com/langflow-ai/langflow/issues) est mise à jour
avec les bugs, les améliorations et les demandes de fonctionnalités. Il existe une taxonomie d'étiquettes pour aider au tri et à la découverte des problèmes qui vous intéressent. [Voir cette page](https://github.com/langflow-ai/langflow/labels) pour un aperçu
du système que nous utilisons pour étiqueter nos problèmes et nos pull requests.

Si vous avez besoin d'aide pour votre code, pensez à poster une question sur le
[tableau de discussion GitHub](https://github.com/langflow-ai/langflow/discussions). Veuillez
comprendre que nous ne pourrons pas fournir d'assistance individuelle par e-mail. Nous
pensons également que l'aide est bien plus précieuse si elle est **partagée publiquement**,
afin que davantage de personnes puissent en bénéficier.

- **Décrivez votre problème :** Essayez de fournir autant de détails que possible. Qu'est-ce qui
ne va pas exactement ? _Comment_ cela échoue-t-il ? Y a-t-il une erreur ?
"XY ne fonctionne pas" n'est généralement pas très utile pour détecter les problèmes. N'oubliez jamais d'inclure le code que vous avez exécuté et, si possible, d'extraire uniquement les
parties pertinentes et ne vous contentez pas de vider l'intégralité de votre script. Cela nous permettra de reproduire plus facilement l'erreur.

- **Partage de longs blocs de code ou de journaux :** si vous devez inclure du code long,
des journaux ou des traces, vous pouvez les encapsuler dans `<details>` et `</details>`. Cela
[réduit le contenu](https://developer.mozilla.org/en/docs/Web/HTML/Element/details)
afin qu'il ne devienne visible qu'au clic, ce qui rend le problème plus facile à lire et à suivre.

## Contribution au code et à la documentation

Vous pouvez développer Langflow localement via uv + NodeJS.

### Cloner le référentiel Langflow

Accédez au [référentiel GitHub Langflow](https://github.com/langflow-ai/langflow) et appuyez sur « Fork » dans le coin supérieur droit.

Ajoutez la nouvelle branche à votre référentiel local sur votre machine locale :

```bash
git remote add fork https://github.com/<your username>/langflow.git
```

Nous fournissons également un fichier .vscode/launch.json pour déboguer le backend dans VSCode, ce qui est beaucoup plus rapide que d'utiliser docker compose.

### Préparez l'environnement

Configuration des hooks :

```bash
make init
```

Cela configurera l'environnement de développement en installant les dépendances backend et frontend, en créant les fichiers statiques frontend et en initialisant le projet. Il exécute `make install_backend`, `make install_frontend`, `make build_frontend` et enfin `uv run langflow run` pour démarrer l'application.

Il est conseillé d'exécuter `make lint`, `make format` et `make unit_tests` avant de pousser vers le référentiel.

### Exécuter localement (uv et Node.js)

Langflow peut s'exécuter localement en clonant le référentiel et en installant les dépendances. Nous vous recommandons d'utiliser un environnement virtuel pour isoler les dépendances de votre système.

Avant de commencer, assurez-vous que les éléments suivants sont installés :

- uv (>=0.4)
- Node.js

Ensuite, dans le dossier racine, installez les dépendances et démarrez le serveur de développement pour le backend :

```bash
make backend
```

Et le frontend :

```bash
make frontend
```

### Exécuter la documentation

La documentation est créée à l'aide de [Docusaurus](https://docusaurus.io/). Pour exécuter la documentation localement, exécutez les commandes suivantes :

```bash
cd docs
npm install
npm run start
```

La documentation sera disponible dans `localhost:3000` et tous les fichiers se trouvent dans le dossier `docs/docs`.

## Ouverture d'une pull request

Une fois que vous avez écrit et testé manuellement votre modification, vous pouvez commencer à envoyer le correctif au référentiel principal.

- Ouvrez une nouvelle pull request GitHub avec le correctif sur la branche `main`.
- Assurez-vous que le titre de la pull request respecte les conventions de validation sémantique.
  - Par exemple, `feat : add new feature`, `fix : correct issue with X`.
- Assurez-vous que la description de la demande d'extraction décrit clairement le problème et la solution. Incluez le numéro de problème pertinent, le cas échéant.

> [!IMPORTANT]
> Votre pull request doit être écrite en anglais afin que les développeurs puissent la traiter.