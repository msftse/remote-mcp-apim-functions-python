"""
AI Foundry Agent with Multiple MCP Server Tools

Creates an Azure AI Foundry agent that connects to multiple MCP server
backends exposed through the APIM gateway and directly:
  - MCP Functions (/mcp/sse) - sample tools (hello, snippets)
  - Slack MCP (/slack-mcp/sse) - Slack workspace integration
  - Jira MCP (/jira-mcp/sse) - Jira/Atlassian integration
  - GitHub MCP (api.githubcopilot.com) - GitHub repos, issues, PRs

Uses the new Foundry Agent SDK v2 (PromptAgentDefinition + OpenAI Responses API).
"""

import os
import json
import sys
from typing import cast

from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, MCPTool, Tool
from openai import BadRequestError
from openai.types.responses.response_input_param import McpApprovalResponse

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PROJECT_ENDPOINT = os.environ.get(
    "AZURE_AI_PROJECT_ENDPOINT",
    "https://roeyzalta-resource.services.ai.azure.com/api/projects/roeyzalta",
)
MODEL_DEPLOYMENT = os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4o")
APIM_GATEWAY = os.environ.get(
    "APIM_GATEWAY_URL",
    "https://apim-zjb46ckkogdgm.azure-api.net",
)
GITHUB_MCP_URL = os.environ.get(
    "GITHUB_MCP_URL",
    "https://api.githubcopilot.com/mcp/",
)
GITHUB_MCP_CONNECTION = os.environ.get(
    "GITHUB_MCP_CONNECTION_NAME",
    "github-mcp",
)

# ---------------------------------------------------------------------------
# System prompt with few-shot examples for reliable tool routing
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
You are a helpful assistant with access to multiple tool backends exposed \
through an Azure API Management gateway and directly via remote MCP servers.

## Available Tool Servers

1. **mcp-functions** — sample MCP tools.
   - hello_mcp: returns a greeting
   - get_snippet / save_snippet: read and write code snippets

2. **slack-mcp** — Slack workspace tools.
   - list channels, search messages, read conversation history
   - conversations_add_message: post messages to channels (enabled)

3. **jira-mcp** — Jira / Atlassian tools (16 available tools).
   - jira_search_issues: search with JQL (also used to look up a single issue)
   - jira_list_projects, jira_get_project: project info
   - jira_get_comments, jira_get_worklogs: issue details
   - jira_list_sprints, jira_get_sprint, jira_list_boards, jira_get_board: agile data
   - jira_list_statuses, jira_list_priorities, jira_get_transitions: metadata
   - jira_get_issue_link_types, jira_link_issues, jira_list_fields, jira_get_field

4. **github-mcp** — GitHub tools (repos, issues, pull requests, users).
   - Search and browse repositories, list files, read file contents
   - List, create, and manage issues and pull requests
   - Search code across repositories
   - Get user profiles and organization info

## Rules

- ONLY use tools from the server that is relevant to the user's request.
  If the user asks about Jira, use jira-mcp tools. If the user asks about \
Slack, use slack-mcp tools. If the user asks about GitHub repos, issues, or \
PRs, use github-mcp tools. Never mix servers unless the user explicitly asks \
for cross-tool work.
- The jira_get_issue tool is NOT available. To look up a specific issue by \
key, always use jira_search_issues with JQL.
- Give concise, structured answers. Use bullet points or tables for lists.

## Few-Shot Examples

### Example 1 — Look up a specific Jira issue
User: "Find me info about Jira issue PROJ-42"
→ Call jira_search_issues with jql="key = PROJ-42"
→ Respond with the issue summary, status, assignee, and priority.

### Example 2 — Search Jira issues with filters
User: "Show me all open bugs assigned to me"
→ Call jira_search_issues with jql="type = Bug AND status != Done AND assignee = currentUser() ORDER BY priority DESC"
→ Respond with a numbered list of matching issues.

### Example 3 — List Slack channels
User: "What Slack channels do we have?"
→ Call the slack-mcp list channels tool.
→ Respond with channel names, purposes, and member counts.

### Example 4 — Get comments on a Jira issue
User: "Show me the comments on SMS-1"
→ First call jira_search_issues with jql="key = SMS-1" to confirm the issue exists.
→ Then call jira_get_comments with the issue key.
→ Respond with each comment's author, date, and body.

### Example 5 — Greeting / hello test
User: "Say hello"
→ Call mcp-functions hello_mcp tool.
→ Respond with the greeting returned by the tool.

### Example 6 — Sprint overview
User: "What are the active sprints for project SMS?"
→ First call jira_list_boards to find the board for project SMS.
→ Then call jira_list_sprints with that board ID and state="active".
→ Respond with sprint names, start/end dates, and goals.

### Example 7 — Cross-tool request
User: "Summarize my open Jira issues and post the summary to #tech on Slack"
→ First call jira_search_issues with jql="assignee = currentUser() AND status != Done"
→ Compose a summary from the results.
→ Then call the slack-mcp tool to post the summary to #tech.
→ Confirm to the user what was posted.

### Example 8 — List GitHub repos
User: "What repos does the user roy2392 have?"
→ Call the github-mcp tool to list repositories for user roy2392.
→ Respond with repo names, descriptions, stars, and languages.

### Example 9 — GitHub issues
User: "Show me open issues on repo roy2392/my-project"
→ Call the github-mcp tool to list issues for the repository.
→ Respond with issue numbers, titles, labels, and assignees.

### Example 10 — GitHub pull requests
User: "What are the open PRs on Azure-Samples/remote-mcp-apim-functions-python?"
→ Call the github-mcp tool to list pull requests for the repository.
→ Respond with PR numbers, titles, authors, and status.

