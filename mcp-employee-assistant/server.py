import logging
import sqlite3
import time
import math
from typing import Optional

import uvicorn

from mcp.server import MCPServer
from mcp.server.mcpserver import Context

from database.db import get_connection

from security import (
    authenticate_request,
    require_permission,
    RateLimitMiddleware
)

from starlette.middleware.base import BaseHTTPMiddleware

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

mcp = MCPServer("Employee Management Server")


# ==================================================
# 3. GET EMPLOYEE BY ID
# ==================================================

@mcp.tool()
def get_employee(
    employee_id: int,
    ctx: Context
) -> dict:

    start_time = time.perf_counter()

    logger.info(
        "GET_EMPLOYEE: Operation started | Employee ID: %s",
        employee_id
    )

    require_permission(ctx, "employee.read")

    try:

        if employee_id <= 0:
            raise ValidationError(
                "Employee ID must be greater than zero"
            )

        logger.info(
            "GET_EMPLOYEE: Database query started | Employee ID: %s",
            employee_id
        )

        with get_connection() as connection:

            employee = connection.execute(
                """
                SELECT *
                FROM employees
                WHERE employee_id = ?
                """,
                (employee_id,)
            ).fetchone()

            if employee is None:
                raise ResourceNotFoundError(
                    "Employee not found"
                )

            duration = time.perf_counter() - start_time

            logger.info(
                "GET_EMPLOYEE: Employee retrieved successfully | "
                "Employee ID: %s | Duration: %.4f seconds",
                employee_id,
                duration
            )

            return dict(employee)

    except (ValidationError, ResourceNotFoundError):
        raise

    except sqlite3.Error as exc:

        logger.exception(
            "GET_EMPLOYEE: Database error | Employee ID: %s",
            employee_id
        )

        raise DatabaseError(
            "Unable to retrieve employee"
        ) from exc


# ==================================================
# 4. GET ALL EMPLOYEES
# ==================================================

@mcp.tool()
def get_all_employees(ctx: Context) -> list[dict]:

    logger.info("GET_ALL_EMPLOYEES TOOL INVOKED")

    require_permission(ctx, "employee.read")

    try:

        logger.info(
            "GET_ALL_EMPLOYEES: Database query started"
        )

        with get_connection() as connection:

            employees = connection.execute(
                """
                SELECT *
                FROM employees
                ORDER BY employee_id
                """
            ).fetchall()

            logger.info(
                "GET_ALL_EMPLOYEES: Retrieved %s employees",
                len(employees)
            )

            return [
                dict(employee)
                for employee in employees
            ]

    except sqlite3.Error as exc:

        logger.exception(
            "GET_ALL_EMPLOYEES: Database error"
        )

        raise DatabaseError(
            "Unable to retrieve employees"
        ) from exc


# ==================================================
# 5. GET EMPLOYEES BY DEPARTMENT
# ==================================================

@mcp.tool()
def get_employees_by_department(
    department: str,
    ctx: Context
) -> list[dict]:

    logger.info(
        "GET_EMPLOYEES_BY_DEPARTMENT TOOL INVOKED | Department: %s",
        department
    )

    require_permission(ctx, "employee.read")

    if not isinstance(department, str) or not department.strip():
        raise ValidationError(
            "Department cannot be empty"
        )

    try:

        logger.info(
            "GET_EMPLOYEES_BY_DEPARTMENT: Database query started"
        )

        with get_connection() as connection:

            employees = connection.execute(
                """
                SELECT *
                FROM employees
                WHERE LOWER(department) = LOWER(?)
                """,
                (department.strip(),)
            ).fetchall()

            logger.info(
                "GET_EMPLOYEES_BY_DEPARTMENT: Retrieved %s employees "
                "from department %s",
                len(employees),
                department
            )

            return [
                dict(employee)
                for employee in employees
            ]

    except sqlite3.Error as exc:

        logger.exception(
            "GET_EMPLOYEES_BY_DEPARTMENT: Database error"
        )

        raise DatabaseError(
            "Unable to retrieve department employees"
        ) from exc


