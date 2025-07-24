import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    GOOGLE_SHEETS_CREDENTIALS = os.getenv('GOOGLE_SHEETS_CREDENTIALS', 'credentials/service_account.json')
    SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
    GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
    
    # =====================================================
    # HARDCODED INPUT PARAMETERS - CHANGE THESE AS NEEDED
    # =====================================================
    
    # ROW RANGE TO EVALUATE
    DEFAULT_START_ROW = 4    # Change this to start from different row
    DEFAULT_END_ROW = 4     # Change this to end at different row
    
    # WORKSHEET NAME (optional)
    DEFAULT_WORKSHEET = "Sigma"  # Change to "Sheet1" or specific sheet name
    
    LLM_CONFIG = {
        'claude_sonnet_37': {
            'trail_column': 'J',
            'eval_column': 'K',
            'display_name': 'Claude Sonnet 3.7'
        },
        'gemini_25_flash': {
            'trail_column': 'O',
            'eval_column': 'P',
            'display_name': 'Gemini 2.5 Flash'
        },
        'gpt_4o': {
            'trail_column': 'AB',
            'eval_column': 'AC',
            'display_name': 'GPT-4o'
        },
        'llama_4_maverick_17b': {
            'trail_column': 'AK',
            'eval_column': 'AL',
            'display_name': 'Llama 4 Maverick 17B'
        },
        'qwen_25_72b': {
            'trail_column': 'AN',
            'eval_column': 'AO',
            'display_name': 'Qwen 2.5 72B'
        }
    }

    # ADD THESE CONSTANTS:
    TASK_ID_COLUMN = 'A'
    IDEAL_STATES_COLUMN = 'H'  # Update this to your actual column
    
    # DERIVED LISTS FOR BACKWARD COMPATIBILITY
    LLM_NAMES = list(LLM_CONFIG.keys())
    
    # EVALUATION SETTINGS
    EVALUATOR_MODEL = "gpt-4o"  # Model used for evaluation
    MAX_OUTPUT_TOKENS = 8192         # Max tokens for the evaluator's output to prevent truncation
    MAX_RETRIES = 3                  # Number of retries for failed evaluations
    TIMEOUT_SECONDS = 60             # Timeout for each evaluation
    
    # FILE MANAGEMENT
    CLEANUP_OLD_FILES_DAYS = 7       # Delete downloaded files older than this
    SAVE_BACKUP_RESULTS = True       # Save results locally as backup
    
    # =====================================================
    # DIRECTORY STRUCTURE - USUALLY NO NEED TO CHANGE
    # =====================================================
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    DOWNLOAD_DIR = os.path.join(DATA_DIR, 'downloaded_files')
    RESULTS_DIR = os.path.join(DATA_DIR, 'results')
    
    # EVALUATION RUBRIC - MODIFY WEIGHTS IF NEEDED
    EVALUATION_RUBRIC = {
        "final_score_formula": "final_score = (tool_selection_score * 0.30) + (tool_sequencing_score * 0.25) + (function_execution_score * 0.30) + (efficiency_score * 0.15)",
        "rubrics": {
            "Tool Selection": {
                "weight": 0.30,
                "labels": {
                    "Completely Appropriate": {"score": 10, "definition": "Selected tools were the best possible choices and fully aligned with the user intent."},
                    "Partially Appropriate": {"score": 7, "definition": "Selected tools were reasonable alternatives that supported achieving the user intent, though not optimal."},
                    "Inappropriate (Non-impacting)": {"score": 3, "definition": "Selected tools were incorrect but did not prevent successful achievement of the user intent."},
                    "Inappropriate (Impacting)": {"score": 0, "definition": "Selected tools were incorrect or no tool was used and led to failure or compromise in achieving the user intent."}
                }
            },
            "Tool Sequencing": {
                "weight": 0.25,
                "labels": {
                    "Completely Correct": {"score": 10, "definition": "Sequence of tools used was entirely correct and aligned with the optimal flow to achieve the user intent."},
                    "Partially Correct": {"score": 6, "definition": "Sequence of tools was not ideal, but it did not affect the successful achievement of the user intent."},
                    "Incorrect": {"score": 0, "definition": "Sequence of tools was incorrect and negatively affected or prevented the fulfillment of the user intent."}
                }
            },
            "Function Execution": {
                "weight": 0.30,
                "labels": {
                    "Complete Execution": {"score": 10, "definition": "All parameters and constraints used to execute the function were correct and aligned with the intended use."},
                    "Partial Execution": {"score": 5, "definition": "Selected parameters were irrelevant or suboptimal but did not affect the successful achievement of the user intent."},
                    "Incorrect Execution": {"score": 0, "definition": "Selected parameters were incorrect or irrelevant and negatively affected or prevented the achievement of the user intent."}
                }
            },
            "Efficiency": {
                "weight": 0.15,
                "labels": {
                    "Completely Efficient": {"score": 10, "definition": "The LLM chose the best and shortest path to achieve the correct output, completing the task with minimal and accurate steps."},
                    "Partially Efficient": {"score": 6, "definition": "The LLM took unnecessary steps, but they did not interfere with the successful completion of the task."},
                    "Inefficient": {"score": 0, "definition": "The LLM took unnecessary or redundant steps that led to confusion, delay, or failure in achieving the user intent."}
                }
            }
        }
    }

# Create directories if they don't exist
for directory in [Config.DATA_DIR, Config.DOWNLOAD_DIR, Config.RESULTS_DIR]:
    os.makedirs(directory, exist_ok=True)

# Create LLM-specific directories
for llm_name in Config.LLM_NAMES:
    llm_dir = os.path.join(Config.DOWNLOAD_DIR, llm_name)
    os.makedirs(llm_dir, exist_ok=True)