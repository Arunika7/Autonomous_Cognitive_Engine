from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_groq import ChatGroq
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
import os
import re
import json

from backend.app.tools import ToolExecutor
from .utils import AgentState
from .config import settings

# LLM configuration 
llm = ChatGroq(
    model=settings.sub_agent_model,
    temperature=settings.llm_temperature,
    max_tokens=settings.max_tokens,
    groq_api_key=settings.groq_api_key
)

def create_sub_agent(
    name: str,
    system_prompt: str,
    can_read_state: bool = False,
    can_create_tasks: bool = False,
    can_read_files: bool = False,
    can_search_documents: bool = False
):
    """
    Factory function to create traceable, reusable sub-agents using native tool calling.
    """
    def build_context(input_dict: Dict[str, Any]) -> str:
        messages = input_dict.get("messages", [])
        state: AgentState = input_dict.get("state", {})
        
        user_text = ""
        if messages:
            last_msg = messages[-1]
            if isinstance(last_msg, dict):
                user_text = last_msg.get("content", "")
            else:
                user_text = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
        
        context_parts = []
        if can_read_state and state:
            todos = state.get("todos", [])
            if todos:
                pending = len([t for t in todos if not t.get("completed", False)])
                context_parts.append(f"Current tasks: {len(todos)} total, {pending} pending")
            
            files = state.get("files", {})
            if files:
                context_parts.append(f"Files in memory: {list(files.keys())}")
            
            calendar = state.get("calendar", [])
            if calendar:
                context_parts.append(f"Calendar events: {len(calendar)}")
        
        ctx = "\n".join(context_parts) if context_parts else "No additional state context available."
        return f"{ctx}\n\nUser Request: {user_text}"

    tools = []
    
    if can_create_tasks:
        @tool
        def create_multiple_todos(todos_list: list) -> str:
            """Create new follow-up tasks. Each item must be a dict with: title (str), description (str), priority (high/medium/low)."""
            pass 
        tools.append(create_multiple_todos)
        
    if can_read_files:
        @tool
        def read_file(filename: str) -> str:
            """Read the full content of a file to analyze or summarize it."""
            pass 
        tools.append(read_file)
        
    if can_search_documents:
        @tool
        def semantic_search(query: str) -> str:
            """Search through all historically saved documents to find semantic chunks relevant to a query. Use this for RAG on large datasets."""
            pass
        tools.append(semantic_search)

    if tools:
        llm_with_tools = llm.bind_tools(tools)
    else:
        llm_with_tools = llm

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt + "\n\nYou have access to tools. If you use tools, you MUST wait for the tool observation before giving your final response.\n\nCurrent context:\n{context}"),
        ("human", "Execute the request.") 
    ])

    chain = prompt | llm_with_tools

    def agent_executor(input_dict: Dict[str, Any]) -> Dict[str, Any]:
        state = input_dict.get("state", {})
        context_text = build_context(input_dict)
        
        msg1 = chain.invoke({"context": context_text})
        
        # 2. Process tool calls naturally
        if hasattr(msg1, "tool_calls") and msg1.tool_calls:
            tool_messages = []
            for tc in msg1.tool_calls:
                if tc["name"] == "create_multiple_todos":
                    args = tc["args"].get("todos_list", [])
                    ToolExecutor.create_multiple_todos(state, args)
                    tool_messages.append(ToolMessage("Tasks successfully added to the system state.", tool_call_id=tc["id"]))
                
                elif tc["name"] == "read_file":
                    fname = tc["args"].get("filename", "")
                    res = ToolExecutor.read_file(state, fname)
                    content = res.get("content") or res.get("summary", "File not found.")
                    tool_messages.append(ToolMessage(str(content), tool_call_id=tc["id"]))
                    
                elif tc["name"] == "semantic_search":
                    query = tc["args"].get("query", "")
                    res = ToolExecutor.semantic_search(state, query)
                    tool_messages.append(ToolMessage(res.get("summary", "Search failed."), tool_call_id=tc["id"]))
            
            # 3. Final synthesis
            final_messages = [
                ("system", system_prompt + "\n\nCurrent context:\n" + context_text),
                ("human", "Execute the request."),
                msg1,
                *tool_messages,
                ("human", "Now provide your final concise response/summary based on the tool observations.")
            ]
            final_msg = llm.invoke(final_messages)
            response_text = final_msg.content
        else:
            response_text = msg1.content if hasattr(msg1, "content") else str(msg1)

        return {
            "messages": [{"role": "assistant", "content": response_text}],
            "state": state,
            "output": response_text
        }

    return RunnableLambda(agent_executor).with_config({"run_name": f"SubAgent_{name}"})

# ──────────────────────────────────────────────────────────────────────────────
#                Individual Sub-Agent Definitions
# ──────────────────────────────────────────────────────────────────────────────

