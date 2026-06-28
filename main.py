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
    {
        "name": "get_data_certification_exam_prep",
        "description": "Returns CISA exam preparation resources including official study materials, exam domain breakdowns, study tips, exam format, and CPE requirements.",
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


# Audit-checklist data lives alongside the other tool data under isaca_data/.
_AUDIT_DATA = json.loads(read_data_file("audit_checklists.json"))

# Educational disclaimer attached to every checklist response.
CHECKLIST_DISCLAIMER = _AUDIT_DATA["disclaimer"]

# Keyword/alias -> canonical domain. Used for fuzzy (non-exact) matching.
DOMAIN_ALIASES = _AUDIT_DATA["aliases"]

# Ordered audit steps per domain (plus the "general" fallback).
AUDIT_CHECKLISTS = _AUDIT_DATA["checklists"]


def match_domain(domain: str) -> tuple:
    """Normalize the input and match it to a known domain via keyword/alias
    matching. Returns (canonical_domain, matched) where matched is False when
    the general fallback is used."""
    normalized = " ".join(domain.lower().split())
    for canonical, aliases in DOMAIN_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                return canonical, True
    return "general", False


def generate_audit_checklist(arguments: dict) -> dict:
    """Build the structured audit-checklist response for a control domain."""
    domain = arguments.get("domain")
    if not isinstance(domain, str) or not domain.strip():
        return {
            "type": "text",
            "text": json.dumps({
                "error": "Invalid input: 'domain' must be a non-empty string, "
                         "e.g. \"cloud security\" or \"access management\".",
            }, indent=2),
        }

    canonical, matched = match_domain(domain)
    payload = {
        "domain": canonical,
        "requested_domain": domain.strip(),
        "matched": matched,
        "steps": AUDIT_CHECKLISTS[canonical],
        "note": CHECKLIST_DISCLAIMER,
    }
    return {"type": "text", "text": json.dumps(payload, indent=2)}


def run_tool(name: str, arguments: dict = None) -> dict:
    arguments = arguments or {}
    if name == "about_isaca":
        text = read_data_file("about_isaca.txt")
    elif name == "about_cisa":
        text = read_data_file("about_cisa.txt")
    elif name == "get_cobit_data":
        text = read_data_file("Cobit.txt")
    elif name == "get_data_certification_exam_prep":
        text = read_data_file("exam_prep.txt")
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
        arguments = params.get("arguments", {})
        result = run_tool(name, arguments)

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
