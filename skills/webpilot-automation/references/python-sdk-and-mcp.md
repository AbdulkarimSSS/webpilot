# Programmatic Python SDK & FastMCP Integration

Reference for programmatic Python development and MCP server deployment with WebPilot.

---

## 1. Programmatic Python SDK for AI Agents (`import webpilot`)

AI agents and automated Python pipelines can control WebPilot programmatically with persistent supervisor sessions and native verification:

```python
from webpilot import WebPilot

# 1. Initialize client (auto-connects or auto-spawns background supervisor daemon)
wp = WebPilot()

# 2. Inspect page schema
schema = wp.inspect("https://example.com/apply")

# 3. Fill fields with 0.0% false success physical verification
result = wp.apply(
    url="https://example.com/apply",
    fields={
        "first_name": "Alice",
        "last_name": "Nakamura",
        "email": "alice@example.com",
        "authorized": "Yes"
    },
    press="Submit Application"
)

# result.success is True only when all fields physically match in the DOM
print(f"Confirmed fields: {result.confirmed_fields}")

# 4. Probe element options or attributes
probe = wp.find("country", options=True)
print("Options:", probe.output_lines)

# 5. Multi-Tab Control
tabs = wp.list_tabs()
wp.switch_tab(0)
```

---

## 2. Low-Level Architecture & Integration Patterns

### Method 1: Client RPC to Background Master Supervisor (Recommended)
Connects to the persistent background daemon via high-speed HTTP RPC:

```python
from supervisor.client import SupervisorClient

client = SupervisorClient(base_url="http://127.0.0.1:9333")
response = client.apply_form(
    url="https://example.com/portal",
    fill_arguments=["username=user@example.com", "password=@env:PASS"],
    press_buttons=["Login"],
    submit=True
)
print("Confirmed:", response.confirmed_fields)
print("Failed:", response.failed_fields)
```

### Method 2: Direct In-Process FlowOrchestrator (Standalone / CI/CD)
Runs directly in-process without any daemon, ideal for isolated testing containers:

```python
from webpilot import FlowOrchestrator

orchestrator = FlowOrchestrator(headed=False)
result = orchestrator.execute(
    url="https://example.com/apply",
    fill_arguments=["name=John", "email=john@example.com"],
    press_buttons=["Next"],
    submit=False
)
```

---

## 3. WebPilot MCP Server Integration (`webpilot-mcp`)

WebPilot exposes a standard Model Context Protocol (MCP) server for Claude Desktop, Antigravity, OpenCode, and other AI harnesses:

```json
{
  "mcpServers": {
    "webpilot": {
      "command": "webpilot-mcp",
      "args": []
    }
  }
}
```

### Exposed MCP Tools:
- `inspect_page`: Introspect active or new web page schemas.
- `apply_form`: Populate fields, upload files, and click buttons.
- `probe_element`: Deeply probe element attributes, options, or HTML.
- `manage_service`: Inspect status, restart worker, or stop supervisor.
- `manage_tabs`: List, switch, and close browser tabs.
