---
title: GCP
slug: /deployment-gcp
---

# Deploy on Google Cloud Platform

To deploy Langflow on Google Cloud Platform using Cloud Shell, use the below script.
The script will guide you through setting up a Debian-based VM with the Langflow package, Nginx, and the necessary configurations to run the Langflow dev environment in GCP.

## Prerequisites

* A GCP account with the necessary permissions to create resources
* A project on GCP where you want to deploy Langflow

## Deploy Langflow in GCP

1. Click below to launch Cloud Shell.

[![GCP Deploy](/logos/cloud_deploy.svg) Deploy to Google Cloud](https://console.cloud.google.com/cloudshell/open?git_repo=https://github.com/langflow-ai/langflow&working_dir=scripts/gcp&shellonly=true&tutorial=walkthroughtutorial.md)

2. Click **Trust repo**. Some gcloud commands may not run in an ephemeral Cloud Shell environment.
3. Click **Start** and follow the tutorial to deploy Langflow.

## Spot/Preemptible Instance

When running a [spot (preemptible) instance](https://cloud.google.com/compute/docs/instances/preemptible), the code and VM will behave the same way as in a regular instance, executing the startup script to configure the environment, install necessary dependencies, and run the Langflow application. However, **due to the nature of spot instances, the VM may be terminated at any time if Google Cloud needs to reclaim the resources**. This makes spot instances suitable for fault-tolerant, stateless, or interruptible workloads that can handle unexpected terminations and restarts.

## Pricing

For more information, see the [GCP pricing calculator](https://cloud.google.com/products/calculator?hl=en).
