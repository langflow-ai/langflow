# Run Langflow from a New Google Cloud Project

This guide will help you set up a Langflow development VM in a Google Cloud Platform project using Google Cloud Shell.

> **Note**: When Cloud Shell opens, be sure to select **Trust repo**. Some `gcloud` commands might not run in an ephemeral Cloud Shell environment.


## Standard VM 
[![Open in Cloud Shell](https://gstatic.com/cloudssh/images/open-btn.svg)](https://console.cloud.google.com/cloudshell/open?git_repo=https://github.com/logspace-ai/langflow&working_dir=scripts&shellonly=true&tutorial=walkthroughtutorial.md)

This script sets up a Debian-based VM with the Langflow package, Nginx, and the necessary configurations to run the Langflow Dev environment.
<hr>

## Spot/Preemptible Instance

[![Open in Cloud Shell - Spot Instance](https://gstatic.com/cloudssh/images/open-btn.svg)](https://console.cloud.google.com/cloudshell/open?git_repo=https://github.com/genome21/langflow&working_dir=scripts&shellonly=true&tutorial=walkthroughtutorial_spot.md)

When running as a [spot (preemptible) instance](https://cloud.google.com/compute/docs/instances/preemptible), the code and VM will behave the same way as in a regular instance, executing the startup script to configure the environment, install necessary dependencies, and run the Langflow application. However, **due to the nature of spot instances, the VM may be terminated at any time if Google Cloud needs to reclaim the resources**. This makes spot instances suitable for fault-tolerant, stateless, or interruptible workloads that can handle unexpected terminations and restarts.

## Pricing (approximate)
> For a more accurate breakdown of costs, please use the [**GCP Pricing Calculator**](https://cloud.google.com/products/calculator)
<br>

| Component      | Regular Cost (Hourly) | Regular Cost (Monthly) | Spot/Preemptible Cost (Hourly) | Spot/Preemptible Cost (Monthly) | Notes |
| -------------- | --------------------- | ---------------------- | ------------------------------ | ------------------------------- | ----- |
| 100 GB Disk    | -                     | $10/month              | -                              | $10/month                        | Disk cost remains the same for both regular and Spot/Preemptible VMs |
| VM (n1-standard-4) | $0.15/hr        | ~$108/month            | ~$0.04/hr                      | ~$29/month                       | The VM cost can be significantly reduced using a Spot/Preemptible instance |
| **Total**          | **$0.15/hr**         | **~$118/month**        | **~$0.04/hr**                  | **~$39/month**                  | Total costs for running the VM and disk 24/7 for an entire month |
