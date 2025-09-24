# Azure AKS Disaster Recovery - Simplified Manual Operations Guide

**Version:** 2.0  
**Configuration:** Manual Operations without Front Door or GitOps  
**Last Updated:** January 2024

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Initial Setup Scripts](#2-initial-setup-scripts)
3. [Manual Deployment Procedures](#3-manual-deployment-procedures)
4. [Daily Operations Scripts](#4-daily-operations-scripts)
5. [Disaster Recovery Scripts](#5-disaster-recovery-scripts)
6. [Testing Procedures](#6-testing-procedures)
7. [Troubleshooting Guide](#7-troubleshooting-guide)

---

## 1. Architecture Overview

### Simplified Architecture (No Front Door, No GitOps)

```
┌──────────────────────────────────────────────────────────────┐
│                    DNS (Manual Update Required)              │
│                    A Record → Active Region IP               │
└──────────┬───────────────────────────┬──────────────────────┘
           │                           │ (Manual DNS Update)
           ▼                           ▼
┌──────────────────────┐    ┌──────────────────────┐
│  PRIMARY REGION      │    │  SECONDARY REGION    │
│  East US 2           │    │  Central US          │
├──────────────────────┤    ├──────────────────────┤
│  • AKS Cluster       │    │  • AKS Cluster       │
│  • Load Balancer IP  │    │  • Load Balancer IP  │
│  • PostgreSQL (RW)   │───►│  • PostgreSQL (RO)   │
│  • Cosmos DB (RW)    │◄──►│  • Cosmos DB (RO)    │
│  • AI Search         │    │  • AI Search         │
│  • Doc Intelligence  │───►│  • Doc Intelligence  │
│  • Storage (GZRS)    │───►│  • Storage (RA)      │
└──────────────────────┘    └──────────────────────┘
```

---

## 2. Initial Setup Scripts

### 2.1 Complete Infrastructure Setup Script

```bash
#!/bin/bash
# setup-all-infrastructure.sh
# Complete setup without Front Door or GitOps

set -euo pipefail

# ============================================
# CONFIGURATION SECTION
# ============================================
export SUBSCRIPTION_ID=$(az account show --query id -o tsv)
export PRIMARY_REGION="eastus2"
export SECONDARY_REGION="centralus"
export RESOURCE_PREFIX="aksdr"
export ADMIN_USERNAME="aksadmin"
export ADMIN_EMAIL="admin@company.com"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ============================================
# FUNCTIONS
# ============================================
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ============================================
# PREREQUISITES
# ============================================
log_info "Starting DR Infrastructure Setup"
log_info "Primary Region: $PRIMARY_REGION"
log_info "Secondary Region: $SECONDARY_REGION"

# Check Azure CLI
if ! command -v az &> /dev/null; then
    log_error "Azure CLI not found. Please install it first."
    exit 1
fi

# Login check
if ! az account show &> /dev/null; then
    log_error "Not logged in to Azure. Please run 'az login' first."
    exit 1
fi

# ============================================
# RESOURCE GROUPS
# ============================================
log_info "Creating Resource Groups..."

az group create \
    --name "${RESOURCE_PREFIX}-primary-rg" \
    --location "$PRIMARY_REGION" \
    --tags Environment=DR Region=Primary Owner=Platform

az group create \
    --name "${RESOURCE_PREFIX}-secondary-rg" \
    --location "$SECONDARY_REGION" \
    --tags Environment=DR Region=Secondary Owner=Platform

az group create \
    --name "${RESOURCE_PREFIX}-shared-rg" \
    --location "$PRIMARY_REGION" \
    --tags Environment=DR Type=Shared Owner=Platform

# ============================================
# NETWORKING
# ============================================
log_info "Creating Virtual Networks..."

# Primary VNet
az network vnet create \
    --resource-group "${RESOURCE_PREFIX}-primary-rg" \
    --name "${RESOURCE_PREFIX}-vnet-primary" \
    --address-prefixes "10.0.0.0/16" \
    --location "$PRIMARY_REGION"

# Primary Subnets
az network vnet subnet create \
    --resource-group "${RESOURCE_PREFIX}-primary-rg" \
    --vnet-name "${RESOURCE_PREFIX}-vnet-primary" \
    --name "aks-subnet" \
    --address-prefixes "10.0.1.0/24"

az network vnet subnet create \
    --resource-group "${RESOURCE_PREFIX}-primary-rg" \
    --vnet-name "${RESOURCE_PREFIX}-vnet-primary" \
    --name "db-subnet" \
    --address-prefixes "10.0.2.0/24"

# Secondary VNet
az network vnet create \
    --resource-group "${RESOURCE_PREFIX}-secondary-rg" \
    --name "${RESOURCE_PREFIX}-vnet-secondary" \
    --address-prefixes "10.1.0.0/16" \
    --location "$SECONDARY_REGION"

# Secondary Subnets
az network vnet subnet create \
    --resource-group "${RESOURCE_PREFIX}-secondary-rg" \
    --vnet-name "${RESOURCE_PREFIX}-vnet-secondary" \
    --name "aks-subnet" \
    --address-prefixes "10.1.1.0/24"

az network vnet subnet create \
    --resource-group "${RESOURCE_PREFIX}-secondary-rg" \
    --vnet-name "${RESOURCE_PREFIX}-vnet-secondary" \
    --name "db-subnet" \
    --address-prefixes "10.1.2.0/24"

# VNet Peering
log_info "Setting up VNet Peering..."

# Get VNet IDs
PRIMARY_VNET_ID=$(az network vnet show \
    --resource-group "${RESOURCE_PREFIX}-primary-rg" \
    --name "${RESOURCE_PREFIX}-vnet-primary" \
    --query id -o tsv)

SECONDARY_VNET_ID=$(az network vnet show \
    --resource-group "${RESOURCE_PREFIX}-secondary-rg" \
    --name "${RESOURCE_PREFIX}-vnet-secondary" \
    --query id -o tsv)

# Create peering from primary to secondary
az network vnet peering create \
    --resource-group "${RESOURCE_PREFIX}-primary-rg" \
    --name "primary-to-secondary" \
    --vnet-name "${RESOURCE_PREFIX}-vnet-primary" \
    --remote-vnet "$SECONDARY_VNET_ID" \
    --allow-vnet-access

# Create peering from secondary to primary
az network vnet peering create \
    --resource-group "${RESOURCE_PREFIX}-secondary-rg" \
    --name "secondary-to-primary" \
    --vnet-name "${RESOURCE_PREFIX}-vnet-secondary" \
    --remote-vnet "$PRIMARY_VNET_ID" \
    --allow-vnet-access

# ============================================
# AKS CLUSTERS
# ============================================
log_info "Creating AKS Clusters (this will take 10-15 minutes)..."

# Primary AKS Cluster
az aks create \
    --resource-group "${RESOURCE_PREFIX}-primary-rg" \
    --name "${RESOURCE_PREFIX}-aks-primary" \
    --location "$PRIMARY_REGION" \
    --kubernetes-version "1.28.3" \
    --node-count 3 \
    --node-vm-size "Standard_D4s_v3" \
    --network-plugin azure \
    --vnet-subnet-id "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_PREFIX}-primary-rg/providers/Microsoft.Network/virtualNetworks/${RESOURCE_PREFIX}-vnet-primary/subnets/aks-subnet" \
    --service-cidr "10.0.100.0/24" \
    --dns-service-ip "10.0.100.10" \
    --generate-ssh-keys \
    --enable-managed-identity \
    --node-resource-group "${RESOURCE_PREFIX}-primary-nodes-rg" \
    --load-balancer-sku standard \
    --zones 1 2 3

# Secondary AKS Cluster (smaller for cost savings)
az aks create \
    --resource-group "${RESOURCE_PREFIX}-secondary-rg" \
    --name "${RESOURCE_PREFIX}-aks-secondary" \
    --location "$SECONDARY_REGION" \
    --kubernetes-version "1.28.3" \
    --node-count 2 \
    --node-vm-size "Standard_D2s_v3" \
    --network-plugin azure \
    --vnet-subnet-id "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_PREFIX}-secondary-rg/providers/Microsoft.Network/virtualNetworks/${RESOURCE_PREFIX}-vnet-secondary/subnets/aks-subnet" \
    --service-cidr "10.1.100.0/24" \
    --dns-service-ip "10.1.100.10" \
    --generate-ssh-keys \
    --enable-managed-identity \
    --node-resource-group "${RESOURCE_PREFIX}-secondary-nodes-rg" \
    --load-balancer-sku standard \
    --zones 1 2 3

# ============================================
# POSTGRESQL SETUP
# ============================================
log_info "Setting up PostgreSQL with Read Replica..."

# Generate secure password
PG_PASSWORD=$(openssl rand -base64 32)
echo "PostgreSQL Password: $PG_PASSWORD" > pg_credentials.txt

# Create Primary PostgreSQL
az postgres flexible-server create \
    --resource-group "${RESOURCE_PREFIX}-primary-rg" \
    --name "${RESOURCE_PREFIX}-pg-primary" \
    --location "$PRIMARY_REGION" \
    --admin-user "dradmin" \
    --admin-password "$PG_PASSWORD" \
    --sku-name "Standard_D2ds_v4" \
    --storage-size 128 \
    --version "15" \
    --high-availability Enabled \
    --backup-retention 35 \
    --geo-redundant-backup Enabled

# Wait for primary to be ready
log_info "Waiting for PostgreSQL primary to be ready..."
sleep 60

# Create Read Replica
az postgres flexible-server replica create \
    --replica-name "${RESOURCE_PREFIX}-pg-replica" \
    --resource-group "${RESOURCE_PREFIX}-secondary-rg" \
    --source-server "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_PREFIX}-primary-rg/providers/Microsoft.DBforPostgreSQL/flexibleServers/${RESOURCE_PREFIX}-pg-primary" \
    --location "$SECONDARY_REGION"

# ============================================
# COSMOS DB SETUP
# ============================================
log_info "Setting up Cosmos DB with Multi-Region..."

az cosmosdb create \
    --name "${RESOURCE_PREFIX}-cosmos" \
    --resource-group "${RESOURCE_PREFIX}-shared-rg" \
    --kind MongoDB \
    --server-version "6.0" \
    --locations regionName="$PRIMARY_REGION" failoverPriority=0 isZoneRedundant=true \
    --locations regionName="$SECONDARY_REGION" failoverPriority=1 isZoneRedundant=true \
    --default-consistency-level "Session" \
    --enable-automatic-failover true

# Create database
az cosmosdb mongodb database create \
    --account-name "${RESOURCE_PREFIX}-cosmos" \
    --resource-group "${RESOURCE_PREFIX}-shared-rg" \
    --name "platformdb"

# Create collection
az cosmosdb mongodb collection create \
    --account-name "${RESOURCE_PREFIX}-cosmos" \
    --resource-group "${RESOURCE_PREFIX}-shared-rg" \
    --database-name "platformdb" \
    --name "documents"

# ============================================
# STORAGE ACCOUNTS
# ============================================
log_info "Creating Storage Accounts..."

# Primary storage with geo-redundancy
az storage account create \
    --name "${RESOURCE_PREFIX}storage" \
    --resource-group "${RESOURCE_PREFIX}-primary-rg" \
    --location "$PRIMARY_REGION" \
    --sku Standard_RAGZRS \
    --kind StorageV2 \
    --access-tier Hot

# Create containers
az storage container create \
    --name "backups" \
    --account-name "${RESOURCE_PREFIX}storage" \
    --auth-mode login

az storage container create \
    --name "data" \
    --account-name "${RESOURCE_PREFIX}storage" \
    --auth-mode login

# ============================================
# CONTAINER REGISTRY
# ============================================
log_info "Creating Container Registry..."

az acr create \
    --resource-group "${RESOURCE_PREFIX}-shared-rg" \
    --name "${RESOURCE_PREFIX}acr" \
    --location "$PRIMARY_REGION" \
    --sku Premium

# Enable geo-replication
az acr replication create \
    --registry "${RESOURCE_PREFIX}acr" \
    --location "$SECONDARY_REGION"

# ============================================
# AI SERVICES SETUP
# ============================================
log_info "Setting up AI Services..."

# AI Search - Primary
az search service create \
    --name "${RESOURCE_PREFIX}-search-primary" \
    --resource-group "${RESOURCE_PREFIX}-primary-rg" \
    --location "$PRIMARY_REGION" \
    --sku "basic"

# AI Search - Secondary
az search service create \
    --name "${RESOURCE_PREFIX}-search-secondary" \
    --resource-group "${RESOURCE_PREFIX}-secondary-rg" \
    --location "$SECONDARY_REGION" \
    --sku "basic"

# Document Intelligence - Primary
az cognitiveservices account create \
    --name "${RESOURCE_PREFIX}-docintel-primary" \
    --resource-group "${RESOURCE_PREFIX}-primary-rg" \
    --kind "FormRecognizer" \
    --sku "S0" \
    --location "$PRIMARY_REGION" \
    --yes

# Document Intelligence - Secondary
az cognitiveservices account create \
    --name "${RESOURCE_PREFIX}-docintel-secondary" \
    --resource-group "${RESOURCE_PREFIX}-secondary-rg" \
    --kind "FormRecognizer" \
    --sku "S0" \
    --location "$SECONDARY_REGION" \
    --yes

# ============================================
# KEY VAULTS
# ============================================
log_info "Creating Key Vaults..."

az keyvault create \
    --name "${RESOURCE_PREFIX}-kv-primary" \
    --resource-group "${RESOURCE_PREFIX}-primary-rg" \
    --location "$PRIMARY_REGION" \
    --sku standard

az keyvault create \
    --name "${RESOURCE_PREFIX}-kv-secondary" \
    --resource-group "${RESOURCE_PREFIX}-secondary-rg" \
    --location "$SECONDARY_REGION" \
    --sku standard

# ============================================
# PUBLIC IPS FOR MANUAL DNS
# ============================================
log_info "Reserving Static Public IPs for Manual DNS Management..."

# Create static public IP for primary
az network public-ip create \
    --resource-group "${RESOURCE_PREFIX}-primary-nodes-rg" \
    --name "${RESOURCE_PREFIX}-primary-ip" \
    --location "$PRIMARY_REGION" \
    --allocation-method Static \
    --sku Standard

# Create static public IP for secondary
az network public-ip create \
    --resource-group "${RESOURCE_PREFIX}-secondary-nodes-rg" \
    --name "${RESOURCE_PREFIX}-secondary-ip" \
    --location "$SECONDARY_REGION" \
    --allocation-method Static \
    --sku Standard

# Get the IPs
PRIMARY_IP=$(az network public-ip show \
    --resource-group "${RESOURCE_PREFIX}-primary-nodes-rg" \
    --name "${RESOURCE_PREFIX}-primary-ip" \
    --query ipAddress -o tsv)

SECONDARY_IP=$(az network public-ip show \
    --resource-group "${RESOURCE_PREFIX}-secondary-nodes-rg" \
    --name "${RESOURCE_PREFIX}-secondary-ip" \
    --query ipAddress -o tsv)

# ============================================
# OUTPUT SUMMARY
# ============================================
log_info "Infrastructure setup complete!"
echo ""
echo "=========================================="
echo "DEPLOYMENT SUMMARY"
echo "=========================================="
echo "Primary Region: $PRIMARY_REGION"
echo "Secondary Region: $SECONDARY_REGION"
echo ""
echo "AKS Clusters:"
echo "  Primary: ${RESOURCE_PREFIX}-aks-primary"
echo "  Secondary: ${RESOURCE_PREFIX}-aks-secondary"
echo ""
echo "Public IPs (for DNS):"
echo "  Primary: $PRIMARY_IP"
echo "  Secondary: $SECONDARY_IP"
echo ""
echo "PostgreSQL:"
echo "  Primary: ${RESOURCE_PREFIX}-pg-primary.postgres.database.azure.com"
echo "  Replica: ${RESOURCE_PREFIX}-pg-replica.postgres.database.azure.com"
echo "  Admin User: dradmin"
echo "  Password: See pg_credentials.txt"
echo ""
echo "Container Registry:"
echo "  ${RESOURCE_PREFIX}acr.azurecr.io"
echo ""
echo "NEXT STEPS:"
echo "1. Update your DNS A record to point to: $PRIMARY_IP"
echo "2. Run deployment script: ./deploy-applications.sh"
echo "3. Configure monitoring: ./setup-monitoring.sh"
echo "=========================================="

# Save configuration for later use
cat > dr-config.sh << EOF
export PRIMARY_REGION="$PRIMARY_REGION"
export SECONDARY_REGION="$SECONDARY_REGION"
export RESOURCE_PREFIX="$RESOURCE_PREFIX"
export PRIMARY_IP="$PRIMARY_IP"
export SECONDARY_IP="$SECONDARY_IP"
export PRIMARY_AKS="${RESOURCE_PREFIX}-aks-primary"
export SECONDARY_AKS="${RESOURCE_PREFIX}-aks-secondary"
export PRIMARY_RG="${RESOURCE_PREFIX}-primary-rg"
export SECONDARY_RG="${RESOURCE_PREFIX}-secondary-rg"
export PG_PRIMARY="${RESOURCE_PREFIX}-pg-primary"
export PG_REPLICA="${RESOURCE_PREFIX}-pg-replica"
EOF

log_info "Configuration saved to dr-config.sh"
```

---

## 3. Manual Deployment Procedures

### 3.1 Application Deployment Script (Without GitOps)

```bash
#!/bin/bash
# deploy-applications.sh
# Manual deployment to both AKS clusters

set -euo pipefail
source ./dr-config.sh

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# ============================================
# KUBERNETES MANIFESTS PREPARATION
# ============================================
log_info "Preparing Kubernetes manifests..."

# Create namespace manifest
cat > namespace.yaml << EOF
apiVersion: v1
kind: Namespace
metadata:
  name: production
---
apiVersion: v1
kind: Namespace
metadata:
  name: monitoring
EOF

# Create ConfigMap for application configuration
cat > configmap.yaml << EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  namespace: production
data:
  DB_HOST: "${RESOURCE_PREFIX}-pg-primary.postgres.database.azure.com"
  DB_NAME: "platformdb"
  DB_PORT: "5432"
  COSMOS_ENDPOINT: "https://${RESOURCE_PREFIX}-cosmos.documents.azure.com:443/"
  SEARCH_ENDPOINT: "https://${RESOURCE_PREFIX}-search-primary.search.windows.net"
  STORAGE_ACCOUNT: "${RESOURCE_PREFIX}storage"
  REGION: "primary"
  MAINTENANCE_MODE: "false"
EOF

# Create application deployment
cat > deployment.yaml << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-app
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web-app
  template:
    metadata:
      labels:
        app: web-app
    spec:
      containers:
      - name: app
        image: ${RESOURCE_PREFIX}acr.azurecr.io/web-app:latest
        ports:
        - containerPort: 8080
        envFrom:
        - configMapRef:
            name: app-config
        env:
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: password
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
EOF

# Create service with LoadBalancer (using static IP)
cat > service.yaml << EOF
apiVersion: v1
kind: Service
metadata:
  name: web-app-service
  namespace: production
  annotations:
    service.beta.kubernetes.io/azure-load-balancer-resource-group: "${RESOURCE_PREFIX}-primary-nodes-rg"
spec:
  type: LoadBalancer
  loadBalancerIP: "${PRIMARY_IP}"
  ports:
  - port: 80
    targetPort: 8080
  selector:
    app: web-app
EOF

# Create HPA for autoscaling
cat > hpa.yaml << EOF
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: web-app-hpa
  namespace: production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: web-app
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
EOF

# ============================================
# DEPLOY TO PRIMARY CLUSTER
# ============================================
log_info "Deploying to PRIMARY cluster..."

# Get AKS credentials
az aks get-credentials \
    --resource-group "$PRIMARY_RG" \
    --name "$PRIMARY_AKS" \
    --overwrite-existing

# Get ACR credentials and create secret
ACR_PASSWORD=$(az acr credential show \
    --name "${RESOURCE_PREFIX}acr" \
    --query "passwords[0].value" -o tsv)

# Create namespaces
kubectl apply -f namespace.yaml

# Create ACR secret
kubectl create secret docker-registry acr-secret \
    --docker-server="${RESOURCE_PREFIX}acr.azurecr.io" \
    --docker-username="${RESOURCE_PREFIX}acr" \
    --docker-password="$ACR_PASSWORD" \
    --namespace=production \
    --dry-run=client -o yaml | kubectl apply -f -

# Create database secret
PG_PASSWORD=$(cat pg_credentials.txt | grep "PostgreSQL Password:" | cut -d' ' -f3)
kubectl create secret generic db-secret \
    --from-literal=password="$PG_PASSWORD" \
    --namespace=production \
    --dry-run=client -o yaml | kubectl apply -f -

# Deploy application
kubectl apply -f configmap.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f hpa.yaml

# Wait for deployment
log_info "Waiting for PRIMARY deployment to be ready..."
kubectl rollout status deployment/web-app -n production --timeout=300s

# ============================================
# DEPLOY TO SECONDARY CLUSTER
# ============================================
log_info "Deploying to SECONDARY cluster..."

# Get AKS credentials for secondary
az aks get-credentials \
    --resource-group "$SECONDARY_RG" \
    --name "$SECONDARY_AKS" \
    --overwrite-existing

# Update ConfigMap for secondary region
sed -i "s/pg-primary/pg-replica/g" configmap.yaml
sed -i "s/search-primary/search-secondary/g" configmap.yaml
sed -i "s/REGION: \"primary\"/REGION: \"secondary\"/g" configmap.yaml

# Update Service for secondary IP
cat > service-secondary.yaml << EOF
apiVersion: v1
kind: Service
metadata:
  name: web-app-service
  namespace: production
  annotations:
    service.beta.kubernetes.io/azure-load-balancer-resource-group: "${RESOURCE_PREFIX}-secondary-nodes-rg"
spec:
  type: LoadBalancer
  loadBalancerIP: "${SECONDARY_IP}"
  ports:
  - port: 80
    targetPort: 8080
  selector:
    app: web-app
EOF

# Update deployment replicas for secondary (cost optimization)
sed -i "s/replicas: 3/replicas: 1/g" deployment.yaml

# Create namespaces
kubectl apply -f namespace.yaml

# Create secrets
kubectl create secret docker-registry acr-secret \
    --docker-server="${RESOURCE_PREFIX}acr.azurecr.io" \
    --docker-username="${RESOURCE_PREFIX}acr" \
    --docker-password="$ACR_PASSWORD" \
    --namespace=production \
    --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic db-secret \
    --from-literal=password="$PG_PASSWORD" \
    --namespace=production \
    --dry-run=client -o yaml | kubectl apply -f -

# Deploy application
kubectl apply -f configmap.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service-secondary.yaml

# Don't apply HPA to secondary (cost optimization)
# kubectl apply -f hpa.yaml

log_info "Waiting for SECONDARY deployment to be ready..."
kubectl rollout status deployment/web-app -n production --timeout=300s

# ============================================
# VERIFICATION
# ============================================
log_info "Verifying deployments..."

# Check primary
az aks get-credentials --resource-group "$PRIMARY_RG" --name "$PRIMARY_AKS" --overwrite-existing
echo ""
echo "PRIMARY Cluster Status:"
kubectl get pods -n production
kubectl get svc -n production

# Check secondary
az aks get-credentials --resource-group "$SECONDARY_RG" --name "$SECONDARY_AKS" --overwrite-existing
echo ""
echo "SECONDARY Cluster Status:"
kubectl get pods -n production
kubectl get svc -n production

log_info "Deployment complete!"
echo ""
echo "=========================================="
echo "DEPLOYMENT COMPLETE"
echo "=========================================="
echo "Primary Application URL: http://${PRIMARY_IP}"
echo "Secondary Application URL: http://${SECONDARY_IP} (standby)"
echo ""
echo "To test:"
echo "  curl http://${PRIMARY_IP}/health"
echo ""
echo "DNS Configuration Required:"
echo "  Point your domain A record to: ${PRIMARY_IP}"
echo "=========================================="
```

### 3.2 Manual Application Update Script

```bash
#!/bin/bash
# update-application.sh
# Manually update application on both clusters

set -euo pipefail
source ./dr-config.sh

# Parameters
VERSION=${1:-latest}
DEPLOYMENT=${2:-web-app}
NAMESPACE=${3:-production}

log_info() {
    echo "[INFO] $1"
}

log_info "Updating $DEPLOYMENT to version $VERSION"

# Update function
update_cluster() {
    local CLUSTER_NAME=$1
    local RESOURCE_GROUP=$2
    local REGION=$3
    
    log_info "Updating $REGION cluster..."
    
    # Get credentials
    az aks get-credentials \
        --resource-group "$RESOURCE_GROUP" \
        --name "$CLUSTER_NAME" \
        --overwrite-existing
    
    # Update image
    kubectl set image deployment/$DEPLOYMENT \
        $DEPLOYMENT=${RESOURCE_PREFIX}acr.azurecr.io/$DEPLOYMENT:$VERSION \
        -n $NAMESPACE
    
    # Wait for rollout
    kubectl rollout status deployment/$DEPLOYMENT -n $NAMESPACE --timeout=300s
    
    # Verify
    kubectl get pods -n $NAMESPACE -l app=$DEPLOYMENT
}

# Update Primary
update_cluster "$PRIMARY_AKS" "$PRIMARY_RG" "PRIMARY"

# Update Secondary
update_cluster "$SECONDARY_AKS" "$SECONDARY_RG" "SECONDARY"

log_info "Update complete on both clusters!"
```

---

## 4. Daily Operations Scripts

### 4.1 Health Check Script

```bash
#!/bin/bash
# daily-health-check.sh
# Manual health checks without monitoring tools

set -euo pipefail
source ./dr-config.sh

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "DR Platform Daily Health Check"
echo "Date: $(date)"
echo "=========================================="

# Function to check service
check_service() {
    local SERVICE=$1
    local EXPECTED=$2
    local ACTUAL=$3
    
    if [ "$ACTUAL" == "$EXPECTED" ]; then
        echo -e "${GREEN}✓${NC} $SERVICE: Healthy"
        return 0
    else
        echo -e "${RED}✗${NC} $SERVICE: Unhealthy (Status: $ACTUAL)"
        return 1
    fi
}

ERRORS=0

# Check AKS Clusters
echo -e "\n--- AKS Clusters ---"
PRIMARY_AKS_STATUS=$(az aks show -g "$PRIMARY_RG" -n "$PRIMARY_AKS" --query powerState.code -o tsv 2>/dev/null || echo "Failed")
check_service "Primary AKS" "Running" "$PRIMARY_AKS_STATUS" || ((ERRORS++))

SECONDARY_AKS_STATUS=$(az aks show -g "$SECONDARY_RG" -n "$SECONDARY_AKS" --query powerState.code -o tsv 2>/dev/null || echo "Failed")
check_service "Secondary AKS" "Running" "$SECONDARY_AKS_STATUS" || ((ERRORS++))

# Check PostgreSQL
echo -e "\n--- PostgreSQL ---"
PG_PRIMARY_STATUS=$(az postgres flexible-server show -g "$PRIMARY_RG" -n "$PG_PRIMARY" --query state -o tsv 2>/dev/null || echo "Failed")
check_service "Primary PostgreSQL" "Ready" "$PG_PRIMARY_STATUS" || ((ERRORS++))

PG_REPLICA_STATUS=$(az postgres flexible-server show -g "$SECONDARY_RG" -n "$PG_REPLICA" --query state -o tsv 2>/dev/null || echo "Failed")
check_service "PostgreSQL Replica" "Ready" "$PG_REPLICA_STATUS" || ((ERRORS++))

# Check Replication Lag
echo -e "\n--- Replication Status ---"
REPLICATION_LAG=$(az postgres flexible-server replica list \
    -g "$PRIMARY_RG" \
    --server "$PG_PRIMARY" \
    --query "[0].replicationLag" -o tsv 2>/dev/null || echo "Unknown")

if [ "$REPLICATION_LAG" != "Unknown" ] && [ "$REPLICATION_LAG" -lt "300" ]; then
    echo -e "${GREEN}✓${NC} PostgreSQL Replication Lag: ${REPLICATION_LAG} seconds"
else
    echo -e "${YELLOW}⚠${NC} PostgreSQL Replication Lag: ${REPLICATION_LAG} seconds"
    ((ERRORS++))
fi

# Check Cosmos DB
echo -e "\n--- Cosmos DB ---"
COSMOS_STATUS=$(az cosmosdb show -g "${RESOURCE_PREFIX}-shared-rg" -n "${RESOURCE_PREFIX}-cosmos" --query provisioningState -o tsv 2>/dev/null || echo "Failed")
check_service "Cosmos DB" "Succeeded" "$COSMOS_STATUS" || ((ERRORS++))

# Check Application Pods
echo -e "\n--- Application Status ---"

# Primary cluster
az aks get-credentials -g "$PRIMARY_RG" -n "$PRIMARY_AKS" --overwrite-existing 2>/dev/null
PRIMARY_PODS=$(kubectl get pods -n production --no-headers 2>/dev/null | grep -c "Running" || echo "0")
echo "Primary Cluster: $PRIMARY_PODS pods running"

# Secondary cluster
az aks get-credentials -g "$SECONDARY_RG" -n "$SECONDARY_AKS" --overwrite-existing 2>/dev/null
SECONDARY_PODS=$(kubectl get pods -n production --no-headers 2>/dev/null | grep -c "Running" || echo "0")
echo "Secondary Cluster: $SECONDARY_PODS pods running"

# Check Public IPs
echo -e "\n--- Public IP Status ---"
echo "Primary IP: $PRIMARY_IP"
echo "Secondary IP: $SECONDARY_IP"

# Test application endpoints
echo -e "\n--- Application Endpoints ---"
PRIMARY_HTTP=$(curl -s -o /dev/null -w "%{http_code}" "http://${PRIMARY_IP}/health" 2>/dev/null || echo "000")
if [ "$PRIMARY_HTTP" == "200" ]; then
    echo -e "${GREEN}✓${NC} Primary endpoint responding"
else
    echo -e "${RED}✗${NC} Primary endpoint not responding (HTTP $PRIMARY_HTTP)"
    ((ERRORS++))
fi

# Summary
echo -e "\n=========================================="
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}Health Check PASSED - All systems operational${NC}"
else
    echo -e "${RED}Health Check FAILED - $ERRORS issues found${NC}"
fi
echo "=========================================="

exit $ERRORS
```

### 4.2 Backup Script

```bash
#!/bin/bash
# backup-databases.sh
# Manual backup of databases

set -euo pipefail
source ./dr-config.sh

BACKUP_DATE=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="./backups/$BACKUP_DATE"

log_info() {
    echo "[INFO] $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_info "Starting backup process..."

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup PostgreSQL
log_info "Backing up PostgreSQL..."
PG_PASSWORD=$(cat pg_credentials.txt | grep "PostgreSQL Password:" | cut -d' ' -f3)

PGPASSWORD=$PG_PASSWORD pg_dump \
    -h "${PG_PRIMARY}.postgres.database.azure.com" \
    -U "dradmin" \
    -d "platformdb" \
    -f "$BACKUP_DIR/postgresql-backup.sql"

if [ $? -eq 0 ]; then
    log_info "PostgreSQL backup completed"
else
    log_info "PostgreSQL backup failed"
fi

# Backup Cosmos DB
log_info "Initiating Cosmos DB backup..."
az cosmosdb sql container backup \
    --resource-group "${RESOURCE_PREFIX}-shared-rg" \
    --account-name "${RESOURCE_PREFIX}-cosmos" \
    --database-name "platformdb" \
    --container-name "documents"

# Backup Kubernetes configurations
log_info "Backing up Kubernetes configurations..."

# Primary cluster
az aks get-credentials -g "$PRIMARY_RG" -n "$PRIMARY_AKS" --overwrite-existing
kubectl get all -A -o yaml > "$BACKUP_DIR/k8s-primary-all.yaml"
kubectl get configmap -A -o yaml > "$BACKUP_DIR/k8s-primary-configmaps.yaml"
kubectl get secrets -A -o yaml > "$BACKUP_DIR/k8s-primary-secrets.yaml"

# Secondary cluster
az aks get-credentials -g "$SECONDARY_RG" -n "$SECONDARY_AKS" --overwrite-existing
kubectl get all -A -o yaml > "$BACKUP_DIR/k8s-secondary-all.yaml"

# Compress backup
log_info "Compressing backup..."
tar -czf "backup-$BACKUP_DATE.tar.gz" -C ./backups "$BACKUP_DATE"

# Upload to storage
log_info "Uploading to Azure Storage..."
az storage blob upload \
    --account-name "${RESOURCE_PREFIX}storage" \
    --container-name "backups" \
    --name "backup-$BACKUP_DATE.tar.gz" \
    --file "backup-$BACKUP_DATE.tar.gz" \
    --auth-mode login

log_info "Backup completed successfully!"
echo "Backup saved to: backup-$BACKUP_DATE.tar.gz"
```

---

## 5. Disaster Recovery Scripts

### 5.1 Complete Failover Script (Manual DNS Update Required)

```bash
#!/bin/bash
# dr-failover.sh
# Complete DR failover script with manual DNS update

set -euo pipefail
source ./dr-config.sh

# Parameters
FAILOVER_TYPE=${1:-"planned"}  # planned or emergency
DRY_RUN=${2:-"false"}

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging
LOG_FILE="dr-failover-$(date +%Y%m%d-%H%M%S).log"

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

# ============================================
# FAILOVER START
# ============================================
echo "=========================================="
echo "DISASTER RECOVERY FAILOVER"
echo "Type: $FAILOVER_TYPE"
echo "Dry Run: $DRY_RUN"
echo "Time: $(date)"
echo "=========================================="

# Step 1: Pre-failover validation
log_info "Step 1: Validating secondary region..."

SECONDARY_AKS_STATUS=$(az aks show -g "$SECONDARY_RG" -n "$SECONDARY_AKS" --query powerState.code -o tsv)
if [ "$SECONDARY_AKS_STATUS" != "Running" ]; then
    log_error "Secondary AKS cluster is not running!"
    if [ "$FAILOVER_TYPE" != "emergency" ]; then
        exit 1
    fi
fi

# Step 2: Scale up secondary cluster
log_info "Step 2: Scaling up secondary cluster..."

if [ "$DRY_RUN" == "false" ]; then
    az aks nodepool scale \
        --resource-group "$SECONDARY_RG" \
        --cluster-name "$SECONDARY_AKS" \
        --name "nodepool1" \
        --node-count 3
    
    log_info "Waiting for nodes to be ready (this may take 5 minutes)..."
    sleep 300
fi

# Step 3: PostgreSQL Failover
log_info "Step 3: Promoting PostgreSQL read replica..."

if [ "$FAILOVER_TYPE" == "planned" ]; then
    # Check replication lag
    REPLICATION_LAG=$(az postgres flexible-server replica list \
        -g "$PRIMARY_RG" \
        --server "$PG_PRIMARY" \
        --query "[0].replicationLag" -o tsv || echo "999999")
    
    if [ "$REPLICATION_LAG" -gt "60" ]; then
        log_warn "Replication lag is $REPLICATION_LAG seconds. Waiting..."
        if [ "$DRY_RUN" == "false" ]; then
            sleep 60
        fi
    fi
fi

if [ "$DRY_RUN" == "false" ]; then
    log_info "Promoting PostgreSQL replica to primary..."
    az postgres flexible-server replica promote \
        --resource-group "$SECONDARY_RG" \
        --replica-name "$PG_REPLICA" \
        --promote-mode standalone \
        --promote-option "$FAILOVER_TYPE"
fi

# Step 4: Cosmos DB Failover
log_info "Step 4: Failing over Cosmos DB..."

if [ "$DRY_RUN" == "false" ]; then
    az cosmosdb failover-priority-change \
        --name "${RESOURCE_PREFIX}-cosmos" \
        --resource-group "${RESOURCE_PREFIX}-shared-rg" \
        --failover-policies "${SECONDARY_REGION}=0" "${PRIMARY_REGION}=1"
fi

# Step 5: Update application configurations
log_info "Step 5: Updating application configurations..."

# Get credentials for secondary cluster
az aks get-credentials -g "$SECONDARY_RG" -n "$SECONDARY_AKS" --overwrite-existing

if [ "$DRY_RUN" == "false" ]; then
    # Update ConfigMap to use promoted PostgreSQL
    kubectl patch configmap app-config -n production --type merge -p \
        "{\"data\":{\"DB_HOST\":\"${PG_REPLICA}.postgres.database.azure.com\",\"REGION\":\"secondary-active\"}}"
    
    # Scale up applications
    kubectl scale deployment web-app --replicas=3 -n production
    
    # Restart pods to pick up new configuration
    kubectl rollout restart deployment -n production
    
    # Wait for rollout
    kubectl rollout status deployment/web-app -n production --timeout=300s
fi

# Step 6: DNS Update Instructions
log_warn "Step 6: MANUAL DNS UPDATE REQUIRED!"
echo ""
echo "=========================================="
echo -e "${RED}ACTION REQUIRED: UPDATE DNS${NC}"
echo "=========================================="
echo "Update your DNS A record from:"
echo "  Current: $PRIMARY_IP"
echo "  To:      $SECONDARY_IP"
echo ""
echo "DNS Provider Instructions:"
echo "1. Log in to your DNS provider"
echo "2. Find the A record for your domain"
echo "3. Change the IP address to: $SECONDARY_IP"
echo "4. Save the changes"
echo "5. Wait for DNS propagation (5-30 minutes)"
echo "=========================================="

# Step 7: Verification
log_info "Step 7: Verifying failover..."

if [ "$DRY_RUN" == "false" ]; then
    # Check application health
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://${SECONDARY_IP}/health" || echo "000")
    if [ "$HTTP_STATUS" == "200" ]; then
        log_info "Application is responding on secondary region"
    else
        log_error "Application health check failed (HTTP $HTTP_STATUS)"
    fi
    
    # Check pod status
    kubectl get pods -n production
fi

# Summary
echo ""
echo "=========================================="
echo "FAILOVER SUMMARY"
echo "=========================================="
echo "Status: COMPLETE (Pending DNS Update)"
echo "Active Region: $SECONDARY_REGION"
echo "Active IP: $SECONDARY_IP"
echo "Database: ${PG_REPLICA}.postgres.database.azure.com"
echo ""
echo "Next Steps:"
echo "1. Update DNS A record to: $SECONDARY_IP"
echo "2. Monitor application at: http://${SECONDARY_IP}"
echo "3. Verify DNS propagation: nslookup yourdomain.com"
echo "=========================================="

# Save failover state
cat > failover-state.txt << EOF
FAILOVER_DATE: $(date)
ACTIVE_REGION: $SECONDARY_REGION
ACTIVE_IP: $SECONDARY_IP
PREVIOUS_REGION: $PRIMARY_REGION
PREVIOUS_IP: $PRIMARY_IP
EOF

log_info "Failover completed. State saved to failover-state.txt"
```

### 5.2 Failback Script

```bash
#!/bin/bash
# dr-failback.sh
# Failback to primary region

set -euo pipefail
source ./dr-config.sh

log_info() {
    echo "[INFO] $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

echo "=========================================="
echo "DISASTER RECOVERY FAILBACK"
echo "Returning to PRIMARY region"
echo "=========================================="

# Step 1: Verify primary region is healthy
log_info "Verifying primary region health..."

PRIMARY_AKS_STATUS=$(az aks show -g "$PRIMARY_RG" -n "$PRIMARY_AKS" --query powerState.code -o tsv)
if [ "$PRIMARY_AKS_STATUS" != "Running" ]; then
    echo "ERROR: Primary AKS cluster is not running!"
    exit 1
fi

# Step 2: Re-create PostgreSQL primary from promoted replica
log_info "Re-creating PostgreSQL primary server..."

# This requires manual recreation as the original primary no longer exists
echo "Manual steps required:"
echo "1. Create new PostgreSQL server in primary region"
echo "2. Restore from backup or migrate data from current primary"
echo "3. Re-establish replication"

# Step 3: Update applications
log_info "Updating application configurations in primary..."

az aks get-credentials -g "$PRIMARY_RG" -n "$PRIMARY_AKS" --overwrite-existing

kubectl patch configmap app-config -n production --type merge -p \
    "{\"data\":{\"DB_HOST\":\"${PG_PRIMARY}.postgres.database.azure.com\",\"REGION\":\"primary\"}}"

kubectl rollout restart deployment -n production

# Step 4: DNS Update
echo ""
echo "=========================================="
echo "ACTION REQUIRED: UPDATE DNS"
echo "=========================================="
echo "Update your DNS A record from:"
echo "  Current: $SECONDARY_IP"
echo "  To:      $PRIMARY_IP"
echo "=========================================="

# Step 5: Scale down secondary
log_info "Scaling down secondary cluster..."

az aks nodepool scale \
    --resource-group "$SECONDARY_RG" \
    --cluster-name "$SECONDARY_AKS" \
    --name "nodepool1" \
    --node-count 2

log_info "Failback process initiated. Manual steps required for completion."
```

---

## 6. Testing Procedures

### 6.1 DR Test Script

```bash
#!/bin/bash
# test-dr-readiness.sh
# Test DR readiness without actual failover

set -euo pipefail
source ./dr-config.sh

TESTS_PASSED=0
TESTS_FAILED=0

run_test() {
    local TEST_NAME=$1
    local TEST_CMD=$2
    
    echo -n "Testing $TEST_NAME... "
    if eval "$TEST_CMD" > /dev/null 2>&1; then
        echo "✓ PASSED"
        ((TESTS_PASSED++))
    else
        echo "✗ FAILED"
        ((TESTS_FAILED++))
    fi
}

echo "=========================================="
echo "DR READINESS TEST"
echo "Date: $(date)"
echo "=========================================="

# Test 1: Secondary AKS is running
run_test "Secondary AKS Status" \
    "[ '$(az aks show -g $SECONDARY_RG -n $SECONDARY_AKS --query powerState.code -o tsv)' == 'Running' ]"

# Test 2: PostgreSQL replica exists
run_test "PostgreSQL Replica" \
    "az postgres flexible-server show -g $SECONDARY_RG -n $PG_REPLICA"

# Test 3: Replication lag is acceptable
run_test "Replication Lag < 5 min" \
    "[ '$(az postgres flexible-server replica list -g $PRIMARY_RG --server $PG_PRIMARY --query \"[0].replicationLag\" -o tsv)' -lt '300' ]"

# Test 4: Cosmos DB multi-region is configured
run_test "Cosmos DB Multi-Region" \
    "[ '$(az cosmosdb show -g ${RESOURCE_PREFIX}-shared-rg -n ${RESOURCE_PREFIX}-cosmos --query \"locations | length(@)\")' -gt '1' ]"

# Test 5: Container Registry geo-replication
run_test "ACR Geo-Replication" \
    "az acr replication list --registry ${RESOURCE_PREFIX}acr --query \"[?location=='$SECONDARY_REGION']\" | grep -q $SECONDARY_REGION"

# Test 6: Secondary application pods exist
run_test "Secondary Pods" \
    "az aks get-credentials -g $SECONDARY_RG -n $SECONDARY_AKS --overwrite-existing && kubectl get pods -n production"

# Test 7: Backup exists
run_test "Recent Backup" \
    "az storage blob list --account-name ${RESOURCE_PREFIX}storage --container-name backups --auth-mode login --query \"[0].name\""

# Summary
echo ""
echo "=========================================="
echo "TEST RESULTS"
echo "=========================================="
echo "Tests Passed: $TESTS_PASSED"
echo "Tests Failed: $TESTS_FAILED"

if [ $TESTS_FAILED -eq 0 ]; then
    echo "Status: READY FOR FAILOVER"
else
    echo "Status: NOT READY - Fix failed tests"
fi
echo "=========================================="
```

---

## 7. Troubleshooting Guide

### 7.1 Common Issues

#### Issue: DNS not updating after failover
**Solution:**
```bash
# Check current DNS resolution
nslookup yourdomain.com

# Force DNS flush (Windows)
ipconfig /flushdns

# Force DNS flush (Linux/Mac)
sudo dscacheutil -flushcache

# Use host file for immediate testing
echo "$SECONDARY_IP yourdomain.com" | sudo tee -a /etc/hosts
```

#### Issue: Pods not starting after failover
**Solution:**
```bash
# Check pod events
kubectl describe pod <pod-name> -n production

# Check secrets
kubectl get secrets -n production

# Recreate secrets if needed
kubectl delete secret db-secret -n production
kubectl create secret generic db-secret \
    --from-literal=password="<password>" \
    -n production
```

#### Issue: Application can't connect to database
**Solution:**
```bash
# Test database connectivity
kubectl run -it --rm debug --image=postgres:15 --restart=Never -- \
    psql "postgresql://dradmin@${PG_REPLICA}.postgres.database.azure.com:5432/platformdb?sslmode=require"

# Update connection string
kubectl edit configmap app-config -n production
```

### 7.2 Recovery Procedures

#### Recover from Failed Failover
```bash
#!/bin/bash
# recover-failed-failover.sh

# Check current state
source ./dr-config.sh

# Determine active region
if curl -s "http://${PRIMARY_IP}/health" > /dev/null 2>&1; then
    echo "Primary is active"
    ACTIVE_REGION="primary"
else
    echo "Secondary is active"
    ACTIVE_REGION="secondary"
fi

# Fix based on active region
if [ "$ACTIVE_REGION" == "primary" ]; then
    # Ensure primary is properly configured
    az aks get-credentials -g "$PRIMARY_RG" -n "$PRIMARY_AKS" --overwrite-existing
    kubectl patch configmap app-config -n production --type merge -p \
        "{\"data\":{\"REGION\":\"primary\"}}"
else
    # Ensure secondary is properly configured
    az aks get-credentials -g "$SECONDARY_RG" -n "$SECONDARY_AKS" --overwrite-existing
    kubectl patch configmap app-config -n production --type merge -p \
        "{\"data\":{\"REGION\":\"secondary\"}}"
fi

kubectl rollout restart deployment -n production
```

This simplified manual approach:
1. **Removes Azure Front Door** - Uses manual DNS updates instead
2. **Removes GitOps/Flux** - Uses manual kubectl deployments
3. **Provides clear scripts** for all operations
4. **Includes manual DNS update instructions** at each failover
5. **Simplifies monitoring** to basic health checks
6. **Reduces complexity** while maintaining DR capabilities

The key differences:
- DNS failover is manual (update A records)
- Application deployment uses kubectl directly
- Configuration updates are manual
- No automated synchronization (all manual)
- Simpler architecture with lower cost
- Clear step-by-step procedures for all operations