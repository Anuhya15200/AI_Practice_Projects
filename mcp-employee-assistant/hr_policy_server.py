import logging
import time

import uvicorn

from mcp.server import MCPServer
from mcp.server.mcpserver import Context

from starlette.middleware.base import BaseHTTPMiddleware

from security import (
    authenticate_request,
    require_permission,
    RateLimitMiddleware
)

from logging_config import setup_logging, get_logger

from exceptions import (
    ValidationError,
    ResourceNotFoundError
)


# ==================================================
# 1. CENTRALIZED LOGGING CONFIGURATION
# ==================================================

setup_logging()

logger = get_logger(__name__)


# ==================================================
# 2. CREATE MCP SERVER
# ==================================================

mcp = MCPServer("HR Policy Server")


# ==================================================
# 3. HR POLICY DATA
# ==================================================

HR_POLICIES = {

    "leave": {
        "title": "Leave Policy",
        "description": (
            "This is demonstration leave policy information. "
            "Employees should refer to their official HR portal "
            "for actual leave entitlements."
        ),
        "details": {
            "annual_leave": "Example: 20 days per year",
            "sick_leave": "Example: 10 days per year",
            "casual_leave": "Example: 5 days per year",
            "approval": "Manager approval is required."
        }
    },

    "attendance": {
        "title": "Attendance Policy",
        "description": "Demonstration attendance policy.",
        "details": {
            "working_days": "Monday to Friday",
            "working_hours": "9 AM to 6 PM",
            "attendance": "Employees should record attendance.",
            "late_arrival": "Repeated late arrivals may require review."
        }
    },

    "remote_work": {
        "title": "Remote Work Policy",
        "description": "Demonstration remote work policy.",
        "details": {
            "eligibility": "Subject to manager approval.",
            "work_location": "Employees should communicate their location.",
            "availability": "Employees should remain available during working hours."
        }
    },

    "reimbursement": {
        "title": "Reimbursement Policy",
        "description": "Demonstration reimbursement policy.",
        "details": {
            "expenses": "Eligible business expenses may be reimbursed.",
            "receipts": "Supporting bills or receipts are required.",
            "approval": "Manager and finance approval may be required."
        }
    },

    "parental_leave": {
        "title": "Parental Leave Policy",
        "description": "Demonstration parental leave policy.",
        "details": {
            "eligibility": "Subject to applicable company policy.",
            "application": "Employees should contact HR.",
            "documentation": "Required supporting documentation may apply."
        }
    }
}


# ==================================================
# 4. GET ALL HR POLICIES
# ==================================================

@mcp.tool()
def get_all_hr_policies(ctx: Context) -> list:

    start_time = time.perf_counter()

    logger.info(
        "GET_ALL_HR_POLICIES: Operation started"
    )

    # STEP 1: AUTHORIZATION

    require_permission(ctx, "policy.read")

    logger.info(
        "GET_ALL_HR_POLICIES: Authorization successful"
    )

    # STEP 2: RETRIEVE POLICIES

    logger.info(
        "GET_ALL_HR_POLICIES: Retrieving policy records"
    )

    result = [
        {
            "policy_name": key,
            "title": value["title"],
            "description": value["description"]
        }
        for key, value in HR_POLICIES.items()
    ]

    duration = time.perf_counter() - start_time

    logger.info(
        "GET_ALL_HR_POLICIES: Retrieved %s policies | "
        "Duration: %.4f seconds",
        len(result),
        duration
    )

    return result


# ==================================================
# 5. GET PARTICULAR HR POLICY
# ==================================================

@mcp.tool()
def get_hr_policy(
    policy_name: str,
    ctx: Context
) -> dict:

    start_time = time.perf_counter()

    logger.info(
        "GET_HR_POLICY: Operation started | Policy: %s",
        policy_name
    )

    # STEP 1: AUTHORIZATION

    require_permission(ctx, "policy.read")

    logger.info(
        "GET_HR_POLICY: Authorization successful"
    )

    # STEP 2: INPUT VALIDATION

    if not policy_name or not policy_name.strip():

        logger.warning(
            "GET_HR_POLICY: Empty policy name"
        )

        raise ValidationError(
            "Policy name cannot be empty"
        )

    policy_name = policy_name.lower().strip()

    # STEP 3: RETRIEVE POLICY

    logger.info(
        "GET_HR_POLICY: Searching policy | %s",
        policy_name
    )

    policy = HR_POLICIES.get(policy_name)

    if policy is None:

        logger.warning(
            "GET_HR_POLICY: Policy not found | %s",
            policy_name
        )

        raise ResourceNotFoundError(
            f"Policy '{policy_name}' not found"
        )

    duration = time.perf_counter() - start_time

    logger.info(
        "GET_HR_POLICY: Policy retrieved successfully | "
        "Policy: %s | Duration: %.4f seconds",
        policy_name,
        duration
    )

    return {
        "policy_name": policy_name,
        **policy
    }


# ==================================================
# 6. SEARCH HR POLICIES
# ==================================================

@mcp.tool()
def search_hr_policies(
    query: str,
    ctx: Context
) -> list:

    start_time = time.perf_counter()

    logger.info(
        "SEARCH_HR_POLICIES: Operation started | Query: %s",
        query
    )

    # STEP 1: AUTHORIZATION

    require_permission(ctx, "policy.read")

    logger.info(
        "SEARCH_HR_POLICIES: Authorization successful"
    )

    # STEP 2: INPUT VALIDATION

    if not query or not query.strip():

        logger.warning(
            "SEARCH_HR_POLICIES: Empty search query"
        )

        raise ValidationError(
            "Search query cannot be empty"
        )

    query = query.lower().strip()

    # STEP 3: SEARCH POLICIES

    logger.info(
        "SEARCH_HR_POLICIES: Searching policy records"
    )

    matching_policies = []

    for policy_name, policy in HR_POLICIES.items():

        searchable_text = (
            policy_name + " "
            + policy["title"] + " "
            + policy["description"] + " "
            + str(policy["details"])
        ).lower()

        if query in searchable_text:

            matching_policies.append({
                "policy_name": policy_name,
                **policy
            })

    duration = time.perf_counter() - start_time

    logger.info(
        "SEARCH_HR_POLICIES: Search completed | "
        "Query: %s | Matches: %s | Duration: %.4f seconds",
        query,
        len(matching_policies),
        duration
    )

    return matching_policies


# ==================================================
# 7. MIDDLEWARE CONFIGURATION
# ==================================================

app = mcp.streamable_http_app()

# RATE LIMITING

app = RateLimitMiddleware(
    app,
    max_requests=60,
    window_seconds=60
)

# AUTHENTICATION

app = BaseHTTPMiddleware(
    app,
    dispatch=authenticate_request
)


# ==================================================
# 8. START SERVER
# ==================================================

if __name__ == "__main__":

    logger.info(
        "Starting HR Policy MCP Server..."
    )

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8002,
        ssl_keyfile="certs/server-key.pem",
        ssl_certfile="certs/server-cert.pem"
    )