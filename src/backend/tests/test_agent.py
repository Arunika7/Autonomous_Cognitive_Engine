# test_agent.py - Comprehensive testing and debugging script

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def print_section(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def test_health():
    print_section("Health Check")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))
    return response.status_code == 200

def test_simple_query():
    print_section("Test 1: Simple Query")
    
    payload = {
        "message": "Create a todo to research LangGraph",
        "reset_session": True
    }
    
    response = requests.post(f"{BASE_URL}/chat", json=payload)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"\nThread ID: {data.get('thread_id')}")
        print(f"Response: {data.get('response')}")
        print(f"Todos: {len(data.get('todos', []))} created")
        print(f"Iterations: {data.get('iteration_count')}")
        return data.get('thread_id')
    else:
        print(f"Error: {response.text}")
        return None

def test_complex_query():
    print_section("Test 2: Complex Query (Startup Roadmap)")
    
    payload = {
        "message": "Develop a 12-month roadmap for launching a sustainable agriculture startup in Andhra Pradesh, India.",
        "reset_session": True
    }
    
    response = requests.post(f"{BASE_URL}/chat", json=payload)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        thread_id = data.get('thread_id')
        
        print(f"\nThread ID: {thread_id}")
        print(f"Iterations: {data.get('iteration_count')}")
        print(f"Todos Created: {len(data.get('todos', []))}")
        print(f"Files Created: {len(data.get('files', {}))}")
        
        print(f"\n--- Response Preview (first 500 chars) ---")
        response_text = data.get('response', 'No response')
        print(response_text[:500])
        
        if len(response_text) > 500:
            print("...")
        
        # Show todos
        todos = data.get('todos', [])
        if todos:
            print(f"\n--- Todos ({len(todos)} total) ---")
            for i, todo in enumerate(todos[:5], 1):
                status = "✓" if todo.get('completed') else "○"
                print(f"{status} {i}. {todo.get('title', 'Untitled')}")
            if len(todos) > 5:
                print(f"... and {len(todos) - 5} more")
        
        return thread_id
    else:
        print(f"Error: {response.text}")
        return None

def debug_session(thread_id):
    print_section(f"Debug Session: {thread_id}")
    
    response = requests.get(f"{BASE_URL}/debug/{thread_id}")
    
    if response.status_code == 200:
        data = response.json()
        
        print(f"Iteration Count: {data.get('iteration_count')}")
        print(f"Messages: {data.get('messages_count')}")
        print(f"Todos: {len(data.get('todos', []))}")
        print(f"Files: {data.get('files', [])}")
        
        print(f"\n--- Last Decision ---")
        last_decision = data.get('last_decision', {})
        print(json.dumps(last_decision, indent=2))
        
        print(f"\n--- Message History (last 5) ---")
        messages = data.get('messages', [])
        for msg in messages[-5:]:
            print(f"\n[{msg['type']}] Index {msg['index']}:")
            print(f"  {msg['content_preview']}")
        
        print(f"\n--- Metrics ---")
        print(json.dumps(data.get('metrics', {}), indent=2))
    else:
        print(f"Error: {response.text}")

def test_session_continuation(thread_id):
    print_section(f"Test 3: Session Continuation")
    
    payload = {
        "message": "What todos are still pending?",
        "thread_id": thread_id
    }
    
    response = requests.post(f"{BASE_URL}/chat", json=payload)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response: {data.get('response')}")
        print(f"Todos: {len(data.get('todos', []))}")
        print(f"Iterations: {data.get('iteration_count')}")
    else:
        print(f"Error: {response.text}")

def list_all_sessions():
    print_section("All Active Sessions")
    
    response = requests.get(f"{BASE_URL}/sessions")
    
    if response.status_code == 200:
        data = response.json()
        sessions = data.get('sessions', [])
        
        print(f"Active Sessions: {len(sessions)}")
        for i, session in enumerate(sessions, 1):
            print(f"\n{i}. Thread: {session['thread_id'][:20]}...")
            print(f"   Messages: {session['message_count']}")
            print(f"   Pending Todos: {session['todos_pending']}")
            print(f"   Iterations: {session['iteration_count']}")
    else:
        print(f"Error: {response.text}")

def main():
    print("\n" + "="*60)
    print("  AUTONOMOUS AGENT TEST SUITE")
    print("="*60)
    
    # Test 1: Health check
    if not test_health():
        print("\n❌ Server not responding. Start the server first:")
        print("   uvicorn src.backend.app.main:app --reload")
        return
    
    print("\n✓ Server is healthy")
    time.sleep(1)
    
    # Test 2: Simple query
    thread_id_simple = test_simple_query()
    time.sleep(1)
    
    # Test 3: Complex query (main test)
    thread_id_complex = test_complex_query()
    time.sleep(1)
    
    # Test 4: Debug the complex session
    if thread_id_complex:
        debug_session(thread_id_complex)
        time.sleep(1)
    
    # Test 5: Session continuation
    if thread_id_complex:
        test_session_continuation(thread_id_complex)
        time.sleep(1)
    
    # Test 6: List all sessions
    list_all_sessions()
    
    print("\n" + "="*60)
    print("  TEST SUITE COMPLETE")
    print("="*60)
    print("\nTo run individual tests:")
    print("  python test_agent.py")
    print("\nTo debug a specific thread:")
    print(f"  curl http://localhost:8000/debug/{{thread_id}}")

if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Could not connect to server")
        print("Start the server with: uvicorn src.backend.app.main:app --reload")
    except KeyboardInterrupt:
        print("\n\nTest suite interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()