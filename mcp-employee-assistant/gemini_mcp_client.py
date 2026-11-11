import os
import json
import asyncio
import logging
import time

import httpx2

from contextlib import AsyncExitStack
from dotenv import load_dotenv

from google import genai
from google.genai import types

from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from oauth_client import login, refresh_access_token


# ==========================================================
# 1. LOAD ENVIRONMENT VARIABLES
# ==========================================================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is missing")

if not GEMINI_MODEL:
    raise ValueError("GEMINI_MODEL is missing")


# ==========================================================
# 2. MCP SERVER CONFIGURATION
# ==========================================================

MCP_SERVERS = {
    "employee": "https://127.0.0.1:8000/mcp",
    "department": "https://127.0.0.1:8001/mcp",
    "policy": "https://127.0.0.1:8002/mcp"
}


# ==========================================================
# 3. LOGGING
# ==========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


# ==========================================================
# 4. INITIALIZE GEMINI
# ==========================================================

gemini_client = genai.Client(
    api_key=GEMINI_API_KEY
)


# ==========================================================
# 5. OAUTH TOKEN MANAGER
# ==========================================================

class OAuthTokenManager:

    def __init__(self, token_response):

        self.access_token = token_response["access_token"]

        self.refresh_token = token_response["refresh_token"]

        self.expires_at = (
            time.time() + token_response.get("expires_in", 300)
        )
        # self.expires_at = time.time() + 30

        self.http_clients = []

        self.refresh_lock = asyncio.Lock()

    def register_http_client(self, http_client):

        self.http_clients.append(http_client)

    async def refresh_if_required(self):

        # Refresh 60 seconds before expiry.
        if time.time() < self.expires_at - 60:
            return

        async with self.refresh_lock:

            # Check again after acquiring the lock.
            if time.time() < self.expires_at - 60:
                return

            print("\nAccess token is expiring.")

            print("Refreshing OAuth access token...")

            token_response = await asyncio.to_thread(
                refresh_access_token,
                self.refresh_token
            )

            new_access_token = token_response.get("access_token")

            if not new_access_token:
                raise ValueError(
                    "Keycloak did not return a new access token"
                )

            self.access_token = new_access_token

            # Keycloak may rotate the refresh token.
            self.refresh_token = token_response.get(
                "refresh_token",
                self.refresh_token
            )

            expires_in = token_response.get("expires_in", 300)

            self.expires_at = time.time() + expires_in

            # Update every connected MCP HTTP client.
            for http_client in self.http_clients:

                http_client.headers.update({
                    "Authorization": f"Bearer {self.access_token}"
                })

            print("OAuth access token refreshed successfully!")

            print("All MCP HTTP clients updated.")


# ==========================================================
# 6. KEYCLOAK OAUTH LOGIN
# ==========================================================

async def authenticate_user():

    print("\nStarting Keycloak OAuth authentication...")

    token_response = await asyncio.to_thread(login)

    if not token_response.get("access_token"):
        raise ValueError(
            "Keycloak did not return an access token"
        )

    if not token_response.get("refresh_token"):
        raise ValueError(
            "Keycloak did not return a refresh token"
        )

    print("\nKeycloak authentication successful!")

    return OAuthTokenManager(token_response)


# ==========================================================
# 7. DYNAMIC MCP TOOL DISCOVERY
# ==========================================================

async def discover_all_tools(stack, token_manager):

    tool_registry = {}

    gemini_declarations = []

    print("\nConnecting to MCP servers...")

    for server_name, server_url in MCP_SERVERS.items():

        print(f"\nConnecting to {server_name} server...")

        headers = {
            "Authorization": f"Bearer {token_manager.access_token}"
        }

        http_client = await stack.enter_async_context(
            httpx2.AsyncClient(
                headers=headers,
                timeout=httpx2.Timeout(
                    30.0,
                    read=300.0
                ),
            verify="certs/server-cert.pem"
            )
        )

        # Register HTTP client for future token updates.
        token_manager.register_http_client(http_client)

        transport = streamable_http_client(
            url=server_url,
            http_client=http_client
        )

        mcp_client = await stack.enter_async_context(
            Client(transport)
        )

        print(f"{server_name} server connected!")

        # Discover tools dynamically.
        tool_result = await mcp_client.list_tools()

        server_tools = tool_result.tools

        print(f"\nTools discovered from {server_name}:")

        for tool in server_tools:

            namespaced_name = f"{server_name}__{tool.name}"

            print(f"- {namespaced_name}")

            tool_registry[namespaced_name] = {
                "server_name": server_name,
                "original_tool_name": tool.name,
                "client": mcp_client
            }

            declaration = types.FunctionDeclaration(
                name=namespaced_name,
                description=tool.description or "",
                parameters_json_schema=tool.input_schema
            )

            gemini_declarations.append(declaration)

    gemini_tools = [
        types.Tool(
            function_declarations=gemini_declarations
        )
    ]

    print("\nAll MCP servers connected successfully!")

    print(
        f"Total tools discovered: {len(gemini_declarations)}"
    )

    return tool_registry, gemini_tools


# ==========================================================
# 8. EXTRACT MCP TOOL RESULT
# ==========================================================

