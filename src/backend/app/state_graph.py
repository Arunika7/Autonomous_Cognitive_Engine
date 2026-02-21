
from typing import Literal

from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableLambda

from backend.app.utils import AgentState
from backend.app.tools import ToolExecutor
from backend.app.sub_agents import SUB_AGENTS
from backend.app.reasoning import (
    reasoning_node,
    _execute_tool_action,
    _execute_delegation
)


# ──────────────────────────────────────────────────────────────────────────────
# Tool execution node (handles both direct tools and delegation)
# ──────────────────────────────────────────────────────────────────────────────
def tools_node(state: AgentState) -> AgentState:
    """Execute the action decided by the reasoning node"""
    print("→ Entering tools_node")
    print(f"  Pending todos before: {len([t for t in state.get('todos', []) if not t.get('completed', False)])}")

    messages = state.get("messages", [])
    if not messages:
        state["messages"] = [{"role": "assistant", "content": "No messages to process."}]
        return state

    last_content = messages[-1].content if messages else ""

    try:
        import json, re
        # Try to find JSON block (common LLM output patterns)
        decision_match = re.search(r'\{[\s\S]*\}', last_content, re.DOTALL)
        if not decision_match:
            raise ValueError("No JSON decision found in last message")
        
        decision = json.loads(decision_match.group(0))
    except Exception as e:
        print(f"  Decision parsing failed: {e}")
        state["messages"].append({"role": "assistant", "content": f"Error parsing decision: {str(e)}"})
        return state

    action = decision.get("action", "respond")

    print(f"  Decided action: {action}")

    if action == "tool":
        _execute_tool_action(state, decision)
    elif action == "delegate":
        # Get user request from previous message
        user_request = messages[-2].content if len(messages) >= 2 else "No previous user message"
        _execute_delegation(state, decision, user_request)
    else:
        # Simple response fallback
        response_text = decision.get("response", "I'm not sure what to do next.")
        state["messages"].append({"role": "assistant", "content": response_text})

    print(f"  Pending todos after: {len([t for t in state.get('todos', []) if not t.get('completed', False)])}")
    return state


def should_continue(state: AgentState) -> str:
    pending = len([t for t in state.get("todos", []) if not t.get("completed", False)])
    
    last_content = ""
    if state.get("messages"):
        last_content = state["messages"][-1].content.lower()

    print(f"should_continue → pending: {pending}, last msg: '{last_content[:50]}...'")

    # Keep looping while there are pending tasks
    if pending > 0:
        print("  → CONTINUE (still pending tasks)")
        return "reasoning"

    # Only stop if no tasks OR explicit final phrase
    if any(word in last_content for word in ["final answer", "done", "finished", "complete", "all done"]):
        print("  → STOP (final phrase detected)")
        return END

    print("  → STOP (no pending tasks)")
    return END


# ──────────────────────────────────────────────────────────────────────────────
# Build the graph
# ──────────────────────────────────────────────────────────────────────────────
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("reasoning", RunnableLambda(reasoning_node))
workflow.add_node("tools", RunnableLambda(tools_node))

# Set entry point
workflow.set_entry_point("reasoning")

# Always go from reasoning → tools
workflow.add_edge("reasoning", "tools")

# Conditional edge from tools → reasoning or END
workflow.add_conditional_edges(
    "tools",
    should_continue,
    {
        "reasoning": "reasoning",
        END: END
    }
)

# Compile the graph
agent = workflow.compile(checkpointer=None)  

print("LangGraph workflow compiled successfully")