
import json
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Literal, TypedDict

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
from langsmith import traceable

from backend.app.utils import AgentState
from backend.app.tools import ToolExecutor
from backend.app.sub_agents import SUB_AGENTS
from backend.app.reasoning import robust_parse_json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[3]

possible_env_paths = [
    BASE_DIR / ".env",
    Path.cwd() / ".env",
    Path(__file__).parent.parent.parent / ".env",
    Path(__file__).parent / ".env",
]

env_loaded = False
for env_path in possible_env_paths:
    if env_path.is_file():
        load_dotenv(env_path)
        env_loaded = True
        logger.info(f"Loaded .env from: {env_path}")
        break

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found")

# Configuration
MAX_HISTORY = 8
MAX_ITERATIONS = 12
CURRENT_DATE = datetime.now().strftime("%Y-%m-%d")

llm = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0,
    max_tokens=300,
    api_key=GROQ_API_KEY
)

class Decision(BaseModel):
    action: str
    reasoning: str = Field(default="no reasoning")
    tool_name: str | None = None
    tool_params: dict | None = None
    agent_name: str | None = None
    response: str | None = None

class EnhancedAgentState(TypedDict):
    messages: list[BaseMessage]
    todos: list[dict]
    last_decision: dict
    files: dict[str, str]
    calendar_events: list[dict]
    research_insights: list[dict]
    iteration_count: int
    metrics: dict
    planning_done: bool
    execution_log: list[dict]
    sub_agent_outputs: dict 

# Simple prompt with all variables properly defined
SYSTEM_PROMPT = """You coordinate tasks. Respond ONLY with valid JSON.

Status: Iteration {iteration_count}/{max_iterations} | Todos: {pending_count} pending, {completed_count} done | Planning: {planning_status}

RULES:
1. For SIMPLE single-action tasks (schedule meeting, save file, create 1 todo):
   - Use tool directly: {{"action": "tool", "tool_name": "create_calendar_event", "tool_params": {{"title": "Meeting", "date": "2026-01-20", "time": "14:00"}}, "reasoning": "scheduling meeting"}}
   - Then respond: {{"action": "respond", "response": "Meeting scheduled for...", "reasoning": "task complete"}}

2. For COMPLEX multi-step tasks (research, analysis, reports):
   - Delegate to planning ONCE: {{"action": "delegate", "agent_name": "planning", "reasoning": "need breakdown"}}
   - Then work through todos created

3. If todos exist AND pending > 0:
   - Complete next todo: {{"action": "tool", "tool_name": "complete_todo", "tool_params": {{"todo_id": 0}}, "reasoning": "completing todo"}}

Available tools: create_calendar_event, save_file, read_file, list_files, complete_todo, list_calendar_events
Available agents: planning, web_search, summarizer, analyzer, report_generator

Output JSON only, no markdown."""

decision_prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "{user_input}")
])


