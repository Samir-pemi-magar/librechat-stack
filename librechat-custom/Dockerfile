FROM ghcr.io/danny-avila/librechat:latest

COPY librechat-custom/tools/InternalData.js /app/api/app/clients/tools/structured/InternalData.js
COPY librechat-custom/tools/WorkbookAnalysis.js /app/api/app/clients/tools/structured/WorkbookAnalysis.js

RUN python3 - <<'PY'
from pathlib import Path
import json

# ---------------------------------------------------------
# 1. Register InternalData in tools/index.js
# ---------------------------------------------------------
path = Path("/app/api/app/clients/tools/index.js")
text = path.read_text()

if "const WorkbookAnalysis = require('./structured/WorkbookAnalysis');" not in text:
    text = text.replace(
        "const OpenWeather = require('./structured/OpenWeather');",
        "const OpenWeather = require('./structured/OpenWeather');\n"
        "const InternalData = require('./structured/InternalData');\n"
        "const WorkbookAnalysis = require('./structured/WorkbookAnalysis');"
    )

if "  InternalData," not in text:
    text = text.replace(
        "  OpenWeather,\n",
        "  OpenWeather,\n  InternalData,\n  WorkbookAnalysis,\n"
    )

path.write_text(text)


# ---------------------------------------------------------
# 2. Add InternalData to the tool manifest
# ---------------------------------------------------------
path = Path("/app/api/app/clients/tools/manifest.json")
manifest = json.loads(path.read_text())

if not any(t.get("pluginKey") == "internal_data" for t in manifest):
    manifest.append({
        "name": "Prarambha Internal Data",
        "pluginKey": "internal_data",
        "description": "Retrieve information from Prarambha's local internal data source.",
        "icon": "",
        "authConfig": []
    })

if not any(t.get("pluginKey") == "workbook_analysis" for t in manifest):
    manifest.append({
        "name": "Workbook Analysis",
        "pluginKey": "workbook_analysis",
        "description": "Analyze company Excel workbooks using the internal Python analysis service.",
        "icon": "",
        "authConfig": []
    })

path.write_text(json.dumps(manifest, indent=2) + "\n")


# ---------------------------------------------------------
# 3. Register InternalData in handleTools.js
# ---------------------------------------------------------
path = Path("/app/api/app/clients/tools/util/handleTools.js")
text = path.read_text()

if "  InternalData," not in text:
    text = text.replace(
        "  OpenWeather,\n",
        "  OpenWeather,\n  InternalData,\n  WorkbookAnalysis,\n",
        1
    )

if "    workbook_analysis: WorkbookAnalysis," not in text:
    text = text.replace(
        "    tavily_search_results_json: TavilySearchResults,\n",
        "    tavily_search_results_json: TavilySearchResults,\n"
        "    internal_data: InternalData,\n"
        "    workbook_analysis: WorkbookAnalysis,\n"
    )

# Remove any old global injection.
text = text.replace(
    "  tools = [...new Set([...tools, 'internal_data'])];\n\n",
    ""
)

path.write_text(text)


# ---------------------------------------------------------
# 4. Automatically add internal_data to Agent tools
# ---------------------------------------------------------
path = Path("/app/api/server/services/ToolService.js")
text = path.read_text()

needle = """async function loadAgentTools({
  req,
  res,
  agent,
  signal,
  tool_resources,
  openAIApiKey,
  streamId = null,
  definitionsOnly = true,
}) {
"""

replacement = needle + """  // Prarambha: make the internal data tool available
  // without requiring clients to configure an Agent manually.
  if (agent && Array.isArray(agent.tools)) {
    agent.tools = [...new Set([...agent.tools, 'internal_data'])];
  }

"""

if "Prarambha: make the internal data tool available" not in text:
    if needle not in text:
        raise SystemExit("Could not find loadAgentTools function signature")
    text = text.replace(needle, replacement, 1)


# ---------------------------------------------------------
# 5. Automatically add internal_data to tool definitions
# ---------------------------------------------------------
needle = """async function loadToolDefinitionsWrapper({ req, res, agent, streamId = null, tool_resources }) {
"""

replacement = needle + """  // Prarambha: make the internal data tool visible to the model
  // without requiring clients to configure an Agent manually.
  if (agent && Array.isArray(agent.tools)) {
    agent.tools = [...new Set([...agent.tools, 'internal_data'])];
  }

"""

if "Prarambha: make the internal data tool visible to the model" not in text:
    if needle not in text:
        raise SystemExit("Could not find loadToolDefinitionsWrapper function signature")
    text = text.replace(needle, replacement, 1)


# ---------------------------------------------------------
# 6. Allow internal_data in Agent capability filtering
# ---------------------------------------------------------
old = """    } else if (!areToolsEnabled) {
      return false;
    }
    return true;
"""

new = """    } else if (!areToolsEnabled && tool != 'internal_data') {
      return false;
    }
    return true;
"""

