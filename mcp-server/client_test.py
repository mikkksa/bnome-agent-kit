import asyncio, sys
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

TOKEN = sys.argv[1]
URL = "http://localhost:8010/mcp"

async def main():
    transport = StreamableHttpTransport(url=URL, headers={"Authorization": f"Bearer {TOKEN}"})
    client = Client(transport)
    async with client:
        tools = await client.list_tools()
        print("TOOLS:", [t.name for t in tools])
        res = await client.call_tool("list_my_apps", {})
        data = getattr(res, "structured_content", None) or getattr(res, "data", None)
        print("LIST_MY_APPS ->", data)

asyncio.run(main())
