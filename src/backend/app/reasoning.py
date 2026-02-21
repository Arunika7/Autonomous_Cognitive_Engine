import json
import re
import logging

logger = logging.getLogger(__name__)

def robust_parse_json(content: str) -> dict:
    """
    Robustly parse JSON from LLM output with multiple fallback strategies.
    
    Args:
        content: Raw string output from LLM
        
    Returns:
        Parsed dictionary or fallback error response
    """
    if not content or not isinstance(content, str):
        logger.error("Invalid content provided to robust_parse_json")
        return {
            "action": "respond",
            "response": "Error: Invalid response format",
            "reasoning": "Content validation failed"
        }
    
    # Strategy 1: Direct JSON parse
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        logger.debug("Direct JSON parse failed, trying cleanup strategies")
    
    # Strategy 2: Remove markdown code blocks
    cleaned = content.strip()
    

    if "```json" in cleaned:
        cleaned = re.sub(r'```json\s*', '', cleaned)
        cleaned = re.sub(r'```\s*$', '', cleaned)
    elif "```" in cleaned:
        cleaned = re.sub(r'```\s*', '', cleaned)
    

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.debug("Cleaned JSON parse failed, trying extraction")
    
    # Strategy 3: Extract JSON object from text

    json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            logger.debug("Extracted JSON parse failed")
    
    # Strategy 4: Try to find JSON-like structure and fix common issues
    try:
     
        fixed = cleaned.replace("'", '"')
        
        
        fixed = re.sub(r'\bTrue\b', 'true', fixed)
        fixed = re.sub(r'\bFalse\b', 'false', fixed)
        fixed = re.sub(r'\bNone\b', 'null', fixed)
        
        return json.loads(fixed)
    except json.JSONDecodeError:
        logger.debug("Fixed JSON parse failed")
    
    # Strategy 5: Try to extract key fields manually
    try:
        result = {}
        
        # Extract action
        action_match = re.search(r'"action"\s*:\s*"([^"]+)"', content)
        if action_match:
            result["action"] = action_match.group(1)
        
        # Extract reasoning
        reasoning_match = re.search(r'"reasoning"\s*:\s*"([^"]+)"', content)
        if reasoning_match:
            result["reasoning"] = reasoning_match.group(1)
        
        # Extract response
        response_match = re.search(r'"response"\s*:\s*"([^"]+)"', content)
        if response_match:
            result["response"] = response_match.group(1)
        
        # Extract tool_name
        tool_match = re.search(r'"tool_name"\s*:\s*"([^"]+)"', content)
        if tool_match:
            result["tool_name"] = tool_match.group(1)
        
        # Extract agent_name
        agent_match = re.search(r'"agent_name"\s*:\s*"([^"]+)"', content)
        if agent_match:
            result["agent_name"] = agent_match.group(1)
        
        # Extract tool_params as a dict
        params_match = re.search(r'"tool_params"\s*:\s*(\{[^}]+\})', content)
        if params_match:
            try:
                result["tool_params"] = json.loads(params_match.group(1))
            except:
                result["tool_params"] = {}
        
        if result.get("action"):
            logger.warning(f"Used manual extraction for parsing, result: {result}")
            return result
    except Exception as e:
        logger.error(f"Manual extraction failed: {e}")
    
    # Strategy 6: Ultimate fallback - return error response
    logger.error(f"All JSON parsing strategies failed for content: {content[:200]}...")
    
    return {
        "action": "respond",
        "response": "I encountered a formatting error in my response. Could you please try rephrasing your request?",
        "reasoning": "JSON parsing completely failed"
    }


def extract_code_blocks(content: str) -> list[dict]:
    """
    Extract code blocks from markdown-formatted content.
    
    Args:
        content: String containing markdown code blocks
        
    Returns:
        List of dicts with 'language' and 'code' keys
    """
    pattern = r'```(\w+)?\n(.*?)```'
    matches = re.findall(pattern, content, re.DOTALL)
    
    return [
        {"language": lang or "text", "code": code.strip()}
        for lang, code in matches
    ]


def sanitize_json_string(s: str) -> str:
    """
    Sanitize a string to be valid JSON string content.
    
    Args:
        s: Input string
        
    Returns:
        Sanitized string safe for JSON
    """
    # Escape backslashes
    s = s.replace('\\', '\\\\')
    
    # Escape quotes
    s = s.replace('"', '\\"')
    
    # Escape newlines
    s = s.replace('\n', '\\n')
    s = s.replace('\r', '\\r')
    
    # Escape tabs
    s = s.replace('\t', '\\t')
    
    return s


def validate_decision_structure(decision: dict) -> tuple[bool, str]:
    """
    Validate that a decision dict has required fields.
    
    Args:
        decision: Decision dictionary to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(decision, dict):
        return False, "Decision must be a dictionary"
    
    # Check action field
    if "action" not in decision:
        return False, "Missing required field: action"
    
    action = decision["action"]
    if action not in ["tool", "delegate", "respond"]:
        return False, f"Invalid action: {action}. Must be 'tool', 'delegate', or 'respond'"
    
    # Validate based on action type
    if action == "tool":
        if "tool_name" not in decision:
            return False, "tool action requires tool_name field"
    
    elif action == "delegate":
        if "agent_name" not in decision:
            return False, "delegate action requires agent_name field"
    
    elif action == "respond":
        if "response" not in decision:
            return False, "respond action requires response field"
    
    # Check reasoning 
    if "reasoning" not in decision:
        logger.warning("Decision missing reasoning field")
    
    return True, ""


def merge_partial_jsons(parts: list[str]) -> dict:
    """
    Merge multiple partial JSON strings into a complete object.
    Useful for streaming LLM responses.
    
    Args:
        parts: List of partial JSON strings
        
    Returns:
        Merged dictionary
    """
    combined = "".join(parts)
    return robust_parse_json(combined)