@traceable(name="Supervisor_Decision", run_type="chain")
def reasoning_node(state: EnhancedAgentState) -> dict:
    messages = state.get("messages", [])
    iteration_count = state.get("iteration_count", 0)
    planning_done = state.get("planning_done", False)
    
    logger.info(f"=== ITERATION {iteration_count} ===")
    
    if iteration_count >= MAX_ITERATIONS:
        logger.warning("Max iterations reached")
        return {
            "messages": messages + [AIMessage(content=json.dumps({
                "action": "respond",
                "response": "Task execution limit reached. Progress saved.",
                "reasoning": "max iterations"
            }))],
            "last_decision": {"action": "respond", "response": "Limit reached", "reasoning": "max"},
            "iteration_count": iteration_count + 1
        }
    
    last_input = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_input = msg.content
            break
    
    todos = state.get("todos", [])
    pending = [t for t in todos if not t.get("completed", False)]
    completed = [t for t in todos if t.get("completed", False)]
    
    # ===== UPDATED: Include sub-agent outputs in final response =====
    if todos and not pending and planning_done:
        logger.info("All todos complete - generating final summary with sub-agent outputs")
        
        calendar_events = state.get("calendar_events", [])
        files = state.get("files", {})
        research_insights = state.get("research_insights", [])
        sub_agent_outputs = state.get("sub_agent_outputs", {})
        execution_log = state.get("execution_log", [])
        
        # Build comprehensive response including sub-agent outputs
        response_parts = []
        
        # ===== Include outputs from web_search, analyzer, etc. =====
        if sub_agent_outputs:
            response_parts.append("=" * 70)
            response_parts.append("RESEARCH & ANALYSIS RESULTS")
            response_parts.append("=" * 70 + "\n")
            
            for agent_name, output in sub_agent_outputs.items():
                agent_title = agent_name.replace("_", " ").title()
                response_parts.append(f"\n### {agent_title} Output:\n")
                
                # Show substantial content
                if len(output) > 5000:
                    response_parts.append(output[:5000] + f"\n\n... (truncated - showing first 5000 of {len(output)} characters)")
                else:
                    response_parts.append(output)
                
                response_parts.append("\n" + "-" * 70 + "\n")
        
        # Research insights
        if research_insights:
            response_parts.append("\nKEY RESEARCH INSIGHTS:\n")
            for idx, insight in enumerate(research_insights[:15], 1):
                insight_text = insight.get("insight", insight.get("summary", ""))
                if insight_text:
                    response_parts.append(f"{idx}. {insight_text}")
        
        # Files generated
        if files:
            response_parts.append(f"\nGENERATED {len(files)} FILE(S):")
            for filename, content in files.items():
                response_parts.append(f"  - {filename}")
                # Show preview of file content
                if content and len(content) > 100:
                    preview = content[:300].replace('\n', ' ')
                    response_parts.append(f"    Preview: {preview}...")
        
        # Calendar events
        if calendar_events:
            response_parts.append(f"\nSCHEDULED {len(calendar_events)} EVENT(S):")
            for event in calendar_events:
                response_parts.append(f"  - {event.get('title')} on {event.get('date')} at {event.get('time')}")
        
        # Task completion summary
        response_parts.append(f"\nCOMPLETED {len(completed)} TASK(S) SUCCESSFULLY")
        
        final_response = "\n".join(response_parts) if response_parts else "All tasks completed successfully."
        
        decision = {
            "action": "respond",
            "response": final_response,
            "reasoning": "all todos complete - final summary with sub-agent outputs"
        }
        
        return {
            "messages": messages + [AIMessage(content=json.dumps(decision))],
            "last_decision": decision,
            "iteration_count": iteration_count + 1,
            "execution_log": execution_log
        }
    
    # Check if we just executed a tool and should respond (simple tasks)
    last_decision = state.get("last_decision", {})
    if last_decision.get("action") == "tool" and not todos:
        logger.info("Tool executed, generating response")
        calendar_events = state.get("calendar_events", [])
        files = state.get("files", {})
        
        if calendar_events:
            last_event = calendar_events[-1]
            response_text = f"Meeting '{last_event.get('title', 'Event')}' scheduled for {last_event.get('date', 'the specified date')} at {last_event.get('time', 'the specified time')}."
        elif files:
            last_file = list(files.keys())[-1]
            response_text = f"File '{last_file}' saved successfully."
        else:
            response_text = "Task completed successfully."
        
        decision = {
            "action": "respond",
            "response": response_text,
            "reasoning": "task complete"
        }
        
        execution_log = state.get("execution_log", [])
        log_entry = {
            "iteration": iteration_count,
            "action": "respond",
            "details": "auto-response after tool",
            "reasoning": "Generated automatic response after tool execution"
        }
        execution_log.append(log_entry)
        
        return {
            "messages": messages + [AIMessage(content=json.dumps(decision))],
            "last_decision": decision,
            "iteration_count": iteration_count + 1,
            "execution_log": execution_log
        }
    
    try:
        llm_response = (decision_prompt | llm).invoke({
            "user_input": last_input,
            "iteration_count": iteration_count,
            "max_iterations": MAX_ITERATIONS,
            "pending_count": len(pending),
            "completed_count": len(completed),
            "planning_status": "DONE" if planning_done else "NOT YET"
        })
        
        parsed = robust_parse_json(llm_response.content)
        
        if parsed.get("action") in ["planning", "web_search", "analyzer"]:
            parsed["agent_name"] = parsed["action"]
            parsed["action"] = "delegate"
        elif parsed.get("action") in ["complete_todo", "save_file"]:
            parsed["tool_name"] = parsed["action"]
            parsed["action"] = "tool"
        
        if parsed.get("action") == "delegate" and parsed.get("agent_name") == "planning":
            if planning_done:
                logger.warning("Preventing duplicate planning")
                if pending:
                    parsed = {
                        "action": "tool",
                        "tool_name": "complete_todo",
                        "tool_params": {"todo_id": 0},
                        "reasoning": "working on pending todo instead of re-planning"
                    }
                else:
                    parsed = {
                        "action": "respond",
                        "response": "Planning already complete. Ready for next steps.",
                        "reasoning": "planning already done"
                    }
        
        decision = Decision(**parsed).dict()
        logger.info(f"Decision: {decision['action']} - {decision.get('reasoning', '')[:50]}")
        
        execution_log = state.get("execution_log", [])
        log_entry = {
            "iteration": iteration_count,
            "action": decision['action'],
            "details": decision.get('tool_name') or decision.get('agent_name') or 'response',
            "reasoning": decision.get('reasoning', '')[:100]
        }
        execution_log.append(log_entry)
        
    except Exception as e:
        logger.error(f"LLM error: {str(e)[:100]}")
        execution_log = state.get("execution_log", [])
        
        if pending:
            decision = {
                "action": "tool",
                "tool_name": "complete_todo",
                "tool_params": {"todo_id": 0},
                "reasoning": "fallback - completing todo"
            }
        else:
            decision = {
                "action": "respond",
                "response": "Task processed. Please check results.",
                "reasoning": "fallback"
            }
        
        log_entry = {
            "iteration": iteration_count,
            "action": "error_fallback",
            "details": str(e)[:100],
            "reasoning": "LLM error - using fallback"
        }
        execution_log.append(log_entry)
    
    return {
        "messages": messages + [AIMessage(content=json.dumps(decision))],
        "last_decision": decision,
        "iteration_count": iteration_count + 1,
        "execution_log": execution_log
    }


