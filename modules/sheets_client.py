import gspread
from google.oauth2.service_account import Credentials
import json
import pandas as pd
from typing import List, Dict, Any
from .config import Config

class SheetsClient:
    def __init__(self):
        self.client = None
        self.authenticate()
    
    def authenticate(self):
        """Authenticate with Google Sheets using service account from env variable"""
        try:
            scope = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            credentials = Credentials.from_service_account_info(
                json.loads(Config.GOOGLE_SERVICE_ACCOUNT_JSON),
                scopes=scope
            )
            self.client = gspread.authorize(credentials)
            print("✅ Successfully authenticated with Google Sheets")
        except Exception as e:
            print(f"❌ Error authenticating with Google Sheets: {e}")
            raise
    
    def get_worksheet(self, spreadsheet_id: str, worksheet_name: str = None):
        """Get worksheet object"""
        try:
            spreadsheet = self.client.open_by_key(spreadsheet_id)
            if worksheet_name:
                return spreadsheet.worksheet(worksheet_name)
            else:
                return spreadsheet.sheet1
        except Exception as e:
            print(f"❌ Error opening worksheet: {e}")
            raise
    
    def column_letter_to_index(self, col_letter: str) -> int:
        """Convert column letter(s) to zero-based index (A=0, B=1, ..., AA=26, AB=27, etc.)"""
        result = 0
        for i, char in enumerate(reversed(col_letter)):
            result += (ord(char) - ord('A') + 1) * (26 ** i)
        return result - 1
    
    def get_range_data(self, spreadsheet_id: str, start_row: int = None, end_row: int = None, worksheet_name: str = None) -> List[Dict]:
        """Get data from specified row range using config defaults"""
        
        # Use config defaults if not provided
        start_row = start_row or Config.DEFAULT_START_ROW
        end_row = end_row or Config.DEFAULT_END_ROW
        worksheet_name = worksheet_name or Config.DEFAULT_WORKSHEET
        
        try:
            worksheet = self.get_worksheet(spreadsheet_id, worksheet_name)
            
            # Find the rightmost column we need to read
            all_columns = [Config.TASK_ID_COLUMN, Config.IDEAL_STATES_COLUMN]
            for llm_config in Config.LLM_CONFIG.values():
                all_columns.extend([llm_config['trail_column'], llm_config['eval_column']])
            
            # Get the rightmost column
            rightmost_col = max(all_columns, key=lambda x: self.column_letter_to_index(x))
            
            # Build range
            range_name = f"A{start_row}:{rightmost_col}{end_row}"
            
            print(f"📊 Getting range: {range_name}")
            values = worksheet.get(range_name)
            
            print(f"📊 Retrieved {len(values)} rows from sheet")
            
            # Convert to structured data
            structured_data = []
            for row_idx, row in enumerate(values, start=start_row):
                print(f"\n[DEBUG] Row {row_idx} raw values: {row}")
                if len(row) < 2:  # Skip rows without minimum data
                    continue
                
                # Helper function to get column value
                def get_col_value(col_letter):
                    col_idx = self.column_letter_to_index(col_letter)
                    val = row[col_idx] if len(row) > col_idx else ""
                    print(f"[DEBUG] Col {col_letter} (idx {col_idx}): {val}")
                    return val
                
                row_data = {
                    'row_number': row_idx,
                    'task_id': get_col_value(Config.TASK_ID_COLUMN),
                    'ideal_end_states': get_col_value(Config.IDEAL_STATES_COLUMN),
                    'llm_files': {}
                }
                
                # Extract LLM file URLs using LLM_CONFIG
                for llm_name, llm_config in Config.LLM_CONFIG.items():
                    trail_col = llm_config['trail_column']
                    file_url = get_col_value(trail_col)
                    if file_url:
                        row_data['llm_files'][llm_name] = file_url
                
                structured_data.append(row_data)
            
            return structured_data
            
        except Exception as e:
            print(f"❌ Error getting range data: {e}")
            raise
    
    def write_individual_evaluation(self, spreadsheet_id: str, row_number: int, llm_name: str, evaluation_result: Dict, worksheet_name: str = None):
        """Write evaluation result for a specific LLM to its dedicated column"""
        try:
            worksheet = self.get_worksheet(spreadsheet_id, worksheet_name)
            
            # Get the evaluation column for this LLM
            if llm_name not in Config.LLM_CONFIG:
                raise ValueError(f"Unknown LLM name: {llm_name}")
            
            eval_col = Config.LLM_CONFIG[llm_name]['eval_column']
            cell_range = f"{eval_col}{row_number}"
            
            # Add metadata to the result
            result_with_metadata = {
                **evaluation_result,
                'metadata': {
                    **evaluation_result.get('metadata', {}),
                    'written_at': pd.Timestamp.now().isoformat(),
                    'cell_location': cell_range
                }
            }
            
            results_json = json.dumps(result_with_metadata, indent=2)
            
            worksheet.update(cell_range, [[results_json]])
            print(f"✅ Written {llm_name} evaluation to {cell_range}")
            
        except Exception as e:
            print(f"❌ Error writing {llm_name} evaluation to sheet: {e}")
            raise
    
    def batch_write_evaluations(self, spreadsheet_id: str, evaluation_results: List[Dict], worksheet_name: str = None):
        """Write multiple evaluation results to their respective columns"""
        try:
            worksheet = self.get_worksheet(spreadsheet_id, worksheet_name)
            
            # Group results by LLM and row for batch writing
            updates = []
            
            for result in evaluation_results:
                row_number = result['row_number']
                llm_name = result['metadata']['llm_name']
                
                # Get the evaluation column for this LLM
                if llm_name not in Config.LLM_CONFIG:
                    print(f"⚠️ Unknown LLM name: {llm_name}, skipping")
                    continue
                
                eval_col = Config.LLM_CONFIG[llm_name]['eval_column']
                cell_range = f"{eval_col}{row_number}"
                
                # Add metadata
                result_with_metadata = {
                    **result,
                    'metadata': {
                        **result.get('metadata', {}),
                        'written_at': pd.Timestamp.now().isoformat(),
                        'cell_location': cell_range
                    }
                }
                
                results_json = json.dumps(result_with_metadata, indent=2)
                
                updates.append({
                    'range': cell_range,
                    'values': [[results_json]]
                })
            
            # Batch update all cells
            if updates:
                worksheet.batch_update(updates)
                print(f"✅ Batch written {len(updates)} evaluations to their respective columns")
                
                # Print summary of what was written
                llm_counts = {}
                for update in updates:
                    # Extract column from range (e.g., "AB5" -> "AB")
                    col_letter = ''.join(c for c in update['range'] if c.isalpha())
                    llm_name = self.get_llm_name_by_eval_column(col_letter)
                    llm_counts[llm_name] = llm_counts.get(llm_name, 0) + 1
                
                for llm_name, count in llm_counts.items():
                    print(f"  - {llm_name}: {count} evaluations")
            
        except Exception as e:
            print(f"❌ Error batch writing evaluations: {e}")
            raise
    
    def get_llm_name_by_eval_column(self, column_letter: str) -> str:
        """Helper function to get LLM name by its evaluation column"""
        for llm_name, config in Config.LLM_CONFIG.items():
            if config['eval_column'] == column_letter:
                return config['display_name']
        return f"Column {column_letter}"
    
    def clear_evaluation_columns(self, spreadsheet_id: str, start_row: int, end_row: int, llm_names: List[str] = None, worksheet_name: str = None):
        """Clear evaluation columns for specified LLMs and row range"""
        try:
            worksheet = self.get_worksheet(spreadsheet_id, worksheet_name)
            
            # Default to all LLMs if none specified
            if llm_names is None:
                llm_names = Config.LLM_NAMES
            
            # Clear each LLM's evaluation column
            ranges_to_clear = []
            for llm_name in llm_names:
                if llm_name in Config.LLM_CONFIG:
                    eval_col = Config.LLM_CONFIG[llm_name]['eval_column']
                    range_to_clear = f"{eval_col}{start_row}:{eval_col}{end_row}"
                    ranges_to_clear.append(range_to_clear)
                    print(f"🧹 Will clear {llm_name} evaluation column: {range_to_clear}")
            
            # Batch clear all ranges
            if ranges_to_clear:
                worksheet.batch_clear(ranges_to_clear)
                print(f"✅ Cleared {len(ranges_to_clear)} evaluation columns")
            
        except Exception as e:
            print(f"❌ Error clearing evaluation columns: {e}")
            raise