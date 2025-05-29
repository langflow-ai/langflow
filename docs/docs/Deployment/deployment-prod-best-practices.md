---
title: Langflow architecture and best practices on Kubernetes
slug: /deployment-prod-best-practices
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

While Langflow offers flexible deployment options, deploying on a Kubernetes cluster is highly recommended for production environments.

Deploying on Kubernetes offers the following advantages:

* **Scalability**: Kubernetes allows you to scale the Langflow service to meet the demands of your workload.
* **Availability and resilience**: Kubernetes provides built-in resilience features, such as automatic failover and self-healing, to ensure that the Langflow service is always available.
* **Security**: Kubernetes provides security features, such as role-based access control and network isolation, to protect the Langflow service and its data.
* **Portability**: Kubernetes is a portable platform, which means that you can deploy the Langflow service to any Kubernetes cluster, on-premises or in the cloud.

Langflow can be deployed on cloud deployments like **AWS EKS, Google GKE, or Azure AKS**. For more information about deploying Langflow on AWS EKS, Google GKE, or Azure AKS, see the [Langflow Helm charts repository](https://github.com/langflow-ai/langflow-helm-charts).

## Langflow deployment

A typical Langflow deployment includes:

* **Langflow API and UI** – The Langflow service is the core component of the Langflow platform. It provides a RESTful API for executing flows.
* **Kubernetes cluster** – The Kubernetes cluster provides a platform for deploying and managing the Langflow service and its supporting components.
* **Persistent storage** – Persistent storage is used to store the Langflow service's data, such as models and training data.
* **Ingress controller** – The ingress controller provides a single entry point for traffic to the Langflow service.
* **Load balancer** – Balances traffic across multiple Langflow replicas.
* **Vector database** – If you are using Langflow for RAG, you can integrate with the vector database in Astra Serverless.

![Langflow reference architecture on Kubernetes](/img/langflow-reference-architecture.png)

## Environment isolation

It is recommended to deploy and run two separate environments for Langflow, with one environment reserved for development use and another for production use.


![Langflow environments](/img/langflow-env.png)

* **The Langflow development environment** must include the Integrated Development Environment (IDE) for the full experience of Langflow, optimized for prototyping and testing new flows.
* **The Langflow production environment** executes the flow logic in production and enables Langflow flows as standalone services.

## Why is it important to have separate deployments?

This separation is designed to enhance security, optimize resource allocation, and streamline management.

* **Security**
  * **Isolation**: By separating the development and production environments, you can better isolate different phases of the application lifecycle. This isolation minimizes the risk of development-related issues impacting the production environments.
  * **Access control**: Different security policies and access controls can be applied to each environment. Developers may require broader access in the IDE for testing and debugging, while the runtime environment can be locked down with stricter security measures.
  * **Reduced attack surface**: The runtime environment is configured to include only essential components, reducing the attack surface and potential vulnerabilities.
* **Resource allocation**
  * **Optimized resource usage and cost efficiency**: By separating the two environments, you can allocate resources more effectively. Each flow can be deployed independently, providing fine-grained resource control.
  * **Scalability**: The runtime environment can be scaled independently based on application load and performance requirements, without affecting the development environment.