def should_continue(state: EnhancedAgentState) -> Literal["reasoning", "__end__"]:
    iteration_count = state.get("iteration_count", 0)
    last_decision = state.get("last_decision", {})
    
    # Hard stop at max iterations
    if iteration_count >= MAX_ITERATIONS:
        logger.info("Max iterations reached")
        return "__end__"
    
    # If last action was respond, we're done
    if last_decision.get("action") == "respond":
        logger.info("Response action detected, ending")
        return "__end__"
    
    todos = state.get("todos", [])
    pending = [t for t in todos if not t.get("completed", False)]
    planning_done = state.get("planning_done", False)
    
    # ===== UPDATED: Ensure we generate final response before ending =====
    if planning_done and todos and not pending:
        logger.info(f"All {len(todos)} todos complete - checking for final response")
        
        # Check if we already have a final response
        messages = state.get("messages", [])
        has_final_response = False
        
        for msg in reversed(messages[-3:]):  # Check last 3 messages
            if isinstance(msg, AIMessage):
                try:
                    content = json.loads(msg.content) if isinstance(msg.content, str) and msg.content.startswith('{') else {}
                    if content.get("action") == "respond" and content.get("reasoning") == "all todos complete - final summary":
                        has_final_response = True
                        logger.info("Final summary already generated")
                        break
                except:
                    pass
        
        if has_final_response:
            return "__end__"
        else:
            logger.info("Need to generate final summary - continuing to reasoning")
            return "reasoning"
    
    # Check what artifacts were created (calendar events, files, etc)
    calendar_events = state.get("calendar_events", [])
    files = state.get("files", {})
    
    # If we just executed a tool that created something, continue to respond
    if last_decision.get("action") == "tool" and not todos:
        logger.info(f"Simple tool executed, continuing to respond")
        return "reasoning"
    
    # If planning not done and no todos, continue to plan
    if not todos and not planning_done:
        logger.info("No todos and planning not done, continuing to plan")
        return "reasoning"
    
    # If todos exist and some are pending, continue working
    if pending:
        logger.info(f"{len(pending)} todos pending, continuing")
        return "reasoning"
    
    # Default: end
    logger.info("Default: ending")
    return "__end__"



