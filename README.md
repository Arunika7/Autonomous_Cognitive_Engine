#  Autonomous Cognitive Engine  (ACE)
**for Deep Research & Long-Horizon Tasks**

> A stateful, governed, multi-agent AI system built with **LangGraph, FastAPI, and Groq LLMs** for executing complex, long-horizon tasks with memory, safety, and auditability.

---

## 1. Overview

The **Autonomous Cognitive Engine (ACE)** is an advanced AI agent platform designed to go far beyond simple chatbots.

It can:
- Understand natural language
- Plan multi-step workflows
- Delegate work to specialized agents
- Use tools safely
- Store and retrieve long-term memory
- Maintain a full audit trail of every decision

ACE uses a **Supervisor-driven multi-agent architecture** that prevents hallucinations, enforces tool governance, and enables reliable, enterprise-grade AI automation.

---

## 2. What Makes ACE Different

| Normal AI Agents | ACE |
|-----------------|-----|
| One-shot reasoning | Long-horizon planning |
| No memory | Persistent Virtual File System |
| Uncontrolled tool use | Strict Supervisor governance |
| Hallucinations | Source-validated outputs |
| No audit trail | Full LangSmith tracing |
| Monolithic | Specialized sub-agents |

---

## 3. System Architecture

```
User
↓
Supervisor Agent (Control Plane)
├── Web Search Agent
├── Planning Agent
├── Analyzer Agent
├── Summarizer Agent
├── Report Generator Agent
├── Tool Executor (Calendar, Files, Search)
└── Virtual File System (Persistent Memory)
↓
LangSmith (Tracing, Logging, Observability)

```

Every action is routed through the **Supervisor**, ensuring deterministic, safe, and auditable execution.

---

## 4. Sub-Agents

###  Web Search Agent
The only agent allowed to access the internet.

- Performs sandboxed web queries  
- Returns structured, source-grounded data  
- Cannot write to memory  

---

### Planning Agent
Responsible for breaking complex user requests into executable steps.

- Creates multi-step plans  
- Assigns tasks to other agents  
- Enforces execution order  

---

### Analyzer Agent
Processes and reasons over collected data.

- Validates facts  
- Detects inconsistencies  
- Performs structured reasoning  
- Prepares data for reporting  

---

###  Summarizer Agent
Compresses large content into useful knowledge.

- Produces TL;DRs  
- Bullet-point summaries  
- Section-wise condensation  

---

###  Report Generator Agent
Creates final human-readable outputs.

- Generates reports  
- Formats findings  
- Produces structured documents  

---

## 5. Supervisor Agent

The **Supervisor** is the brain of ACE.

It:
- Interprets user intent  
- Selects which sub-agent or tool to use  
- Enforces single-tool-per-turn policy  
- Validates every output  
- Writes approved results to the Virtual File System  
- Logs all activity to LangSmith  

---

## 6. Virtual File System (VFS)

A persistent, auditable external memory for ACE.

Stores:
- Research results  
- Notes  
- JSON  
- CSV  
- Reports  
- Logs  

Includes:
- Versioning  
- Metadata  
- Provenance  
- Full audit trails  

---

## 7. Tech Stack

- **Backend**: FastAPI (Python)
- **Agent Framework**: LangGraph
- **LLM**: Groq (llama-3.3-70b-versatile)
- **Memory**: Custom Virtual File System
- **Observability**: LangSmith
- **Configuration**: YAML
- **Environment**: dotenv

---

## 8. Project Structure

```
src/
├── backend/
│   └── app/
│       ├── agent_core.py      ← Core reasoning + state graph (LangGraph)
│       ├── agent.py           ← Supervisor Agent (decision maker)
│       ├── sub_agents.py      ← 5 Sub-Agents (websearch, planner, analyzer, summarizer, report)
│       ├── tool_executor.py  ← Tool-gating + safe execution layer
│       ├── tools.py          ← Actual tool implementations (calendar, files, web, etc.)
│       ├── utils.py          ← State model, prompts, helper functions
│       └── main.py           ← FastAPI server + API routes
│
├── tests/
│   └── test_delegation.py    ← Verifies correct agent → tool delegation
│
├── frontend/
│   ├── index.html            ← Chat UI
│   ├── script.js             ← Frontend → backend API logic
│   └── styles.css            ← UI styling
│
├── .env                     ← API keys (Groq, LangSmith, etc.)
├── requirements.txt
├── README.md
└── LICENSE

```

---

## 9. Setup

```
git clone <repo-url>
cd Autonomous-Cognitive-Engine-for-Deep-Research-and-Long-Horizon-Tasks
git checkout intern-arunika

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

```

Create `.env`:

```
GROQ_API_KEY=your_groq_key
LANGSMITH_KEY=your_langsmith_key

```

---

## 11. Why This Matters

ACE is not a chatbot — it is a **governed autonomous reasoning system**.

It enables:
- Research automation  
- Strategy planning  
- Knowledge synthesis  
- Enterprise-grade AI workflows  

---








