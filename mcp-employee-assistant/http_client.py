import anyio

from mcp import Client


# =====================================
# 1. MCP SERVER URL
# =====================================

SERVER_URL = "http://127.0.0.1:8000/mcp"


# =====================================
# 2. MAIN CLIENT FUNCTION
# =====================================

async def main():

    async with Client(SERVER_URL) as client:

        print("\nCONNECTED TO HTTP MCP SERVER")

        # =================================
        # 3. DISCOVER AVAILABLE TOOLS
        # =================================

        tools = await client.list_tools()

        print("\nAVAILABLE TOOLS")

        for tool in tools.tools:

            print(tool.name)


        # =================================
        # 4. CALL EMPLOYEE TOOL
        # =================================

        print("\nGETTING EMPLOYEE DETAILS")

        result = await client.call_tool(
            "get_employee",
             {
                "employee_id": 101
            }
        )

        print("IS ERROR:", result.is_error)

        print("STRUCTURED CONTENT:")
        print(result.structured_content)

        print("NORMAL CONTENT:")

        for item in result.content:
            if hasattr(item, "text"):
                print(item.text)


        # =================================
        # 5. CALCULATE BONUS
        # =================================

        print("\nCALCULATING BONUS")

        bonus = await client.call_tool(
            "calculate_bonus",
            {
                "salary": 50000,
                "percentage": 15
            }
        )

        print(bonus.structured_content)


# =====================================
# 6. RUN CLIENT
# =====================================

if __name__ == "__main__":

    anyio.run(main)