param location string = resourceGroup().location
param appName string = 'bizcomai-${uniqueString(resourceGroup().id)}'

// Azure Static Web App for Frontend
resource staticWebApp 'Microsoft.Web/staticSites@2022-09-01' = {
  name: '${appName}-frontend'
  location: location
  sku: {
    name: 'Free'
    tier: 'Free'
  }
  properties: {}
}

// App Service Plan for Backend
resource appServicePlan 'Microsoft.Web/serverfarms@2022-09-01' = {
  name: '${appName}-asp'
  location: location
  sku: {
    name: 'B1'
    tier: 'Basic'
  }
  kind: 'linux'
  properties: {
    reserved: true
  }
}

// App Service for Python Backend
resource appService 'Microsoft.Web/sites@2022-09-01' = {
  name: '${appName}-backend'
  location: location
  kind: 'app,linux'
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      appSettings: [
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
      ]
    }
  }
}

// Cognitive Services for Voice/Translation (Person B)
resource cognitiveServices 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: '${appName}-cog'
  location: location
  kind: 'CognitiveServices'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: '${appName}-cog'
  }
}

output frontendUrl string = staticWebApp.properties.defaultHostname
output backendUrl string = appService.properties.defaultHostName