planning_agent = create_sub_agent(
    name="planning",
    system_prompt="""You are a strategic planning expert. Your role is to break down complex goals into clear, actionable phases and tasks using the create_multiple_todos tool. Be realistic about dependencies, effort and sequence.""",
    can_read_state=True,
    can_create_tasks=True
)

def create_web_search_agent():
    tool = DuckDuckGoSearchRun()
    llm_with_tools = llm.bind_tools([tool])
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a precise web research assistant.
Provide factual, up-to-date information. You MUST use the duckduckgo_search tool to find recent information before answering.
Structure answers:
- Summary
- Key facts (bullet points)
- Sources / references"""),
        ("human", "{input}"),
    ])
    
    chain = prompt | llm_with_tools
    
    def executor_wrapper(input_dict: Dict[str, Any]) -> Dict[str, Any]:
        messages = input_dict.get("messages", [])
        state = input_dict.get("state", {})
        
        user_text = ""
        if messages:
            last_msg = messages[-1]
            if isinstance(last_msg, dict):
                user_text = last_msg.get("content", "")
            else:
                user_text = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
                
        msg1 = chain.invoke({"input": user_text})
        
        if hasattr(msg1, "tool_calls") and msg1.tool_calls:
            print(f"\\n[WebSearch] Excuting {len(msg1.tool_calls)} DuckDuckGo query(s)...")
            tool_messages = []
            for tool_call in msg1.tool_calls:
                try:
                    tool_result = tool.invoke(tool_call["args"])
                except Exception as e:
                    tool_result = f"Error during search: {e}"
                
                tool_messages.append(ToolMessage(
                    content=str(tool_result),
                    tool_call_id=tool_call["id"]
                ))
            
            final_messages = [
                ("system", "You are a precise web research assistant. Synthesize the tool results into a comprehensive answer."),
                ("human", user_text),
                msg1,
                *tool_messages
            ]
            final_msg = llm.invoke(final_messages)
            response_text = final_msg.content
        else:
            response_text = msg1.content if hasattr(msg1, "content") else str(msg1)
            
        return {
            "messages": [{"role": "assistant", "content": response_text}],
            "state": state,
            "output": response_text
        }
        
    return RunnableLambda(executor_wrapper).with_config({"run_name": "SubAgent_web_search"})

web_search_agent = create_web_search_agent()

summarizer_agent = create_sub_agent(
    name="summarizer",
    system_prompt="""You are an expert summarizer.
Create concise, structured summaries that preserve meaning and key details. If referring to a file, use the read_file tool to ingest its contents first.
Use:
- Main conclusion first
- Hierarchical bullet points
- Highlight important facts/numbers
Keep tone neutral and accurate.""",
    can_read_state=True,
    can_create_tasks=False,
    can_read_files=True
)

analyzer_agent = create_sub_agent(
    name="analyzer",
    system_prompt="""You are a sharp data/patterns analyst.
When given information or state:
- Identify trends and patterns
- Highlight anomalies or risks
- Provide clear, data-driven insights
- Suggest next actions
If you need file context, use the read_file tool to read the file first. To query across large manuals, use semantic_search.""",
    can_read_state=True,
    can_create_tasks=False,
    can_read_files=True,
    can_search_documents=True
)

report_generator_agent = create_sub_agent(
    name="report_generator",
    system_prompt="""You are a professional report writer.
Create well-structured markdown reports including:
- Executive Summary
- Key Findings
- Detailed Analysis
- Recommendations / Next Steps
Use proper headings, bullets, and tables when appropriate. Use the read_file tool to fetch full files or semantic_search to query vectors.""",
    can_read_state=True,
    can_create_tasks=False,
    can_read_files=True,
    can_search_documents=True
)

# Registry for supervisor / router to use
SUB_AGENTS = {
    "planning": {
        "agent": planning_agent,
        "description": "Breaks down goals into structured tasks and phases",
        "capabilities": ["task decomposition", "planning", "auto-task creation"]
    },
    "web_search": {
        "agent": web_search_agent,
        "description": "Performs factual web research",
        "capabilities": ["research", "fact checking"]
    },
    "summarizer": {
        "agent": summarizer_agent,
        "description": "Creates concise, structured summaries",
        "capabilities": ["summarization", "distillation", "file_reading"]
    },
    "analyzer": {
        "agent": analyzer_agent,
        "description": "Deep analysis of data, patterns and insights",
        "capabilities": ["analysis", "insight generation", "file_reading"]
    },
    "report_generator": {
        "agent": report_generator_agent,
        "description": "Creates professional formatted reports",
        "capabilities": ["reporting", "professional writing", "file_reading"]
    }
}

def get_available_agents_info() -> Dict[str, Dict[str, Any]]:
    return {
        name: {
            "description": info["description"],
            "capabilities": info["capabilities"]
        }
        for name, info in SUB_AGENTS.items()
    }