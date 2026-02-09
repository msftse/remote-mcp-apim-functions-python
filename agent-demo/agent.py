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

from system_prompt import SYSTEM_PROMPT

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
