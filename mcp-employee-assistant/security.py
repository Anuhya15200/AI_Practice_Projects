import logging
import time

from collections import defaultdict, deque

from starlette.responses import JSONResponse

from jwt_validator import validate_access_token
from logging_config import setup_logging, get_logger

from exceptions import (
    AuthenticationError,
    AuthorizationError
)


# ==================================================
# 1. LOGGING CONFIGURATION
# ==================================================

setup_logging()

logger = get_logger(__name__)


# ==================================================
# 2. ROLE PERMISSIONS
# ==================================================

ROLE_PERMISSIONS = {

    "employee": [
        "employee.read",
        "department.read",
        "policy.read"
    ],

    "hr_manager": [
        "employee.read",
        "employee.create",
        "employee.update",
        "department.read",
        "policy.read"
    ],

    "admin": [
        "employee.read",
        "employee.create",
        "employee.update",
        "employee.delete",
        "department.read",
        "policy.read"
    ]
}


# ==================================================
# 3. EXTRACT BEARER TOKEN
# ==================================================

def extract_bearer_token(request):

    authorization = request.headers.get(
        "authorization", ""
    )

    if not authorization.startswith("Bearer "):
        return None

    return authorization[len("Bearer "):].strip()


# ==================================================
# 4. AUTHENTICATION MIDDLEWARE
# ==================================================

async def authenticate_request(request, call_next):

    if request.url.path.rstrip("/") == "/mcp":

        token = extract_bearer_token(request)

        if not token:

            logger.warning(
                "Authentication failed: Missing Bearer token"
            )

            return JSONResponse(
                status_code=401,
                content={
                    "error": "Unauthorized",
                    "message": "Missing Bearer access token"
                }
            )

        try:

            payload = validate_access_token(token)

            request.state.jwt_payload = payload

            logger.info(
                "Authentication successful for user: %s",
                payload.get("preferred_username", "unknown")
            )

        except ValueError:

            logger.warning(
                "Authentication failed: Invalid access token"
            )

            return JSONResponse(
                status_code=401,
                content={
                    "error": "Unauthorized",
                    "message": "Invalid or expired access token"
                }
            )

        except Exception:

            logger.exception(
                "Unexpected error during authentication"
            )

            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal Server Error",
                    "message": "Authentication could not be completed"
                }
            )

    return await call_next(request)


# ==================================================
# 5. AUTHORIZATION CHECK - RBAC
# ==================================================

def require_permission(ctx, required_permission):

    # --------------------------------------------------
    # STEP 1: EXTRACT REQUEST HEADERS
    # --------------------------------------------------

    headers = ctx.headers or {}

    authorization = (
        headers.get("authorization")
        or headers.get("Authorization")
        or ""
    )

    if not authorization.startswith("Bearer "):

        logger.warning(
            "RBAC denied: Missing authentication token"
        )

        raise AuthenticationError(
            "Authentication required"
        )

    token = authorization[len("Bearer "):].strip()

    # --------------------------------------------------
    # STEP 2: VALIDATE JWT
    # --------------------------------------------------

    try:

        payload = validate_access_token(token)

    except ValueError:

        logger.warning(
            "RBAC denied: Invalid access token"
        )

        raise AuthenticationError(
            "Invalid access token"
        )

    # --------------------------------------------------
    # STEP 3: EXTRACT USER INFORMATION
    # --------------------------------------------------

    username = payload.get(
        "preferred_username",
        "unknown"
    )

    realm_access = payload.get(
        "realm_access", {}
    )

    user_roles = realm_access.get(
        "roles", []
    )

    # --------------------------------------------------
    # STEP 4: COLLECT USER PERMISSIONS
    # --------------------------------------------------

    user_permissions = set()

    for role in user_roles:

        permissions = ROLE_PERMISSIONS.get(
            role, []
        )

        user_permissions.update(permissions)

    # --------------------------------------------------
    # STEP 5: DEBUG LOGGING
    # --------------------------------------------------

    logger.debug("========== RBAC DEBUG ==========")

    logger.debug("Username: %s", username)

    logger.debug("User roles: %s", user_roles)

    logger.debug(
        "User permissions: %s",
        sorted(user_permissions)
    )

    logger.debug(
        "Required permission: %s",
        required_permission
    )

    # --------------------------------------------------
    # STEP 6: CHECK AUTHORIZATION
    # --------------------------------------------------

    is_authorized = (
        required_permission in user_permissions
    )

    logger.debug(
        "Authorization result: %s",
        is_authorized
    )

    logger.debug("================================")

    if not is_authorized:

        logger.warning(
            "ACCESS DENIED: User '%s' attempted permission '%s'",
            username,
            required_permission
        )

        raise AuthorizationError(
            "You do not have permission to perform this operation."
        )

    logger.info(
        "ACCESS GRANTED: User '%s' has permission '%s'",
        username,
        required_permission
    )

    return True


# ==================================================
# 6. CUSTOM RATE LIMITING MIDDLEWARE
# ==================================================

class RateLimitMiddleware:

    def __init__(
        self,
        app,
        max_requests=60,
        window_seconds=60
    ):

        self.app = app

        self.max_requests = max_requests

        self.window_seconds = window_seconds

        self.requests = defaultdict(deque)

    async def __call__(self, scope, receive, send):

        if scope["type"] != "http":

            await self.app(
                scope,
                receive,
                send
            )

            return

        path = scope.get("path", "")

        # Apply rate limiting only to MCP endpoints.
        if path.rstrip("/") != "/mcp":

            await self.app(
                scope,
                receive,
                send
            )

            return

        # Identify client IP.
        client = scope.get("client")

        client_ip = (
            client[0] if client else "unknown"
        )

        current_time = time.time()

        request_times = self.requests[client_ip]

        # Remove expired requests.
        while (
            request_times
            and current_time - request_times[0]
            >= self.window_seconds
        ):

            request_times.popleft()

        # Check request limit.
        if len(request_times) >= self.max_requests:

            logger.warning(
                "Rate limit exceeded for IP: %s",
                client_ip
            )

            response = JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "message": (
                        "Rate limit exceeded. "
                        "Please try again later."
                    )
                },
                headers={
                    "Retry-After": str(
                        self.window_seconds
                    )
                }
            )

            await response(
                scope,
                receive,
                send
            )

            return

        # Record current request.
        request_times.append(current_time)

        await self.app(
            scope,
            receive,
            send
        )