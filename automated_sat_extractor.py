#!/usr/bin/env python3
"""
Complete Automated SAT PDF Processing Pipeline with Intelligent Retry
Automatically split PDFs, extract questions and explanations in parallel, then merge and organize results
"""

import os
import json
import time
import subprocess
import threading
import argparse
import shutil
import math
import re
from datetime import datetime
import PyPDF2

class CompleteSATAutomation:
    def __init__(self):
        self.start_time = time.time()
        self.questions_completed = False
        self.explanations_completed = False
        self.questions_result = None
        self.explanations_result = None
        self.questions_error = None
        self.explanations_error = None
    
    def extract_test_number(self, path):
        """Extract test number from directory or file name"""
        
        # Look for test number in path
        patterns = [
            r'test[\s_-]*(\d+)',  # "test 1", "test_1", "test-1"
            r'(\d+)',             # any number
        ]
        
        path_str = str(path).lower()
        
        for pattern in patterns:
            match = re.search(pattern, path_str)
            if match:
                return match.group(1)
        
        return "1"  # Default
        
    def split_pdf(self, input_file, pages_per_file=10):     
        try:
            with open(input_file, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pages = len(pdf_reader.pages)
                
                num_files = math.ceil(total_pages / pages_per_file)
                
                # Create directory to hold the split files
                base_name = os.path.splitext(input_file)[0]
                output_dir = f"{base_name}_split"
                
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                
                for i in range(num_files):
                    start_page = i * pages_per_file
                    end_page = min((i + 1) * pages_per_file, total_pages)
                    
                    pdf_writer = PyPDF2.PdfWriter()
                    
                    for page_num in range(start_page, end_page):
                        pdf_writer.add_page(pdf_reader.pages[page_num])
                    
                    output_filename = f"{os.path.basename(base_name)}_part{i+1:02d}_pages{start_page+1}-{end_page}.pdf"
                    output_path = os.path.join(output_dir, output_filename)
                    
                    with open(output_path, 'wb') as output_file:
                        pdf_writer.write(output_file)
                    
                return output_dir
                
        except Exception as e:
            print(f"❌ Error splitting PDF: {e}")
            return None
    
    def run_questions_extraction(self, questions_dir, questions_output, max_files=None):
        """Run questions extraction in separate thread"""
        
        try:
            cmd = ["python", "batch_extract_v2_questions.py", questions_dir, "-o", questions_output]
            if max_files:
                cmd.extend(["--max-files", str(max_files)])
            
            print(f"🔵 Questions command: {' '.join(cmd)}")
            
            # Run command
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            
            if result.returncode == 0:
                print("✅ QUESTIONS extraction completed successfully!")
                self.questions_result = questions_output
            else:
                print("❌ QUESTIONS extraction failed!")
                print(f"Error: {result.stderr}")
                self.questions_error = result.stderr
                
        except Exception as e:
            print(f"❌ Exception in questions extraction: {e}")
            self.questions_error = str(e)
        
        finally:
            self.questions_completed = True
    
    def run_explanations_extraction(self, explanations_dir, explanations_output, max_files=None, retry_attempt=1):
        """Run explanations extraction in separate thread with retry logic"""
        
        print(f"🟡 Starting EXPLANATIONS extraction (attempt {retry_attempt})...")
        
        try:
            # Build command
            cmd = ["python", "batch_extract_v2_explanations.py", explanations_dir, "-o", explanations_output]
            if max_files:
                cmd.extend(["--max-files", str(max_files)])
            
            print(f"🟡 Explanations command: {' '.join(cmd)}")
            
            # Run command
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            
            if result.returncode == 0:
                print(f"✅ EXPLANATIONS extraction completed successfully! (attempt {retry_attempt})")
                self.explanations_result = explanations_output
            else:
                print(f"❌ EXPLANATIONS extraction failed! (attempt {retry_attempt})")
                print(f"Error: {result.stderr}")
                self.explanations_error = result.stderr
                
        except Exception as e:
            print(f"❌ Exception in explanations extraction: {e}")
            self.explanations_error = str(e)
        
        finally:
            self.explanations_completed = True
    
    def wait_for_completion(self):
        """Wait for both threads to complete"""
        
        print("⏳ Waiting for both extractions to complete...")
        
        while not (self.questions_completed and self.explanations_completed):
            # Show progress
            q_status = "✅" if self.questions_completed else "⏳"
            e_status = "✅" if self.explanations_completed else "⏳"
            
            elapsed = time.time() - self.start_time
            print(f"\r{q_status} Questions | {e_status} Explanations | Elapsed: {elapsed:.1f}s", end="", flush=True)
            
            time.sleep(2)
        
        print(f"\n🎯 Both extractions completed in {time.time() - self.start_time:.1f} seconds")
    
    def analyze_coverage(self, questions_file, explanations_file):
        """Analyze coverage between questions and explanations"""
        
        print(f"\n🔍 ANALYZING COVERAGE...")
        
        try:
            # Load questions
            with open(questions_file, 'r', encoding='utf-8') as f:
                questions_data = json.load(f)
            questions = questions_data.get('questions', [])
            
            # Load explanations
            with open(explanations_file, 'r', encoding='utf-8') as f:
                explanations_data = json.load(f)
            explanations = explanations_data.get('explanations', [])
            
            # Create ID mappings
            question_ids = set(q.get('id', '') for q in questions)
            explanation_ids = set(e.get('id', '') for e in explanations)
            
            # Find missing explanations
            missing_explanations = question_ids - explanation_ids
            
            print(f"📊 Coverage Analysis:")
            print(f"   - Total questions: {len(questions)}")
            print(f"   - Total explanations: {len(explanations)}")
            print(f"   - Missing explanations: {len(missing_explanations)}")
            
            if missing_explanations:
                print(f"   - Missing IDs: {sorted(list(missing_explanations))}")
                coverage_rate = len(explanation_ids) / len(question_ids) * 100 if question_ids else 0
                print(f"   - Coverage rate: {coverage_rate:.1f}%")
                
                return False, missing_explanations
            else:
                print(f"   - ✅ Perfect coverage: 100%")
                return True, set()
                
        except Exception as e:
            print(f"❌ Error analyzing coverage: {e}")
            return False, set()
    
    def retry_explanations_extraction(self, explanations_dir, explanations_output, max_retries=2):
        """Retry explanations extraction with improved settings"""
        
        print(f"\n🔄 RETRY EXPLANATIONS EXTRACTION...")
        
        for attempt in range(1, max_retries + 1):
            print(f"\n🎯 RETRY ATTEMPT {attempt}/{max_retries}")
            
            # Reset status
            self.explanations_completed = False
            self.explanations_error = None
            
            # Create new output file for this attempt
            attempt_output = f"temp_explanations_retry_{attempt}.json"
            
            # Run extraction
            explanations_thread = threading.Thread(
                target=self.run_explanations_extraction,
                args=(explanations_dir, attempt_output, None, attempt + 1)
            )
            
            explanations_thread.start()
            
            # Wait for completion
            while not self.explanations_completed:
                elapsed = time.time() - self.start_time
                print(f"\r🟡 Retry attempt {attempt} | Elapsed: {elapsed:.1f}s", end="", flush=True)
                time.sleep(2)
            
            explanations_thread.join()
            print()  # New line
            
            # Check if successful
            if not self.explanations_error and os.path.exists(attempt_output):
                # Replace original output with retry result
                shutil.move(attempt_output, explanations_output)
                print(f"✅ Retry attempt {attempt} successful!")
                return True
            else:
                print(f"❌ Retry attempt {attempt} failed")
                if os.path.exists(attempt_output):
                    os.remove(attempt_output)
        
        print(f"❌ All retry attempts failed")
        return False
    
    def merge_results_with_updated_format(self, questions_file, explanations_file, output_file):
        """Merge questions with explanations using updated merge script"""
        
        print(f"\n🔄 MERGING RESULTS WITH UPDATED FORMAT...")
        print(f"📄 Questions: {questions_file}")
        print(f"📄 Explanations: {explanations_file}")
        print(f"📄 Output: {output_file}")
        
        try:
            # Run merge script
            cmd = ["python", "merge_questions_explanations.py"]
            
            # For now, let's copy the files to the expected names and run merge
            temp_questions = "questions_new.json"  # Updated to match merge script expectation
            temp_explanations = "explanations.json"
            
            # Copy files to expected names
            shutil.copy2(questions_file, temp_questions)
            shutil.copy2(explanations_file, temp_explanations)
            
            # Modify merge script temporarily to use our files
            merge_script_content = f'''#!/usr/bin/env python3
import sys
import os
sys.path.append('.')

# Import the merger class
from merge_questions_explanations import QuestionExplanationMerger

# Run merge with our specific files
merger = QuestionExplanationMerger()
result = merger.merge_files("{temp_questions}", "{temp_explanations}", "{output_file}")

if result:
    print("✅ Merge successful!")
else:
    print("❌ Merge failed!")
    sys.exit(1)
'''
            
            # Write temporary merge script
            temp_merge_script = "temp_merge.py"
            with open(temp_merge_script, 'w', encoding='utf-8') as f:
                f.write(merge_script_content)
            
            # Run merge
            result = subprocess.run(["python", temp_merge_script], capture_output=True, text=True, encoding='utf-8')
            
            if result.returncode == 0:
                print("✅ Merge completed successfully!")
                
                # Clean up temp files
                for temp_file in [temp_questions, temp_explanations, temp_merge_script]:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                
                return True
            else:
                print("❌ Merge failed!")
                print(f"Error: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Merge error: {e}")
            return False
    
    def organize_output(self, source_file, questions_dir=None, data_raw_dir="data-raw"):
        """Move final file to data-raw directory with organized naming"""
        
        print(f"\n📁 ORGANIZING OUTPUT...")
        
        try:
            # Create data-raw directory if it doesn't exist
            if not os.path.exists(data_raw_dir):
                os.makedirs(data_raw_dir)
                print(f"📂 Created directory: {data_raw_dir}")
            
            # Extract test number from questions directory
            test_number = self.extract_test_number(questions_dir) if questions_dir else "1"
            
            # Generate final filename: sat_test_1_20250624_120028.json
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            final_filename = f"sat_test_{test_number}_{timestamp}.json"
            final_path = os.path.join(data_raw_dir, final_filename)
            
            # Move file
            shutil.move(source_file, final_path)
            
            print(f"✅ File organized successfully!")
            print(f"📄 Final location: {final_path}")
            
            return final_path
            
        except Exception as e:
            print(f"❌ Error organizing output: {e}")
            return None
    
    def run_complete_automation(self, questions_pdf=None, explanations_pdf=None, 
                               questions_dir=None, explanations_dir=None,
                               pages_per_file=10, max_files=None, 
                               output_file="complete_sat_extraction.json",
                               enable_retry=True, max_retries=2):
        """Run complete automated pipeline with intelligent retry"""        
        try:
            if questions_pdf or explanations_pdf:
                if questions_pdf:
                    questions_dir = self.split_pdf(questions_pdf, pages_per_file)
                    if not questions_dir:
                        return False
                
                if explanations_pdf:
                    explanations_dir = self.split_pdf(explanations_pdf, pages_per_file)
                    if not explanations_dir:
                        return False
            
            if not questions_dir or not os.path.exists(questions_dir):
                return False
            
            timestamp = int(time.time())
            questions_temp = f"temp_questions_{timestamp}.json"
            explanations_temp = f"temp_explanations_{timestamp}.json"
            
            self.questions_completed = False
            self.explanations_completed = False
            self.questions_error = None
            self.explanations_error = None
            
            questions_thread = threading.Thread(
                target=self.run_questions_extraction,
                args=(questions_dir, questions_temp, max_files)
            )
            
            explanations_thread = threading.Thread(
                target=self.run_explanations_extraction,
                args=(explanations_dir, explanations_temp, max_files, 1)
            )
            
            # Start both threads
            questions_thread.start()
            explanations_thread.start()
            
            # Wait for completion
            self.wait_for_completion()
            
            # Join threads
            questions_thread.join()
            explanations_thread.join()
            
            # Check results
            if self.questions_error or self.explanations_error:
                print("\n❌ EXTRACTION ERRORS:")
                if self.questions_error:
                    print(f"Questions error: {self.questions_error}")
                if self.explanations_error:
                    print(f"Explanations error: {self.explanations_error}")
                return False
            
            if not self.questions_result or not self.explanations_result:
                print("\n❌ EXTRACTION INCOMPLETE:")
                print(f"Questions result: {self.questions_result}")
                print(f"Explanations result: {self.explanations_result}")
                return False
            
            # Step 2.5: Analyze coverage and retry if needed
            if enable_retry:
                print(f"\n🎯 STEP 2.5: COVERAGE ANALYSIS AND RETRY")
                
                perfect_coverage, missing_ids = self.analyze_coverage(questions_temp, explanations_temp)
                
                if not perfect_coverage and missing_ids:
                    print(f"🔄 Poor coverage detected, initiating retry...")
                    retry_success = self.retry_explanations_extraction(explanations_dir, explanations_temp, max_retries)
                    
                    if retry_success:
                        # Re-analyze coverage after retry
                        perfect_coverage, missing_ids = self.analyze_coverage(questions_temp, explanations_temp)
                        if perfect_coverage:
                            print(f"✅ Perfect coverage achieved after retry!")
                        else:
                            print(f"⚠️ Coverage improved but not perfect: {len(missing_ids)} still missing")
                    else:
                        print(f"❌ Retry failed, continuing with current results")
                else:
                    print(f"✅ Good coverage on first attempt!")
            
            print(f"\n🎯 STEP 3: MERGING WITH UPDATED FORMAT")
            
            merge_success = self.merge_results_with_updated_format(
                questions_temp, explanations_temp, output_file
            )
            
            if not merge_success:
                return False
            
            # Step 4: Organize output
            print(f"\n🎯 STEP 4: ORGANIZING OUTPUT")
            
            final_path = self.organize_output(output_file, questions_dir)
            
            if not final_path:
                return False
            
            # Step 5: Final summary and cleanup
            print(f"\n🎉 COMPLETE AUTOMATION SUCCESSFUL!")
            print("=" * 75)
            print(f"📄 Final file: {final_path}")
            
            # Load and show statistics
            try:
                with open(final_path, 'r', encoding='utf-8') as f:
                    final_data = json.load(f)
                
                questions = final_data.get('questions', [])
                print(f"📊 Final Statistics:")
                print(f"   - Total questions: {len(questions)}")
                
                # Count questions with explanations
                with_explanations = sum(1 for q in questions if q.get('explanation'))
                print(f"   - With explanations: {with_explanations}")
                coverage = with_explanations/len(questions)*100 if questions else 0
                print(f"   - Coverage: {coverage:.1f}%")
                
                # Coverage quality indicator
                if coverage >= 98:
                    print(f"   - Quality: ✅ EXCELLENT")
                elif coverage >= 95:
                    print(f"   - Quality: 🟡 GOOD")
                elif coverage >= 90:
                    print(f"   - Quality: 🟠 FAIR")
                else:
                    print(f"   - Quality: 🔴 NEEDS IMPROVEMENT")
                
                # Count by type
                math_count = sum(1 for q in questions if q.get('type') == 'math')
                reading_count = sum(1 for q in questions if q.get('type') == 'reading_and_writing')
                print(f"   - Math questions: {math_count}")
                print(f"   - Reading/Writing questions: {reading_count}")
                
                print(f"   - Processing time: {time.time() - self.start_time:.1f}s")
                
                # Show sample
                if questions:
                    print(f"\n📝 SAMPLE QUESTION:")
                    sample = questions[0]
                    print(f"   Type: {sample.get('type', 'N/A')}")
                    print(f"   Domain: {sample.get('domain', 'N/A')}")
                    print(f"   Skill: {sample.get('skill', 'N/A')}")
                    print(f"   Answer: {sample.get('correct_answer', 'N/A')}")
                    print(f"   Question: {sample.get('question_text', '')[:100]}...")
                    if sample.get('explanation'):
                        print(f"   Explanation: {sample.get('explanation', '')[:100]}...")
                    print(f"   Options: {len(sample.get('options', []))}")
                
            except Exception as e:
                print(f"⚠️ Could not load final statistics: {e}")
            
            # Cleanup temp files
            print(f"\n🧹 Cleaning up temporary files...")
            for temp_file in [questions_temp, explanations_temp]:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        print(f"   ✅ Removed: {temp_file}")
                except Exception as e:
                    print(f"   ⚠️ Could not remove {temp_file}: {e}")
            
            return True
            
        except Exception as e:
            print(f"\n❌ AUTOMATION FAILED: {e}")
            return False

def main():
    """Main function with comprehensive command line arguments"""
    
    parser = argparse.ArgumentParser(description='Complete Automated SAT PDF Processing Pipeline with Retry')
    
    # PDF files to split
    parser.add_argument('--questions-pdf', help='PDF file containing questions to split and process')
    parser.add_argument('--explanations-pdf', help='PDF file containing explanations to split and process')
    
    # Or pre-split directories
    parser.add_argument('--questions-dir', help='Directory containing question PDF files (already split)')
    parser.add_argument('--explanations-dir', help='Directory containing explanation PDF files (already split)')
    
    # Processing options
    parser.add_argument('--pages-per-file', type=int, default=10, help='Pages per file when splitting PDFs (default: 10)')
    parser.add_argument('--max-files', type=int, default=None, help='Maximum number of files to process per directory (for testing)')
    parser.add_argument('-o', '--output', default='complete_sat_extraction.json', help='Output JSON file name')
    
    # Retry options
    parser.add_argument('--enable-retry', action='store_true', default=True, help='Enable intelligent retry for better coverage (default: enabled)')
    parser.add_argument('--disable-retry', action='store_true', help='Disable retry logic')
    parser.add_argument('--max-retries', type=int, default=2, help='Maximum number of retry attempts (default: 2)')
    
    args = parser.parse_args()
    
    # Validate input - need either PDFs to split or directories
    if not (args.questions_pdf or args.questions_dir):
        print("❌ Must provide either --questions-pdf or --questions-dir")
        return
    
    if not (args.explanations_pdf or args.explanations_dir):
        print("❌ Must provide either --explanations-pdf or --explanations-dir")
        return
    
    # Validate PDF files exist if provided
    if args.questions_pdf and not os.path.exists(args.questions_pdf):
        print(f"❌ Questions PDF not found: {args.questions_pdf}")
        return
    
    if args.explanations_pdf and not os.path.exists(args.explanations_pdf):
        print(f"❌ Explanations PDF not found: {args.explanations_pdf}")
        return
    
    # Validate directories exist if provided
    if args.questions_dir and not os.path.exists(args.questions_dir):
        print(f"❌ Questions directory not found: {args.questions_dir}")
        return
    
    if args.explanations_dir and not os.path.exists(args.explanations_dir):
        print(f"❌ Explanations directory not found: {args.explanations_dir}")
        return
    
    # Check required scripts exist
    required_scripts = [
        'batch_extract_v2_questions.py', 
        'batch_extract_v2_explanations.py',
        'merge_questions_explanations.py'
    ]
    for script in required_scripts:
        if not os.path.exists(script):
            print(f"❌ Required script not found: {script}")
            return
    
    # Check PyPDF2 is available if splitting is needed
    if args.questions_pdf or args.explanations_pdf:
        try:
            import PyPDF2
        except ImportError:
            print("❌ PyPDF2 not installed. Install with: pip install PyPDF2")
            return
    
    # Determine retry settings
    enable_retry = args.enable_retry and not args.disable_retry
    
    # Run automation
    try:
        automation = CompleteSATAutomation()
        success = automation.run_complete_automation(
            questions_pdf=args.questions_pdf,
            explanations_pdf=args.explanations_pdf,
            questions_dir=args.questions_dir,
            explanations_dir=args.explanations_dir,
            pages_per_file=args.pages_per_file,
            max_files=args.max_files,
            output_file=args.output,
            enable_retry=enable_retry,
            max_retries=args.max_retries
        )
        
        if success:
            print(f"\n🎉 COMPLETE PIPELINE SUCCESSFUL!")
            print(f"🏁 Check the data-raw directory for your processed SAT questions!")
        else:
            print(f"\n❌ PIPELINE FAILED!")
            
    except KeyboardInterrupt:
        print(f"\n⚠️ PIPELINE INTERRUPTED BY USER")
    except Exception as e:
        print(f"\n❌ PIPELINE ERROR: {e}")
        print("\n💡 Troubleshooting:")
        print("   - Check if .env file contains GEMINI_KEY")
        print("   - Verify API key is valid")
        print("   - Ensure PDF files or directories exist")
        print("   - Make sure all required scripts are present")
        print("   - Install PyPDF2 if splitting PDFs: pip install PyPDF2")

if __name__ == "__main__":
    main() 