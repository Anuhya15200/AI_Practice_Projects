import os
import asyncio

import uvicorn

from dotenv import load_dotenv
from google import genai
from starlette.applications import Starlette

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks import InMemoryTaskStore

from a2a.helpers import new_text_message, get_text_parts

from a2a.types import (
    AgentCard,
    AgentCapabilities,
    AgentInterface,
    AgentSkill,
    Role,
)


# ==================================================
# 1. LOAD CONFIGURATION
# ==================================================

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing. Add it to your .env file."
    )

gemini_client = genai.Client(api_key=API_KEY)


# ==================================================
# 2. RESEARCH AGENT EXECUTOR
# ==================================================

class ResearchAgentExecutor(AgentExecutor):
    """
    Research Agent:
    Uses Gemini to explain topics and generate structured research notes.
    """

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:

        # Extract the user's message.
        user_message = context.message

        if user_message is None:
            await event_queue.enqueue_event(
                new_text_message(
                    "No research question was provided.",
                    role=Role.ROLE_AGENT,
                )
            )
            return

        parts = get_text_parts(user_message.parts)
        topic = "\n".join(parts).strip()

        if not topic:
            topic = "Generative AI"

        # Remove the optional prefix sent by the client.
        if topic.lower().startswith("research "):
            topic = topic[len("research "):].strip()

        print(f"\n[Research Agent] Topic: {topic}")

        # Create a prompt for Gemini.
        prompt = f"""
You are an expert technical research assistant.

Answer the user's question accurately and clearly.

USER QUESTION:
{topic}

INSTRUCTIONS:

1. Explain the topic in simple language.
2. Provide a clear introduction.
3. Explain the important concepts.
4. Describe how it works.
5. Give practical examples and applications.
6. Explain the advantages.
7. Explain the limitations and challenges.
8. Finish with a concise conclusion.

Use headings and bullet points where appropriate.

Do not claim to have searched the internet.
Do not invent citations, statistics, or sources.
Clearly identify uncertainty when relevant.
"""

        try:
            # Gemini SDK calls are asynchronous here.
            response = await gemini_client.aio.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
            )

            research_result = response.text

            if not research_result:
                research_result = (
                    "The model returned an empty response. "
                    "Please try again."
                )

        except Exception as exc:
            print(f"[Research Agent] Gemini error: {exc}")

            research_result = (
                "The Research Agent could not generate a response. "
                "Please check the Gemini API key, model availability, "
                "network connection, and API quota."
            )

        print("[Research Agent] Response generated.")

        # Return the result through A2A.
        await event_queue.enqueue_event(
            new_text_message(
                research_result,
                role=Role.ROLE_AGENT,
            )
        )

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        raise NotImplementedError(
            "Cancellation is not implemented."
        )


# ==================================================
# 3. DEFINE AGENT SKILL
# ==================================================

research_skill = AgentSkill(
    id="research",
    name="AI Research",
    description=(
        "Explains technical topics and generates "
        "structured research notes using Gemini."
    ),
    tags=["research", "generative-ai", "analysis"],
    examples=[
        "Explain Generative AI",
        "Explain the A2A protocol",
        "Explain Retrieval-Augmented Generation",
    ],
)


# ==================================================
# 4. DEFINE AGENT CARD
# ==================================================

research_agent_card = AgentCard(
    name="Research Agent",
    description=(
        "An AI research agent powered by Gemini."
    ),
    version="1.0.0",
    supported_interfaces=[
        AgentInterface(
            url="http://127.0.0.1:8001/",
            protocol_binding="JSONRPC",
            protocol_version="1.0",
        )
    ],
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    capabilities=AgentCapabilities(
        streaming=False,
    ),
    skills=[research_skill],
)


# ==================================================
# 5. CREATE A2A REQUEST HANDLER
# ==================================================

research_request_handler = DefaultRequestHandler(
    agent_executor=ResearchAgentExecutor(),
    task_store=InMemoryTaskStore(),
    agent_card=research_agent_card,
)


# ==================================================
# 6. CREATE A2A SERVER
# ==================================================

research_routes = []

research_routes.extend(
    create_agent_card_routes(research_agent_card)
)

research_routes.extend(
    create_jsonrpc_routes(
        research_request_handler,
        rpc_url="/",
    )
)

app = Starlette(routes=research_routes)


# ==================================================
# 7. START SERVER
# ==================================================

if __name__ == "__main__":
    print("Starting Gemini Research Agent...")
    print("URL: http://127.0.0.1:8001")
    print("Model:", MODEL_NAME)

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8001,
    )