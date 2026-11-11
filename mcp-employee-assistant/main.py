from contextlib import asynccontextmanager

from fastapi import FastAPI

from server import mcp


# Create MCP ASGI application
mcp_app = mcp.streamable_http_app()


# Manage MCP server lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):

    async with mcp.session_manager.run():

        yield


# Create FastAPI application
app = FastAPI(
    title="Employee Management API",
    lifespan=lifespan
)


# Normal REST API
@app.get("/")
def home():

    return {
        "message": "Employee Management Application"
    }


@app.get("/health")
def health():

    return {
        "status": "healthy"
    }


# Mount MCP application
app.mount("/", mcp_app)