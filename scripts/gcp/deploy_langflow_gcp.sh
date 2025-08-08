#!/bin/bash
#
# Langflow Final IP-Only Deployment Script for Google Cloud Platform
# Deploys Langflow with built-in auth, proxied by Nginx on a static IP.

# --- Script Configuration ---
set -e
set -o pipefail

# --- Color Definitions ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# --- Main Function ---
main() {
    echo -e "${GREEN}--- Langflow GCP Deployment (IP-Only Model) ---${NC}"

    get_user_input
    setup_gcp_project
    create_networking
    create_vm_and_configure
    final_summary
}

# --- Function to get user inputs ---
get_user_input() {
    echo -e "\n${YELLOW}Step 1: Gathering Information${NC}"
    read -p "Enter your Google Cloud Project ID: " PROJECT_ID
    read -p "Enter a Region (e.g., us-central1): " REGION
    read -p "Enter a Zone (e.g., us-central1-a): " ZONE
    read -p "Enter a name for your new VM (e.g., langflow-server): " VM_NAME
    read -p "Enter a username for the Langflow SUPERUSER: " LANGFLOW_SUPERUSER
    read -s -p "Enter a password for the Langflow SUPERUSER: " LANGFLOW_SUPERUSER_PASSWORD
    echo
}

# --- Function to set up GCP project and APIs ---
setup_gcp_project() {
    echo -e "\n${YELLOW}Step 2: Configuring GCP Project${NC}"
    gcloud config set project "$PROJECT_ID"
    echo "Enabling necessary APIs (compute.googleapis.com)..."
    gcloud services enable compute.googleapis.com
}

# --- Function to create networking resources ---
create_networking() {
    echo -e "\n${YELLOW}Step 3: Setting Up Networking${NC}"
    IP_NAME="${VM_NAME}-ip"
    echo "Reserving a static IP address named '$IP_NAME'..."
    gcloud compute addresses create "$IP_NAME" --project="$PROJECT_ID" --region="$REGION" &> /dev/null || echo "Static IP '$IP_NAME' already exists."
    STATIC_IP=$(gcloud compute addresses describe "$IP_NAME" --project="$PROJECT_ID" --region="$REGION" --format='value(address)')

    echo "Creating firewall rules (HTTP and SSH only)..."
    gcloud compute firewall-rules create "allow-ssh-$VM_NAME" --allow tcp:22 --source-ranges=0.0.0.0/0 --target-tags="$VM_NAME" &> /dev/null || echo "Firewall rule 'allow-ssh-$VM_NAME' already exists."
    gcloud compute firewall-rules create "allow-http-$VM_NAME" --allow tcp:80 --source-ranges=0.0.0.0/0 --target-tags="$VM_NAME" &> /dev/null || echo "Firewall rule 'allow-http-$VM_NAME' already exists."

    echo -e "${GREEN}Static IP ($STATIC_IP) and firewall rules are ready.${NC}"
}

# --- Function to create and configure the VM ---
create_vm_and_configure() {
    echo -e "\n${YELLOW}Step 4: Creating and Configuring VM (This may take a few minutes)${NC}"
    
    # Create the VM, passing user credentials and IP as metadata for the startup script
    gcloud compute instances create "$VM_NAME" \
        --project="$PROJECT_ID" \
        --zone="$ZONE" \
        --machine-type="e2-medium" \
        --network-interface="address=$STATIC_IP" \
        --image-family="ubuntu-2204-lts" \
        --image-project="ubuntu-os-cloud" \
        --boot-disk-size="20GB" \
        --boot-disk-type="pd-balanced" \
        --tags="$VM_NAME" \
        --metadata="langflow-superuser=$LANGFLOW_SUPERUSER,langflow-superuser-password=$LANGFLOW_SUPERUSER_PASSWORD,server-ip=$STATIC_IP" \
        --metadata-from-file startup-script=<(cat <<'EOF'
#!/bin/bash
# Update and install dependencies
apt-get update
apt-get install -y docker.io git nginx

# Enable and start Docker
systemctl enable --now docker

# Pull the specified Langflow image
docker pull langflowai/langflow:latest

# Create a simple, IP-only Nginx configuration
cat > /etc/nginx/sites-available/langflow <<'EON'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:7860;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EON

# Enable the Nginx site and restart Nginx
ln -s /etc/nginx/sites-available/langflow /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
systemctl restart nginx

# Retrieve metadata passed to the VM
SUPERUSER=$(curl -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/attributes/langflow-superuser)
SUPERUSER_PASSWORD=$(curl -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/attributes/langflow-superuser-password)
SERVER_IP=$(curl -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/attributes/server-ip)
SECRET_KEY=$(openssl rand -hex 32)

# Start the Langflow container with its own authentication
# We bind to 127.0.0.1 to force traffic through Nginx for security.
docker run -d \
    --name langflow-secure \
    --restart always \
    -p 127.0.0.1:7860:7860 \
    -e LANGFLOW_BASE_URL="http://$SERVER_IP" \
    -e LANGFLOW_AUTO_LOGIN=False \
    -e LANGFLOW_SIGN_UP_ENABLED=False \
    -e LANGFLOW_SUPERUSER="$SUPERUSER" \
    -e LANGFLOW_SUPERUSER_PASSWORD="$SUPERUSER_PASSWORD" \
    -e LANGFLOW_SECRET_KEY="$SECRET_KEY" \
    -e LANGFLOW_NEW_USER_IS_ACTIVE=False \
    langflowai/langflow:latest
EOF
)

    echo -e "${GREEN}VM '$VM_NAME' created and configuration is in progress.${NC}"
}

# --- Function to display the final summary ---
final_summary() {
    echo -e "\n\n${GREEN}--- ✅ Deployment Complete ---${NC}"
    echo "Please allow 2-3 minutes for the startup script on the VM to finish."
    echo ""
    echo -e "${YELLOW}Your Langflow instance is ready!${NC}"
    echo "1. Access your site at the following IP address:"
    echo -e "   ${GREEN}http://$STATIC_IP${NC}"
    echo "2. Log in with the Langflow superuser credentials you provided during setup."
    echo ""
    echo "---"
    echo -e "VM Name:            ${GREEN}$VM_NAME${NC}"
    echo -e "Static IP:          ${GREEN}$STATIC_IP${NC}"
    echo -e "Langflow Superuser: ${GREEN}$LANGFLOW_SUPERUSER${NC}"
    echo "---"
}

# --- Run the main function ---
main