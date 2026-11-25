import os
from pathlib import Path
import sys
import tempfile
import unittest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_sdk_stdio_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            binary=os.environ.get("CANVASLINK_TEST_EXE")
            args=["mcp"] if binary else ["-m","canvaslink","mcp"]
            env=dict(os.environ,CANVASLINK_DATA_DIR=directory)
            params=StdioServerParameters(command=binary or sys.executable,args=args,env=env)
            async with stdio_client(params) as (read,write):
                async with ClientSession(read,write) as session:
                    await session.initialize();tools=await session.list_tools()
                    names={tool.name for tool in tools.tools}
                    self.assertIn("canvas_assignments",names);self.assertIn("canvas_change",names)
                    result=await session.call_tool("canvas_status",{})
                    self.assertFalse(result.isError)
                    import json
                    status=json.loads(result.content[0].text)
                    self.assertFalse(status["configured"])
                    denied=await session.call_tool("canvas_get",{"path":"https://other.example/x"})
                    self.assertTrue(denied.isError)
                    self.assertEqual(list(Path(directory).iterdir()),[])


if __name__=="__main__":unittest.main()
