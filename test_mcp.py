"""Test réel du protocole MCP stdio, indépendant de Claude."""
import asyncio
import json
from pathlib import Path
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    server = StdioServerParameters(command=sys.executable, args=[str(Path(__file__).with_name('mcp_server.py').resolve())])
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert {t.name for t in tools.tools} == {'list_factures', 'total_factures'}
            for name, arguments in [('list_factures', {'limit': 3}), ('total_factures', {}),
                                    ('total_factures', {'debut': '2026-11-01', 'fin': '2026-11-30'})]:
                result = await session.call_tool(name, arguments)
                assert not result.isError, result
                payload = result.structuredContent or json.loads(result.content[0].text)
                if name == 'list_factures':
                    assert len(payload['factures']) == 3
                print(name, payload if name == 'total_factures' else '3 factures reçues')
            bad = await session.call_tool('total_factures', {'debut': 'date invalide'})
            assert bad.isError
    print('Protocole MCP stdio : OK')

if __name__ == '__main__':
    async def bounded():
        async with asyncio.timeout(30):
            await main()
    asyncio.run(bounded())