if old in text:
    text = text.replace(old, new, 1)
else:
    raise SystemExit("Could not find Agent tool capability filter")


# ---------------------------------------------------------
# 7. Allow internal_data in tool-definition capability filtering
# ---------------------------------------------------------
old = """    if (!areToolsEnabled) {
      return false;
    }
    return true;
"""

new = """    if (!areToolsEnabled && tool !== 'internal_data') {
      return false;
    }
    return true;
"""

if old in text:
    text = text.replace(old, new, 1)
else:
    raise SystemExit("Could not find tool-definition capability filter")


# ---------------------------------------------------------
# 8. Debug Agent tool list before loading
# ---------------------------------------------------------
path = Path("/app/api/server/services/Endpoints/agents/initialize.js")
text = path.read_text()

needle = """    const agent = { id: agentId, tools, provider, model, tool_options };
"""

replacement = """    const agent = { id: agentId, tools, provider, model, tool_options };
    console.log("[Prarambha DEBUG] Agent tools received:", tools);

"""

if "[Prarambha DEBUG] Agent tools received:" not in text:
    if needle not in text:
        raise SystemExit("Could not find Agent construction line")
    text = text.replace(needle, replacement, 1)

path.write_text(text)

print("Custom LibreChat tool patch applied successfully.")

# ---------------------------------------------------------
# 8.5. Register internal_data in LibreChat's manifest
# ---------------------------------------------------------
manifest = Path("/app/api/app/clients/tools/manifest.json")
data = json.loads(manifest.read_text())

if not any(tool.get("pluginKey") == "internal_data" for tool in data):
    data.append({
        "name": "Internal Data",
        "pluginKey": "internal_data",
        "description": "Retrieve information from Prarambha's local internal data source.",
        "authConfig": []
    })
    manifest.write_text(json.dumps(data, indent=2) + "\n")

# ---------------------------------------------------------
# 8.8. Debug actual tool definitions
# ---------------------------------------------------------
path = Path("/app/api/server/services/ToolService.js")
text = path.read_text()

end_needle = """  );

  for (const serverName of getMCPServerNamesFromTools(filteredTools)) {
"""

debug_replacement = """  );

  // Prarambha: explicitly expose custom internal tools to the Agent model.
  // The normal handleTools constructor path can execute the tools, but the
  // definitions-only Agent path does not reliably discover these custom tools.
  const prarambhaTools = [
    {
      name: "internal_data",
      Class: require("/app/api/app/clients/tools/structured/InternalData"),
    },
    {
      name: "workbook_analysis",
      Class: require("/app/api/app/clients/tools/structured/WorkbookAnalysis"),
    },
  ];

  for (const { name, Class } of prarambhaTools) {
    if (!filteredTools.includes(name)) {
      continue;
    }

    const toolInstance = new Class();

    if (!toolDefinitions.some((t) => t?.name === name)) {
      toolDefinitions.push({
        name,
        description: toolInstance.description,
        schema: toolInstance.schema?.jsonSchema ?? {
          type: "object",
          properties: {},
        },
      });
    }

    toolRegistry ??= {};
    if (!toolRegistry[name]) {
      toolRegistry[name] = toolInstance;
    }
  }

  console.log(
    "[Prarambha DEBUG] ACTUAL TOOL DEFINITIONS:",
    JSON.stringify({
      requestedTools: filteredTools,
      definitionNames: (toolDefinitions || []).map(
        (t) => t?.name || t?.function?.name || "unknown"
      ),
      registryKeys: toolRegistry ? Object.keys(toolRegistry) : [],
      hasDeferredTools,
    })
  );

  for (const serverName of getMCPServerNamesFromTools(filteredTools)) {
"""

if "[Prarambha DEBUG] ACTUAL TOOL DEFINITIONS:" not in text:
    if end_needle not in text:
        raise SystemExit("Could not find tool-definition return point")
    text = text.replace(end_needle, debug_replacement, 1)

path.write_text(text)

# ---------------------------------------------------------
# 9. Automatically add internal_data to the primary Agent
# ---------------------------------------------------------
path = Path("/app/api/server/services/Endpoints/agents/initialize.js")
text = path.read_text()

needle = """  const primaryConfig = await initializeAgent(
"""

replacement = """  // Prarambha: always provide the preconfigured internal tools.
  if (primaryAgent && Array.isArray(primaryAgent.tools)) {
    primaryAgent.tools = [
      ...new Set([
        ...primaryAgent.tools,
        'internal_data',
        'workbook_analysis',
      ]),
    ];
  }

  console.log(
    "[Prarambha DEBUG] primaryAgent before initialize:",
    JSON.stringify(primaryAgent)
  );

""" + needle

if "Prarambha: always provide the preconfigured internal data tool." not in text:
    if needle not in text:
        raise SystemExit("Could not find primary initializeAgent call")
    text = text.replace(needle, replacement, 1)

path.write_text(text)

PY