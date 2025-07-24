import json
from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class ToolCall:
    tool_name: str
    parameters: Dict[str, str]  # String format for consistent comparison
    # Removed timestamp - not needed for evaluation

@dataclass
class ConversationTurn:
    user_prompt: str
    tool_calls: List[ToolCall]
    # Removed response - not needed for evaluation

class TrajectoryExtractor:
    def __init__(self):
        pass
    
    def normalize_parameters(self, parameters: Dict[str, Any]) -> Dict[str, str]:
        """Convert parameters to string format for consistent comparison"""
        normalized = {}
        for key, value in parameters.items():
            if isinstance(value, (dict, list)):
                normalized[key] = json.dumps(value, sort_keys=True)
            elif value is None:
                normalized[key] = "null"
            else:
                normalized[key] = str(value)
        return normalized
    
    def extract_trajectory(self, conversation_data: Dict) -> List[ConversationTurn]:
        """Extract conversation turns from logged trajectory - focus only on tool calls"""
        if not conversation_data or 'traj' not in conversation_data:
            print("❌ No trajectory data found")
            return []
        
        turns = []
        current_turn = None
        
        try:
            for item in conversation_data['traj']:
                if item.get('role') == 'user':
                    # Save previous turn if exists
                    if current_turn:
                        turns.append(current_turn)
                    
                    # Start new turn
                    current_turn = ConversationTurn(
                        user_prompt=item.get('content', '').strip(),
                        tool_calls=[]
                    )
                
                elif item.get('role') == 'assistant' and current_turn:
                    # Extract only tool calls from assistant response
                    tool_calls = item.get('tool_calls', [])
                    
                    for tool_call in tool_calls:
                        if isinstance(tool_call, dict):
                            tool_name = tool_call.get('tool', '')
                            parameters = tool_call.get('parameters', {})
                            
                            # Skip if no tool name
                            if not tool_name:
                                continue
                            
                            # Normalize parameters to strings for comparison
                            string_params = self.normalize_parameters(parameters)
                            
                            current_turn.tool_calls.append(ToolCall(
                                tool_name=tool_name,
                                parameters=string_params
                            ))
            
            # Don't forget the last turn
            if current_turn:
                turns.append(current_turn)
            
            # Filter out turns with no tool calls for cleaner evaluation
            turns_with_tools = [turn for turn in turns if turn.tool_calls]
            
            print(f"✅ Extracted {len(turns_with_tools)} turns with tool calls from {len(turns)} total turns")
            return turns_with_tools
            
        except Exception as e:
            print(f"❌ Error extracting trajectory: {e}")
            return []
    
    def format_for_evaluation(self, trajectory: List[ConversationTurn]) -> str:
        """Format trajectory for the evaluator - only tool calls and user prompts"""
        formatted_turns = []
        
        for turn in trajectory:
            turn_data = {
                'user_prompt': turn.user_prompt,
                'tool_calls': []
            }
            
            for tool_call in turn.tool_calls:
                turn_data['tool_calls'].append({
                    'tool_name': tool_call.tool_name,
                    'parameters': tool_call.parameters
                })
            
            formatted_turns.append(turn_data)
        
        return json.dumps(formatted_turns, indent=2)
    
    def extract_ideal_states(self, ideal_states_json: str) -> List[Dict]:
        """Extract and validate ideal end states - expecting array format"""
        try:
            if not ideal_states_json or ideal_states_json.strip() == "":
                return []
            
            ideal_states = json.loads(ideal_states_json)
            
            # Handle both array and object formats
            if isinstance(ideal_states, list):
                print(f"✅ Parsed ideal states array with {len(ideal_states)} entries")
                return ideal_states
            elif isinstance(ideal_states, dict):
                # Convert object format to array format
                converted = []
                for user_prompt, data in ideal_states.items():
                    converted.append({
                        'user_prompt': user_prompt,
                        'ideal_tool_calls': data.get('ideal_tool_calls', [])
                    })
                print(f"✅ Converted ideal states object to array with {len(converted)} entries")
                return converted
            else:
                print("❌ Invalid ideal states format")
                return []
                
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing ideal states JSON: {e}")
            return []
        except Exception as e:
            print(f"❌ Unexpected error parsing ideal states: {e}")
            return []