def extract_tool_result(result):

    if getattr(result, "structured_content", None) is not None:

        return result.structured_content

    text_parts = []

    for content in result.content:

        if hasattr(content, "text"):
            text_parts.append(content.text)

    if text_parts:

        combined_text = "\n".join(text_parts)

        try:
            return json.loads(combined_text)

        except json.JSONDecodeError:
            return combined_text

    return "Tool executed, but no result was returned."


# ==========================================================
# 9. EXECUTE MCP TOOL
# ==========================================================

async def execute_mcp_tool(
    namespaced_name,
    arguments,
    tool_registry,
    token_manager
):

    if namespaced_name not in tool_registry:

        return {
            "error": f"Unknown tool: {namespaced_name}"
        }

    tool_info = tool_registry[namespaced_name]

    server_name = tool_info["server_name"]

    original_tool_name = tool_info["original_tool_name"]

    mcp_client = tool_info["client"]

    print(f"\nSelected server: {server_name}")

    print(f"Selected tool: {original_tool_name}")

    print("Arguments:", arguments)

    try:

        # Check token expiry before every MCP request.
        await token_manager.refresh_if_required()

        result = await mcp_client.call_tool(
            original_tool_name,
            arguments
        )

        tool_output = extract_tool_result(result)

        if getattr(result, "is_error", False):

            return {
                "error": tool_output
            }

        return tool_output

    except Exception as error:

        logger.exception("MCP tool execution failed")

        return {
            "error": str(error)
        }


# ==========================================================
# 10. MAIN APPLICATION
# ==========================================================

async def main():

    print("=" * 65)

    print("GEMINI MULTI-SERVER MCP ASSISTANT")

    print("KEYCLOAK OAUTH WITH AUTOMATIC TOKEN REFRESH")

    print("=" * 65)

    # ------------------------------------------------------
    # STEP 1: AUTHENTICATE USER
    # ------------------------------------------------------

    token_manager = await authenticate_user()

    print("\nOAuth Token Manager initialized.")

    # ------------------------------------------------------
    # STEP 2: CONNECT TO ALL MCP SERVERS
    # ------------------------------------------------------

    async with AsyncExitStack() as stack:

        tool_registry, gemini_tools = await discover_all_tools(
            stack,
            token_manager
        )

        # --------------------------------------------------
        # STEP 3: CONVERSATION CONFIGURATION
        # --------------------------------------------------

        conversation = []

        system_instruction = """
        You are an intelligent Employee Management AI Assistant.

        You have access to three MCP servers.

        1. Employee Server:
           Employee CRUD operations and bonus calculation.

        2. Department Server:
           Department information and employee statistics.

        3. HR Policy Server:
           HR policies and policy search.

        Instructions:

        - Select the appropriate MCP tool for each request.
        - Use actual tool results instead of inventing information.
        - You may call tools from different servers.
        - Never claim an operation succeeded unless confirmed.
        - Explain authorization errors clearly.
        - Never attempt to bypass server-side permissions.
        """

        print("\nAssistant is ready!")

        print("\nAvailable operations:")
        print("- Employee management")
        print("- Department information")
        print("- HR policies")
        print("- Salary and bonus calculations")

        print("\nType 'exit' to stop.\n")

        # --------------------------------------------------
        # STEP 4: USER INTERACTION LOOP
        # --------------------------------------------------

        while True:

            user_input = input("You: ").strip()

            if user_input.lower() in ["exit", "quit"]:

                print("\nExiting assistant...")

                break

            if not user_input:
                continue

            conversation.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(
                            text=user_input
                        )
                    ]
                )
            )

            # --------------------------------------------------
            # STEP 5: GEMINI TOOL EXECUTION LOOP
            # --------------------------------------------------

            for tool_round in range(5):

                response = gemini_client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=conversation,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        tools=gemini_tools,
                        temperature=0
                    )
                )

                candidate_content = (
                    response.candidates[0].content
                )

                conversation.append(candidate_content)

                function_calls = response.function_calls

                if not function_calls:

                    print("\nAssistant:")

                    print(
                        response.text or "No response generated."
                    )

                    break

                function_response_parts = []

                # --------------------------------------------------
                # STEP 6: EXECUTE MCP TOOL CALLS
                # --------------------------------------------------

                for function_call in function_calls:

                    tool_name = function_call.name

                    arguments = dict(
                        function_call.args or {}
                    )

                    print(
                        f"\nCalling MCP tool: {tool_name}"
                    )

                    tool_output = await execute_mcp_tool(
                        tool_name,
                        arguments,
                        tool_registry,
                        token_manager
                    )

                    print("\nTool result:", tool_output)

                    function_response_parts.append(
                        types.Part.from_function_response(
                            name=tool_name,
                            response={
                                "result": tool_output
                            }
                        )
                    )

                conversation.append(
                    types.Content(
                        role="user",
                        parts=function_response_parts
                    )
                )

            else:

                print(
                    "\nMaximum tool execution rounds reached."
                )


# ==========================================================
# 11. APPLICATION ENTRY POINT
# ==========================================================

if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        print("\nApplication stopped.")

    except Exception:

        logger.exception(
            "Unexpected application error"
        )