def extract_final_response(agent_result: dict) -> str:
    """
    Extract the user-facing response from agent execution.
    Now includes sub-agent outputs!
    """
    messages = agent_result.get("messages", [])
    
    # Look for the last "respond" action
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            try:
                content = msg.content
                if isinstance(content, str) and content.startswith('{'):
                    content_dict = json.loads(content)
                    
                    if content_dict.get("action") == "respond":
                        response_text = content_dict.get("response", "")
                        if response_text:
                            return response_text
            except:
                continue
    
    # Fallback: build from state including sub-agent outputs
    logger.warning("No explicit response found, building from state")
    
    todos = agent_result.get("todos", [])
    completed = [t for t in todos if t.get("completed", False)]
    files = agent_result.get("files", {})
    calendar_events = agent_result.get("calendar_events", [])
    research_insights = agent_result.get("research_insights", [])
    sub_agent_outputs = agent_result.get("sub_agent_outputs", {})
    
    parts = []
    
    # Include sub-agent outputs
    if sub_agent_outputs:
        parts.append("=" * 70)
        parts.append("RESEARCH & ANALYSIS RESULTS")
        parts.append("=" * 70)
        for agent_name, output in sub_agent_outputs.items():
            agent_title = agent_name.replace("_", " ").title()
            parts.append(f"\n### {agent_title}:")
            if len(output) > 3000:
                parts.append(output[:3000] + f"\n... (truncated, {len(output)} total chars)")
            else:
                parts.append(output)
            parts.append("-" * 70)
    
    if research_insights:
        parts.append(f"\nFound {len(research_insights)} research insights")
    if files:
        parts.append(f"Generated {len(files)} file(s): {', '.join(files.keys())}")
    if calendar_events:
        parts.append(f"Scheduled {len(calendar_events)} event(s)")
    if completed:
        parts.append(f"Completed {len(completed)} tasks")
    
    return "\n".join(parts) if parts else "Task completed successfully"

@traceable(name="Tool_Execution", run_type="tool")
def tool_node(state: EnhancedAgentState) -> dict:
    decision = state.get("last_decision", {})
    if decision.get("action") != "tool":
        return state
    
    tool_name = decision.get("tool_name")
    params = decision.get("tool_params", {})
    
    logger.info(f"Tool: {tool_name}({params})")
    
    if not hasattr(ToolExecutor, tool_name):
        return {"messages": state["messages"] + [AIMessage(content=f"Unknown tool: {tool_name}")]}
    
    try:
        result = getattr(ToolExecutor, tool_name)(state, **params)
        updated_state = dict(state)
        
        if "files" in result:
            updated_state["files"] = {**state.get("files", {}), **result["files"]}
        if "calendar_events" in result:
            updated_state["calendar_events"] = state.get("calendar_events", []) + result.get("calendar_events", [])
        if "todos" in result:
            updated_state["todos"] = result["todos"]
        
        summary = result.get("summary", str(result)[:200])
        logger.info(f"Tool success: {summary[:60]}")
        
        updated_state["messages"] = state["messages"] + [AIMessage(content=f"Tool: {summary}")]
        return updated_state
        
    except Exception as e:
        logger.error(f"Tool error: {e}")
        return {"messages": state["messages"] + [AIMessage(content=f"Tool error: {str(e)}")]}

