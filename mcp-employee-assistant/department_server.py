import logging
import time
import sqlite3

import uvicorn

from mcp.server import MCPServer
from mcp.server.mcpserver import Context

from database.db import get_connection

from starlette.middleware.base import BaseHTTPMiddleware

from security import (
    authenticate_request,
    require_permission,
    RateLimitMiddleware
)

from logging_config import setup_logging, get_logger

from exceptions import (
    ValidationError,
    ResourceNotFoundError,
    DatabaseError
)


# ==================================================
# 1. CENTRALIZED LOGGING CONFIGURATION
# ==================================================

setup_logging()

logger = get_logger(__name__)


# ==================================================
# 2. CREATE MCP SERVER
# ==================================================

mcp = MCPServer("Department Management Server")


# ==================================================
# 3. GET ALL DEPARTMENTS
# ==================================================

@mcp.tool()
def get_all_departments(ctx: Context) -> list:

    start_time = time.perf_counter()

    logger.info("GET_ALL_DEPARTMENTS: Operation started")

    # STEP 1: AUTHORIZATION
    require_permission(ctx, "department.read")

    logger.info(
        "GET_ALL_DEPARTMENTS: Authorization successful"
    )

    try:

        # STEP 2: DATABASE QUERY
        logger.info(
            "GET_ALL_DEPARTMENTS: Database query started"
        )

        with get_connection() as connection:

            departments = connection.execute(
                """
                SELECT DISTINCT department
                FROM employees
                ORDER BY department
                """
            ).fetchall()

            result = [
                row["department"]
                for row in departments
            ]

            duration = time.perf_counter() - start_time

            logger.info(
                "GET_ALL_DEPARTMENTS: Retrieved %s departments | "
                "Duration: %.4f seconds",
                len(result),
                duration
            )

            return result

    except sqlite3.Error as exc:

        logger.exception(
            "GET_ALL_DEPARTMENTS: Database query failed"
        )

        raise DatabaseError(
            "Unable to retrieve departments"
        ) from exc


# ==================================================
# 4. GET DEPARTMENT SUMMARY
# ==================================================

@mcp.tool()
def get_department_summary(
    department: str,
    ctx: Context
) -> dict:

    start_time = time.perf_counter()

    logger.info(
        "GET_DEPARTMENT_SUMMARY: Operation started | Department: %s",
        department
    )

    # STEP 1: AUTHORIZATION
    require_permission(ctx, "department.read")

    logger.info(
        "GET_DEPARTMENT_SUMMARY: Authorization successful"
    )

    # STEP 2: INPUT VALIDATION
    if not department or not department.strip():

        logger.warning(
            "GET_DEPARTMENT_SUMMARY: Empty department name"
        )

        raise ValidationError(
            "Department name cannot be empty"
        )

    try:

        # STEP 3: DATABASE QUERY
        logger.info(
            "GET_DEPARTMENT_SUMMARY: Database query started | "
            "Department: %s",
            department
        )

        with get_connection() as connection:

            summary = connection.execute(
                """
                SELECT
                    department,
                    COUNT(*) AS total_employees,
                    AVG(salary) AS average_salary,
                    MAX(salary) AS highest_salary,
                    MIN(salary) AS lowest_salary
                FROM employees
                WHERE LOWER(department) = LOWER(?)
                GROUP BY department
                """,
                (department.strip(),)
            ).fetchone()

            if summary is None:

                logger.warning(
                    "GET_DEPARTMENT_SUMMARY: Department not found | %s",
                    department
                )

                raise ResourceNotFoundError(
                    f"Department '{department}' not found"
                )

            result = dict(summary)

            if result["average_salary"] is not None:

                result["average_salary"] = round(
                    result["average_salary"], 2
                )

            duration = time.perf_counter() - start_time

            logger.info(
                "GET_DEPARTMENT_SUMMARY: Successfully retrieved "
                "summary | Department: %s | Employees: %s | "
                "Duration: %.4f seconds",
                department,
                result["total_employees"],
                duration
            )

            return result

    except sqlite3.Error as exc:

        logger.exception(
            "GET_DEPARTMENT_SUMMARY: Database query failed"
        )

        raise DatabaseError(
            "Unable to retrieve department summary"
        ) from exc


# ==================================================
# 5. GET EMPLOYEES IN A DEPARTMENT
# ==================================================

@mcp.tool()
def get_department_employees(
    department: str,
    ctx: Context
) -> list:

    start_time = time.perf_counter()

    logger.info(
        "GET_DEPARTMENT_EMPLOYEES: Operation started | Department: %s",
        department
    )

    # STEP 1: AUTHORIZATION
    require_permission(ctx, "department.read")

    logger.info(
        "GET_DEPARTMENT_EMPLOYEES: Authorization successful"
    )

    # STEP 2: INPUT VALIDATION
    if not department or not department.strip():

        logger.warning(
            "GET_DEPARTMENT_EMPLOYEES: Empty department name"
        )

        raise ValidationError(
            "Department name cannot be empty"
        )

    try:

        # STEP 3: DATABASE QUERY
        logger.info(
            "GET_DEPARTMENT_EMPLOYEES: Database query started | "
            "Department: %s",
            department
        )

        with get_connection() as connection:

            employees = connection.execute(
                """
                SELECT
                    employee_id,
                    name,
                    department,
                    salary
                FROM employees
                WHERE LOWER(department) = LOWER(?)
                ORDER BY employee_id
                """,
                (department.strip(),)
            ).fetchall()

            result = [
                dict(employee)
                for employee in employees
            ]

            duration = time.perf_counter() - start_time

            logger.info(
                "GET_DEPARTMENT_EMPLOYEES: Retrieved %s employees | "
                "Department: %s | Duration: %.4f seconds",
                len(result),
                department,
                duration
            )

            return result

    except sqlite3.Error as exc:

        logger.exception(
            "GET_DEPARTMENT_EMPLOYEES: Database query failed"
        )

        raise DatabaseError(
            "Unable to retrieve department employees"
        ) from exc


# ==================================================
# 6. MIDDLEWARE CONFIGURATION
# ==================================================

app = mcp.streamable_http_app()

# Rate limiting
app = RateLimitMiddleware(
    app,
    max_requests=60,
    window_seconds=60
)

# Authentication
app = BaseHTTPMiddleware(
    app,
    dispatch=authenticate_request
)


# ==================================================
# 7. START SERVER
# ==================================================

if __name__ == "__main__":

    logger.info(
        "Starting Department Management MCP Server..."
    )

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8001,
        ssl_keyfile="certs/server-key.pem",
        ssl_certfile="certs/server-cert.pem"
    )