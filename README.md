<!--
---
name: Remote MCP  using Azure API Management
description: Use Azure API Management as the AI Gateway for multiple MCP Servers using Azure Functions and Container Apps
page_type: sample
languages:
- python
- bicep
- azdeveloper
products:
- azure-api-management
- azure-functions
- azure-container-apps
- azure
urlFragment: remote-mcp-apim-functions-python
---
-->

# Secure Remote MCP Servers using Azure API Management (Experimental)

[![Deploy with azd](https://img.shields.io/static/v1?style=for-the-badge&label=azd&message=Deploy+to+Azure&color=blue&logo=microsoft-azure)](https://github.com/Azure-Samples/remote-mcp-apim-functions-python#deploy-to-azure)
[![Open in GitHub Codespaces](https://img.shields.io/static/v1?style=for-the-badge&label=GitHub+Codespaces&message=Open&color=brightgreen&logo=github)](https://codespaces.new/Azure-Samples/remote-mcp-apim-functions-python)
[![Open in Dev Container](https://img.shields.io/static/v1?style=for-the-badge&label=Dev+Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/Azure-Samples/remote-mcp-apim-functions-python)

![Diagram](mcp-client-authorization.gif)

Azure API Management acts as the [AI Gateway](https://github.com/Azure-Samples/AI-Gateway) for MCP servers.

This sample implements the latest [MCP Authorization specification](https://modelcontextprotocol.io/specification/2025-03-26/basic/authorization#2-10-third-party-authorization-flow) and demonstrates how to route multiple MCP server backends through a single APIM gateway with unified OAuth 2.0 authentication.

This is a [sequence diagram](infra/app/apim-oauth/diagrams/diagrams.md) to understand the flow.

## MCP Server Backends

This sample deploys three MCP server backends behind the APIM gateway, plus a fourth remote-hosted backend:

| Backend | Compute | APIM Path | Description |
|---|---|---|---|
| **MCP Functions** | Azure Functions (Python) | `/mcp/sse` | Sample tools (`hello_mcp`, `get_snippet`, `save_snippet`) |
| **Slack MCP** | Azure Container App | `/slack-mcp/sse` | Slack workspace integration via [slack-mcp-server](https://github.com/korotovsky/slack-mcp-server) |
| **Jira MCP** | Azure Container App | `/jira-mcp/sse` | Jira/Atlassian integration via [mcp-atlassian](https://github.com/sooperset/mcp-atlassian) |
| **GitHub MCP** | GitHub-hosted (remote) | N/A | GitHub integration via [GitHub Copilot MCP](https://api.githubcopilot.com/mcp/) — no APIM proxy needed |

All APIM-proxied backends share the same OAuth 2.0 authorization flow managed by APIM. MCP clients authenticate once and can access any backend.

The repo also includes an **AI Foundry Agent Demo** (`agent-demo/`) that connects all four MCP backends to a single conversational agent. See [Agent Demo](#agent-demo) below.

---

## Prerequisites

Before deploying, you need the following accounts, credentials, and tooling.

### Required Tooling

- [Azure Developer CLI (`azd`)](https://aka.ms/azd) v1.5+
- [Azure CLI (`az`)](https://learn.microsoft.com/cli/azure/install-azure-cli)
- An Azure subscription with **Contributor** access
- Python 3.10+

### Slack Bot Token

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and click **Create New App** → **From scratch**.
2. Under **OAuth & Permissions**, add the following **Bot Token Scopes**:
   - `channels:history`, `channels:read`, `chat:write`, `groups:history`, `groups:read`
   - `im:history`, `im:read`, `mpim:history`, `mpim:read`, `users:read`
3. Click **Install to Workspace** and authorize.
4. Copy the **Bot User OAuth Token** (starts with `xoxb-`).

### Jira API Token

1. Go to [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens).
2. Click **Create API token**, give it a label, and copy the token.
3. Note your Jira instance URL (e.g. `https://yourorg.atlassian.net`) and the email address you log in with.

### GitHub Personal Access Token (for Agent Demo only)

If you plan to use the Agent Demo with GitHub tools:

1. Go to [github.com/settings/tokens](https://github.com/settings/tokens) → **Generate new token (classic)** or **Fine-grained token**.
2. Grant scopes for the operations you need (e.g. `repo`, `read:org`, `read:user`).
3. Copy the token.

### Azure AI Foundry Project (for Agent Demo only)

If you plan to use the Agent Demo:

1. Create an [Azure AI Foundry](https://ai.azure.com) project.
2. Deploy a **gpt-4o** model (or another supported model) in the project.
3. Note the project endpoint URL from the project's **Overview** page.

---

## Deploy to Azure

### 1. Register the required resource provider

```shell
az provider register --namespace Microsoft.App --wait
```

### 2. Log in and initialize

```shell
azd auth login
azd init
```

### 3. Set environment variables

Set the credentials for the Slack and Jira MCP server backends:

```shell
# Slack MCP Server
azd env set SLACK_BOT_TOKEN <your-slack-bot-xoxb-token>

# Jira MCP Server
azd env set JIRA_URL <your-jira-instance-url>         # e.g. https://yourorg.atlassian.net
azd env set JIRA_USERNAME <your-jira-email>
azd env set JIRA_API_TOKEN <your-jira-api-token>
```

**All four variables are required.** If you skip them, the Slack/Jira Container Apps will deploy but fail to connect to their respective services.

### 4. Deploy

```shell
azd up
```

This provisions all Azure resources and deploys the code. The output will display the APIM gateway URL and the three MCP SSE endpoints.

### 5. Verify deployment

After `azd up` completes, the output will show:

```
SERVICE_API_ENDPOINTS:
  - https://<apim-name>.azure-api.net/mcp/sse
  - https://<apim-name>.azure-api.net/slack-mcp/sse
  - https://<apim-name>.azure-api.net/jira-mcp/sse
```

---

## Test with MCP Inspector

1. In a **new terminal**, install and run MCP Inspector:

    ```shell
    npx @modelcontextprotocol/inspector
    ```

2. CTRL-click to load the MCP Inspector web app from the URL displayed (e.g. `http://127.0.0.1:6274`).
3. Set the transport type to **SSE**.
4. Set the URL to one of the APIM SSE endpoints and click **Connect**:

    ```
    https://<apim-name>.azure-api.net/mcp/sse        # MCP Functions
    https://<apim-name>.azure-api.net/slack-mcp/sse   # Slack MCP
    https://<apim-name>.azure-api.net/jira-mcp/sse    # Jira MCP
    ```

5. Click **List Tools**, then select a tool and **Run Tool**.

> **Note**: MCP Inspector's web UI will auto-discover the OAuth metadata at `/.well-known/oauth-authorization-server` and initiate the OAuth flow. You can also test directly using CLI mode:
> ```shell
> npx @modelcontextprotocol/inspector --cli --transport sse \
>   --server-url "https://<apim-name>.azure-api.net/jira-mcp/sse" \
>   --method tools/list
> ```

---

## Agent Demo

The `agent-demo/` directory contains an interactive AI Foundry agent that connects to all four MCP backends as tools. The agent can query Slack channels, search Jira issues, browse GitHub repos, and use the sample MCP Functions tools — all from a single chat interface.

See [`agent-demo/README.md`](agent-demo/README.md) for full setup instructions.

### Quick Start

```shell
cd agent-demo
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your AI Foundry project endpoint and APIM gateway URL
python agent.py
```

### GitHub MCP Connection (required for GitHub tools)

The GitHub MCP server is hosted remotely at `https://api.githubcopilot.com/mcp/` — no Container App or APIM proxy needed. Authentication uses a **Custom Keys** connection in AI Foundry:

1. In Azure Portal or Foundry Portal, go to your AI Foundry project.
2. Navigate to **Connected resources** → **+ New connection** → **Custom Keys**.
3. Set **Credential name** to `Authorization` and **Credential value** to `Bearer <your-github-pat>`.
4. Name the connection `github-mcp`.

Or via CLI:

```bash
az rest --method put \
  --url "https://management.azure.com<your-project-resource-id>/connections/github-mcp?api-version=2025-04-01-preview" \
  --body '{
    "properties": {
      "authType": "CustomKeys",
      "category": "CustomKeys",
      "target": "https://api.githubcopilot.com/mcp/",
      "isSharedToAll": true,
      "credentials": {
        "keys": {
          "Authorization": "Bearer <your-github-pat>"
        }
      }
    }
  }'
```

> **Note**: The GitHub MCP connection is NOT provisioned by Bicep/`azd up`. It must be created manually in your AI Foundry project.

---

## OAuth and Agent Access

The APIM gateway protects each MCP endpoint with OAuth 2.0 (Authorization Code + PKCE). This flow is designed for **interactive browser-based clients** like MCP Inspector or VS Code Copilot.

The AI Foundry agent connects to MCP servers **server-side** and cannot perform a browser-based OAuth flow. For agent access, you have several options:

1. **Disable OAuth validation in APIM policies** — Comment out the token validation block in the policy XML files. This is what the current deployment does (OAuth blocks are commented out in all three policy files).
2. **Bypass APIM** — Point the agent directly at the Container App URLs instead of the APIM gateway.
3. **Use APIM subscription keys** — Configure APIM to accept `Ocp-Apim-Subscription-Key` as an alternative auth mechanism.

To **re-enable OAuth**, uncomment the authorization blocks in:
- `infra/app/apim-mcp/mcp-api.policy.xml`
- `infra/app/apim-slack-mcp/slack-mcp-api.policy.xml`
- `infra/app/apim-jira-mcp/jira-mcp-api.policy.xml`

---

## Technical Architecture Overview

This solution deploys a secure MCP (Model Context Protocol) server infrastructure on Azure. The architecture implements a multi-layered security model with Azure API Management serving as an intelligent gateway that handles authentication, authorization, and request routing to multiple MCP server backends.

![overview diagram](overview.png)

### Deployed Azure Resources

The infrastructure provisions the following Azure resources:

#### Core Gateway Infrastructure
- **Azure API Management (APIM)** - The central security gateway that exposes OAuth and multiple MCP APIs
  - **SKU**: BasicV2 (configurable)
  - **Identity**: System-assigned and user-assigned managed identities
  - **Purpose**: Handles authentication flows, request validation, and secure proxying to backend services

#### Backend Compute
- **Azure Function App** - Hosts the original MCP server implementation
  - **Runtime**: Python 3.11 on Flex Consumption plan
  - **Authentication**: Function-level authentication with managed identity integration
  - **Purpose**: Executes MCP tools and operations (snippet management in this example)

- **Azure Container Apps** - Host additional MCP server backends
  - **Slack MCP Container App** - Runs [slack-mcp-server](https://github.com/korotovsky/slack-mcp-server) for Slack workspace integration
  - **Jira MCP Container App** - Runs [mcp-atlassian](https://github.com/sooperset/mcp-atlassian) for Jira/Atlassian integration
  - **Resources**: 0.25 vCPU, 0.5 Gi memory per container
  - **Scaling**: Each container runs in its own Container Apps Environment with Log Analytics integration
  - **Purpose**: Enables third-party MCP servers to be deployed as containers behind the APIM gateway

#### Storage and Data
- **Azure Storage Account** - Provides multiple storage functions
  - **Function hosting**: Stores function app deployment packages
  - **Application data**: Blob container for snippet storage
  - **Security**: Configured with managed identity access and optional private endpoints

- **Azure Cosmos DB** (Serverless) - Stores OAuth dynamic client registrations

#### Security and Identity
- **User-Assigned Managed Identity** - Enables secure service-to-service authentication
  - **Purpose**: Allows Function App to access Storage and Application Insights without secrets
  - **Permissions**: Storage Blob Data Owner, Storage Queue Data Contributor, Monitoring Metrics Publisher

- **Entra ID Application Registration** - OAuth2/OpenID Connect client for authentication
  - **Purpose**: Enables third-party authorization flow per MCP specification
  - **Configuration**: PKCE-enabled public client with custom redirect URIs
  - **Scopes**: Only requests the `openid` scope (no admin consent required)

#### Monitoring and Observability
- **Application Insights** - Provides telemetry and monitoring
- **Log Analytics Workspace** - Centralized logging and analytics for Functions and Container Apps

#### Optional Network Security
- **Virtual Network (VNet)** - When `vnetEnabled` is true
  - **Private Endpoints**: Secure connectivity to Storage Account
  - **Network Isolation**: Functions and storage communicate over private network

### Why These Resources?

**Azure API Management** serves as the security perimeter, implementing:
- OAuth 2.0/PKCE authentication flows per MCP specification
- Session key encryption/decryption for secure API access  
- Request validation and header injection
- Rate limiting and throttling capabilities
- Centralized policy management
- Unified authentication across multiple MCP backends

**Azure Functions** provides:
- Serverless, pay-per-use compute model
- Native integration with Azure services
- Automatic scaling based on demand
- Built-in monitoring and diagnostics

**Azure Container Apps** provides:
- Flexible hosting for third-party MCP server images
- Simple deployment from container registries (e.g. GHCR)
- Per-container environment variable and secret management
- Integrated logging via Log Analytics

**Managed Identities** eliminate the need for:
- Service credentials management
- Secret rotation processes
- Credential exposure risks

## Azure API Management Configuration Details

The APIM instance is configured with four APIs that work together to implement the MCP authorization specification and route requests to multiple backends:

### OAuth API (`/`)

This API implements the complete OAuth 2.0 authorization server functionality required by the MCP specification:

#### Endpoints and Operations

**Authorization Endpoint** (`GET /authorize`)
- **Purpose**: Initiates the OAuth 2.0/PKCE flow
- **Policy Logic**:
  1. Extracts PKCE parameters from MCP client request
  2. Checks for existing user consent (via cookies)
  3. Redirects to consent page if consent not granted
  4. Generates new PKCE parameters for Entra ID communication
  5. Stores authentication state in APIM cache
  6. Redirects user to Entra ID for authentication

**Consent Management** (`GET/POST /consent`)
- **Purpose**: Handles user consent for MCP client access
- **Features**: Consent persistence via secure cookies

**OAuth Metadata Endpoint** (`GET /.well-known/oauth-authorization-server`)
- **Purpose**: Publishes OAuth server configuration per RFC 8414
- **Returns**: JSON metadata about supported endpoints, flows, and capabilities
  
**Client Registration** (`POST /register`)
- **Purpose**: Supports dynamic client registration per MCP specification
- **Storage**: Client registrations are persisted in Cosmos DB

**Token Endpoint** (`POST /token`)
- **Purpose**: Exchanges authorization codes for access tokens
- **Policy Logic**:
  1. Validates authorization code and PKCE verifier from MCP client
  2. Exchanges Entra ID authorization code for access tokens (using `openid` scope only)
  3. Generates encrypted session key for MCP API access
  4. Caches the access token with session key mapping
  5. Returns encrypted session key to MCP client

#### Named Values and Configuration

The OAuth API uses several APIM Named Values for configuration:
- `McpClientId` - The registered Entra ID application client ID
- `EntraIDFicClientId` - Service identity client ID for token exchange
- `APIMGatewayURL` - Base URL for callback and metadata endpoints
- `OAuthScopes` - Requested OAuth scopes (`openid` only -- no admin consent required)
- `EncryptionKey` / `EncryptionIV` - For session key encryption

### MCP API (`/mcp/*`)

This API provides the original MCP protocol endpoints backed by Azure Functions:

#### Endpoints and Operations

**Server-Sent Events Endpoint** (`GET /mcp/sse`)
- **Purpose**: Establishes real-time communication channel for MCP protocol
- **Security**: Requires valid encrypted session token

**Message Endpoint** (`POST /mcp/message`)
- **Purpose**: Handles MCP protocol messages and tool invocations
- **Security**: Requires valid encrypted session token
- **Backend**: Proxies to Azure Functions with `x-functions-key` header injection

### Slack MCP API (`/slack-mcp/*`)

This API proxies requests to the Slack MCP Server running on Azure Container Apps:

**Server-Sent Events Endpoint** (`GET /slack-mcp/sse`)
- **Purpose**: Establishes SSE connection to the Slack MCP server

**Message Endpoint** (`POST /slack-mcp/message`)
- **Purpose**: Sends messages to the Slack MCP server

The policy rewrites SSE response URLs to include the `/slack-mcp/` prefix so that clients send follow-up messages through APIM rather than directly to the container.

### Jira MCP API (`/jira-mcp/*`)

This API proxies requests to the Jira/Atlassian MCP Server running on Azure Container Apps:

**Server-Sent Events Endpoint** (`GET /jira-mcp/sse`)
- **Purpose**: Establishes SSE connection to the Jira MCP server

**Message Endpoint** (`POST /jira-mcp/messages/`)
- **Purpose**: Sends messages to the Jira MCP server

The policy rewrites SSE response URLs to include the `/jira-mcp/` prefix for correct APIM routing.

> **Note**: The Jira MCP server uses `/messages/?session_id=` (plural, with underscore) unlike the Slack MCP server which uses `/message?sessionId=` (singular, camelCase). Each API policy handles the URL rewriting accordingly.

### Security Policy Implementation

All MCP APIs (MCP Functions, Slack, Jira) share the same security policy pattern:

1. **Authorization Header Validation**
   ```xml
   <check-header name="Authorization" failed-check-httpcode="401" 
                 failed-check-error-message="Not authorized" ignore-case="false" />
   ```

2. **Session Key Decryption**
   - Extracts encrypted session key from Authorization header
   - Decrypts using AES with stored key and IV
   - Validates token format and structure

3. **Token Cache Lookup**
   ```xml
   <cache-lookup-value key="@($"EntraToken-{context.Variables.GetValueOrDefault("decryptedSessionKey")}")" 
                       variable-name="accessToken" />
   ```

4. **Access Token Validation**
   - Verifies cached access token exists and is valid
   - Returns 401 with proper WWW-Authenticate header if invalid

5. **Backend Authentication** (MCP Functions only)
   ```xml
   <set-header name="x-functions-key" exists-action="override">
       <value>{{function-host-key}}</value>
   </set-header>
   ```

### Security Model

The solution implements a multi-layer security model:

**Layer 1: OAuth 2.0/PKCE Authentication**
- MCP clients must complete full OAuth flow with Entra ID
- PKCE prevents authorization code interception attacks
- User consent management with persistent preferences
- Only the `openid` scope is requested (no admin consent required)

**Layer 2: Session Key Encryption**
- Access tokens are never exposed to MCP clients
- Encrypted session keys provide time-bounded access
- AES encryption with secure key management in APIM

**Layer 3: Function-Level Security**
- Function host keys protect direct access to Azure Functions
- Managed identity ensures secure service-to-service communication
- Network isolation available via VNet integration

**Layer 4: Azure Platform Security**
- All traffic encrypted in transit (TLS)
- Storage access via managed identities
- Audit logging through Application Insights

This layered approach ensures that even if one security boundary is compromised, multiple additional protections remain in place.

## Adding a New MCP Server Backend

The architecture is designed to be extensible. To add a new MCP server backend:

1. **Create the APIM API definition**: Add a new directory `infra/app/apim-<name>/` with:
   - `<name>-api.bicep` - API definition with SSE and message operations
   - `<name>-api.policy.xml` - Policy with OAuth validation and URL rewriting

2. **Add the Container App module** in `infra/main.bicep`:
   - Reference the reusable `infra/core/host/container-app.bicep` module
   - Configure the container image, port, command, args, secrets, and environment variables

3. **Add the APIM API module** in `infra/main.bicep`:
   - Reference the new bicep module from step 1
   - Pass the APIM service name and container app FQDN

4. **Add parameters** in `infra/main.bicep` and `infra/main.parameters.json` for any credentials or configuration values needed by the new backend.

5. **Set environment variables** via `azd env set` for any secrets before running `azd up`.

## Known Issues

### Jira MCP Schema Compatibility with AI Foundry

The `mcp-atlassian` Jira MCP server exposes 25 tools, but 9 of them use `anyOf`/`allOf` in their JSON Schema definitions which are not supported by the Azure AI Foundry agent SDK. The agent demo whitelists only the 16 compatible tools via the `allowed_tools` parameter on the `MCPTool` definition.

**Compatible tools (16)**: `jira_search_issues`, `jira_list_projects`, `jira_list_statuses`, `jira_list_priorities`, `jira_get_transitions`, `jira_get_comments`, `jira_get_worklogs`, `jira_get_project`, `jira_list_sprints`, `jira_get_sprint`, `jira_get_board`, `jira_list_boards`, `jira_get_issue_link_types`, `jira_link_issues`, `jira_list_fields`, `jira_get_field`

**Incompatible tools (9)**: `jira_get_issue`, `jira_create_issue`, `jira_update_issue`, `jira_transition_issue`, `jira_add_comment`, `jira_add_worklog`, `jira_create_sprint`, `jira_update_sprint`, `jira_batch_get_changelogs`

**Workaround**: Use `jira_search_issues` with JQL (e.g. `key = PROJ-42`) instead of `jira_get_issue`.

### Pyright Type Warning in Agent Demo

The agent demo shows a persistent Pyright warning about `list[MCPTool]` not being assignable to `list[Tool]`. This is a known SDK typing issue (list invariance in Python) and works correctly at runtime.
