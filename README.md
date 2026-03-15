# Autonomous Cognitive Engine (ACE)
**for Deep Research & Long-Horizon Tasks**

> A stateful, governed, multi-agent AI system built with **LangGraph, FastAPI, ChromaDB, and Groq LLMs** for executing complex, long-horizon tasks with memory, safety, and auditability.

---

## 1. Overview

The **Autonomous Cognitive Engine (ACE)** is an advanced AI agent platform designed to go far beyond simple chatbots.

It can:
- Understand natural language
- Plan multi-step workflows
- Delegate work to specialized tool-bound agents
- Perform real-time live web searches
- Store, embed, and retrieve long-term memory via Retrieval-Augmented Generation (RAG)
- Maintain a full audit trail of every decision and securely gate API access

ACE uses a **Supervisor-driven multi-agent architecture** that prevents hallucinations, enforces tool governance, and enables reliable, enterprise-grade AI automation.

---

## 2. What Makes ACE Different

| Normal AI Agents | ACE |
|-----------------|-----|
| One-shot reasoning | Long-horizon planning |
| No memory | Persistent Virtual File System + ChromaDB Vector Storage |
| Uncontrolled tool use | Strict Supervisor governance |
| Hallucinations | Source-validated live web outputs |
| No audit trail | Full LangSmith tracing |
| Monolithic | Specialized sub-agents using native Tool Calling |
| Insecure | Global API Key authentication via FastAPI Security |

---

## 3. System Architecture

```
User
↓
FastAPI Security Layer (X-API-Key)
↓
Supervisor Agent (Control Plane)
├── Web Search Agent (DuckDuckGo Live Search)
├── Planning Agent (Task Generation Tool)
├── Analyzer Agent (RAG / Semantic Search Tool)
├── Summarizer Agent (File Reading Tool)
├── Report Generator Agent (RAG / Reporting Tools)
├── Tool Executor (Calendar, Files, Tasks)
└── Virtual File System (Persistent Memory) <--> ChromaDB Vector Store
↓
LangSmith (Tracing, Logging, Observability)
```

Every action is routed through the **Supervisor**, ensuring deterministic, safe, and auditable execution.

---

## 4. Sub-Agents

All sub-agents have been structurally upgraded to natively use the **LangChain Tool Calling APIs** (`bind_tools`), giving them precise control over their assigned tasks.

### Web Search Agent
- Performs live web queries to the real internet via `DuckDuckGoSearchRun`.
- Returns structured, source-grounded data to absolutely prevent hallucination.

### Planning Agent
- Breaks complex user requests into executable steps.
- Autonomously injects workflows back into the state via the `create_multiple_todos` tool.

### Analyzer Agent
- Processes and reasons over collected data.
- Capable of querying massive historical document sets natively using the `semantic_search` tool (Vector RAG).

### Summarizer Agent
- Compresses large content into useful knowledge.
- Ingests specific files via the `read_file` tool to summarize.

### Report Generator Agent
- Creates well-structured markdown outputs.
- Can fetch and combine documents autonomously using Vector semantic retrieval or direct file reads.

---

## 5. Supervisor Agent & Configuration

The **Supervisor** is the brain of ACE. It relies on a central **Pydantic configuration manager** (`config.py`) to keep API keys and models hidden securely. 

It:
- Interprets user intent  
- Selects which sub-agent or tool to use  
- Enforces single-tool-per-turn policy  
- Validates every output  
- Logs all activity to LangSmith  

---

## 6. Virtual File System & Vector Storage

A persistent, auditable external memory for ACE built on local disks combined with **ChromaDB**.

When the system writes a file:
- It saves to standard JSON/Markdown.
- It immediately chunk-embeds the document seamlessly using `sentence-transformers` (`all-MiniLM-L6-v2`) and ingests it into a local ChromaDB Vector Store.
- Allows agents to query massive historical data intelligently over time.

---

## 7. Tech Stack

- **Backend / API**: FastAPI (Python), `pydantic-settings`
- **Agent Framework**: LangGraph, LangChain Function Calling
- **LLM**: Groq (`llama-3.1-8b-instant` for Supervisor, `llama-3.3-70b-versatile` for Sub-Agents)
- **Vector Database**: ChromaDB (`langchain-chroma`)
- **Embeddings Model**: local `sentence-transformers`
- **Observability**: LangSmith

---

## 8. Security

ACE is designed for enterprise deployment. The entire FastAPI backend is protected by a global `APIKeyHeader` dependency.

Any request hitting the `/chat`, `/session`, or `/debug` endpoints *must* include the validation key via headers:
```http
X-API-Key: your-secure-api-key
```
Unauthenticated requests receive an immediate `401 Unauthorized` block.

---

## 9. Setup

```bash
git clone <repo-url>
cd Autonomous-Cognitive-Engine-for-Deep-Research-and-Long-Horizon-Tasks
git checkout intern-arunika

python -m venv .venv
# Activate environment:
# source .venv/bin/activate (Linux/Mac) or .venv\Scripts\activate (Windows)
pip install -r requirements.txt
```

Create a `.env` file in the root directory:

```env
GROQ_API_KEY=your_groq_key
LANGSMITH_KEY=your_langsmith_key
API_AUTH_KEY=your_secure_backend_password
```

Run the server with:
```bash
python -m backend.app.main
```

---

## 10. Why This Matters

ACE is not a chatbot — it is a **governed autonomous reasoning system**.

It enables:
- Research automation with live web data
- Strategy planning and execution loops
- Vector-backed Knowledge synthesis
- Secure, Enterprise-grade AI workflows
