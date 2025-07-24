import dspy
import json
from typing import Dict, List
from .sheets_client import SheetsClient
from .file_downloader import FileDownloader
from .trajectory_extractor import TrajectoryExtractor
from .evaluator import Evaluator
from .config import Config

# Configure DSPy
lm = dspy.LM(f'openai/{Config.EVALUATOR_MODEL}', api_key=Config.OPENAI_API_KEY, max_tokens=4000)
dspy.configure(lm=lm)

# Remove EVALUATION_SYSTEM_PROMPT and any evaluation logic or classes from this file.