import re
import json
from langgraph.graph import StateGraph, END
from .utils import AgentState
from .tools import ToolExecutor
from .sub_agents import SUB_AGENTS

def extract_json(text: str) -> dict:
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return {"thinking": "No JSON", "tool_calls": []}
    try:
        return json.loads(match.group(0))
    except:
        return {"thinking": "Bad JSON", "tool_calls": []}

def normalize_tool_params(tool_name: str, params: dict) -> dict:
    mapping = {
        "create_todo": {
            "title": params.get("title") or params.get("task"),
            "description": params.get("description", ""),
            "priority": params.get("priority", "medium"),
            "due_date": params.get("due_date")
        },
        "create_multiple_todos": {
            "todos_list": params.get("todos_list") or params.get("todos") or params.get("tasks") or []
        },
        "complete_todo": {
            "title_match": params.get("title") or params.get("task") or params.get("todo"),
            "todo_id": params.get("todo_id")
        },
        "update_todo": {
            "title_match": params.get("title"),
            "todo_id": params.get("todo_id"),
            "updates": params.get("updates", {})
        }
    }
    return mapping.get(tool_name, params)

def reasoning_node(state: AgentState) -> dict:
    raw_response = "..."  
    plan = extract_json(raw_response)

    state["context"]["last_thinking"] = plan.get("thinking", "")

    tool_results = []

    for call in plan.get("tool_calls", []):
        tool_name = call.get("tool")
        raw_params = call.get("parameters", {})

        # === REAL DELEGATION (orchestration) ===
        if tool_name == "delegate_task":
            agent_name = raw_params.get("agent_name")
            task = raw_params.get("task")

            if not agent_name or agent_name not in SUB_AGENTS:
                tool_results.append({"success": False, "summary": f"Unknown agent: {agent_name}"})
                continue

            try:
                sub_agent = SUB_AGENTS[agent_name]["agent"]
                result = sub_agent.invoke({"messages": [{"role": "user", "content": task}]})
                content = result["messages"][-1].content
                state["context"]["last_delegated_result"] = {"agent": agent_name, "result": content}
                tool_results.append({"success": True, "result": content, "summary": f"Research complete via {agent_name}"})
            except Exception as e:
                tool_results.append({"success": False, "summary": f"Delegation failed: {e}"})
            continue

        # === NORMAL TOOLS ===
        if hasattr(ToolExecutor, tool_name):
            clean_params = normalize_tool_params(tool_name, raw_params)
            try:
                result = getattr(ToolExecutor, tool_name)(state, **clean_params)
                tool_results.append(result)
            except Exception as e:
                tool_results.append({"success": False, "summary": f"Error: {e}"})
        else:
            tool_results.append({"success": False, "summary": f"Unknown tool: {tool_name}"})

    state["messages"].append({"role": "assistant", "content": f"Executed {len(tool_results)} actions"})
    return {"messages": state["messages"], "context": state["context"], "tool_results": tool_results}