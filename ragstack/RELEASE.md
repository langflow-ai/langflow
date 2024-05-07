# Release RAGStack Langflow packages

The main package `ragstack-ai-langflow` depends on `ragstack-ai-langflow-base` and the version is pinned.
This implies that every release of `ragstack-ai-langflow-base` will also need a release of `ragstack-ai-langflow`.

## Release `ragstack-ai-langflow-base`

- Run the release script:
  ```shell
  ./ragstack/ragstack-release.sh 0.0.2 ragstack-ai-langflow-base
  ```
  The script will take care of updating the version in `ragstack-ai-langflow-base` and pushing the changes to the repository. CI will automatically release the package on PyPI.

## Release `ragstack-ai-langflow`

- Update the `pyproject.toml` file pointing to the correct version of `ragstack-ai-langflow-base`. Run `poetry lock` and open a PR to trigger the tests. Once merged, proceed with the next steps.
- Run the release script:
  ```shell
  ./ragstack/ragstack-release.sh 0.0.2 ragstack-ai-langflow
  ```
  The script will take care of updating the version in `ragstack-ai-langflow` and pushing the changes to the repository. CI will automatically release the package on PyPI.
