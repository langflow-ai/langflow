# helm chart

This is the helm chart for RAGStack LangFlow. Postgres is a dependent chart but optional.

## how to install

```
cd ragstack/deploy/kubernetes/helm

helm dependency update ./langflow

kubectl create namespace langflow

helm install --dry-run langflow ./langflow --values ./langflow/values.yaml

helm install --namespace langflow --debug langflow ./langflow --values ./langflow/values.yaml

helm upgrade langflow ./langflow --values ./langflow/values.yaml --namespace langflow --debug
```
