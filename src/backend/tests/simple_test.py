# simple_test.py - Quick agent validation

import requests
import json

BASE_URL = "http://localhost:8000"

def test_1_simple():
    print("\n" + "="*50)
    print("TEST 1: Simple Todo Creation")
    print("="*50)
    
    response = requests.post(f"{BASE_URL}/chat", json={
        "message": "Create a todo to learn Python basics",
        "reset_session": True
    })
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Success")
        print(f"  Response: {data['response'][:100]}")
        print(f"  Todos: {len(data.get('todos', []))}")
        print(f"  Iterations: {data.get('iteration_count')}")
        return True
    else:
        print(f"✗ Failed: {response.status_code}")
        print(f"  {response.text[:200]}")
        return False

def test_2_with_research():
    print("\n" + "="*50)
    print("TEST 2: Task with Research")
    print("="*50)
    
    response = requests.post(f"{BASE_URL}/chat", json={
        "message": "Research the top 3 benefits of sustainable agriculture and create a summary",
        "reset_session": True
    })
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Success")
        print(f"  Response length: {len(data['response'])} chars")
        print(f"  Response preview: {data['response'][:150]}...")
        print(f"  Todos: {len(data.get('todos', []))}")
        print(f"  Completed: {len([t for t in data.get('todos', []) if t.get('completed')])}")
        print(f"  Iterations: {data.get('iteration_count')}")
        return True
    else:
        print(f"✗ Failed: {response.status_code}")
        print(f"  Error: {response.text[:200]}")
        return False

def test_3_roadmap_simple():
    print("\n" + "="*50)
    print("TEST 3: Simple Roadmap (6 months)")
    print("="*50)
    
    response = requests.post(f"{BASE_URL}/chat", json={
        "message": "Create a simple 6-month plan for starting an online tutoring business. Just 3 main phases.",
        "reset_session": True
    })
    
    if response.status_code == 200:
        data = response.json()
        
        is_error_response = "processing difficulties" in data['response'].lower() or \
                          "error" in data['response'].lower()
        
        if is_error_response:
            print(f"⚠ Completed but with error response")
            print(f"  Response: {data['response']}")
        else:
            print(f"✓ Success")
            print(f"  Response length: {len(data['response'])} chars")
            print(f"  Response preview:")
            print(f"  {data['response'][:300]}...")
        
        print(f"\n  Todos created: {len(data.get('todos', []))}")
        print(f"  Todos completed: {len([t for t in data.get('todos', []) if t.get('completed')])}")
        print(f"  Iterations: {data.get('iteration_count')}")
        
        return not is_error_response
    else:
        print(f"✗ Failed: {response.status_code}")
        print(f"  Error: {response.text[:200]}")
        return False

def main():
    print("\n" + "="*50)
    print("QUICK AGENT VALIDATION")
    print("="*50)
    
    try:
        # Check server
        health = requests.get(f"{BASE_URL}/health")
        if health.status_code != 200:
            print("✗ Server not running")
            print("  Start with: uvicorn src.backend.app.main:app --reload")
            return
        
        print("✓ Server is running\n")
        
        # Run tests
        results = []
        results.append(("Simple Todo", test_1_simple()))
        results.append(("With Research", test_2_with_research()))
        results.append(("Simple Roadmap", test_3_roadmap_simple()))
        
        # Summary
        print("\n" + "="*50)
        print("RESULTS SUMMARY")
        print("="*50)
        
        for name, passed in results:
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"{status} - {name}")
        
        passed_count = sum(1 for _, p in results if p)
        print(f"\nPassed: {passed_count}/{len(results)}")
        
        if passed_count == len(results):
            print("\n🎉 All tests passed!")
        elif passed_count > 0:
            print("\n⚠ Some tests failed - check logs")
        else:
            print("\n❌ All tests failed - see errors above")
    
    except requests.exceptions.ConnectionError:
        print("\n✗ Cannot connect to server")
        print("  Start with: uvicorn src.backend.app.main:app --reload")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()