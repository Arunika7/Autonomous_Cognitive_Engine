# src/backend/app/utils.py

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import TypedDict, List, Dict, Any, Union   # ← must have this!

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
# ─── Move AgentState here ──────────────────────────────────────
class AgentState(TypedDict):
    messages: List[Union[BaseMessage, Dict[str, Any]]]
    todos: List[Dict[str, Any]]
    calendar: List[Dict[str, Any]]
    files: Dict[str, str]                  # filename → content
    context: Dict[str, Any]                # flexible scratchpad / metadata

# Now it's safe to use AgentState in type hints
sessions: Dict[str, AgentState] = {}
# ──────────────────────────────────────────────────────────────────────────────
# Session Management (IN-MEMORY + PERSISTENCE)
# ──────────────────────────────────────────────────────────────────────────────

DATA_DIR = Path("data")
SESSIONS_DIR = DATA_DIR / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def get_or_create_session(session_id: str) -> AgentState:
    """Get existing session from memory or disk, create new if not found"""
    if session_id in sessions:
        return sessions[session_id]

    # Try load from disk
    state = load_session_state(session_id)
    
    # Cache in memory
    sessions[session_id] = state
    return state


def save_session_state(session_id: str, state: AgentState) -> bool:
    """Save current agent state to disk (JSON)"""
    try:
        file_path = SESSIONS_DIR / f"{session_id}.json"
        serializable_state = {
            "messages": [
                {"role": "user" if isinstance(m, HumanMessage) else "assistant",
                 "content": m.content if hasattr(m, 'content') else str(m)}
                for m in state.get("messages", [])
            ],
            "todos": state.get("todos", []),
            "calendar": state.get("calendar", []),
            "files": state.get("files", {}),
            "context": state.get("context", {})
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(serializable_state, f, ensure_ascii=False, indent=2, default=str)
        return True
    except Exception as e:
        print(f"Error saving session {session_id}: {e}")
        return False


def load_session_state(session_id: str) -> AgentState:
    """Load agent state from disk, return default if not found"""
    file_path = SESSIONS_DIR / f"{session_id}.json"
    default_state: AgentState = {
        "messages": [],
        "todos": [],
        "calendar": [],
        "files": {},
        "context": {}
    }

    if not file_path.exists():
        return default_state

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        messages = []
        for raw in data.get("messages", []):
            content = raw.get("content", "")
            role = raw.get("role", "assistant").lower()
            if role == "user":
                messages.append(HumanMessage(content=content))
            else:
                messages.append(AIMessage(content=content))

        loaded = AgentState(
            messages=messages,
            todos=data.get("todos", []),
            calendar=data.get("calendar", []),
            files=data.get("files", {}),
            context=data.get("context", {})
        )

        return loaded
    except Exception as e:
        print(f"Error loading session {session_id}: {e}")
        return default_state


# ──────────────────────────────────────────────────────────────────────────────
# Date & Time Parsing Utilities
# ──────────────────────────────────────────────────────────────────────────────

def parse_relative_date(text: str) -> str:
    """
    Convert natural language date expressions → YYYY-MM-DD
    Returns empty string if parsing fails
    """
    if not text:
        return ""

    text = text.lower().strip()
    today = datetime.now()

    # Common keywords
    if "today" in text:
        return today.strftime("%Y-%m-%d")
    if "tomorrow" in text:
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    if "yesterday" in text:
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")

    # "in X days/weeks"
    match = re.search(r"in (\d+)\s*(day|week)s?", text)
    if match:
        count = int(match.group(1))
        unit = match.group(2)
        delta = timedelta(days=count) if unit == "day" else timedelta(weeks=count)
        return (today + delta).strftime("%Y-%m-%d")

    # Next weekday patterns (very basic)
    weekdays = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6
    }
    for day_name, target_weekday in weekdays.items():
        if day_name in text:
            current = today.weekday()
            days_ahead = (target_weekday - current) % 7
            if days_ahead == 0:
                days_ahead = 7  # next week
            return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    # If looks like date already → return as is
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        return text

    return ""  # failed to parse


def parse_time(text: str) -> str:
    """Convert natural time → HH:MM (24h)"""
    if not text:
        return "09:00"

    text = text.lower().strip()

    # Special cases
    if "noon" in text:
        return "12:00"
    if "midnight" in text:
        return "00:00"

    # 12-hour with am/pm
    match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2) or "00")
        period = match.group(3)

        if period == "pm" and hour != 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0

        return f"{hour:02d}:{minute:02d}"

    # 24-hour format fallback
    match = re.search(r"(\d{1,2}):(\d{2})", text)
    if match:
        return f"{int(match.group(1)):02d}:{int(match.group(2)):02d}"

    return "09:00"  # default fallback


# ──────────────────────────────────────────────────────────────────────────────
# State Query Helpers
# ──────────────────────────────────────────────────────────────────────────────

def get_pending_todos(state: AgentState) -> List[Dict[str, Any]]:
    return [t for t in state.get("todos", []) if not t.get("completed", False)]


def get_completed_todos(state: AgentState) -> List[Dict[str, Any]]:
    return [t for t in state.get("todos", []) if t.get("completed", False)]


def get_high_priority_todos(state: AgentState) -> List[Dict[str, Any]]:
    return [
        t for t in state.get("todos", [])
        if t.get("priority", "").lower() == "high" and not t.get("completed", False)
    ]


def get_state_summary(state: AgentState) -> str:
    """Human readable quick status overview"""
    pending = len(get_pending_todos(state))
    completed = len(get_completed_todos(state))
    high_pri = len(get_high_priority_todos(state))
    files_count = len(state.get("files", {}))

    lines = [
        "Current Agent State:",
        f"• Tasks: {pending} pending, {completed} completed ({high_pri} high priority)",
        f"• Files: {files_count} in virtual storage",
        f"• Calendar events: {len(state.get('calendar', []))}"
    ]
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Misc Helpers
# ──────────────────────────────────────────────────────────────────────────────

def sanitize_filename(filename: str) -> str:
    """Remove dangerous characters from filenames"""
    filename = re.sub(r'[^\w\.-]', '_', filename.strip())
    if not filename:
        filename = "unnamed"
    if len(filename) > 120:
        filename = filename[:117] + "..."
    return filename


def format_recent_messages(messages: List[Any], max_count: int = 6) -> str:
    """Format last few messages for context / debugging"""
    recent = messages[-max_count:]
    lines = []
    for msg in recent:
        if isinstance(msg, HumanMessage):
            lines.append(f"User: {msg.content[:180]}{'...' if len(msg.content) > 180 else ''}")
        elif isinstance(msg, AIMessage):
            lines.append(f"Agent: {msg.content[:180]}{'...' if len(msg.content) > 180 else ''}")
        elif isinstance(msg, dict):
            role = msg.get("role", "system").title()
            content = msg.get("content", "")[:180] + ("..." if len(msg.get("content", "")) > 180 else "")
            lines.append(f"{role}: {content}")
    return "\n".join(lines)