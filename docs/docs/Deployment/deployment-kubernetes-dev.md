---
title: Deploy Langflow Dev Environment on Kubernetes
slug: /deployment-kubernetes-dev
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

## Setting up Langflow Development environment  

Helm chart is available to deploy [Langflow Integrated Development Environment (IDE)](https://github.com/langflow-ai/langflow-helm-charts/blob/main/charts/langflow-ide) and should be used for setting up the **Langflow Development environment**.

The `langflow-ide` Helm chart is designed to provide a complete environment for developers to create, test, and debug their flows. It includes both the API and the UI.

```shell
helm repo add langflow https://langflow-ai.github.io/langflow-helm-charts
helm repo update
helm install langflow-ide langflow/langflow-ide -n langflow --create-namespace
```

You can install the Langflow IDE Helm chart for Langflow as an IDE with persistent storage or an external database (for example PostgreSQL).

### Sample Deployment 
#### Prerequisites

- A [Kubernetes](https://kubernetes.io/docs/setup/) cluster
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

#### Install the Langflow IDE Helm chart

1. Add the repository to Helm and update it.

	```shell
	helm repo add langflow https://langflow-ai.github.io/langflow-helm-charts
	helm repo update
	```

2. Install Langflow with the default options in the `langflow` namespace.

	```shell
	helm install langflow-ide langflow/langflow-ide -n langflow --create-namespace
	```

3. Check the status of the pods

	```shell
	kubectl get pods -n langflow
	```


	```shell
	NAME                                 READY   STATUS    RESTARTS       AGE
	langflow-0                           1/1     Running   0              33s
	langflow-frontend-5d9c558dbb-g7tc9   1/1     Running   0              38s
	```

#### Configure port forwarding to access Langflow

Enable local port forwarding to access Langflow from your local machine.

1. To make the Langflow API accessible from your local machine at port 7860:
```shell
kubectl port-forward -n langflow svc/langflow-service-backend 7860:7860
```

2. To make the Langflow UI accessible from your local machine at port 8080:
```shell
kubectl port-forward -n langflow svc/langflow-service 8080:8080
```

Now you can access:
- The Langflow API at `http://localhost:7860`
- The Langflow UI at `http://localhost:8080`


### Deploy a specific Langflow version in Development environment

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

### Configure External storage for Development environment 

By default, the chart deploys a [SQLite](https://www.sqlite.org/docs.html) database stored in a local persistent disk. If you want to use an external [PostgreSQL](https://www.pgadmin.org/download/) database, you can configure it in two ways:

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

### Scaling Development Environment 

You have the option to scale the number of `replicas` and `resources` for both **frontend** and **backend** services.

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
You can scale the Langflow development environment either Horizontally or Vertically to add more resources to the flows container by modifying [values.yaml](https://github.com/langflow-ai/langflow-helm-charts/blob/main/charts/langflow-ide/values.yaml) file.

* Horizontal scaling adds more replicas of the deployment  
* Vertical scaling adds more CPU/memory resources to the deployment

#### Scale horizontally

To scale horizontally you only need to modify the `replicaCount` parameter in the chart.

```yaml
replicaCount: 1
```

Please note that if your flow relies on shared state (e.g. builtin chat memory), you will need to set up a shared database.

#### Scale vertically 

To scale the Langflow Dev application vertically by increasing the resources for the pods, change the `resources` values in the [values.yaml](https://github.com/langflow-ai/langflow-helm-charts/blob/main/charts/langflow-ide/values.yaml) file.

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


More Examples of `langflow-ide` deployment are available [here](https://github.com/langflow-ai/langflow-helm-charts/tree/main/examples/langflow-ide) in the examples directory.
