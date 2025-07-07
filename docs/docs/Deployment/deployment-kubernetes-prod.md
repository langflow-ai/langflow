---
title: Deploy the Langflow production environment on Kubernetes
slug: /deployment-kubernetes-prod
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

The [Langflow Runtime](https://github.com/langflow-ai/langflow-helm-charts/blob/main/charts/langflow-runtime) chart is tailored for deploying applications in a production environment. It is focused on stability, performance, isolation, and security to ensure that applications run reliably and efficiently.

:::important
By default, the [Langflow runtime Helm chart](https://github.com/langflow-ai/langflow-helm-charts/blob/main/charts/langflow-runtime/values.yaml#L46) enables `readOnlyRootFilesystem: true` as a security best practice. This setting prevents modifications to the container's root filesystem at runtime, which is a recommended security measure in production environments.

Disabling `readOnlyRootFilesystem` reduces the security of your deployment. Only disable this setting if you understand the security implications and have implemented other security measures.

For more information, see the [Kubernetes documentation](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/).
:::

### Prerequisites

- A [Kubernetes](https://kubernetes.io/docs/setup/) server
- [kubectl](https://kubernetes.io/docs/tasks/tools/#kubectl)
- [Helm](https://helm.sh/docs/intro/install/)

### Install the Langflow runtime Helm chart

1. Add the repository to Helm.

```shell
helm repo add langflow https://langflow-ai.github.io/langflow-helm-charts
helm repo update
```

2. Install the Langflow app with the default options in the `langflow` namespace.

If you have a created a [custom image with packaged flows](/docs/deployment-docker#package-your-flow-as-a-docker-image), you can deploy Langflow by overriding the default [values.yaml](https://github.com/langflow-ai/langflow-helm-charts/blob/main/charts/langflow-runtime/values.yaml) file with the `--set` flag.

* Use a custom image with bundled flows:
```shell
helm install my-langflow-app langflow/langflow-runtime -n langflow --create-namespace --set image.repository=myuser/langflow-hello-world --set image.tag=1.0.0
```

* Alternatively, install the chart and download the flows from a URL with the `--set` flag:
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

### Access the Langflow runtime

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

### Configure secrets

To inject secrets and Langflow global variables, use the `secrets` and `env` sections in the [values.yaml](https://github.com/langflow-ai/langflow-helm-charts/blob/main/charts/langflow-runtime/values.yaml) file.

For example, the [example flow JSON](https://raw.githubusercontent.com/langflow-ai/langflow-helm-charts/refs/heads/main/examples/flows/basic-prompting-hello-world.json) uses a global variable that is a secret. When you export the flow as JSON, it's recommended to not include the secret.

Instead, when importing the flow in the Langflow runtime, you can set the global variable in one of the following ways:

<Tabs>
<TabItem value="values" label="Using values.yaml">

```yaml
env:
  - name: openai_key_var
    valueFrom:
      secretKeyRef:
        name: openai-key
        key: openai-key
```

Or directly in the values file (not recommended for secret values):

```yaml
env:
  - name: openai_key_var
    value: "sk-...."
```

</TabItem>
<TabItem value="helm" label="Using Helm Commands">

1. Create the secret:
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

</TabItem>
</Tabs>

### Configure the log level

Set the log level and other Langflow configurations in the [values.yaml](https://github.com/langflow-ai/langflow-helm-charts/blob/main/charts/langflow-runtime/values.yaml) file.

```yaml
env:
  - name: LANGFLOW_LOG_LEVEL
    value: "INFO"
```

### Configure scaling

To scale the number of replicas for the Langflow appplication, change the `replicaCount` value in the [values.yaml](https://github.com/langflow-ai/langflow-helm-charts/blob/main/charts/langflow-runtime/values.yaml) file.

```yaml
replicaCount: 3
```

To scale the application vertically by increasing the resources for the pods, change the `resources` values in the [values.yaml](https://github.com/langflow-ai/langflow-helm-charts/blob/main/charts/langflow-runtime/values.yaml) file.

```yaml
resources:
  requests:
    memory: "2Gi"
    cpu: "1000m"
```

For more information about deploying Langflow on AWS EKS, Google GKE, or Azure AKS, see the [Langflow Helm Charts repository](https://github.com/langflow-ai/langflow-helm-charts).




