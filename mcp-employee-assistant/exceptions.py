from mcp.server.mcpserver.exceptions import ToolError


# ==================================================
# BASE APPLICATION EXCEPTION
# ==================================================

class ApplicationError(ToolError):
    """Base exception for expected application errors."""

    def __init__(
        self,
        message,
        error_code="APPLICATION_ERROR"
    ):

        self.message = message
        self.error_code = error_code

        super().__init__(
            f"{error_code}: {message}"
        )


# ==================================================
# AUTHENTICATION EXCEPTION
# ==================================================

class AuthenticationError(ApplicationError):

    def __init__(self, message="Authentication failed"):

        super().__init__(
            message,
            error_code="AUTHENTICATION_ERROR"
        )


# ==================================================
# AUTHORIZATION EXCEPTION
# ==================================================

class AuthorizationError(ApplicationError):

    def __init__(self, message="Access denied"):

        super().__init__(
            message,
            error_code="AUTHORIZATION_ERROR"
        )


# ==================================================
# DATABASE EXCEPTION
# ==================================================

class DatabaseError(ApplicationError):

    def __init__(self, message="Database operation failed"):

        super().__init__(
            message,
            error_code="DATABASE_ERROR"
        )


# ==================================================
# RESOURCE NOT FOUND EXCEPTION
# ==================================================

class ResourceNotFoundError(ApplicationError):

    def __init__(self, message="Requested resource not found"):

        super().__init__(
            message,
            error_code="RESOURCE_NOT_FOUND"
        )


# ==================================================
# VALIDATION EXCEPTION
# ==================================================

class ValidationError(ApplicationError):

    def __init__(self, message="Invalid input"):

        super().__init__(
            message,
            error_code="VALIDATION_ERROR"
        )