@traceable(name="Delegate_To_SubAgent", run_type="chain")
def delegate_node(state: EnhancedAgentState) -> dict:
    decision = state.get("last_decision", {})
    if decision.get("action") != "delegate":
        return state
    
    agent_name = decision.get("agent_name", "").lower()
    logger.info(f"Delegating to: {agent_name}")
    
    if agent_name not in SUB_AGENTS:
        return {"messages": state["messages"] + [AIMessage(content=f"Unknown agent: {agent_name}")]}
    
    sub_agent = SUB_AGENTS[agent_name]["agent"]
    
    user_content = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            user_content = msg.content
            break
    
    try:
        result = sub_agent.invoke({
            "messages": [HumanMessage(content=user_content)],
            "state": state
        })
        
        updated_state = dict(state)
        
        # Mark planning as done
        if agent_name == "planning":
            updated_state["planning_done"] = True
            logger.info("Planning marked as DONE")
        
        # ===== NEW: Capture sub-agent outputs =====
        sub_agent_output = None
        
        if isinstance(result, dict):
            if "state" in result:
                updated_state.update(result["state"])
            
            # Extract the actual output/response from sub-agent
            if "output" in result:
                sub_agent_output = result["output"]
            elif "response" in result:
                sub_agent_output = result["response"]
            elif "content" in result:
                sub_agent_output = result["content"]
            
            if "messages" in result:
                for msg in result["messages"]:
                    if isinstance(msg, dict):
                        content = msg.get("content", "")
                        updated_state["messages"].append(AIMessage(content=content))
                        # Capture content from messages if we don't have output yet
                        if not sub_agent_output and content and len(content) > 50:
                            sub_agent_output = content
                    elif hasattr(msg, "content"):
                        updated_state["messages"].append(msg)
                        if not sub_agent_output and msg.content and len(msg.content) > 50:
                            sub_agent_output = msg.content
        
        # ===== NEW: Store sub-agent outputs in a dedicated field =====
        if "sub_agent_outputs" not in updated_state:
            updated_state["sub_agent_outputs"] = {}
        
        if sub_agent_output:
            updated_state["sub_agent_outputs"][agent_name] = sub_agent_output
            logger.info(f"Captured output from {agent_name}: {len(sub_agent_output)} chars")
        else:
            logger.warning(f"No output captured from {agent_name}")
        
        logger.info(f"Sub-agent {agent_name} complete")
        return updated_state
        
    except Exception as e:
        logger.error(f"Sub-agent error: {e}")
        return {"messages": state["messages"] + [AIMessage(content=f"Agent error: {str(e)}")]}


def log_todos_node(state: EnhancedAgentState) -> dict:
    todos = state.get("todos", [])
    pending = [t for t in todos if not t.get("completed", False)]
    completed = [t for t in todos if t.get("completed", False)]
    
    logger.info(f"[TODOS] {len(pending)} pending, {len(completed)} done")
    
    metrics = state.get("metrics", {})
    metrics["todos_pending"] = len(pending)
    metrics["todos_completed"] = len(completed)
    
    return {**state, "metrics": metrics}

def route_decision(state: EnhancedAgentState) -> Literal["tools", "delegate", "__end__"]:
    decision = state.get("last_decision", {})
    action = decision.get("action", "respond")
    
    if action == "tool":
        return "tools"
    elif action == "delegate":
        return "delegate"
    else:
        return "__end__"


# Build graph
workflow = StateGraph(EnhancedAgentState)

workflow.add_node("reasoning", RunnableLambda(reasoning_node))
workflow.add_node("tools", RunnableLambda(tool_node))
workflow.add_node("delegate", RunnableLambda(delegate_node))
workflow.add_node("log_todos", RunnableLambda(log_todos_node))

workflow.set_entry_point("reasoning")

workflow.add_conditional_edges(
    "reasoning",
    route_decision,
    {
        "tools": "tools",
        "delegate": "delegate",
        "__end__": END
    }
)

workflow.add_edge("tools", "log_todos")
workflow.add_edge("delegate", "log_todos")

workflow.add_conditional_edges(
    "log_todos",
    should_continue,
    {
        "reasoning": "reasoning",
        "__end__": END
    }
)

agent = workflow.compile()

logger.info(f"Agent compiled successfully - MAX_ITERATIONS={MAX_ITERATIONS}, model=llama-3.1-8b-instant")