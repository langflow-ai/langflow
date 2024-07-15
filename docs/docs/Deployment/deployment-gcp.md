---
title: GCP
sidebar_position: 3
slug: /deployment-gcp
---



:::info

This page may contain outdated information. It will be updated as soon as possible.

:::




## Deploy on Google Cloud Platform {#4ee01cda736c4f7396936409f23cdb52}


---


### Run Langflow from a New Google Cloud Project {#ce729796d7404ccdb627bee47d6a4399}


This guide will help you set up a Langflow development VM in a Google Cloud Platform project using Google Cloud Shell.


:::info

When Cloud Shell opens, be sure to select Trust repo. Some gcloud commands might not run in an ephemeral Cloud Shell environment.

:::




### Standard VM {#245b47b450dd4159a5c56a5124bab84f}


[embed](https://console.cloud.google.com/cloudshell/open?git_repo=https://github.com/langflow-ai/langflow&working_dir=scripts/gcp&shellonly=true&tutorial=walkthroughtutorial.md)


This script sets up a Debian-based VM with the Langflow package, Nginx, and the necessary configurations to run the Langflow Dev environment.


---


## Spot/Preemptible Instance {#de9b8f7c71284cbb98e8137a3c44553d}


When running as a [spot (preemptible) instance](https://cloud.google.com/compute/docs/instances/preemptible), the code and VM will behave the same way as in a regular instance, executing the startup script to configure the environment, install necessary dependencies, and run the Langflow application. However, **due to the nature of spot instances, the VM may be terminated at any time if Google Cloud needs to reclaim the resources**. This makes spot instances suitable for fault-tolerant, stateless, or interruptible workloads that can handle unexpected terminations and restarts.


---


## Pricing (approximate) {#2289f4ba9f544e6e9d4b915ef5aacd24}


> For a more accurate breakdown of costs, please use the GCP Pricing Calculator


| Component          | Regular Cost (Hourly) | Regular Cost (Monthly) | Spot/Preemptible Cost (Hourly) | Spot/Preemptible Cost (Monthly) | Notes                                                                      |
| ------------------ | --------------------- | ---------------------- | ------------------------------ | ------------------------------- | -------------------------------------------------------------------------- |
| 100 GB Disk        | -                     | $10/month              | -                              | $10/month                       | Disk cost remains the same for both regular and Spot/Preemptible VMs       |
| VM (n1-standard-4) | $0.15/hr              | ~$108/month            | ~$0.04/hr                      | ~$29/month                      | The VM cost can be significantly reduced using a Spot/Preemptible instance |
| **Total**          | **$0.15/hr**          | **~$118/month**        | **~$0.04/hr**                  | **~$39/month**                  | Total costs for running the VM and disk 24/7 for an entire month           |

