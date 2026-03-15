import sys
import os
import traceback

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

try:
    from backend.app.sub_agents import SUB_AGENTS
    from langchain_core.messages import HumanMessage
    
    web_search = SUB_AGENTS["web_search"]["agent"]
    
    input_state = {
        "messages": [HumanMessage(content="What is the stock price of Tesla (TSLA) today? Give me the exact number.")],
        "state": {}
    }
    
    print("Invoking web search agent...")
    result = web_search.invoke(input_state)
    
    print("\n=== FINAL OUTPUT ===")
    print(result.get("output", "No output returned"))
except Exception as e:
    print("=== CAUGHT EXCEPTION ===")
    traceback.print_exc()
