import os

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
# 2. SUMMARY AGENT EXECUTOR
# ==================================================

class SummaryAgentExecutor(AgentExecutor):
    """
    Summary Agent:
    Uses Gemini to summarize content received from another agent.
    """

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:

        # Extract research notes received through A2A.
        user_message = context.message

        if user_message is None:
            await event_queue.enqueue_event(
                new_text_message(
                    "No research notes were provided.",
                    role=Role.ROLE_AGENT,
                )
            )
            return

        parts = get_text_parts(user_message.parts)
        research_text = "\n".join(parts).strip()

        if not research_text:
            research_text = "No research notes were provided."

        print("\n[Summary Agent] Received research content.")
        print(
            f"[Summary Agent] Input length: "
            f"{len(research_text)} characters"
        )

        # Ask Gemini to summarize the actual research content.
        prompt = f"""
You are an expert technical summarization assistant.

Summarize the research content provided below.

RESEARCH CONTENT:
{research_text}

INSTRUCTIONS:

1. Identify the main topic.
2. Explain the key concepts.
3. Preserve important technical details.
4. Summarize the main applications.
5. Mention significant benefits and limitations.
6. Finish with a short conclusion.

Use clear headings and bullet points.

Do not invent facts.
Do not add claims that are unsupported by the input.
If the input is incomplete, explain that limitation.
"""

        try:
            response = await gemini_client.aio.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
            )

            summary = response.text

            if not summary:
                summary = (
                    "The model returned an empty summary. "
                    "Please try again."
                )

        except Exception as exc:
            print(f"[Summary Agent] Gemini error: {exc}")

            summary = (
                "The Summary Agent could not generate a summary. "
                "Please check the Gemini API key, model availability, "
                "network connection, and API quota."
            )

        print("[Summary Agent] Summary generated.")

        # Send the summary back through A2A.
        await event_queue.enqueue_event(
            new_text_message(
                summary,
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

summary_skill = AgentSkill(
    id="summarize",
    name="AI Summarization",
    description=(
        "Summarizes research content using Gemini "
        "while preserving important technical details."
    ),
    tags=["summary", "analysis", "generative-ai"],
    examples=[
        "Summarize research about Generative AI",
        "Summarize technical documentation",
        "Summarize an A2A agent's response",
    ],
)


# ==================================================
# 4. DEFINE AGENT CARD
# ==================================================

summary_agent_card = AgentCard(
    name="Summary Agent",
    description=(
        "An AI summarization agent powered by Gemini."
    ),
    version="1.0.0",
    supported_interfaces=[
        AgentInterface(
            url="http://127.0.0.1:8002/",
            protocol_binding="JSONRPC",
            protocol_version="1.0",
        )
    ],
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    capabilities=AgentCapabilities(
        streaming=False,
    ),
    skills=[summary_skill],
)


# ==================================================
# 5. CREATE A2A REQUEST HANDLER
# ==================================================

summary_request_handler = DefaultRequestHandler(
    agent_executor=SummaryAgentExecutor(),
    task_store=InMemoryTaskStore(),
    agent_card=summary_agent_card,
)


# ==================================================
# 6. CREATE A2A SERVER
# ==================================================

summary_routes = []

summary_routes.extend(
    create_agent_card_routes(summary_agent_card)
)

summary_routes.extend(
    create_jsonrpc_routes(
        summary_request_handler,
        rpc_url="/",
    )
)

app = Starlette(routes=summary_routes)


# ==================================================
# 7. START SERVER
# ==================================================

if __name__ == "__main__":
    print("Starting Gemini Summary Agent...")
    print("URL: http://127.0.0.1:8002")
    print("Model:", MODEL_NAME)

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8002,
    )