// Template Name: Langflow Docker Deployment

@description('The name of our application. It has to be unique. Type a name followed by your resource group name. (<name>-<resourceGroupName>)')
param webAppName string = 'LangFlow-${uniqueString(resourceGroup().id)}'

@description('Location for all resources.')
param location string = resourceGroup().location

var sku = 'PremiumV2'
var skuCode = 'P2v2'
var workerSize = 2
var appInsightName = '${webAppName}-insights'
var hostingPlanName = 'hpn-${resourceGroup().name}'

resource hostingPlan 'Microsoft.Web/serverfarms@2022-03-01' = {
  name: hostingPlanName
  location: location
  sku: {
    tier: sku
    name: skuCode
  }
  kind: 'linux'
  properties: {
    reserved: true
    targetWorkerSizeId: workerSize
    targetWorkerCount: 1
  }
}

resource webApp 'Microsoft.Web/sites@2022-03-01' = {
  name: webAppName
  location: location
  properties: {
    siteConfig: {
      appSettings: [
        {
          name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE'
          value: 'false'
        }
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: appInsights.properties.InstrumentationKey
        }
        {
          name: 'XDT_MicrosoftApplicationInsights_Mode'
          value: 'default'
        }
        {
          name: 'ApplicationInsightsAgent_EXTENSION_VERSION'
          value: '~2'
        }
        {
          name: 'WEBSITES_PORT'
          value: '7860'
        }
        {
          name: 'DOCKER_CUSTOM_IMAGE_NAME'
          value: 'langflowai/langflow:latest'
        }
      ]
      linuxFxVersion: 'DOCKER|langflowai/langflow:latest'
    }
    clientAffinityEnabled: false
    serverFarmId: hostingPlan.id
    httpsOnly: true
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
  }
}

output webAppNameOutput string = webAppName
output appInsightInstrumentationKey string = appInsights.properties.InstrumentationKey
