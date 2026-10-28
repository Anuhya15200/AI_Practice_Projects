import asyncio
import uuid

import httpx

from a2a.client import A2ACardResolver, create_client
from a2a.helpers import get_message_text, get_artifact_text
from a2a.types import (
    Message,
    Part,
    Role,
    SendMessageRequest,
)


# ==================================================
# 1. COMMUNICATE WITH AN A2A AGENT
# ==================================================

async def send_message_to_agent(
    agent_url: str,
    user_text: str,
) -> str:
    """
    Discovers an A2A agent, sends a message,
    and extracts its text response.
    """

    timeout = httpx.Timeout(120.0)

    async with httpx.AsyncClient(timeout=timeout) as httpx_client:

        # Discover the remote agent.
        resolver = A2ACardResolver(
            httpx_client,
            agent_url,
        )

        agent_card = await resolver.get_agent_card()

        print(f"Connected to: {agent_card.name}")

        # Create a client for the discovered agent.
        client = await create_client(agent_card)

        try:
            # Construct the user message.
            message = Message(
                role=Role.ROLE_USER,
                message_id=str(uuid.uuid4()),
                parts=[
                    Part(text=user_text)
                ],
            )

            request = SendMessageRequest(
                message=message,
            )

            # Send the request through A2A.
            stream = client.send_message(request)

            async for event in stream:

                # Direct message response.
                if event.HasField("message"):
                    return get_message_text(
                        event.message,
                        delimiter="\n",
                    )

                # Artifact response.
                if event.HasField("artifact_update"):
                    artifact = event.artifact_update.artifact

                    return get_artifact_text(
                        artifact,
                        delimiter="\n",
                    )

                # Task status updates may occur before the
                # final artifact or response.
                if event.HasField("status_update"):
                    status = event.status_update.status

                    if status.HasField("message"):
                        status_text = get_message_text(
                            status.message,
                            delimiter="\n",
                        )

                        print("Agent status:", status_text)

            raise RuntimeError(
                f"The agent at {agent_url} did not return "
                "a message or artifact."
            )

        finally:
            await client.close()


# ==================================================
# 2. MAIN MULTI-AGENT WORKFLOW
# ==================================================

async def main():

    print("=" * 60)
    print("GEMINI-POWERED A2A MULTI-AGENT SYSTEM")
    print("=" * 60)

    topic = input(
        "\nEnter a topic to research: "
    ).strip()

    if not topic:
        topic = "Generative AI"

    try:
        # ----------------------------------------------
        # STEP 1: RESEARCH AGENT
        # ----------------------------------------------

        print("\nSTEP 1: Calling Research Agent...")
        print("Gemini is generating the research response...")

        research_result = await send_message_to_agent(
            agent_url="http://127.0.0.1:8001",
            user_text=topic,
        )

        print("\n" + "=" * 60)
        print("RESEARCH AGENT RESPONSE")
        print("=" * 60)
        print(research_result)

        # ----------------------------------------------
        # STEP 2: SUMMARY AGENT
        # ----------------------------------------------

        print("\nSTEP 2: Calling Summary Agent...")
        print("Gemini is summarizing the research...")

        summary_result = await send_message_to_agent(
            agent_url="http://127.0.0.1:8002",
            user_text=research_result,
        )

        print("\n" + "=" * 60)
        print("FINAL SUMMARY")
        print("=" * 60)
        print(summary_result)

        print("\nWorkflow completed successfully!")

    except httpx.HTTPStatusError as exc:
        print("\nHTTP error while communicating with an agent.")
        print("Status:", exc.response.status_code)
        print("URL:", exc.request.url)
        print("Response:", exc.response.text)

    except httpx.RequestError as exc:
        print("\nCould not connect to an A2A server.")
        print("Details:", exc)

        print(
            "Check that both servers are running on ports "
            "8001 and 8002."
        )

    except Exception as exc:
        print("\nWorkflow failed.")
        print(f"{type(exc).__name__}: {exc}")


# ==================================================
# 3. APPLICATION ENTRY POINT
# ==================================================

if __name__ == "__main__":
    asyncio.run(main())