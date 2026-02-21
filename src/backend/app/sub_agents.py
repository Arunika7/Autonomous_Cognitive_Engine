from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_groq import ChatGroq
import os
import re
import json
from dotenv import load_dotenv


from .utils import AgentState

load_dotenv()

# LLM configuration 
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.35,
    max_tokens=2048,
    groq_api_key=os.getenv("GROQ_API_KEY")
)


def create_sub_agent(
    name: str,
    system_prompt: str,
    can_read_state: bool = False,
    can_create_tasks: bool = False
):
    """
    Factory function to create traceable, reusable sub-agents.
    
    Args:
        name: Agent identifier (used in tracing & logs)
        system_prompt: Base system instructions
        can_read_state: Whether agent can see current todos/calendar/files summary
        can_create_tasks: Whether agent is allowed to extract & create todos from its output
    """
    def build_context(input_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare enriched context for the prompt"""
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
                context_parts.append(
                    f"Current tasks: {len(todos)} total, {pending} still pending"
                )
            
            files = state.get("files", {})
            if files:
                context_parts.append(f"Files in memory: {len(files)}")
            
            calendar = state.get("calendar", [])
            if calendar:
                context_parts.append(f"Calendar events: {len(calendar)}")
        
        context_text = "\n".join(context_parts) if context_parts else "No additional state context available."
        
        return {
            "context": context_text,
            "user_request": user_text,
            "state_snapshot": state 
        }

    # Base prompt structure
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt + "\n\nCurrent context:\n{context}"),
        ("human", "{user_request}")
    ])

    # Main processing chain
    chain = (
        RunnableLambda(build_context).with_config({"run_name": f"{name}_prepare_context"})
        | prompt.with_config({"run_name": f"{name}_prompt"})
        | llm.with_config({"run_name": f"{name}_llm_call"})
        | RunnableLambda(lambda x: {"content": x.content}).with_config({"run_name": f"{name}_extract"})
    )

    def agent_executor(input_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Main entry point for the sub-agent"""
        result = chain.invoke(input_dict)
        response_text = result.get("content", "No response generated.")

        state = input_dict.get("state", {})
        return_data = {
            "messages": [{"role": "assistant", "content": response_text}]
        }

        # Optional: auto-extract tasks if allowed
        if can_create_tasks and state is not None:
            tasks_created = _try_extract_and_create_tasks(response_text, state, name)
            if tasks_created > 0:
                response_text += f"\n\n[Auto-created {tasks_created} follow-up tasks]"

        # Always pass back the (potentially modified) state
        return_data["state"] = state
        return return_data

    return RunnableLambda(agent_executor).with_config({"run_name": f"SubAgent_{name}"})


def _try_extract_and_create_tasks(response: str, state: Dict[str, Any], agent_name: str) -> int:
    """
    Attempt to detect task-like items in the response and create todos.
    Very basic pattern matching — can be improved with structured output later.
    """
    from .tools import ToolExecutor  

    patterns = [
        r'(?:^|\n)\s*[-*•]\s*(.+?)(?:\n|$)',
        r'(?:^|\n)\s*\d+[.)]\s*(.+?)(?:\n|$)',
        r'(?:^|\n)\s*Task\s*\d*:\s*(.+?)(?:\n|$)',
    ]

    potential_tasks = []
    for pattern in patterns:
        matches = re.findall(pattern, response, re.MULTILINE)
        potential_tasks.extend([t.strip() for t in matches if len(t.strip()) > 8])

    if not potential_tasks:
        return 0

    task_keywords = {
        'create', 'implement', 'build', 'setup', 'prepare', 'write', 'research',
        'analyze', 'review', 'test', 'deploy', 'document', 'plan', 'organize'
    }

    actual_tasks = [
        t for t in potential_tasks
        if any(kw in t.lower() for kw in task_keywords)
    ]

    if not actual_tasks:
        return 0

    # Limit to reasonable number to avoid spamming
    actual_tasks = actual_tasks[:6]

    todos_list = [
        {
            "title": task,
            "description": f"Generated by {agent_name} sub-agent",
            "priority": "medium",
            "source_agent": agent_name
        }
        for task in actual_tasks
    ]

    try:
        ToolExecutor.create_multiple_todos(state, todos_list=todos_list)
        print(f"[AUTO] {agent_name} created {len(todos_list)} tasks")
        return len(todos_list)
    except Exception as e:
        print(f"Auto-task creation failed in {agent_name}: {e}")
        return 0


# ──────────────────────────────────────────────────────────────────────────────
#                Individual Sub-Agent Definitions
# ──────────────────────────────────────────────────────────────────────────────

planning_agent = create_sub_agent(
    name="planning",
    system_prompt="""You are a strategic planning expert.
Your role is to break down complex goals into clear, actionable phases and tasks.

Always structure your response with:
1. Overview of the plan
2. Numbered phases with goals
3. Concrete, specific tasks under each phase
   Use format: - Task: [clear title] (priority: high/medium/low)

Be realistic about dependencies, effort and sequence.""",
    can_read_state=True,
    can_create_tasks=True
)

web_search_agent = create_sub_agent(
    name="web_search",
    system_prompt="""You are a precise web research assistant.
Provide factual, up-to-date information with clear sources when possible.
Structure answers:
- Summary
- Key facts (bullet points)
- Sources / references
Stay objective. Do not speculate.""",
    can_read_state=False,
    can_create_tasks=False
)

summarizer_agent = create_sub_agent(
    name="summarizer",
    system_prompt="""You are an expert summarizer.
Create concise, structured summaries that preserve meaning and key details.
Use:
- Main conclusion first
- Hierarchical bullet points
- Highlight important facts/numbers
Keep tone neutral and accurate.""",
    can_read_state=True,
    can_create_tasks=False
)

analyzer_agent = create_sub_agent(
    name="analyzer",
    system_prompt="""You are a sharp data/patterns analyst.
When given information or state:
- Identify trends and patterns
- Highlight anomalies or risks
- Provide clear, data-driven insights
- Suggest next actions
Be thorough but concise.""",
    can_read_state=True,
    can_create_tasks=False
)

report_generator_agent = create_sub_agent(
    name="report_generator",
    system_prompt="""You are a professional report writer.
Create well-structured markdown reports including:
- Executive Summary
- Key Findings
- Detailed Analysis
- Recommendations / Next Steps
Use proper headings, bullets, and tables when appropriate.""",
    can_read_state=True,
    can_create_tasks=False
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
        "capabilities": ["summarization", "distillation"]
    },
    "analyzer": {
        "agent": analyzer_agent,
        "description": "Deep analysis of data, patterns and insights",
        "capabilities": ["analysis", "insight generation"]
    },
    "report_generator": {
        "agent": report_generator_agent,
        "description": "Creates professional formatted reports",
        "capabilities": ["reporting", "professional writing"]
    }
}


def get_available_agents_info() -> Dict[str, Dict[str, Any]]:
    """Returns structured info about all sub-agents for supervisor/router"""
    return {
        name: {
            "description": info["description"],
            "capabilities": info["capabilities"]
        }
        for name, info in SUB_AGENTS.items()
    }