---
title: Kubernetes
slug: /deployment-kubernetes
---



This guide will help you get Langflow up and running in Kubernetes cluster, including the following steps:

- Install [LangFlow as IDE](/deployment-kubernetes#langflow-ide) in a Kubernetes cluster (for development)
- Install [LangFlow as a standalone application](/deployment-kubernetes#langflow-runtime) in a Kubernetes cluster (for production runtime workloads)

## Langflow (IDE)

This solution is designed to provide a complete environment for developers to create, test, and debug their flows. It includes both the API and the UI.

The `langflow-ide` Helm chart is available in the [Langflow Helm Charts repository](https://github.com/langflow-ai/langflow-helm-charts/tree/main/charts/langflow-ide).

### Prerequisites

- [Kubernetes](https://kubernetes.io/docs/setup/) server
- [kubectl](https://kubernetes.io/docs/tasks/tools/#kubectl)
- [Helm](https://helm.sh/docs/intro/install/)

### Prepare a Kubernetes cluster


This example uses [Minikube](https://minikube.sigs.k8s.io/docs/start/), but you can use any Kubernetes cluster.

1. Create a Kubernetes cluster on Minikube.

	```text
	minikube start
	```

2. Set `kubectl` to use Minikube.

	```text
	kubectl config use-context minikube
	```


### Install the Langflow Helm chart

1. Add the repository to Helm and update it.

	```text
	helm repo add langflow https://langflow-ai.github.io/langflow-helm-charts
	helm repo update
	```

2. Install Langflow with the default options in the `langflow` namespace.

	```text
	helm install langflow-ide langflow/langflow-ide -n langflow --create-namespace
	```

3. Check the status of the pods

	```text
	kubectl get pods -n langflow
	```


	```text
	NAME                                 READY   STATUS    RESTARTS       AGE
	langflow-0                           1/1     Running   0              33s
	langflow-frontend-5d9c558dbb-g7tc9   1/1     Running   0              38s
	```


### Configure port forwarding to access Langflow

Enable local port forwarding to access Langflow from your local machine.

1. To make the Langflow API accessible from your local machine at port 7860:
```text
kubectl port-forward -n langflow svc/langflow-service-backend 7860:7860
```

2. To make the Langflow UI accessible from your local machine at port 8080:
```text
kubectl port-forward -n langflow svc/langflow-service 8080:8080
```

Now you can access:
- Langflow UI at `http://localhost:8080`
- Langflow API at `http://localhost:7860`


### Configure the Langflow version

Langflow is deployed with the `latest` version by default.

To specify a different Langflow version, set the `langflow.backend.image.tag` and `langflow.frontend.image.tag` values in the [values.yaml](https://github.com/langflow-ai/langflow-helm-charts/blob/main/charts/langflow-ide/values.yaml) file.


```yaml
langflow:
  backend:
    image:
      tag: "1.0.0a59"
  frontend:
    image:
      tag: "1.0.0a59"

```


### Configure external storage

By default, the chart will use a SQLite database stored in a local persistent disk.
If you want to use an external PostgreSQL database, you can configure it in two ways:

* Use the built-in PostgreSQL chart:
```yaml
postgresql:
  enabled: true
  auth:
    username: "langflow"
    password: "langflow-postgres"
    database: "langflow-db"
```

* Use an external database:
```yaml
postgresql:
  enabled: false

langflow:
  backend:
    externalDatabase:
      enabled: true
      driver:
        value: "postgresql"
      port:
        value: "5432"
      user:
        value: "langflow"
      password:
        valueFrom:
          secretKeyRef:
            key: "password"
            name: "your-secret-name"
      database:
        value: "langflow-db"
    sqlite:
      enabled: false
```


### Configure scaling

You can scale the number of replicas and resources for both frontend and backend services:

```yaml
langflow:
  backend:
    replicaCount: 1
    resources:
      requests:
        cpu: 0.5
        memory: 1Gi
      # limits:
      #   cpu: 0.5
      #   memory: 1Gi

  frontend:
    enabled: true
    replicaCount: 1
    resources:
      requests:
        cpu: 0.3
        memory: 512Mi
      # limits:
      #   cpu: 0.3
      #   memory: 512Mi
```

### Deploy on AWS EKS, Google GKE, or Azure AKS and other examples

Visit the [Langflow Helm Charts repository](https://github.com/langflow-ai/langflow-helm-charts) for more information.


## Langflow (Runtime)

The runtime chart is tailored for deploying applications in a production environment. It is focused on stability, performance, isolation, and security to ensure that applications run reliably and efficiently.

Using a dedicated deployment for a set of flows is fundamental in production environments to have granular resource control.

The `langflow-runtime` Helm chart is available in the [Langflow Helm Charts repository](https://github.com/langflow-ai/langflow-helm-charts/tree/main/charts/langflow-runtime).

### Prerequisites

- [Kubernetes](https://kubernetes.io/docs/setup/) server
- [kubectl](https://kubernetes.io/docs/tasks/tools/#kubectl)
- [Helm](https://helm.sh/docs/intro/install/)

### Install the Langflow runtime Helm chart

1. Add the repository to Helm.

```shell
helm repo add langflow https://langflow-ai.github.io/langflow-helm-charts
helm repo update
```

2. Install the Langflow app with the default options in the `langflow` namespace.

If you have a custom image with bundled flows, you can deploy Langflow with packaged flows by overriding the default [values.yaml](https://github.com/langflow-ai/langflow-helm-charts/blob/main/charts/langflow-runtime/values.yaml) file with the `-set` flag.

* Use a custom image with bundled flows:
```shell
helm install my-langflow-app langflow/langflow-runtime -n langflow --create-namespace --set image.repository=myuser/langflow-just-chat --set image.tag=1.0.0
```

* Alternatively, download the flows from a URL with the `-set` flag:
```shell
helm install my-langflow-app-with-flow langflow/langflow-runtime \
  -n langflow \
  --create-namespace \
  --set 'downloadFlows.flows[0].url=https://raw.githubusercontent.com/langflow-ai/langflow/dev/tests/data/basic_example.json'
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

### Access the Langflow app API

1. First, verify your services:
```shell
kubectl get svc -n langflow
```

The service name will be your release name followed by `-langflow-runtime`. For example:
- If you used `helm install my-langflow-app-with-flow ...` the service would be `my-langflow-app-with-flow-langflow-runtime`

2. Enable port forwarding to access Langflow from your local machine:

```shell
kubectl port-forward -n langflow svc/my-langflow-app-with-flow-langflow-runtime 7860:7860
```

Now you can access the API at http://localhost:7860/api/v1/flows and execute the flow:
```shell
id=$(curl -s "http://localhost:7860/api/v1/flows" | jq -r '.flows[0].id')
curl -X POST \\
    "http://localhost:7860/api/v1/run/$id?stream=false" \
    -H 'Content-Type: application/json'\\
    -d '{
      "input_value": "Hello!",
      "output_type": "chat",
      "input_type": "chat"
    }'
```

### Storage


In this case, storage is not needed as our deployment is stateless.


### Log level and Langflow configurations


You can set the log level and other Langflow configurations in the [values.yaml](https://github.com/langflow-ai/langflow-helm-charts/blob/main/charts/langflow-runtime/values.yaml) file.


```yaml
env:
  - name: LANGFLOW_LOG_LEVEL
    value: "INFO"

```


### Configure secrets and variables


To inject secrets and Langflow global variables, you can use the `secrets` and `env` sections in the [values.yaml](https://github.com/langflow-ai/langflow-helm-charts/blob/main/charts/langflow-runtime/values.yaml) file.


Let's say your flow uses a global variable which is a secret; when you export the flow as JSON, it's recommended to not include it.
When importing the flow in the Langflow runtime, you can set the global variable using the `env` section in the [values.yaml](https://github.com/langflow-ai/langflow-helm-charts/blob/main/charts/langflow-runtime/values.yaml) file.
Assuming you have a global variable called `openai_key_var`, you can read it directly from a secret:


```yaml
env:
  - name: openai_key_var
    valueFrom:
      secretKeyRef:
        name: openai-key
        key: openai-key

```


or directly from the values file (not recommended for secret values!):


```yaml
env:
  - name: openai_key_var
    value: "sk-...."

```


### Scaling

You can scale the number of replicas for the Langflow app by changing the `replicaCount` value in the [values.yaml](https://github.com/langflow-ai/langflow-helm-charts/blob/main/charts/langflow-runtime/values.yaml) file.


```yaml
replicaCount: 3

```


To scale vertically (increase the resources for the pods), you can set the `resources` values in the [values.yaml](https://github.com/langflow-ai/langflow-helm-charts/blob/main/charts/langflow-runtime/values.yaml) file.


```yaml
resources:
  requests:
    memory: "2Gi"
    cpu: "1000m"

```


