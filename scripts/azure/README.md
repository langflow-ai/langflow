# Variables
RESOURCE_GROUP="connectorzzz-langflow-rg"

# Create the resource group if it doesn't exist
az group create --name $RESOURCE_GROUP --location "swedencentral"

# Deploy the template
az deployment group create --resource-group $RESOURCE_GROUP --template-file azuredeploy.json --parameters @azuredeploy.parameters.json


```mermaid
graph TD;

subgraph AzureDeployment["Langflow On Azure"]
    LogAnalyticsWorkspace["Log Analytics<br/>Workspace"]
    PostgreSQLServer["PostgreSQL <br/>Flexible Server"]
    PostgreSQLDatabase["PostgreSQL DB"]
    ContainerAppEnv["Container Apps<br/>Environment"]
    ContainerGroup["Container App<br/> (Langflow)"]
    StorageAccount["Storage Account"]
    ContainerRegistry["Container Registry"]
end

ContainerGroup -->|uses| LogAnalyticsWorkspace
PostgreSQLServer -->|contains| PostgreSQLDatabase
ContainerGroup -->|dependsOn| PostgreSQLServer
ContainerGroup -->|contains| StorageAccount
ContainerAppEnv -->|contains| ContainerGroup
ContainerGroup -->|uses| ContainerRegistry



%% Individual node styling. Try the visual editor toolbar for easier styling!
    style ContainerGroup color:#FFFFFF, fill:#AA00FF, stroke:#AA00FF

```