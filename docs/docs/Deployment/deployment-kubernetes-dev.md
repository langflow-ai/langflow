---
title: Deploy the Langflow development environment on Kubernetes
slug: /deployment-kubernetes-dev
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

The [Langflow Integrated Development Environment (IDE)](https://github.com/langflow-ai/langflow-helm-charts/tree/main/charts/langflow-ide) Helm chart is designed to provide a complete environment for developers to create, test, and debug their flows. It includes both the API and the UI.

### Prerequisites

- A [Kubernetes](https://kubernetes.io/docs/setup/) cluster
- [kubectl](https://kubernetes.io/docs/tasks/tools/#kubectl)
- [Helm](https://helm.sh/docs/intro/install/)

### Prepare a Kubernetes cluster

This example uses [Minikube](https://minikube.sigs.k8s.io/docs/start/), but you can use any Kubernetes cluster.

1. Create a Kubernetes cluster on Minikube.

	```shell
	minikube start
	```

2. Set `kubectl` to use Minikube.

	```shell
	kubectl config use-context minikube
	```

### Install the Langflow IDE Helm chart

1. Add the repository to Helm and update it.

	```shell
	helm repo add langflow https://langflow-ai.github.io/langflow-helm-charts
	helm repo update
	```

2. Install Langflow with the default options in the `langflow` namespace.

	```shell
	helm install langflow-ide langflow/langflow-ide -n langflow --create-namespace
	```

3. Check the status of the pods.

	```shell
	kubectl get pods -n langflow
	```

### Access the Langflow IDE

Enable local port forwarding to access Langflow from your local machine.

1. To make the Langflow API accessible from your local machine at port 7860:
```shell
kubectl port-forward -n langflow svc/langflow-service-backend 7860:7860
```

2. To make the Langflow UI accessible from your local machine at port 8080:
```shell
kubectl port-forward -n langflow svc/langflow-service 8080:8080
```

Now you can do the following:
- Access the Langflow API at `http://localhost:7860`.
- Access the Langflow UI at `http://localhost:8080`.

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

By default, the chart deploys a SQLite database stored in a local persistent disk. If you want to use an external PostgreSQL database, you can configure it in two ways:

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

Scale the number of replicas and resources for both frontend and backend services:

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

:::note
If your flow relies on a shared state, such as built-in chat memory, you need to set up a shared database when scaling horizontally.
:::

For more examples of `langflow-ide` deployment, see the [Langflow Helm Charts repository](https://github.com/langflow-ai/langflow-helm-charts/tree/main/examples/langflow-ide).