# ==================================================
# 6. ADD EMPLOYEE
# ==================================================

@mcp.tool()
def add_employee(
    name: str,
    department: str,
    salary: float,
    ctx: Context
) -> dict:

    logger.info(
        "ADD_EMPLOYEE TOOL INVOKED | Employee: %s",
        name
    )

    require_permission(ctx, "employee.create")

    # ==================================================
    # INPUT VALIDATION
    # ==================================================

    # 1. Validate employee name

    if not isinstance(name, str) or not name.strip():

        raise ValidationError(
            "Employee name cannot be empty"
        )

    name = name.strip()

    if len(name) > 100:

        raise ValidationError(
            "Employee name cannot exceed 100 characters"
        )

    # 2. Validate department

    if not isinstance(department, str) or not department.strip():

        raise ValidationError(
            "Department cannot be empty"
        )

    department = department.strip()

    if len(department) > 50:

        raise ValidationError(
            "Department cannot exceed 50 characters"
        )

    # 3. Validate salary

    if isinstance(salary, bool) or not isinstance(salary, (int, float)):

        raise ValidationError(
            "Salary must be a valid number"
        )

    if not math.isfinite(salary):

        raise ValidationError(
            "Salary must be a finite number"
        )

    if salary < 0:

        raise ValidationError(
            "Salary cannot be negative"
        )

    # ==================================================
    # DATABASE INSERTION
    # ==================================================

    try:

        with get_connection() as connection:

            logger.info(
                "ADD_EMPLOYEE: Database insertion started"
            )

            cursor = connection.execute(
                """
                INSERT INTO employees
                (name, department, salary)
                VALUES (?, ?, ?)
                """,
                (
                    name,
                    department,
                    salary
                )
            )

            employee_id = cursor.lastrowid

            logger.info(
                "ADD_EMPLOYEE: Employee created successfully | ID: %s",
                employee_id
            )

            return {
                "message": "Employee added successfully",
                "employee_id": employee_id,
                "name": name,
                "department": department,
                "salary": salary
            }

    except sqlite3.Error as exc:

        logger.exception(
            "ADD_EMPLOYEE: Database insertion failed"
        )

        raise DatabaseError(
            "Unable to add employee"
        ) from exc


# ==================================================
# 7. UPDATE EMPLOYEE
# ==================================================

@mcp.tool()
def update_employee(
    employee_id: int,
    name: Optional[str] = None,
    department: Optional[str] = None,
    salary: Optional[float] = None,
    ctx: Context = None
) -> dict:

    logger.info(
        "UPDATE_EMPLOYEE TOOL INVOKED | Employee ID: %s",
        employee_id
    )

    require_permission(ctx, "employee.update")

    # INPUT VALIDATION

    if employee_id <= 0:

        raise ValidationError(
            "Employee ID must be greater than zero"
        )

    # Explicitly allow only approved database columns

    allowed_columns = {
        "name",
        "department",
        "salary"
    }

    updates = {}

    if name is not None:

        if not isinstance(name, str) or not name.strip():

            raise ValidationError(
                "Name cannot be empty"
            )

        name = name.strip()

        if len(name) > 100:

            raise ValidationError(
                "Employee name cannot exceed 100 characters"
            )

        updates["name"] = name

    if department is not None:

        if not isinstance(department, str) or not department.strip():

            raise ValidationError(
                "Department cannot be empty"
            )

        department = department.strip()

        if len(department) > 50:

            raise ValidationError(
                "Department cannot exceed 50 characters"
            )

        updates["department"] = department

    if salary is not None:

        if isinstance(salary, bool) or not isinstance(salary, (int, float)):

            raise ValidationError(
                "Salary must be a valid number"
            )

        if not math.isfinite(salary):

            raise ValidationError(
                "Salary must be a finite number"
            )

        if salary < 0:

            raise ValidationError(
                "Salary cannot be negative"
            )

        updates["salary"] = salary

    if not updates:

        raise ValidationError(
            "At least one update field must be provided"
        )

    # Check whether all columns are allowed

    if not set(updates.keys()).issubset(allowed_columns):

        raise ValidationError(
            "Invalid update field"
        )

    set_clause = ", ".join(
        f"{column} = ?" for column in updates
    )

    values = list(updates.values())

    values.append(employee_id)

    try:

        logger.info(
            "UPDATE_EMPLOYEE: Database update started | ID: %s",
            employee_id
        )

        with get_connection() as connection:

            cursor = connection.execute(
                f"""
                UPDATE employees
                SET {set_clause}
                WHERE employee_id = ?
                """,
                values
            )

            if cursor.rowcount == 0:

                raise ResourceNotFoundError(
                    "Employee not found"
                )

            logger.info(
                "UPDATE_EMPLOYEE: Employee updated successfully | ID: %s",
                employee_id
            )

            return {
                "message": "Employee updated successfully",
                "employee_id": employee_id,
                "updated_fields": updates
            }

    except ResourceNotFoundError:
        raise

    except sqlite3.Error as exc:

        logger.exception(
            "UPDATE_EMPLOYEE: Database update failed"
        )

        raise DatabaseError(
            "Unable to update employee"
        ) from exc


