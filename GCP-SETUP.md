# Running Langflow from a new GCP project
This guide will help you set up a Langflow Dev VM in a Google Cloud Platform project using Google Cloud Shell.


## Run the following in your GCP cloudshell:

```bash
# Set the VM, image, and networking configuration
VM_NAME="langflow-dev"
IMAGE_FAMILY="debian-11"
IMAGE_PROJECT="debian-cloud"
BOOT_DISK_SIZE="100GB"
ZONE="us-central1-a"
REGION="us-central1"
VPC_NAME="default"
SUBNET_NAME="default"
SUBNET_RANGE="10.128.0.0/20"
NAT_GATEWAY_NAME="nat-gateway"
CLOUD_ROUTER_NAME="nat-client"

# Set the GCP project's compute region
gcloud config set compute/region $REGION

# Check if the VPC exists, and create it if not
vpc_exists=$(gcloud compute networks list --filter="name=$VPC_NAME" --format="value(name)")
if [[ -z "$vpc_exists" ]]; then
  gcloud compute networks create $VPC_NAME --subnet-mode=custom
fi

# Check if the subnet exists, and create it if not
subnet_exists=$(gcloud compute networks subnets list --filter="name=$SUBNET_NAME AND region=$REGION" --format="value(name)")
if [[ -z "$subnet_exists" ]]; then
  gcloud compute networks subnets create $SUBNET_NAME --network=$VPC_NAME --region=$REGION --range=$SUBNET_RANGE
fi

# Create a firewall rule to allow TCP port 8080 for all instances in the VPC
gcloud compute firewall-rules create allow-tcp-8080 \
  --network $VPC_NAME \
  --allow tcp:8080 \
  --source-ranges 0.0.0.0/0 \
  --direction INGRESS

# Create a firewall rule to allow IAP traffic
gcloud compute firewall-rules create allow-iap \
  --network $VPC_NAME \
  --allow tcp:80,tcp:443 \
  --source-ranges 35.235.240.0/20 \
  --direction INGRESS

# Create the Cloud Router and NAT Gateway
gcloud compute routers create $CLOUD_ROUTER_NAME \
  --network $VPC_NAME \
  --region $REGION

gcloud compute routers nats create $NAT_GATEWAY_NAME \
  --router $CLOUD_ROUTER_NAME \
  --auto-allocate-nat-external-ips \
  --nat-all-subnet-ip-ranges \
  --enable-logging \
  --region $REGION

# Define the startup script as a multiline Bash here-doc
STARTUP_SCRIPT=$(cat <<'EOF'
#!/bin/bash

# Update and upgrade the system
apt update
apt upgrade

# Install Python 3 pip, Langflow, and Nginx
apt install python3-pip
pip install langflow
apt-get install nginx

# Configure Nginx for Langflow
touch /etc/nginx/sites-available/langflow-app
echo "server {
    listen 0.0.0.0:7860;

    location / {
        proxy_pass http://127.0.0.1:7860;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}" >> /etc/nginx/sites-available/langflow-app
ln -s /etc/nginx/sites-available/my-app /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
langflow
EOF
)

# Create a temporary file to store the startup script
tempfile=$(mktemp)
echo "$STARTUP_SCRIPT" > $tempfile

# Create the VM instance with the specified configuration and startup script
gcloud compute instances create $VM_NAME \
  --image-family $IMAGE_FAMILY \
  --image-project $IMAGE_PROJECT \
  --boot-disk-size $BOOT_DISK_SIZE \
  --metadata-from-file startup-script=$tempfile \
  --zone $ZONE \
  --network $VPC_NAME \
  --subnet $SUBNET_NAME

# Remove the temporary file after the VM is created
rm $tempfile

```
> This script sets up a Debian-based VM with the Langflow package, Nginx, and the necessary configurations to run the Langflow Dev environment. The VM will be accessible on TCP port 8080 from any IP address.

<br>

## Connecting to your new Langflow VM
1. Navigate to the [VM instances](https://console.cloud.google.com/compute/instances) page
2. Click on the external IP for your VM
3. Add port 8080 (assuming your VM external IP is 192.168.0.1):
http://192.168.0.1:8080
4. You will be greeted by the Langflow Dev environment