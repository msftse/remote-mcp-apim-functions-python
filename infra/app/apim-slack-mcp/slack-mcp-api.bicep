@description('The name of the API Management service')
param apimServiceName string

@description('The FQDN of the Slack MCP Container App')
param slackMcpFqdn string

// Get reference to the existing APIM service
resource apimService 'Microsoft.ApiManagement/service@2023-05-01-preview' existing = {
  name: apimServiceName
}

// Create the Slack MCP API definition in APIM
resource slackMcpApi 'Microsoft.ApiManagement/service/apis@2023-05-01-preview' = {
  parent: apimService
  name: 'slack-mcp'
  properties: {
    displayName: 'Slack MCP API'
    description: 'Slack MCP Server API endpoints proxied through APIM'
    subscriptionRequired: false
    path: 'slack-mcp'
    protocols: [
      'https'
    ]
    serviceUrl: 'https://${slackMcpFqdn}'
  }
}

// Apply policy at the API level
resource slackMcpApiPolicy 'Microsoft.ApiManagement/service/apis/policies@2023-05-01-preview' = {
  parent: slackMcpApi
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: loadTextContent('slack-mcp-api.policy.xml')
  }
}

// SSE endpoint
resource slackMcpSseOperation 'Microsoft.ApiManagement/service/apis/operations@2023-05-01-preview' = {
  parent: slackMcpApi
  name: 'slack-mcp-sse'
  properties: {
    displayName: 'Slack MCP SSE Endpoint'
    method: 'GET'
    urlTemplate: '/sse'
    description: 'Server-Sent Events endpoint for Slack MCP Server'
  }
}

// Message endpoint
resource slackMcpMessageOperation 'Microsoft.ApiManagement/service/apis/operations@2023-05-01-preview' = {
  parent: slackMcpApi
  name: 'slack-mcp-message'
  properties: {
    displayName: 'Slack MCP Message Endpoint'
    method: 'POST'
    urlTemplate: '/message'
    description: 'Message endpoint for Slack MCP Server'
  }
}

output apiId string = slackMcpApi.id
