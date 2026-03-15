import logging
import uuid
import json
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from langchain_core.messages import HumanMessage, AIMessage

from backend.app.agent import agent
from backend.app.utils import AgentState
from backend.app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

async def get_api_key(api_key: str = Security(api_key_header)):
    if api_key != settings.api_auth_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing X-API-Key header"
        )
    return api_key

# Initialize FastAPI app
app = FastAPI(
    title="Autonomous Cognitive Engine API",
    description="Deep research and long-horizon task execution agent",
    version="1.0.0",
    dependencies=[Depends(get_api_key)]
)

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response models
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    thread_id: Optional[str] = None  
    reset_session: bool = False 

class ChatResponse(BaseModel):
    response: str
    thread_id: str
    todos: list[dict] = []
    files: dict[str, str] = {}
    calendar_events: list[dict] = []
    metrics: dict = {}
    iteration_count: int = 0
    messages: list[dict] = []  
    execution_log: list[dict] = []  

class HealthResponse(BaseModel):
    status: str
    timestamp: str

sessions = {}

def extract_final_response(state: dict) -> str:
    """
    Extract user-facing response from agent state.
    Priority: respond action > sub-agent outputs > state artifacts
    """
    
    # Strategy 1: Look for explicit "respond" action in messages
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            try:
                content = msg.content
                if isinstance(content, str) and content.startswith('{'):
                    decision = json.loads(content)
                    if decision.get("action") == "respond" and decision.get("response"):
                        logger.info("✓ Response extracted from 'respond' action")
                        return decision["response"]
            except (json.JSONDecodeError, AttributeError):
                continue
    
    # Strategy 2: Check last_decision
    last_decision = state.get("last_decision", {})
    if last_decision.get("action") == "respond" and last_decision.get("response"):
        logger.info("✓ Response extracted from last_decision")
        return last_decision["response"]
    
    # Strategy 3: Build response from sub-agent outputs 
    sub_agent_outputs = state.get("sub_agent_outputs", {})
    research_insights = state.get("research_insights", [])
    files = state.get("files", {})
    calendar_events = state.get("calendar_events", [])
    todos = state.get("todos", [])
    completed = [t for t in todos if t.get("completed", False)]
    
    response_parts = []
    
    # Include sub-agent outputs
    if sub_agent_outputs:
        logger.info(f"✓ Building response from {len(sub_agent_outputs)} sub-agent outputs")
        response_parts.append("=" * 70)
        response_parts.append(" RESEARCH & ANALYSIS RESULTS")
        response_parts.append("=" * 70 + "\n")
        
        for agent_name, output in sub_agent_outputs.items():
            agent_title = agent_name.replace("_", " ").title()
            response_parts.append(f"\n### {agent_title} Output:\n")
            
            # Show full output 
            if len(output) > 5000:
                response_parts.append(output[:5000] + f"\n\n... (truncated - showing first 5000 of {len(output)} characters)")
            else:
                response_parts.append(output)
            
            response_parts.append("\n" + "-" * 70 + "\n")
    
    # Include research insights
    if research_insights:
        response_parts.append("\n **Key Research Insights:**\n")
        for idx, insight in enumerate(research_insights[:15], 1):
            insight_text = insight.get("insight", insight.get("summary", ""))
            if insight_text:
                response_parts.append(f"{idx}. {insight_text}")
    
    # Include files
    if files:
        response_parts.append(f"\n **Generated {len(files)} File(s):**")
        for filename, content in files.items():
            response_parts.append(f"\n  • **{filename}**")
            if content and len(content) > 100:
                preview = content[:300].replace('\n', ' ')
                response_parts.append(f"    Preview: {preview}...")
    
    # Include calendar events
    if calendar_events:
        response_parts.append(f"\n **Scheduled {len(calendar_events)} Event(s):**")
        for event in calendar_events:
            response_parts.append(f"  • {event.get('title')} on {event.get('date')} at {event.get('time')}")
    
    # Task completion summary
    if completed:
        response_parts.append(f"\n **Completed {len(completed)} Task(s) Successfully**")
    
    if response_parts:
        logger.info("✓ Response built from state artifacts and sub-agent outputs")
        return "\n".join(response_parts)
    
    # Strategy 4: Fallback - build from execution log
    execution_log = state.get("execution_log", [])
    if execution_log:
        actions = [log.get("details", "") for log in execution_log[-5:]]
        logger.warning("⚠ Using execution log fallback")
        return f"Completed actions: {', '.join(actions)}\n\nNote: Full output may be available in the debug endpoint."
    
    # Final fallback
    logger.warning("⚠ No content found - using generic message")
    return "Task processing complete. Please check the session details for results."


# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat()
    )