### Example 11 — Cross-tool: GitHub + Jira
User: "Find open GitHub issues on our repo and create Jira tickets for them"
→ First call the github-mcp tool to list open issues on the specified repo.
→ For each issue, call jira-mcp tools to create corresponding tickets.
→ Summarize what was created.
"""

# ---------------------------------------------------------------------------
# MCP Server definitions (one per backend behind the APIM gateway)
# ---------------------------------------------------------------------------
mcp_functions_tool = MCPTool(
    server_label="mcp-functions",
    server_url=f"{APIM_GATEWAY}/mcp/sse",
    require_approval="never",
)

slack_mcp_tool = MCPTool(
    server_label="slack-mcp",
    server_url=f"{APIM_GATEWAY}/slack-mcp/sse",
    require_approval="never",
)

jira_mcp_tool = MCPTool(
    server_label="jira-mcp",
    server_url=f"{APIM_GATEWAY}/jira-mcp/sse",
    require_approval="never",
    # Foundry agents reject tools with anyOf/allOf in their JSON Schema.
    # 9 of 25 Jira tools have incompatible schemas (jira_get_issue,
    # jira_create_issue, jira_update_issue, etc.). We whitelist the 16
    # compatible tools below.
    allowed_tools=[
        "jira_search_issues",
        "jira_list_projects",
        "jira_list_statuses",
        "jira_list_priorities",
        "jira_get_transitions",
        "jira_get_comments",
        "jira_get_worklogs",
        "jira_get_project",
        "jira_list_sprints",
        "jira_get_sprint",
        "jira_get_board",
        "jira_list_boards",
        "jira_get_issue_link_types",
        "jira_link_issues",
        "jira_list_fields",
        "jira_get_field",
    ],
)

github_mcp_tool = MCPTool(
    server_label="github-mcp",
    server_url=GITHUB_MCP_URL,
    require_approval="never",
    project_connection_id=GITHUB_MCP_CONNECTION,
)

ALL_TOOLS: list[Tool] = [mcp_functions_tool, slack_mcp_tool, jira_mcp_tool, github_mcp_tool]  # type: ignore[list-item]


def main() -> None:
    print("Connecting to Azure AI Foundry project ...")
    print(f"  Endpoint : {PROJECT_ENDPOINT}")
    print(f"  Model    : {MODEL_DEPLOYMENT}")
    print(f"  Gateway  : {APIM_GATEWAY}")
    print(f"  GitHub   : {GITHUB_MCP_URL}")
    print()

    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential) as project_client,
        project_client.get_openai_client() as openai_client,
    ):
        # -- Create the agent with all four MCP tools -------------------------
        agent = project_client.agents.create_version(
            agent_name="apim-mcp-gateway-agent",
            definition=PromptAgentDefinition(
                model=MODEL_DEPLOYMENT,
                instructions=SYSTEM_PROMPT,
                tools=cast(list[Tool], ALL_TOOLS),  # type: ignore[arg-type]
            ),
        )
        print(f"Agent created  (id: {agent.id}, name: {agent.name}, version: {agent.version})")

        # -- Create a conversation -------------------------------------------
        conversation = openai_client.conversations.create()
        print(f"Conversation   (id: {conversation.id})")
        print()

        # -- Interactive loop -------------------------------------------------
        print("=" * 60)
        print("Chat with your agent (type 'quit' to exit)")
        print("=" * 60)

        previous_response_id = None

        while True:
            user_input = input("\nYou: ").strip()
            if not user_input or user_input.lower() in ("quit", "exit", "q"):
                break

            # Build the request
            kwargs = {
                "input": user_input,
                "extra_body": {"agent": {"name": agent.name, "type": "agent_reference"}},
            }
            if previous_response_id:
                kwargs["previous_response_id"] = previous_response_id
            else:
                kwargs["conversation"] = conversation.id

            try:
                response = openai_client.responses.create(**kwargs)
            except BadRequestError as e:
                print(f"\n  [Error] {e.message}")
                print("  (The agent encountered a tool error. Try a different request.)")
                continue

            previous_response_id = response.id

            # -- Handle MCP approval requests (if require_approval != "never") --
            approval_items = [item for item in response.output if item.type == "mcp_approval_request"]

            if approval_items:
                input_list = []
                for item in approval_items:
                    print(f"\n  [MCP approval requested]")
                    print(f"    Server : {item.server_label}")
                    print(f"    Tool   : {getattr(item, 'name', '<unknown>')}")
                    print(f"    Args   : {json.dumps(getattr(item, 'arguments', None), indent=2, default=str)}")

                    # Auto-approve (change to interactive prompt if desired)
                    input_list.append(
                        McpApprovalResponse(
                            type="mcp_approval_response",
                            approve=True,
                            approval_request_id=item.id,
                        )
                    )

                # Send approvals back
                try:
                    response = openai_client.responses.create(
                        input=input_list,
                        previous_response_id=response.id,
                        extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
                    )
                except BadRequestError as e:
                    print(f"\n  [Error] {e.message}")
                    print("  (The agent encountered a tool error. Try a different request.)")
                    continue
                previous_response_id = response.id

            # -- Print agent response -----------------------------------------
            if response.output_text:
                print(f"\nAgent: {response.output_text}")
            else:
                print("\nAgent: (no text response)")

        # -- Cleanup ----------------------------------------------------------
        print("\nCleaning up ...")
        project_client.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
        print("Agent deleted. Goodbye!")


if __name__ == "__main__":
    main()
