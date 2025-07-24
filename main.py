#!/usr/bin/env python3

import os
import sys
import json
import pandas as pd
from datetime import datetime
from typing import List, Dict
from modules import SheetsClient, FileDownloader, TrajectoryExtractor, Evaluator, Config

class LLMEvaluationRunner:
    def __init__(self):
        self.sheets_client = SheetsClient()
        self.file_downloader = FileDownloader()
        self.trajectory_extractor = TrajectoryExtractor()
        self.evaluator = Evaluator()
        
        print("🚀 LLM Evaluation Runner initialized")
        print(f"📊 Spreadsheet ID: {Config.SPREADSHEET_ID}")
        print(f"📁 Download directory: {Config.DOWNLOAD_DIR}")
        print(f"📋 Default row range: {Config.DEFAULT_START_ROW} to {Config.DEFAULT_END_ROW}")
        
        # Print LLM configuration
        print("\n🤖 LLM Configuration:")
        for llm_name, config in Config.LLM_CONFIG.items():
            print(f"  {config['display_name']}: Trail={config['trail_column']}, Eval={config['eval_column']}")
    
    def run_evaluation(self, start_row: int = None, end_row: int = None, worksheet_name: str = None, clear_existing: bool = False):
        """Run complete evaluation pipeline with separate columns for each LLM"""
        
        # Use config defaults if not provided
        start_row = start_row or Config.DEFAULT_START_ROW
        end_row = end_row or Config.DEFAULT_END_ROW
        worksheet_name = worksheet_name or Config.DEFAULT_WORKSHEET
        
        print(f"\n📋 Starting evaluation for rows {start_row} to {end_row}")
        
        # Optional: Clear existing evaluations
        if clear_existing:
            print("\n🧹 Clearing existing evaluations...")
            self.sheets_client.clear_evaluation_columns(
                Config.SPREADSHEET_ID, start_row, end_row, worksheet_name=worksheet_name
            )
        
        # Step 1: Get data from Google Sheets
        print("\n1️⃣ Fetching data from Google Sheets...")
        sheet_data = self.sheets_client.get_range_data(
            Config.SPREADSHEET_ID, start_row, end_row, worksheet_name
        )
        
        if not sheet_data:
            print("❌ No data found in the specified range")
            return
        
        # Step 2: Download files and extract trajectories
        print("\n2️⃣ Downloading files and extracting trajectories...")
        evaluation_tasks = []
        
        for row_data in sheet_data:
            print(f"\n📝 Processing row {row_data['row_number']}: {row_data['task_id']}")
            
            # Parse ideal end states
            ideal_states = self.trajectory_extractor.extract_ideal_states(
                row_data['ideal_end_states']
            )
            
            if not ideal_states:
                print(f"⚠️ No ideal states found for row {row_data['row_number']}")
                continue
            
            # Download LLM files
            downloaded_files = self.file_downloader.download_llm_files(row_data)
            
            # Extract trajectories for each LLM
            for llm_name, file_info in downloaded_files.items():
                trajectory = self.trajectory_extractor.extract_trajectory(file_info['data'])
                
                if trajectory:
                    trajectory_json = self.trajectory_extractor.format_for_evaluation(trajectory)
                    
                    evaluation_tasks.append({
                        'row_number': row_data['row_number'],
                        'task_id': row_data['task_id'],
                        'llm_name': llm_name,
                        'trajectory_json': trajectory_json,
                        'ideal_states': ideal_states
                    })
                else:
                    print(f"⚠️ No trajectory extracted for {llm_name} in row {row_data['row_number']}")
        
        if not evaluation_tasks:
            print("❌ No valid evaluation tasks found")
            return
        
        print(f"\n📊 Prepared {len(evaluation_tasks)} evaluation tasks")
        
        # Step 3: Run evaluations
        print("\n3️⃣ Running evaluations...")
        evaluation_results = self.evaluator.batch_evaluate(evaluation_tasks)
        
        # Step 4: Write individual results back to the sheet
        print("\n4️⃣ Writing individual results to Google Sheets...")
        self.write_individual_results(evaluation_results, worksheet_name)
        
        # Step 5: Generate summary
        print("\n5️⃣ Generating summary...")
        self.generate_summary(evaluation_results)
        
        return evaluation_results
    
    def write_individual_results(self, evaluation_results: List[Dict], worksheet_name: str = None):
        """Write each evaluation result to its corresponding LLM column"""
        try:
            # Write results using batch update for efficiency
            self.sheets_client.batch_write_evaluations(Config.SPREADSHEET_ID, evaluation_results, worksheet_name=worksheet_name)
            
            # Save backup if configured
            if Config.SAVE_BACKUP_RESULTS:
                self.save_results_locally(evaluation_results)
                
        except Exception as e:
            print(f"❌ Error writing individual results: {e}")
            # Always save locally if writing to sheet fails
            self.save_results_locally(evaluation_results)
    
    def save_results_locally(self, evaluation_results: List[Dict]):
        """Save results locally as backup, organized by LLM"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Group results by LLM
        results_by_llm = {}
        for result in evaluation_results:
            llm_name = result['metadata']['llm_name']
            if llm_name not in results_by_llm:
                results_by_llm[llm_name] = []
            results_by_llm[llm_name].append(result)
        
        # Save overall results
        overall_filename = f"evaluation_results_{timestamp}.json"
        overall_filepath = os.path.join(Config.RESULTS_DIR, overall_filename)
        
        with open(overall_filepath, 'w', encoding='utf-8') as f:
            json.dump(evaluation_results, f, indent=2)
        
        print(f"💾 Overall results saved: {overall_filepath}")
        
        # Save individual LLM results
        for llm_name, llm_results in results_by_llm.items():
            llm_filename = f"evaluation_results_{llm_name}_{timestamp}.json"
            llm_filepath = os.path.join(Config.RESULTS_DIR, llm_filename)
            
            with open(llm_filepath, 'w', encoding='utf-8') as f:
                json.dump(llm_results, f, indent=2)
            
            print(f"💾 {llm_name} results saved: {llm_filepath}")
    
    def generate_summary(self, evaluation_results: List[Dict]):
        """Generate and display evaluation summary"""
        print("\n📊 EVALUATION SUMMARY")
        print("=" * 60)
        
        # Overall statistics
        total_evaluations = len(evaluation_results)
        successful_evaluations = [r for r in evaluation_results if r.get('metadata', {}).get('evaluation_success', False)]
        
        print(f"📈 Total evaluations: {total_evaluations}")
        print(f"✅ Successful evaluations: {len(successful_evaluations)}")
        print(f"❌ Failed evaluations: {total_evaluations - len(successful_evaluations)}")
        
        if successful_evaluations:
            # Score statistics
            scores = [r.get('final_score', 0) for r in successful_evaluations]
            avg_score = sum(scores) / len(scores)
            
            print(f"📊 Average score: {avg_score:.2f}")
            print(f"📊 Score range: {min(scores):.2f} - {max(scores):.2f}")
            
            # LLM performance comparison
            print("\n🏆 LLM Performance Ranking:")
            llm_scores = {}
            for result in successful_evaluations:
                llm_name = result['metadata']['llm_name']
                score = result.get('final_score', 0)
                
                if llm_name not in llm_scores:
                    llm_scores[llm_name] = []
                llm_scores[llm_name].append(score)
            
            # Calculate averages and rank
            llm_averages = {}
            for llm_name, scores in llm_scores.items():
                llm_averages[llm_name] = sum(scores) / len(scores)
            
            ranked_llms = sorted(llm_averages.items(), key=lambda x: x[1], reverse=True)
            
            for rank, (llm_name, avg_score) in enumerate(ranked_llms, 1):
                display_name = Config.LLM_CONFIG.get(llm_name, {}).get('display_name', llm_name)
                eval_col = Config.LLM_CONFIG.get(llm_name, {}).get('eval_column', '?')
                print(f"{rank}. {display_name} (Col {eval_col}): {avg_score:.2f} (n={len(llm_scores[llm_name])})")
            
            # Detailed breakdown by category
            print("\n📋 Detailed Score Breakdown:")
            categories = ['tool_selection', 'tool_sequencing', 'function_execution', 'efficiency']
            
            for category in categories:
                print(f"\n{category.replace('_', ' ').title()}:")
                category_scores = {}
                
                for result in successful_evaluations:
                    llm_name = result['metadata']['llm_name']
                    score = result.get('evaluation_summary', {}).get(category, {}).get('score', 0)
                    
                    if llm_name not in category_scores:
                        category_scores[llm_name] = []
                    category_scores[llm_name].append(score)
                
                # Calculate and display averages for this category
                for llm_name, scores in category_scores.items():
                    avg = sum(scores) / len(scores)
                    display_name = Config.LLM_CONFIG.get(llm_name, {}).get('display_name', llm_name)
                    print(f"  {display_name}: {avg:.2f}")
        
        # Error summary
        failed_evaluations = [r for r in evaluation_results if not r.get('metadata', {}).get('evaluation_success', False)]
        if failed_evaluations:
            print(f"\n❌ Failed Evaluations ({len(failed_evaluations)}):")
            for result in failed_evaluations:
                llm_name = result['metadata']['llm_name']
                display_name = Config.LLM_CONFIG.get(llm_name, {}).get('display_name', llm_name)
                error = result.get('error', 'Unknown error')
                row = result.get('row_number', '?')
                print(f"  - {display_name} (Row {row}): {error}")
        
        print(f"\n📍 Results written to columns: {', '.join(config['eval_column'] for config in Config.LLM_CONFIG.values())}")

def main():
    """Main function - uses config defaults or command line args"""
    
    # Check configuration
    if not Config.SPREADSHEET_ID:
        print("❌ SPREADSHEET_ID not configured in .env file")
        return
    
    if not Config.OPENAI_API_KEY:
        print("❌ OPENAI_API_KEY not configured in .env file")
        return
    
    # Parse command line arguments
    start_row = None
    end_row = None
    worksheet_name = None
    clear_existing = False
    
    if len(sys.argv) >= 2:
        try:
            if sys.argv[1] == '--help' or sys.argv[1] == '-h':
                print("Usage: python main.py [start_row] [end_row] [worksheet_name] [--clear]")
                print("Examples:")
                print("  python main.py                    # Use config defaults")
                print("  python main.py 2 10               # Evaluate rows 2-10")
                print("  python main.py 5 5                # Evaluate single row 5")
                print("  python main.py 2 10 Sheet1        # Specify worksheet")
                print("  python main.py 2 10 Sheet1 --clear # Clear existing evaluations first")
                return
            
            start_row = int(sys.argv[1])
            if len(sys.argv) >= 3:
                end_row = int(sys.argv[2])
            if len(sys.argv) >= 4:
                worksheet_name = sys.argv[3]
            if len(sys.argv) >= 5 and sys.argv[4] == '--clear':
                clear_existing = True
                
        except ValueError:
            print("❌ Invalid command line arguments")
            print("Usage: python main.py [start_row] [end_row] [worksheet_name] [--clear]")
            return
    
    try:
        # Run evaluation
        runner = LLMEvaluationRunner()
        results = runner.run_evaluation(start_row, end_row, worksheet_name, clear_existing)
        
        if results:
            print(f"\n🎉 Evaluation completed successfully!")
            print(f"📊 {len(results)} evaluations written to their respective columns")
        
    except KeyboardInterrupt:
        print("\n⚠️ Evaluation interrupted by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()