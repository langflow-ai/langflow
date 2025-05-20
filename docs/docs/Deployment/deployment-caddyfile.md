---
title: Deploy Langflow on a remote server
slug: /deployment-caddyfile
---

Learn how to deploy Langflow on your own remote server with secure web access.
This guide walks you through setting up Langflow on a remote server using [Docker](https://docs.docker.com/) and configuring secure web access with [Caddy](https://caddyserver.com/docs/).

:::tip
The [host-langflow](https://github.com/datastax/host-langflow) repository offers pre-built copies of this `docker-compose.yml` and `Caddyfile`, if you prefer to fork the repository to your server.
:::

## Prerequisites

* A server with a dual-core CPU and at least 2 GB of RAM. This example uses [Hetzner cloud](https://www.hetzner.com/) for hosting. Your deployment may vary.

## Connect to your remote server with SSH

1. Create an SSH key.
Replace `DANA@EXAMPLE.COM` with your email address.
```bash
ssh-keygen -t ed25519 -C "DANA@EXAMPLE.COM"
```

2. In your terminal, follow the instructions to create your public key.
This key allows you to connect to your server remotely.
To copy the key from your terminal, enter the following command:
```bash
cat ~/Downloads/host-lf.pub | pbcopy
```
3. In your remote server, add the SSH key you copied in the previous step.
For example, in the Hetzner cloud server, click **Server** > **SSH keys**, and then click **Add SSH key**.
4. Paste your SSH key into the **SSH key** field, and click **Enter**.
You can now use the SSH key stored on your local machine to connect to your remote server.
5. To connect to your server with SSH, enter the following command.
Replace `PATH_TO_PRIVATE_KEY/PRIVATE_KEY_NAME` with the path to your private SSH key.
Replace `SERVER_IP_ADDRESS` with your server's IP address.
```bash
ssh -i PATH_TO_PRIVATE_KEY/PRIVATE_KEY_NAME root@SERVER_IP_ADDRESS
```
6. When prompted for a key fingerprint, type `yes`.
You are connected to your server.
```text
 System information as of Mon May 19 04:34:44 PM UTC 2025

  System load:  0.0               Processes:             129
  Usage of /:   1.5% of 74.79GB   Users logged in:       0
  Memory usage: 5%                IPv4 address for eth0: 5.161.250.132
  Swap usage:   0%                IPv6 address for eth0: 2a01:4ff:f0:4de7::1
```

## Deploy Langflow on your server

Now that you're connected to your server, install Docker, create a `docker-compose.yml` file, and serve it publicly with Caddy as a reverse proxy.

1. Install Docker on your server.
Since this example server is an Ubuntu server, you can install snap packages.
```bash
snap install docker
```
2. Create a file called `docker-compose.yml`.
```bash
touch docker-compose.yml && nano docker-compose.yml
```
This file defines the Langflow service from the `langflow:latest` image, and a Caddy service to expose Langflow through a reverse proxy.
:::tip
The [host-langflow](https://github.com/datastax/host-langflow) repository offers pre-built copies of this `docker-compose.yml` and `Caddyfile`, if you prefer to fork the repository to your server.
:::
3. Add the following values to `docker-compose.yml`, and then save the file.
```yml
version: "3.8"

services:
  langflow:
    image: langflowai/langflow:latest
    ports:
      - "7860:7860"
    environment:
      - LANGFLOW_HOST=0.0.0.0
      - LANGFLOW_PORT=7860

  caddy:
    image: caddy:latest
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      - langflow

volumes:
  caddy_data:
  caddy_config:
```
4. Create a file called `Caddyfile`.
```bash
touch Caddyfile && nano Caddyfile
```
5. Add the following values to `Caddyfile`, and then save the file.
The Caddyfile configures Caddy to listen on port `80`, and forward all incoming requests to the Langflow service at port `7860`.
```
:80 {
    reverse_proxy langflow:7860
}
```
6. To deploy your server, enter `docker-compose up`.
When the `Welcome to Langflow` message appears, Langflow is running and accessible internally at http://0.0.0.0:7860 inside the Docker network.
7. To open Langflow, navigate to your server's public IP address, such as `http://5.161.250.132`.
Your address must use `http`, because you haven't enabled HTTPS.
8. To enable HTTPS, modify your domain's A record to point to your server's IP address.
For example:
```
Type: A
Name: langflow
Value: 5.161.250.132  (your server's IP address)
```
9. Stop your server.
10. Modify your Caddyfile to include port `443` for HTTPS.

```
:80, :443 {
    reverse_proxy langflow:7860
}
```
11. Start your server.
Caddy recognizes the incoming traffic and routes it to your server.

To exit your SSH session, type `exit`.

## Step-by-step video guide

For a step-by-step guide to deploying Langflow, including deployments to [fly.io](https://fly.io/) and [Flightcontrol.dev](https://www.flightcontrol.dev/), see [How to Host Langflow Anywhere](https://www.youtube.com/watch?v=q4qt5hSnte4).