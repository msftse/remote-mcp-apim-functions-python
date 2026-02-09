@description('The name of the API Management service')
param apimServiceName string

@description('The FQDN of the Jira MCP Container App')
param jiraMcpFqdn string

// Get reference to the existing APIM service
resource apimService 'Microsoft.ApiManagement/service@2023-05-01-preview' existing = {
  name: apimServiceName
}

// Create the Jira MCP API definition in APIM
resource jiraMcpApi 'Microsoft.ApiManagement/service/apis@2023-05-01-preview' = {
  parent: apimService
  name: 'jira-mcp'
  properties: {
    displayName: 'Jira MCP API'
    description: 'Jira/Atlassian MCP Server API endpoints proxied through APIM'
    subscriptionRequired: false
    path: 'jira-mcp'
    protocols: [
      'https'
    ]
    serviceUrl: 'https://${jiraMcpFqdn}'
  }
}

// Apply policy at the API level
resource jiraMcpApiPolicy 'Microsoft.ApiManagement/service/apis/policies@2023-05-01-preview' = {
  parent: jiraMcpApi
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: loadTextContent('jira-mcp-api.policy.xml')
  }
}

// SSE endpoint
resource jiraMcpSseOperation 'Microsoft.ApiManagement/service/apis/operations@2023-05-01-preview' = {
  parent: jiraMcpApi
  name: 'jira-mcp-sse'
  properties: {
    displayName: 'Jira MCP SSE Endpoint'
    method: 'GET'
    urlTemplate: '/sse'
    description: 'Server-Sent Events endpoint for Jira MCP Server'
  }
}

// Message endpoint
resource jiraMcpMessageOperation 'Microsoft.ApiManagement/service/apis/operations@2023-05-01-preview' = {
  parent: jiraMcpApi
  name: 'jira-mcp-message'
  properties: {
    displayName: 'Jira MCP Message Endpoint'
    method: 'POST'
    urlTemplate: '/messages/'
    description: 'Message endpoint for Jira MCP Server'
  }
}

output apiId string = jiraMcpApi.id
