import requests
import json
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
import sys


@dataclass
class TestCase:
    """Test case structure"""
    name: str
    message: str
    expected_agent: str
    expected_outcomes: List[str]
    requires_context: bool = False
    description: str = ""


@dataclass
class TestResult:
    """Test result structure"""
    test_name: str
    success: bool
    agent_used: str
    result_integrated: bool
    context_passed: bool
    execution_time: float
    response_preview: str = ""
    error_message: str = ""


class DelegationTester:
    """Test harness for sub-agent delegation"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session_id = f"test-{int(time.time())}"
        self.results: List[TestResult] = []
        
    def check_server_running(self) -> bool:
        """Check if server is running before tests"""
        print("\n[INFO] Checking if server is running...")
        try:
            response = requests.get(f"{self.base_url}/", timeout=3)
            print("[SUCCESS] Server is running!")
            return True
        except requests.exceptions.ConnectionError:
            print("[ERROR] Server is not running!")
            print(f"\nPlease start the server first:")
            print(f"  cd src")
            print(f"  uvicorn backend.app.main:app --reload")
            print(f"\nThen run this test in a separate terminal.")
            return False
        except Exception as e:
            print(f"[ERROR] Error connecting to server: {str(e)}")
            return False
    
    def run_test(self, test_case: TestCase) -> TestResult:
        """Run a single test case"""
        print(f"\n{'='*70}")
        print(f"[TEST] {test_case.name}")
        print(f"[MESSAGE] {test_case.message}")
        print(f"[EXPECTED] Agent: {test_case.expected_agent}")
        if test_case.description:
            print(f"[DESCRIPTION] {test_case.description}")
        print(f"{'='*70}")
        
        start_time = time.time()
        
        try:
            # Send request
            response = requests.post(
                f"{self.base_url}/chat",
                json={
                    "session_id": self.session_id,
                    "message": test_case.message
                },
                timeout=60  # Increased timeout for complex operations
            )
            
            execution_time = time.time() - start_time
            
            if response.status_code != 200:
                return TestResult(
                    test_name=test_case.name,
                    success=False,
                    agent_used="none",
                    result_integrated=False,
                    context_passed=False,
                    execution_time=execution_time,
                    error_message=f"HTTP {response.status_code}: {response.text[:200]}"
                )
            
            data = response.json()
            response_text = data.get("response", "")
            response_lower = response_text.lower()
            
            # Check if expected agent was mentioned or used
            agent_used = (
                test_case.expected_agent.lower() in response_lower or
                self._check_agent_indicators(response_lower, test_case.expected_agent)
            )
            
            # Check if result was integrated (response contains meaningful content)
            result_integrated = len(response_text) > 50 and any(
                outcome.lower() in response_lower 
                for outcome in test_case.expected_outcomes
            )
            
            # For context-requiring tests, check if context was used
            context_passed = True
            if test_case.requires_context:
                context_passed = any(
                    word in response_lower 
                    for word in ["task", "todo", "calendar", "pending", "completed", "meeting", "event"]
                )
            
            success = agent_used and result_integrated and context_passed
            
            result = TestResult(
                test_name=test_case.name,
                success=success,
                agent_used=test_case.expected_agent if agent_used else "unknown",
                result_integrated=result_integrated,
                context_passed=context_passed,
                execution_time=execution_time,
                response_preview=response_text[:300]
            )
            
            # Print result
            status_text = "SUCCESS" if success else "FAILED"
            print(f"\n[RESULT] {status_text}")
            print(f"   Agent Used: {'PASS' if agent_used else 'FAIL'} - {test_case.expected_agent}")
            print(f"   Result Integrated: {'PASS' if result_integrated else 'FAIL'}")
            print(f"   Context Passed: {'PASS' if context_passed else 'FAIL'}")
            print(f"   Execution Time: {execution_time:.2f}s")
            
            if not success:
                print(f"\n   Response Preview:")
                print(f"   {response_text[:200]}...")
            
            return result
            
        except requests.exceptions.Timeout:
            execution_time = time.time() - start_time
            print(f"[ERROR] TIMEOUT: Request exceeded 60 seconds")
            
            return TestResult(
                test_name=test_case.name,
                success=False,
                agent_used="timeout",
                result_integrated=False,
                context_passed=False,
                execution_time=execution_time,
                error_message="Request timeout after 60 seconds"
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            print(f"[ERROR] EXCEPTION: {str(e)}")
            
            return TestResult(
                test_name=test_case.name,
                success=False,
                agent_used="error",
                result_integrated=False,
                context_passed=False,
                execution_time=execution_time,
                error_message=str(e)
            )
    
    def _check_agent_indicators(self, response: str, agent: str) -> bool:
        """Check for agent-specific indicators in response"""
        indicators = {
            "web_search": ["searched", "found", "according to", "results show"],
            "summarizer": ["summary", "key points", "in summary", "highlights"],
            "analyzer": ["analysis", "insights", "trends", "patterns"],
            "report_generator": ["report", "executive summary", "recommendations", "conclusion"],
            "planning": ["plan", "phase", "step", "timeline", "strategy"]
        }
        
        if agent in indicators:
            return any(indicator in response for indicator in indicators[agent])
        return False
    
    def setup_test_data(self):
        """Create some test data in the session"""
        print("\n" + "="*70)
        print("[SETUP] Setting up test data...")
        print("="*70)
        
        try:
            # Create test tasks
            print("Creating test tasks...")
            response = requests.post(
                f"{self.base_url}/chat",
                json={
                    "session_id": self.session_id,
                    "message": "Create 3 tasks: 'Review code' (high priority), 'Update docs' (medium), and 'Team sync' (low)"
                },
                timeout=30
            )
            if response.status_code == 200:
                print("[SUCCESS] Tasks created")
            
            time.sleep(1)
            
            # Create calendar event
            print("Creating calendar event...")
            response = requests.post(
                f"{self.base_url}/chat",
                json={
                    "session_id": self.session_id,
                    "message": "Schedule a meeting tomorrow at 2pm for project review"
                },
                timeout=30
            )
            if response.status_code == 200:
                print("[SUCCESS] Calendar event created")
            
            print("\n[SUCCESS] Test data setup complete!")
            time.sleep(2)
            
        except Exception as e:
            print(f"[WARNING] Could not set up test data: {str(e)}")
            print("Tests will continue but context-based tests may fail.")
    
    def run_all_tests(self):
        """Run complete test suite"""
        
        # Check if server is running
        if not self.check_server_running():
            return
        
        # Define comprehensive test cases
        test_cases = [
            # Category 1: Simple Research
            TestCase(
                name="Simple Web Search",
                message="What's the current weather in New York?",
                expected_agent="web_search",
                expected_outcomes=["weather", "temperature", "forecast"],
                requires_context=False,
                description="Tests basic web search delegation"
            ),
            
            TestCase(
                name="Research Query",
                message="Research the latest developments in quantum computing",
                expected_agent="web_search",
                expected_outcomes=["research", "quantum", "developments"],
                requires_context=False,
                description="Tests research-focused web search"
            ),
            
            # Category 2: Content Summarization
            TestCase(
                name="Task Summarization",
                message="Summarize my current tasks",
                expected_agent="summarizer",
                expected_outcomes=["summary", "tasks", "key points"],
                requires_context=True,
                description="Tests summarization with context"
            ),
            
            TestCase(
                name="Calendar Summarization",
                message="Give me a summary of my upcoming events",
                expected_agent="summarizer",
                expected_outcomes=["summary", "event", "upcoming"],
                requires_context=True,
                description="Tests calendar summarization"
            ),
            
            # Category 3: Deep Analysis
            TestCase(
                name="Productivity Analysis",
                message="Analyze my productivity based on my current tasks",
                expected_agent="analyzer",
                expected_outcomes=["analysis", "productivity", "insights"],
                requires_context=True,
                description="Tests analytical capabilities with context"
            ),
            
            TestCase(
                name="Task Distribution Analysis",
                message="Analyze how my tasks are distributed by priority",
                expected_agent="analyzer",
                expected_outcomes=["analysis", "distribution", "priority"],
                requires_context=True,
                description="Tests data analysis on user's tasks"
            ),
            
            # Category 4: Report Generation
            TestCase(
                name="Comprehensive Report",
                message="Create a detailed report on my tasks and calendar",
                expected_agent="report_generator",
                expected_outcomes=["report", "summary", "recommendations"],
                requires_context=True,
                description="Tests report generation with multiple data sources"
            ),
            
            TestCase(
                name="Status Report",
                message="Generate a status report of my work",
                expected_agent="report_generator",
                expected_outcomes=["report", "status", "overview"],
                requires_context=True,
                description="Tests status report generation"
            ),
            
            # Category 5: Strategic Planning
            TestCase(
                name="Project Planning",
                message="Help me plan a product launch campaign",
                expected_agent="planning",
                expected_outcomes=["plan", "phase", "timeline", "steps"],
                requires_context=False,
                description="Tests strategic planning capabilities"
            ),
            
            TestCase(
                name="Goal Breakdown",
                message="Break down the goal of 'improve team collaboration' into actionable steps",
                expected_agent="planning",
                expected_outcomes=["steps", "action", "plan"],
                requires_context=False,
                description="Tests goal decomposition"
            ),
            
            # Category 6: Multi-Agent Workflow
            TestCase(
                name="Complex Multi-Step Task",
                message="Research AI trends, analyze the findings, and create a comprehensive report",
                expected_agent="web_search",  # First agent in chain
                expected_outcomes=["research", "analysis", "report"],
                requires_context=False,
                description="Tests multi-agent collaboration"
            ),
        ]
        
        # Setup test environment
        self.setup_test_data()
        
        # Run all tests
        print("\n" + "="*70)
        print("[START] STARTING DELEGATION TEST SUITE")
        print("="*70)
        print(f"Total Tests: {len(test_cases)}")
        print(f"Session ID: {self.session_id}")
        print(f"Base URL: {self.base_url}")
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n[{i}/{len(test_cases)}]")
            result = self.run_test(test_case)
            self.results.append(result)
            
            # Small delay between tests to avoid overwhelming the server
            if i < len(test_cases):
                time.sleep(2)
        
        # Generate report
        self.generate_report()
    
    def generate_report(self):
        """Generate comprehensive test report"""
        
        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results if r.success)
        failed_tests = total_tests - successful_tests
        success_rate = (successful_tests / total_tests * 100) if total_tests > 0 else 0
        
        print("\n" + "="*70)
        print("[SUMMARY] TEST RESULTS SUMMARY")
        print("="*70)
        print(f"Total Tests: {total_tests}")
        print(f"[SUCCESS] Successful: {successful_tests}")
        print(f"[FAILED] Failed: {failed_tests}")
        print(f"[RATE] Success Rate: {success_rate:.1f}%")
        print(f"[TARGET] Required: 80%")
        
        if success_rate >= 80:
            print(f"[PASS] Status: PASS")
        else:
            print(f"[FAIL] Status: FAIL")
        
        # Detailed breakdown
        print("\n" + "="*70)
        print("[DETAILS] DETAILED RESULTS")
        print("="*70)
        
        for i, result in enumerate(self.results, 1):
            status = "[PASS]" if result.success else "[FAIL]"
            print(f"\n{i}. {status} {result.test_name}")
            print(f"   Agent: {result.agent_used}")
            print(f"   Result Integrated: {'PASS' if result.result_integrated else 'FAIL'}")
            print(f"   Context Passed: {'PASS' if result.context_passed else 'FAIL'}")
            print(f"   Time: {result.execution_time:.2f}s")
            if result.error_message:
                print(f"   [ERROR] {result.error_message}")
            if not result.success and result.response_preview:
                print(f"   Preview: {result.response_preview[:150]}...")
        
        # Performance metrics
        avg_time = sum(r.execution_time for r in self.results) / total_tests if total_tests > 0 else 0
        max_time = max((r.execution_time for r in self.results), default=0)
        min_time = min((r.execution_time for r in self.results), default=0)
        
        print("\n" + "="*70)
        print("[PERFORMANCE] PERFORMANCE METRICS")
        print("="*70)
        print(f"Average Execution Time: {avg_time:.2f}s")
        print(f"Maximum Execution Time: {max_time:.2f}s")
        print(f"Minimum Execution Time: {min_time:.2f}s")
        
        # Categorize results by agent
        agent_results = {}
        for result in self.results:
            agent = result.agent_used
            if agent not in agent_results:
                agent_results[agent] = {"total": 0, "success": 0}
            agent_results[agent]["total"] += 1
            if result.success:
                agent_results[agent]["success"] += 1
        
        print("\n" + "="*70)
        print("[AGENTS] RESULTS BY AGENT")
        print("="*70)
        for agent, stats in sorted(agent_results.items()):
            rate = (stats["success"] / stats["total"] * 100) if stats["total"] > 0 else 0
            status = "[PASS]" if rate >= 80 else "[WARN]" if rate >= 50 else "[FAIL]"
            print(f"{status} {agent}: {stats['success']}/{stats['total']} ({rate:.1f}%)")
        
        # Save to file
        filename = self.save_report_to_file()
        
        print("\n" + "="*70)
        print("[COMPLETE] EVALUATION COMPLETE")
        print("="*70)
        
        if success_rate >= 80:
            print("[SUCCESS] Agent meets Week 6 evaluation criteria!")
            print("Your delegation system is working excellently!")
        else:
            print("[WARNING] NEEDS IMPROVEMENT: Success rate below 80% threshold")
            print(f"Need {80 - success_rate:.1f}% improvement to pass")
            print("\nRecommendations:")
            print("   - Review failed test cases above")
            print("   - Check agent delegation logic")
            print("   - Verify context passing between agents")
            print("   - Ensure proper response integration")
        
        print(f"\n[REPORT] Detailed report saved to: {filename}")
    
    def save_report_to_file(self) -> str:
        """Save detailed report to JSON file"""
        report = {
            "metadata": {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "session_id": self.session_id,
                "base_url": self.base_url
            },
            "summary": {
                "total_tests": len(self.results),
                "successful": sum(1 for r in self.results if r.success),
                "failed": sum(1 for r in self.results if not r.success),
                "success_rate": (sum(1 for r in self.results if r.success) / len(self.results) * 100) if self.results else 0,
                "average_execution_time": sum(r.execution_time for r in self.results) / len(self.results) if self.results else 0
            },
            "results": [
                {
                    "test_name": r.test_name,
                    "success": r.success,
                    "agent_used": r.agent_used,
                    "result_integrated": r.result_integrated,
                    "context_passed": r.context_passed,
                    "execution_time": r.execution_time,
                    "response_preview": r.response_preview,
                    "error_message": r.error_message
                }
                for r in self.results
            ]
        }
        
        filename = f"delegation_test_results_{int(time.time())}.json"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            return filename
        except Exception as e:
            print(f"[WARNING] Could not save report to file: {str(e)}")
            return "report_not_saved.json"


# =========================================================
# MAIN EXECUTION
# =========================================================

def main():
    """Main execution function"""
    print("="*70)
    print("[TEST FRAMEWORK] DELEGATION TESTING FRAMEWORK")
    print("="*70)
    print("This script will test your agent's delegation capabilities")
    print("Ensure your server is running before proceeding!")
    print("="*70)
    
    # Allow custom base URL via command line
    base_url = "http://localhost:8000"
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
        print(f"Using custom base URL: {base_url}")
    
    tester = DelegationTester(base_url=base_url)
    
    try:
        tester.run_all_tests()
    except KeyboardInterrupt:
        print("\n\n[WARNING] Tests interrupted by user")
        if tester.results:
            tester.generate_report()
    except Exception as e:
        print(f"\n\n[FATAL] Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        if tester.results:
            print("\nGenerating partial report...")
            tester.generate_report()


if __name__ == "__main__":
    main()