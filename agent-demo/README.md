# AI Foundry Agent Demo

An interactive AI agent that connects to four MCP server backends — three through the Azure API Management gateway and one directly via GitHub's remote MCP server. The agent can use tools from:

- **MCP Functions** — sample tools (`hello_mcp`, `get_snippet`, `save_snippet`)
- **Slack MCP** — Slack workspace integration (channels, messages, search, post messages)
- **Jira MCP** — Jira/Atlassian integration (issues, projects, sprints)
- **GitHub MCP** — GitHub integration (repos, issues, PRs, code search, users)

## Prerequisites

1. The APIM gateway and all MCP backends must be deployed (run `azd up` from the repo root).
2. An [Azure AI Foundry](https://ai.azure.com) project with a `gpt-4o` model deployment.
3. Python 3.10+.
4. You must be logged in with `az login` (the script uses `DefaultAzureCredential`).
5. A **Custom Keys** connection named `github-mcp` in your AI Foundry project with your GitHub PAT (see below).

## GitHub MCP Setup

The GitHub MCP server is hosted remotely at `https://api.githubcopilot.com/mcp/` — no Container App or APIM proxy needed.

Authentication uses a **Custom Keys** connection in AI Foundry:

1. Go to your AI Foundry project in the Azure Portal or Foundry Portal.
2. Navigate to **Connected resources** → **+ New connection** → **Custom Keys**.
3. Set:
   - **Credential name**: `Authorization`
   - **Credential value**: `Bearer <your-github-personal-access-token>`
4. Name the connection `github-mcp` (or set `GITHUB_MCP_CONNECTION_NAME` in `.env` to match your chosen name).

Alternatively, create it via Azure CLI:

```bash
az rest --method put \
  --url "https://management.azure.com{your-project-resource-id}/connections/github-mcp?api-version=2025-04-01-preview" \
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

## Setup

```bash
cd agent-demo
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `AZURE_AI_PROJECT_ENDPOINT` | Your AI Foundry project endpoint (from Azure Portal -> AI Foundry project -> Overview) |
| `MODEL_DEPLOYMENT_NAME` | Model deployment name in your project (default: `gpt-4o`) |
| `APIM_GATEWAY_URL` | APIM gateway base URL (from `azd` output or Azure Portal) |
| `GITHUB_MCP_URL` | GitHub MCP server URL (default: `https://api.githubcopilot.com/mcp/`) |
| `GITHUB_MCP_CONNECTION_NAME` | Name of the Custom Keys connection in AI Foundry (default: `github-mcp`) |

## Run

```bash
python agent.py
```

The script will:
1. Create a temporary agent in your AI Foundry project with all four MCP tools attached.
2. Start an interactive chat loop — ask the agent to use Slack, Jira, GitHub, or the sample tools.
3. Clean up (delete the agent version) on exit.

### Example prompts

```
You: Say hello using the mcp-functions tools
You: List all Slack channels
You: Search Jira for open bugs assigned to me
You: What repos does roy2392 have on GitHub?
You: Show me open PRs on Azure-Samples/remote-mcp-apim-functions-python
You: Post a summary of my Jira issues to the #general Slack channel
```

## Important: OAuth and Agent Access

The APIM gateway protects each MCP endpoint with OAuth 2.0 (Authorization Code + PKCE). This flow is designed for **interactive browser-based clients** (like MCP Inspector or VS Code Copilot).

The AI Foundry agent connects to MCP servers **server-side**, so it cannot perform a browser-based OAuth flow. Options to handle this:

1. **Bypass APIM for agent use** — Point the `MCPTool` URLs directly at the Container App URLs instead of the APIM gateway. This skips OAuth entirely but also loses the gateway layer.
2. **Disable OAuth on specific endpoints** — Temporarily remove the token validation block from the APIM policy XML for endpoints used by the agent.
3. **Use APIM subscription keys** — Add an `Ocp-Apim-Subscription-Key` header via `MCPTool` headers, and configure APIM to accept subscription-key auth as an alternative.

This is an open design question — choose the approach that fits your security requirements.
