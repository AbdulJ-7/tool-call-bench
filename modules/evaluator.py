import dspy
import json
from typing import Dict, List
from .config import Config

# Configure DSPy
lm = dspy.LM(f'openai/{Config.EVALUATOR_MODEL}', api_key=Config.OPENAI_API_KEY, max_tokens=Config.MAX_OUTPUT_TOKENS)
dspy.configure(lm=lm)

class TrajectoryEvaluator(dspy.Signature):
    """
EVALUATION TASK:

You are an expert evaluator of LLM-powered conversational agents. Your job is to analyze a logged conversation trajectory (user prompts and tool calls) and compare it to the ideal end states (the perfect tool calls for each user prompt).

Your evaluation must be detailed, fair, and robust to minor differences in tool names or parameter phrasing.

TOOL EQUIVALENCE (CRITICAL!):
- Treat the following tool names as **exactly equivalent** (no points should be deducted for using any variant):
    - "web_search", "websearch", "search", "google_search"
    - "youtube_search", "youtube", "yt_search"
    - "wikipedia_search", "wikipedia", "wiki"
    - "amadeus_travel", "amadeus", "travel_search", "flight_search"
    - "google_places", "places_search", "places"
    - "current_time", "time", "get_time"
    - "calculator", "calc", "math"
    - "email_sender", "send_email", "email"
- **Do not penalize** for capitalization, underscores, or minor spelling differences if the tool is clearly intended to be the same.

PARAMETER/INTENT MATCHING:
- Parameters are considered a match if they accomplish the same semantic intent, even if the wording is different.
- Focus on whether the agent's tool call would achieve the user's goal, not on exact string matches.

EVALUATION CATEGORIES (Score 0-10 each):

1. TOOL SELECTION (0-10):
    - 10: All tool choices are ideal or equivalent (see above).
    - 7: Reasonable alternatives that work, but not the ideal tool.
    - 3: Poor tool choices, but the task is still possible.
    - 0: Wrong tools that prevent success.

2. TOOL SEQUENCING (0-10):
    - 10: Perfect sequence matching the ideal order.
    - 6: Minor sequence issues, but the task is still completed.
    - 0: Wrong sequence that prevents or degrades success.

3. FUNCTION EXECUTION (0-10):
    - 10: Parameters perfectly match the intended goal.
    - 5: Parameters are suboptimal but functional.
    - 0: Parameters are wrong and prevent success.

4. EFFICIENCY (0-10):
    - 10: Minimal, optimal steps to complete the task.
    - 6: Some unnecessary steps, but the task is completed.
    - 0: Very inefficient, redundant, or causes failure.

SCORING FORMULA:
    final_score = (tool_selection × 0.30) + (tool_sequencing × 0.25) + (function_execution × 0.30) + (efficiency × 0.15)

INSTRUCTIONS:
- For each user prompt, compare the logged tool calls to the ideal tool calls.
- Justify every score with clear reasoning, especially when deducting points.
- For tool equivalence, **never deduct points** for using any of the equivalent tool names above.
- Provide a detailed per-turn analysis, including the user prompt, logged tools, ideal tools, and your analysis.

OUTPUT FORMAT:
Return a JSON object:
{
  "evaluation_summary": {
    "tool_selection": {"score": ..., "justification": "..."},
    "tool_sequencing": {"score": ..., "justification": "..."},
    "function_execution": {"score": ..., "justification": "..."},
    "efficiency": {"score": ..., "justification": "..."}
  },
  "final_score": ...,
  "per_turn_analysis": [
    {
      "user_prompt": "...",
      "logged_tools": [...],
      "ideal_tools": [...],
      "analysis": "..."
    }
  ]
}
"""
    
    logged_trajectory: str = dspy.InputField(desc="JSON string of logged conversation with user prompts and tool calls")
    ideal_end_states: str = dspy.InputField(desc="JSON string of ideal tool calls for each user prompt")
    
    tool_selection_score: int = dspy.OutputField(desc="Score 0-10 for tool selection accuracy")
    tool_selection_justification: str = dspy.OutputField(desc="Detailed justification for tool selection score")
    
    tool_sequencing_score: int = dspy.OutputField(desc="Score 0-10 for tool sequencing accuracy") 
    tool_sequencing_justification: str = dspy.OutputField(desc="Detailed justification for tool sequencing score")
    
    function_execution_score: int = dspy.OutputField(desc="Score 0-10 for parameter execution accuracy")
    function_execution_justification: str = dspy.OutputField(desc="Detailed justification for function execution score")
    
    efficiency_score: int = dspy.OutputField(desc="Score 0-10 for task completion efficiency")
    efficiency_justification: str = dspy.OutputField(desc="Detailed justification for efficiency score")
    
    per_turn_analysis: str = dspy.OutputField(desc="JSON array with detailed analysis for each user prompt comparing logged vs ideal tool calls")

