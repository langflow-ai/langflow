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

- Update the `ragstack-ai-langflow-base` version under the `[tool.poetry.dependencies]` in the `pyproject.toml` file.
- Run `poetry lock --no-update` and open a PR to trigger the tests. Once merged, proceed with the next steps.
- Run the release script:
  ```shell
  ./ragstack/ragstack-release.sh 0.0.2 ragstack-ai-langflow
  ```
  The script will take care of updating the version in `ragstack-ai-langflow` and pushing the changes to the repository. CI will automatically release the package on PyPI.

### Error

You can re-run the release job for this error. It's because the size of the package sometime cannot be uploaded properly.

```
 - Uploading ragstack_ai_langflow-0.0.5-py3-none-any.whl 100%
HTTP Error 400: The digest supplied does not match a digest calculated from the uploaded file. | b'<html>\n <head>\n  <title>400 The digest supplied does not match a digest calculated from the uploaded file.\n \n <body>\n  <h1>400 The digest supplied does not match a digest calculated from the uploaded file.\n  The server could not comply with the request since it is either malformed or otherwise incorrect.<br/><br/>\nThe digest supplied does not match a digest calculated from the uploaded file.\n\n\n \n'
```