# ==================================================
# 8. DELETE EMPLOYEE
# ==================================================

@mcp.tool()
def delete_employee(
    employee_id: int,
    ctx: Context
) -> dict:

    logger.info(
        "DELETE_EMPLOYEE TOOL INVOKED | Employee ID: %s",
        employee_id
    )

    require_permission(ctx, "employee.delete")

    if employee_id <= 0:

        raise ValidationError(
            "Employee ID must be greater than zero"
        )

    try:

        logger.info(
            "DELETE_EMPLOYEE: Database deletion started | ID: %s",
            employee_id
        )

        with get_connection() as connection:

            cursor = connection.execute(
                """
                DELETE FROM employees
                WHERE employee_id = ?
                """,
                (employee_id,)
            )

            if cursor.rowcount == 0:

                raise ResourceNotFoundError(
                    "Employee not found"
                )

            logger.info(
                "DELETE_EMPLOYEE: Employee deleted successfully | ID: %s",
                employee_id
            )

            return {
                "message": "Employee deleted successfully",
                "employee_id": employee_id
            }

    except ResourceNotFoundError:
        raise

    except sqlite3.Error as exc:

        logger.exception(
            "DELETE_EMPLOYEE: Database deletion failed | ID: %s",
            employee_id
        )

        raise DatabaseError(
            "Unable to delete employee"
        ) from exc


# ==================================================
# 9. CALCULATE BONUS
# ==================================================

@mcp.tool()
def calculate_bonus(
    salary: float,
    percentage: float,
    ctx: Context
) -> dict:

    logger.info(
        "CALCULATE_BONUS TOOL INVOKED"
    )

    require_permission(ctx, "employee.read")

    # INPUT VALIDATION

    if isinstance(salary, bool) or not isinstance(salary, (int, float)):

        raise ValidationError(
            "Salary must be a valid number"
        )

    if not math.isfinite(salary) or salary < 0:

        raise ValidationError(
            "Salary must be a finite non-negative number"
        )

    if isinstance(percentage, bool) or not isinstance(percentage, (int, float)):

        raise ValidationError(
            "Percentage must be a valid number"
        )

    if not math.isfinite(percentage) or percentage < 0 or percentage > 100:

        raise ValidationError(
            "Percentage must be between 0 and 100"
        )

    bonus = salary * percentage / 100

    logger.info(
        "CALCULATE_BONUS: Calculation completed successfully"
    )

    return {
        "salary": salary,
        "bonus_percentage": percentage,
        "bonus_amount": round(bonus, 2),
        "total_salary": round(salary + bonus, 2)
    }


# ==================================================
# 10. MIDDLEWARE CONFIGURATION
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
# 11. START SERVER
# ==================================================

if __name__ == "__main__":

    logger.info(
        "Starting Employee Management MCP Server..."
    )

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        ssl_keyfile="certs/server-key.pem",
        ssl_certfile="certs/server-cert.pem"
    )