class Evaluator:
    def __init__(self):
        # Single unified evaluator following the working keynode pattern
        self.evaluator = dspy.ChainOfThought(TrajectoryEvaluator)
        self.rubric = Config.EVALUATION_RUBRIC
    
    def evaluate_trajectory(self, trajectory_json: str, ideal_states: List[Dict], llm_name: str, task_id: str) -> Dict:
        """Evaluate a single trajectory against ideal end states using unified evaluator"""
        try:
            print(f"🔍 Evaluating {llm_name} for task {task_id}")
            
            # Format inputs exactly like the working keynode evaluation
            ideal_states_json = json.dumps(ideal_states, indent=2)
            
            # Run the unified evaluation
            result = self.evaluator(
                logged_trajectory=trajectory_json,
                ideal_end_states=ideal_states_json
            )
            
            # Validate and clean scores (same as keynode approach)
            tool_selection_score = self.validate_score(result.tool_selection_score)
            tool_sequencing_score = self.validate_score(result.tool_sequencing_score)
            function_execution_score = self.validate_score(result.function_execution_score)
            efficiency_score = self.validate_score(result.efficiency_score)
            
            # Calculate final score using rubric weights
            final_score = self.calculate_final_score(
                tool_selection_score,
                tool_sequencing_score,
                function_execution_score,
                efficiency_score
            )
            
            # Parse per-turn analysis
            per_turn_analysis = self.parse_per_turn_analysis(result.per_turn_analysis)
            
            # Build final evaluation result in the required format
            evaluation_result = {
                'evaluation_summary': {
                    'tool_selection': {
                        'score': tool_selection_score,
                        'justification': result.tool_selection_justification
                    },
                    'tool_sequencing': {
                        'score': tool_sequencing_score,
                        'justification': result.tool_sequencing_justification
                    },
                    'function_execution': {
                        'score': function_execution_score,
                        'justification': result.function_execution_justification
                    },
                    'efficiency': {
                        'score': efficiency_score,
                        'justification': result.efficiency_justification
                    }
                },
                'final_score': final_score,
                'per_turn_analysis': per_turn_analysis,
                'metadata': {
                    'llm_name': llm_name,
                    'task_id': task_id,
                    'evaluator_model': Config.EVALUATOR_MODEL,
                    'evaluation_success': True
                }
            }
            
            print(f"✅ Evaluation completed for {llm_name} - Score: {final_score}")
            return evaluation_result
            
        except Exception as e:
            print(f"❌ Error evaluating {llm_name}: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                'error': str(e),
                'evaluation_summary': {
                    'tool_selection': {'score': 0, 'justification': f'Error during evaluation: {str(e)}'},
                    'tool_sequencing': {'score': 0, 'justification': f'Error during evaluation: {str(e)}'},
                    'function_execution': {'score': 0, 'justification': f'Error during evaluation: {str(e)}'},
                    'efficiency': {'score': 0, 'justification': f'Error during evaluation: {str(e)}'}
                },
                'final_score': 0.0,
                'per_turn_analysis': [],
                'metadata': {
                    'llm_name': llm_name,
                    'task_id': task_id,
                    'evaluator_model': Config.EVALUATOR_MODEL,
                    'evaluation_success': False
                }
            }
    
    def validate_score(self, score) -> int:
        """Validate and clean score to ensure it's an integer between 0-10"""
        try:
            if isinstance(score, str):
                # Try to extract number from string
                import re
                match = re.search(r'\d+', score)
                if match:
                    score = int(match.group())
                else:
                    return 0
            
            score = int(score)
            return max(0, min(10, score))  # Clamp between 0-10
        except (ValueError, TypeError):
            return 0
    
    def parse_per_turn_analysis(self, analysis_text: str) -> List[Dict]:
        """Parse per-turn analysis from text to list format"""
        try:
            # Try to parse as JSON first
            if analysis_text.strip().startswith('[') or analysis_text.strip().startswith('{'):
                return json.loads(analysis_text)
            
            # If not JSON, create structured analysis from text
            # This is a fallback - ideally the LLM should return JSON
            lines = analysis_text.split('\n')
            analysis_list = []
            current_analysis = {}
            
            for line in lines:
                line = line.strip()
                if line.startswith('User:') or line.startswith('User Prompt:'):
                    if current_analysis:
                        analysis_list.append(current_analysis)
                    current_analysis = {
                        'user_prompt': line.replace('User:', '').replace('User Prompt:', '').strip(),
                        'logged_tools': [],
                        'ideal_tools': [],
                        'analysis': ''
                    }
                elif line.startswith('Analysis:') or line.startswith('Comparison:'):
                    if current_analysis:
                        current_analysis['analysis'] = line.replace('Analysis:', '').replace('Comparison:', '').strip()
                elif line and current_analysis:
                    current_analysis['analysis'] += ' ' + line
            
            if current_analysis:
                analysis_list.append(current_analysis)
            
            return analysis_list if analysis_list else []
            
        except (json.JSONDecodeError, AttributeError, Exception):
            # Return empty list if parsing fails
            return []
    
    def calculate_final_score(self, tool_selection: int, tool_sequencing: int, function_execution: int, efficiency: int) -> float:
        """Calculate final score using the rubric weights"""
        try:
            weights = {
                'tool_selection': 0.30,
                'tool_sequencing': 0.25,
                'function_execution': 0.30,
                'efficiency': 0.15
            }
            
            final_score = (
                tool_selection * weights['tool_selection'] +
                tool_sequencing * weights['tool_sequencing'] +
                function_execution * weights['function_execution'] +
                efficiency * weights['efficiency']
            )
            
            return round(final_score, 2)
        except Exception as e:
            print(f"Error calculating final score: {e}")
            return 0.0
    
    def batch_evaluate(self, evaluation_tasks: List[Dict]) -> List[Dict]:
        """Evaluate multiple trajectories"""
        results = []
        
        total_tasks = len(evaluation_tasks)
        for idx, task in enumerate(evaluation_tasks, 1):
            print(f"\n📊 Processing evaluation {idx}/{total_tasks}")
            
            result = self.evaluate_trajectory(
                trajectory_json=task['trajectory_json'],
                ideal_states=task['ideal_states'],
                llm_name=task['llm_name'],
                task_id=task['task_id']
            )
            
            result['row_number'] = task['row_number']
            results.append(result)
        
        # Print summary
        successful = len([r for r in results if r.get('metadata', {}).get('evaluation_success', False)])
        print(f"\n📈 Batch evaluation completed: {successful}/{total_tasks} successful")
        
        return results