# Main chat endpoint
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        # Generate or retrieve thread_id
        thread_id = request.thread_id or str(uuid.uuid4())
        
        logger.info(f"Processing chat request for thread: {thread_id}")
        logger.info(f"User message: {request.message[:100]}...")
        
        # Reset session if requested or if new thread
        if request.reset_session or thread_id not in sessions:
            logger.info(f"Initializing new session for thread: {thread_id}")
            sessions[thread_id] = {
                "messages": [],
                "todos": [],
                "files": {},
                "calendar_events": [],
                "research_insights": [],
                "iteration_count": 0,
                "metrics": {},
                "planning_done": False,
                "execution_log": [],
                "last_decision": {},
                "sub_agent_outputs": {} 
            }
        
        # Get current state
        state = sessions[thread_id]
        
        # Add user message to state
        state["messages"].append(HumanMessage(content=request.message))
        
        # Invoke agent with thread_id in config and higher recursion limit
        logger.info("Invoking agent...")
        updated_state = agent.invoke(
            state,
            config={
                "configurable": {
                    "thread_id": thread_id
                },
                "recursion_limit": 50  
            }
        )
        
        # Update session with new state
        sessions[thread_id] = updated_state
        
     
        final_response = extract_final_response(updated_state)
        
        logger.info(f"Agent completed. Iterations: {updated_state.get('iteration_count', 0)}")
        logger.info(f"Response length: {len(final_response)} characters")
        
        # Build response
        return ChatResponse(
            response=final_response,
            thread_id=thread_id,
            todos=updated_state.get("todos", []),
            files=updated_state.get("files", {}),
            calendar_events=updated_state.get("calendar_events", []),
            metrics=updated_state.get("metrics", {}),
            iteration_count=updated_state.get("iteration_count", 0),
            execution_log=updated_state.get("execution_log", [])
        )
        
    except Exception as e:
        logger.error(f"Error processing chat request: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

# Get session state endpoint
@app.get("/session/{thread_id}")
async def get_session(thread_id: str):
    if thread_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    state = sessions[thread_id]
    return {
        "thread_id": thread_id,
        "todos": state.get("todos", []),
        "files": state.get("files", {}),
        "calendar_events": state.get("calendar_events", []),
        "metrics": state.get("metrics", {}),
        "iteration_count": state.get("iteration_count", 0),
        "message_count": len(state.get("messages", [])),
        "sub_agents_used": list(state.get("sub_agent_outputs", {}).keys())
    }

# Delete session endpoint
@app.delete("/session/{thread_id}")
async def delete_session(thread_id: str):
    if thread_id in sessions:
        del sessions[thread_id]
        logger.info(f"Deleted session: {thread_id}")
        return {"status": "deleted", "thread_id": thread_id}
    
    raise HTTPException(status_code=404, detail="Session not found")

# List all active sessions
@app.get("/sessions")
async def list_sessions():
    return {
        "sessions": [
            {
                "thread_id": tid,
                "message_count": len(state.get("messages", [])),
                "todos_pending": len([t for t in state.get("todos", []) if not t.get("completed")]),
                "iteration_count": state.get("iteration_count", 0),
                "sub_agents_used": list(state.get("sub_agent_outputs", {}).keys())
            }
            for tid, state in sessions.items()
        ]
    }

# Debug endpoint to see full state
@app.get("/debug/{thread_id}")
async def debug_session(thread_id: str):
    if thread_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    state = sessions[thread_id]
    
    # Extract all messages with types
    messages_debug = []
    for i, msg in enumerate(state.get("messages", [])):
        msg_info = {
            "index": i,
            "type": type(msg).__name__,
            "content_preview": str(msg.content if hasattr(msg, 'content') else msg)[:200]
        }
        messages_debug.append(msg_info)
    
    # Extract sub-agent outputs with sizes
    sub_agent_debug = {}
    for agent_name, output in state.get("sub_agent_outputs", {}).items():
        sub_agent_debug[agent_name] = {
            "size": len(output),
            "preview": output[:300] + "..." if len(output) > 300 else output
        }
    
    return {
        "thread_id": thread_id,
        "iteration_count": state.get("iteration_count", 0),
        "todos": state.get("todos", []),
        "last_decision": state.get("last_decision", {}),
        "messages_count": len(state.get("messages", [])),
        "messages": messages_debug,
        "files": list(state.get("files", {}).keys()),
        "metrics": state.get("metrics", {}),
        "sub_agent_outputs": sub_agent_debug,
        "planning_done": state.get("planning_done", False)
    }

@app.get("/session/{thread_id}/outputs")
async def get_sub_agent_outputs(thread_id: str):
    """Get all sub-agent outputs for a session"""
    if thread_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    state = sessions[thread_id]
    sub_agent_outputs = state.get("sub_agent_outputs", {})
    
    return {
        "thread_id": thread_id,
        "sub_agent_outputs": sub_agent_outputs,
        "agents_used": list(sub_agent_outputs.keys()),
        "total_output_size": sum(len(output) for output in sub_agent_outputs.values())
    }

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Autonomous Cognitive Engine API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "chat": "/chat (POST)",
            "session": "/session/{thread_id} (GET)",
            "sessions": "/sessions (GET)",
            "outputs": "/session/{thread_id}/outputs (GET)",
            "delete_session": "/session/{thread_id} (DELETE)",
            "debug": "/debug/{thread_id} (GET)"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)