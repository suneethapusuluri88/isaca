import os
import json
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path(__file__).parent / "isaca_data"

MCP_SERVER_INFO = {
    "name": "isaca-info",
    "version": "1.0.0",
}

TOOLS = [
    {
        "name": "about_isaca",
        "description": "Returns detailed information about ISACA — who they are, what they do, their certifications, membership, and mission.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "about_cisa",
        "description": "Returns detailed information about the CISA (Certified Information Systems Auditor) certification — exam details, eligibility, syllabus, and benefits.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_cobit_data",
        "description": "Returns detailed information about COBIT (Control Objectives for Information and Related Technologies) — the ISACA framework for governance and management of enterprise IT, including COBIT 2019, core components, governance vs. management, and key objectives.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


def read_data_file(filename: str) -> str:
    path = DATA_DIR / filename
    if not path.exists():
        return f"Error: {filename} not found."
    return path.read_text(encoding="utf-8")


def run_tool(name: str) -> dict:
    if name == "about_isaca":
        text = read_data_file("about_isaca.txt")
    elif name == "about_cisa":
        text = read_data_file("about_cisa.txt")
    elif name == "get_cobit_data":
        text = read_data_file("Cobit.txt")
    else:
        return None
    return {"type": "text", "text": text}


# SSE endpoint — Claude calls GET to discover tools
@app.get("/sse")
async def mcp_sse_handler(request: Request):
    async def event_stream():
        def send(data: dict) -> str:
            return f"data: {json.dumps(data)}\n\n"

        yield send({
            "jsonrpc": "2.0",
            "method": "initialize",
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": MCP_SERVER_INFO,
                "capabilities": {"tools": {}},
            },
        })

        yield send({
            "jsonrpc": "2.0",
            "method": "tools/list",
            "result": {"tools": TOOLS},
        })

        # Keep connection alive until client disconnects
        while not await request.is_disconnected():
            await asyncio.sleep(15)
            yield ": ping\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
    )


# POST endpoint — Claude calls this with tool name + arguments
@app.post("/")
async def mcp_tool_call_handler(request: Request):
    body = await request.json()
    method = body.get("method")
    params = body.get("params", {})
    req_id = body.get("id")

    if method == "initialize":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": MCP_SERVER_INFO,
                "capabilities": {"tools": {}},
            },
        })

    if method == "tools/list":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS},
        })

    if method == "tools/call":
        name = params.get("name")
        result = run_tool(name)

        if result is None:
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Tool '{name}' not found"},
            })

        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"content": [result]},
        })

    return JSONResponse({
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method '{method}' not supported"},
    })
