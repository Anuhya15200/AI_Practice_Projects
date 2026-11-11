import anyio

from mcp import Client, StdioServerParameters


# =====================================
# 1. CONNECT TO MCP SERVER
# =====================================

server = StdioServerParameters(
    command="uv",
    args=["run", "server.py"]
)


# =====================================
# 2. MAIN CLIENT FUNCTION
# =====================================

async def main():

    async with Client(server) as client:

        print("\nCONNECTED TO MCP SERVER")

        # =================================
        # 3. DISCOVER AVAILABLE TOOLS
        # =================================

        print("\nAVAILABLE TOOLS")

        tools_result = await client.list_tools()

        for tool in tools_result.tools:

            print("Tool Name:", tool.name)

            print("Description:", tool.description)

            print("Input Schema:", tool.input_schema)

            print("------------------------")


        # =================================
        # 4. CALL AN MCP TOOL
        # =================================

        print("\nCALLING GET EMPLOYEE TOOL")

        result = await client.call_tool(
            "get_employee",
            {
                "employee_id": 101
            }
        )

        print("Tool Result:")

        print(result.structured_content)

        print("Is Error:", result.is_error)


        # =================================
        # 5. CALL ANOTHER TOOL
        # =================================

        print("\nCALCULATING BONUS")

        bonus_result = await client.call_tool(
            "calculate_bonus",
            {
                "salary": 50000,
                "percentage": 15
            }
        )

        print(bonus_result.structured_content)


        # =================================
        # 6. DISCOVER RESOURCES
        # =================================

        print("\nAVAILABLE RESOURCES")

        resources = await client.list_resources()

        for resource in resources.resources:

            print(resource.uri)


        # =================================
        # 7. READ RESOURCE
        # =================================

        print("\nREADING COMPANY INFORMATION")

        company = await client.read_resource(
            "company://information"
        )

        for content in company.contents:

            if hasattr(content, "text"):

                print(content.text)


        # =================================
        # 8. DISCOVER PROMPTS
        # =================================

        print("\nAVAILABLE PROMPTS")

        prompts = await client.list_prompts()

        for prompt in prompts.prompts:

            print(prompt.name)


        # =================================
        # 9. GET PROMPT
        # =================================

        print("\nGETTING EMPLOYEE SUMMARY PROMPT")

        prompt_result = await client.get_prompt(
            "employee_summary",
            {
                "name": "Rahul",
                "department": "IT"
            }
        )

        for message in prompt_result.messages:

            print(message.content.text)


# =====================================
# EXECUTE CLIENT
# =====================================

if __name__ == "__main__":

    anyio.run(main)