# Kubernetes

This guide will help you get LangFlow up and running in Kubernetes cluster, including the following steps:

- Install [LangFlow as IDE](#langflow-ide) in a Kubernetes cluster (for development)
- Install [LangFlow as a standalone application](#langflow-runtime) in a Kubernetes cluster (for production runtime workloads)

## LangFlow (IDE)

This solution is designed to provide a complete environment for developers to create, test, and debug their flows. It includes both the API and the UI.

### Prerequisites

- Kubernetes server
- kubectl
- Helm

### Step 0. Prepare a Kubernetes cluster

We use [Minikube](https://minikube.sigs.k8s.io/docs/start/) for this example, but you can use any Kubernetes cluster.

1. Create a Kubernetes cluster on Minikube.
   ```shell
   minikube start
   ```
2. Set `kubectl` to use Minikube.
   ```shell
   kubectl config use-context minikube
   ```

### Step 1. Install the LangFlow Helm chart

1. Add the repository to Helm.
   ```shell
   helm repo add langflow https://langflow-ai.github.io/langflow-helm-charts
   helm repo update
   ```
2. Install LangFlow with the default options in the `langflow` namespace.
   ```shell
   helm install langflow-ide langflow/langflow-ide -n langflow --create-namespace
   ```
3. Check the status of the pods
   ```shell
   kubectl get pods -n langflow
   ```
   ```
   NAME                                 READY   STATUS    RESTARTS       AGE
   langflow-0                           1/1     Running   0              33s
   langflow-frontend-5d9c558dbb-g7tc9   1/1     Running   0              38s
   ```

### Step 2. Access LangFlow

Enable local port forwarding to access LangFlow from your local machine.

```shell
kubectl port-forward -n langflow svc/langflow-langflow-runtime 7860:7860
```

Now you can access LangFlow at [http://localhost:7860/](http://localhost:7860/).

### LangFlow version

To specify a different LangFlow version, you can set the `langflow.backend.image.tag` and `langflow.frontend.image.tag` values in the `values.yaml` file.

```yaml
langflow:
  backend:
    image:
      tag: "1.0.0a59"
  frontend:
    image:
      tag: "1.0.0a59"
```

### Storage

By default, the chart will use a SQLLite database stored in a local persistent disk.
If you want to use an external PostgreSQL database, you can set the `langflow.database` values in the `values.yaml` file.

```yaml
# Deploy postgresql. You can skip this section if you have an existing postgresql database.
postgresql:
  enabled: true
  fullnameOverride: "langflow-ide-postgresql-service"
  auth:
    username: "langflow"
    password: "langflow-postgres"
    database: "langflow-db"

langflow:
  backend:
    externalDatabase:
      enabled: true
      driver:
        value: "postgresql"
      host:
        value: "langflow-ide-postgresql-service"
      port:
        value: "5432"
      database:
        value: "langflow-db"
      user:
        value: "langflow"
      password:
        valueFrom:
          secretKeyRef:
            key: "password"
            name: "langflow-ide-postgresql-service"
    sqlite:
      enabled: false
```

### Scaling

You can scale the number of replicas for the LangFlow backend and frontend services by changing the `replicaCount` value in the `values.yaml` file.

```yaml
langflow:
  backend:
    replicaCount: 3
  frontend:
    replicaCount: 3
```

You can scale frontend and backend services independently.

To scale vertically (increase the resources for the pods), you can set the `resources` values in the `values.yaml` file.

```yaml
langflow:
  backend:
    resources:
      requests:
        memory: "2Gi"
        cpu: "1000m"
  frontend:
    resources:
      requests:
        memory: "1Gi"
        cpu: "1000m"
```

### Deploy on AWS EKS, Google GKE, or Azure AKS and other examples

Visit the [LangFlow Helm Charts repository](https://github.com/langflow-ai/langflow-helm-charts) for more examples and configurations.

Use the [default values file](https://github.com/langflow-ai/langflow-helm-charts/blob/main/charts/langflow-ide/values.yaml) as reference for all the options available.

Visit the [examples directory](https://github.com/langflow-ai/langflow-helm-charts/tree/main/examples/langflow-ide) to learn more about different deployment options.

## LangFlow (Runtime)

The runtime chart is tailored for deploying applications in a production environment. It is focused on stability, performance, isolation and security to ensure that applications run reliably and efficiently.

Using a dedicated deployment for a set of flows is fundamental in production environments in order to have a granular resource control.

## Import a flow

There are two ways to import a flow (or multiple flows) and deploy it with the LangFlow runtime Helm chart:

1. **From a remote location**: You can reference a flow stored in a remote location, such as a URL or a Git repository by customizing the `values.yaml` file in the section `downloadFlows`:

   ```yaml
   downloadFlows:
     flows:
       - url: https://raw.githubusercontent.com/langflow-ai/langflow/dev/src/backend/base/langflow/initial_setup/starter_projects/Basic%20Prompting%20(Hello%2C%20world!).json
   ```

   When the LangFlow runtime starts, it will download the flow from the specified URL and run it.
   The flow UUID to use to call the API endpoints is the same as the one in the JSON file under the `id` field.
   You can also specify a `endpoint_name` field to give a friendly name to the flow.

2. **Packaging the flow as docker image**: You can add a flow from to a docker image based on Langflow runtime and refer to it in the chart.

   First you need a base Dockerfile to get the langflow image and add your local flows:

   ```Dockerfile
      FROM langflowai/langflow-backend:latest
      RUN mkdir /app/flows
      COPY ./*json /app/flows/.
   ```

   Then you can build the image and push it to DockerHub (or any registry you prefer):

   ```bash
   # Create the Dockerfile
   echo """FROM langflowai/langflow-backend:latest
   RUN mkdir /app/flows
   ENV LANGFLOW_LOAD_FLOWS_PATH=/app/flows
   COPY ./*json /app/flows/.""" > Dockerfile
   # Download the flows
   wget https://raw.githubusercontent.com/langflow-ai/langflow/dev/src/backend/base/langflow/initial_setup/starter_projects/Basic%20Prompting%20(Hello%2C%20world!).json
   # Build the docker image locally
   docker build -t myuser/langflow-just-chat:1.0.0 -f Dockerfile .
   # Push the image to DockerHub
   docker push myuser/langflow-just-chat:1.0.0
   ```

### Prerequisites

- Kubernetes server
- kubectl
- Helm

### Step 0. Prepare a Kubernetes cluster

Follow the same steps as for the LangFlow IDE.

### Step 1. Install the LangFlow runtime Helm chart

1. Add the repository to Helm.
   ```shell
   helm repo add langflow https://langflow-ai.github.io/langflow-helm-charts
   helm repo update
   ```
2. Install the LangFlow app with the default options in the `langflow` namespace.
   If you bundled the flow in a docker image, you can specify the image name in the `values.yaml` file or with the `--set` flag:
   ```shell
   helm install my-langflow-app langflow/langflow-runtime -n langflow --create-namespace --set image.repository=myuser/langflow-just-chat --set image.tag=1.0.0
   ```
   If you want to download the flow from a remote location, you can specify the URL in the `values.yaml` file or with the `--set` flag:
   ```shell
   helm install my-langflow-app langflow/langflow-runtime -n langflow --create-namespace --set downloadFlows.flows[0].url=https://raw.githubusercontent.com/langflow-ai/langflow/dev/src/backend/base/langflow/initial_setup/starter_projects/Basic%20Prompting%20(Hello%2C%20world!).json
   ```
   3. Check the status of the pods
   ```shell
   kubectl get pods -n langflow
   ```

### Step 2. Access the LangFlow app API

Enable local port forwarding to access LangFlow from your local machine.

```shell
kubectl port-forward -n langflow svc/langflow-my-langflow-app 7860:7860
```

Now you can access the API at [http://localhost:7860/api/v1/flows](http://localhost:7860/api/v1/flows) and execute the flow:

```bash
id=$(curl -s http://localhost:7860/api/v1/flows | jq -r '.flows[0].id')
curl -X POST \
    "http://localhost:7860/api/v1/run/$id?stream=false" \
    -H 'Content-Type: application/json'\
    -d '{
      "input_value": "Hello!",
      "output_type": "chat",
      "input_type": "chat"
    }'
```

### Storage

In this case, the storage is not needed as our deployment is stateless.

### Log level and LangFlow configurations

You can set the log level and other LangFlow configurations in the `values.yaml` file.

```yaml
env:
  - name: LANGFLOW_LOG_LEVEL
    value: "INFO"
```

### Configure secrets and variables

In order to inject secrets and LangFlow global variables, you can use the `secrets` and `env` sections in the `values.yaml` file.

Let's say your flow uses a global variable which is a secret; when you export the flow as JSON, it's recommended to not include it.
When importing the flow in the LangFlow runtime, you can set the global variable using the `env` section in the `values.yaml` file.
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

You can scale the number of replicas for the LangFlow app by changing the `replicaCount` value in the `values.yaml` file.

```yaml
replicaCount: 3
```

To scale vertically (increase the resources for the pods), you can set the `resources` values in the `values.yaml` file.

```yaml
resources:
  requests:
    memory: "2Gi"
    cpu: "1000m"
```

### Other examples

Visit the [LangFlow Helm Charts repository](https://github.com/langflow-ai/langflow-helm-charts) for more examples and configurations.

Use the [default values file](https://github.com/langflow-ai/langflow-helm-charts/blob/main/charts/langflow-runtime/values.yaml) as reference for all the options available.

Visit the [examples directory](https://github.com/langflow-ai/langflow-helm-charts/tree/main/examples/langflow-runtime) to learn more about different deployment options.
