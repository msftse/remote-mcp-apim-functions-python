@description('The name of the Container Apps Environment')
param containerAppEnvName string

@description('The name of the Container App')
param containerAppName string

@description('Location for all resources')
param location string

@description('Tags for all resources')
param tags object = {}

@description('The container image to deploy')
param containerImage string

@description('The target port for the container')
param targetPort int

@description('Environment variables for the container')
param envVars array = []

@description('Secrets for the container app')
param secrets array = []

@description('Log Analytics workspace resource ID')
param logAnalyticsWorkspaceId string

@description('Command to run in the container (entrypoint override)')
param command array = []

@description('Arguments for the container command')
param args array = []

// Container Apps Environment
resource containerAppEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: containerAppEnvName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: reference(logAnalyticsWorkspaceId, '2023-09-01').customerId
        sharedKey: listKeys(logAnalyticsWorkspaceId, '2023-09-01').primarySharedKey
      }
    }
  }
}

// Container App
resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppName
  location: location
  tags: tags
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: targetPort
        transport: 'auto'
        allowInsecure: false
      }
      secrets: secrets
    }
    template: {
      containers: [
        {
          name: containerAppName
          image: containerImage
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: envVars
          command: !empty(command) ? command : null
          args: !empty(args) ? args : null
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

output fqdn string = containerApp.properties.configuration.ingress.fqdn
output name string = containerApp.name
