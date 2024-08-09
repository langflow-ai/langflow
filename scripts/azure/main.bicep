@description('The location where the resources will be created.')
param location string

@description('The name of the container group.')
param containerGroupName string

@description('The base name of the storage account.')
param storageAccountName string

@description('The base name of the PostgreSQL server.')
param postgresServerName string

@description('The admin username for the PostgreSQL server.')
param postgresAdmin string

@description('The admin password for the PostgreSQL server.')
@secure()
param postgresPassword string

@description('The name of the container app environment.')
param containerAppEnvironmentName string

@description('The name of the log analytics workspace.')
param logAnalyticsWorkspaceName string

@description('The base name of the container registry.')
param containerRegistryName string

var uniqueStringSuffix = substring(uniqueString(resourceGroup().id), 0, 5)
var storageAccountNameUnique = '${storageAccountName}${uniqueStringSuffix}'
var containerRegistryNameUnique = '${containerRegistryName}${uniqueStringSuffix}'
var postgresServerNameUnique = '${postgresServerName}${uniqueStringSuffix}'

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2021-06-01' = {
  name: logAnalyticsWorkspaceName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource postgresServer 'Microsoft.DBforPostgreSQL/flexibleServers@2023-12-01-preview' = {
  name: postgresServerNameUnique
  location: location
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
    capacity: 1
  }
  properties: {
    version: '16'
    administratorLogin: postgresAdmin
    administratorLoginPassword: postgresPassword
    storage: {
      storageSizeGB: 32
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
    network: {
      publicNetworkAccess: 'Enabled'
    }
  }
}

resource postgresDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-12-01-preview' = {
  parent: postgresServer
  name: 'langflow'
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

resource postgresFirewallRule 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-12-01-preview' = {
  parent: postgresServer
  name: 'AllowAllAzureIPs'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource containerAppEnvironment 'Microsoft.App/managedEnvironments@2023-08-01-preview' = {
  name: containerAppEnvironmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspace.properties.customerId
        sharedKey: logAnalyticsWorkspace.listKeys().primarySharedKey
      }
    }
  }
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2019-05-01' = {
  name: containerRegistryNameUnique
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2019-06-01' = {
  name: storageAccountNameUnique
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
  }
}

resource appStorage 'Microsoft.App/managedEnvironments/storages@2023-08-01-preview' = {
  parent: containerAppEnvironment
  name: 'langflow-storage'
  properties: {
    azureFile: {
      accessMode: 'ReadWrite'
      accountName: storageAccount.name
      accountKey: storageAccount.listKeys().keys[0].value
      shareName: 'appconfig'
    }
  }
}

resource fileShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2021-02-01' = {
  name: '${storageAccount.name}/default/appconfig'
  properties: {
    accessTier: 'TransactionOptimized'
  }
}

resource containerApp 'Microsoft.App/containerapps@2023-08-01-preview' = {
  name: containerGroupName
  location: location
  properties: {
    managedEnvironmentId: containerAppEnvironment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 7860
      }
    }
    template: {
      containers: [
        {
          name: 'langflow'
          image: 'langflowai/langflow:latest'
          resources: {
            cpu: json('1')
            memory: '2.0Gi'
          }
          env: [
            {
              name: 'LANGFLOW_DATABASE_URL'
              value: 'postgresql://${postgresAdmin}:${postgresPassword}@${postgresServerNameUnique}.postgres.database.azure.com:5432/langflow?sslmode=require'
            }
            {
              name: 'LANGFLOW_CONFIG_DIR'
              value: '/mnt/data'
            }
            {
              name: 'LANGFLOW_AUTO_LOGIN'
              value: 'true'
            }
            {
              name: 'LANGFLOW_SUPERUSER'
              value: 'admin'
            }
            {
              name: 'LANGFLOW_SUPERUSER_PASSWORD'
              value: '04W8oQTd'
            }
          ]
          volumeMounts: [
            {
              volumeName: 'appconfigvol'
              mountPath: '/mnt/data'
            }
          ]
        }
      ]
      volumes: [
        {
          name: 'appconfigvol'
          storageType: 'AzureFile'
          storageName: 'langflow-storage'
        }
      ]
    }
  }
}
