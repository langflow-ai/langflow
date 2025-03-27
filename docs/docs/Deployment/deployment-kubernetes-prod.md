---
title: Deploy Langflow Prod Environment on Kubernetes
slug: /deployment-kubernetes-prod
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

## Setting up Langflow Production environment 

Helm chart is available for [Langflow Runtime](https://github.com/langflow-ai/langflow-helm-charts/blob/main/charts/langflow-runtime) and should be used for setting up the **Langflow Production** environment.

The [Langflow Runtime](https://github.com/langflow-ai/langflow-helm-charts/blob/main/charts/langflow-runtime) chart is tailored for deploying applications in a production environment. It is focused on stability, performance, isolation and security to ensure that applications run reliably and efficiently.

### Sample Deployment 

#### Prerequisites

- A [Kubernetes](https://kubernetes.io/docs/setup/) server
- [kubectl](https://kubernetes.io/docs/tasks/tools/#kubectl)
- [Helm](https://helm.sh/docs/intro/install/)

#### Prepare a Kubernetes cluster

This example uses [Minikube](https://minikube.sigs.k8s.io/docs/start/), but you can use any Kubernetes cluster.

1. Create a Kubernetes cluster on Minikube.

	```shell
	minikube start
	```

2. Set `kubectl` to use Minikube.

	```shell
	kubectl config use-context minikube
	```

#### Install the Langflow runtime Helm chart 

1. Add the repository to Helm and update it.

	```shell
	helm repo add langflow https://langflow-ai.github.io/langflow-helm-charts
	helm repo update
	```

2. Install the Langflow app with the default options in the `langflow` namespace.  
   1. If you have a created a [custom image with packaged flows](/deployment-docker#package-your-flow-as-a-docker-image), you can deploy Langflow by overriding the default [values.yaml](https://github.com/langflow-ai/langflow-helm-charts/blob/main/charts/langflow-runtime/values.yaml) file with the `--set` flag.
      1. Use a custom image with bundled flows:

    ```shell
    helm install my-langflow-app langflow/langflow-runtime -n langflow --create-namespace --set image.repository=myuser/langflow-hello-world --set image.tag=1.0.0
    ```

      2. Alternatively, install the chart and download the flows from a URL with the `--set` flag:


    ```shell
    helm install my-langflow-app-with-flow langflow/langflow-runtime \
    -n langflow \
    --create-namespace \
    --set'downloadFlows.flows[0].url=https://raw.githubusercontent.com/langflow-ai/langflow/dev/tests/data/basic_example.json'
    ```
    :::important
    You may need to escape the square brackets in this command if you are using a shell that requires it:

    ```shell
    helm install my-langflow-app-with-flow langflow/langflow-runtime \
    -n langflow \
    --create-namespace \
    --set 'downloadFlows.flows\[0\].url=https://raw.githubusercontent.com/langflow-ai/langflow/dev/tests/data/basic_example.json'
    ```
    :::

3. Check the status of the pods.

```shell
kubectl get pods -n langflow
```

#### Access the Langflow app API 

1. Get your service name.

```shell
kubectl get svc -n langflow
```

The service name is your release name followed by `-langflow-runtime`. For example, if you used `helm install my-langflow-app-with-flow` the service name is `my-langflow-app-with-flow-langflow-runtime`.

2. Enable port forwarding to access Langflow from your local machine:

```shell
kubectl port-forward -n langflow svc/my-langflow-app-with-flow-langflow-runtime 7860:7860
```

3. Confirm you can access the API at `http://localhost:7860/api/v1/flows/` and view a list of flows.

```shell
curl -v http://localhost:7860/api/v1/flows/
```
4. Execute the packaged flow.

The following command gets the first flow ID from the flows list and runs the flow.

```shell
# Get flow ID
id=$(curl -s "http://localhost:7860/api/v1/flows/" | jq -r '.[0].id')

# Run flow
curl -X POST \
    "http://localhost:7860/api/v1/run/$id?stream=false" \
    -H 'Content-Type: application/json' \
    -d '{
      "input_value": "Hello!",
      "output_type": "chat",
      "input_type": "chat"
    }'
```

### Deploy a specific Langflow version in Production environment

Langflow is deployed with the `latest` version by default.

To change the Langflow version or use a custom docker image, you can modify the `image` parameter in the the [values.yaml](https://github.com/langflow-ai/langflow-helm-charts/blob/main/charts/langflow-runtime/values.yaml) file.

```yaml
image:
  repository: "langflowai/langflow-backend"
  tag: 1.x.y
```

### Secrets Management in Production 

The recommended way to set sensitive information is to use **Kubernetes secrets.** 

The `env` section in the [values.yaml](https://github.com/langflow-ai/langflow-helm-charts/blob/main/charts/langflow-runtime/values.yaml) file allows you to set environment variables for the Langflow deployment. 

#### Using values.yaml

You can reference a secret in the [values.yaml](https://github.com/langflow-ai/langflow-helm-charts/blob/main/charts/langflow-runtime/values.yaml) file by using the valueFrom key.

```yaml
env:
  - name: OPENAI_API_KEY
    valueFrom:
      secretKeyRef:
        name: langflow-secrets
        key: openai-key
  - name: ASTRA_DB_APPLICATION_TOKEN
    valueFrom:
      secretKeyRef:
        name: langflow-secrets
        key: astra-token
```

where:

* `name`: refer to the environment variable name used by your flow.  
* `valueFrom.secretKeyRef.name`: refers to the kubernetes secret name.  
* `valueFrom.secretKeyRef.key`: refers to the key in the secret. 

#### Using Helm Commands

1. To create a matching secret with the above example you can use the following command:

```shell
kubectl create secret generic openai-credentials \
  --namespace langflow \
  --from-literal=OPENAI_API_KEY=sk...
```

2. Verify the secret exists. The result is encrypted.

```shell
kubectl get secrets -n langflow openai-credentials
```

3. Upgrade the Helm release to use the secret.

```shell
helm upgrade my-langflow-app-image langflow/langflow-runtime -n langflow \
  --reuse-values \
  --set "extraEnv[0].name=OPENAI_API_KEY" \
  --set "extraEnv[0].valueFrom.secretKeyRef.name=openai-credentials" \
  --set "extraEnv[0].valueFrom.secretKeyRef.key=OPENAI_API_KEY"
```

### Configure Logging 

Set the log level and other Langflow configurations in the [values.yaml](https://github.com/langflow-ai/langflow-helm-charts/blob/main/charts/langflow-runtime/values.yaml) file.

```yaml
env:
  - name: LANGFLOW_LOG_LEVEL
    value: "INFO"
```

### Scaling Production Environment 

You have the option to scale the Langflow production environment either Horizontally or Vertically to add more resources to the flows container.

* Horizontal scaling adds more replicas of the deployment  
* Vertical scaling adds more CPU/memory resources to the deployment

#### Scale horizontally

To scale horizontally you only need to modify the `replicaCount` parameter in the [values.yaml](https://github.com/langflow-ai/langflow-helm-charts/blob/main/charts/langflow-runtime/values.yaml) file.

```yaml
replicaCount: 5
```

Please note that if your flow relies on shared state (e.g. builtin chat memory), you will need to set up a shared database.

#### Scale vertically 

To scale the application vertically by increasing the resources for the pods, change the `resources` values in the [values.yaml](https://github.com/langflow-ai/langflow-helm-charts/blob/main/charts/langflow-runtime/values.yaml) file.

By default the deployment doesn't have any limits and it could consume all the node `resources`. In order to limit the available resources, you can modify the resources value:

```yaml
resources:
  limits:
    cpu: 100m
    memory: 128Mi
  requests:
    cpu: 100m
    memory: 128Mi
```




