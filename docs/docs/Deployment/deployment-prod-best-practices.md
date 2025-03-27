---
title: Langflow in Production Best Practices
slug: /deployment-prod-best-practices
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Langflow in Production Best Practices

While Langflow offers flexible deployment options, **deploying on a Kubernetes cluster is highly recommended for production environments.**

Deploying on Kubernetes offers following advantages:

* **Scalability**: Kubernetes allows you to scale the Langflow service to meet the demands of your workload.  
* **Availability and Resilience**: Kubernetes provides built-in resilience features, such as automatic failover and self-healing, to ensure that the Langflow service is always available.  
* **Security**: Kubernetes provides security features, such as role-based access control and network isolation, to protect the Langflow service and its data.  
* **Portability**: Kubernetes is a portable platform, which means that you can deploy the Langflow service to any Kubernetes cluster, on-premises or in the cloud.

Langflow can be easily deployed on Cloud deployments like **AWS EKS, Google GKE, or Azure AKS**.

## Langflow Components 

A typical Langflow deployment includes:  
 

* **Langflow API & UI** – The Langflow service is the core component of the Langflow platform. It provides a RESTful API for executing flows.  
* **Kubernetes Cluster** – The Kubernetes cluster provides a platform for deploying and managing the Langflow service and its supporting components.  
* **Persistent Storage** – Persistent storage is used to store the Langflow service's data, such as models and training data.  
* **Ingress Controller** – The ingress controller provides a single entry point for traffic to the Langflow service.  
* **Load Balancer** – Balances traffic across multiple Langflow replicas.  
* **Vector Database** – If using Langflow for RAG, Vector DB (e.g., Astra DB) can be integrated.

![Langflow Reference Architecture on Kubernetes](/img/langflow-reference-architecture.png)

## Environment Segregation 

It is recommended to deploy and run two separate environments for Langflow. 

One environment to be reserved for Development use and another for Production use. 

![Langflow Environments](/img/langflow-env.png)

* **The Langflow Development environment** must include the Integrated Development Environment (IDE) for full experience of Langflow, optimized for prototyping and testing new flows.  
* **The Langflow Production environment** executes the flow logic in production and productionizes Langflow flows as standalone services.

## Why is it important to have separate deployments? 

This separation is designed to enhance security, optimize resource allocation, and streamline management. Understanding the rationale behind these deployment options will help you make informed decisions about how to best deploy and manage your applications.

* **Security**  
  * **Isolation**: By separating the development and production environments, we can better isolate different phases of the application lifecycle. This isolation minimizes the risk of development-related issues impacting the production environment.  
  * **Access Control**: Different security policies and access controls can be applied to each environment. Developers may require broader access in the IDE for testing and debugging, whereas the runtime environment can be locked down with stricter security measures.  
  * **Reduced Attack Surface**: The runtime environment is configured to only include essential components, reducing the attack surface and potential vulnerabilities.  
* **Resource Allocation**  
  * **Optimized Resource Usage and cost efficiency**: By separating the two, we can allocate resources more effectively. Additionally, each flow can be deployed independently, providing fine-grained resource control.  
  * **Scalability**: The runtime environment can be scaled independently based on application load and performance requirements, without affecting the development environment.  
    


