#!/usr/bin/env python3
"""
Automated SAT PDF Extractor - Complete Pipeline
Automatically extract questions and explanations in parallel, then merge results
"""

import os
import json
import time
import subprocess
import threading
import argparse
from datetime import datetime

class AutomatedSATExtractor:
    def __init__(self):
        self.start_time = time.time()
        self.questions_completed = False
        self.explanations_completed = False
        self.questions_result = None
        self.explanations_result = None
        self.questions_error = None
        self.explanations_error = None
        
    def run_questions_extraction(self, questions_dir, questions_output, max_files=None):
        """Run questions extraction in separate thread"""
        
        print("🔵 Starting QUESTIONS extraction...")
        
        try:
            # Build command
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
    
    def run_explanations_extraction(self, explanations_dir, explanations_output, max_files=None):
        """Run explanations extraction in separate thread"""
        
        print("🟡 Starting EXPLANATIONS extraction...")
        
        try:
            # Build command
            cmd = ["python", "batch_extract_v2_explanations.py", explanations_dir, "-o", explanations_output]
            if max_files:
                cmd.extend(["--max-files", str(max_files)])
            
            print(f"🟡 Explanations command: {' '.join(cmd)}")
            
            # Run command
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            
            if result.returncode == 0:
                print("✅ EXPLANATIONS extraction completed successfully!")
                self.explanations_result = explanations_output
            else:
                print("❌ EXPLANATIONS extraction failed!")
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
    
    def merge_results(self, questions_file, explanations_file, output_file):
        """Merge questions with explanations"""
        
        print(f"\n🔄 MERGING RESULTS...")
        print(f"📄 Questions: {questions_file}")
        print(f"📄 Explanations: {explanations_file}")
        print(f"📄 Output: {output_file}")
        
        try:
            # Load questions
            if not os.path.exists(questions_file):
                raise FileNotFoundError(f"Questions file not found: {questions_file}")
            
            with open(questions_file, 'r', encoding='utf-8') as f:
                questions_data = json.load(f)
            
            questions = questions_data.get('questions', [])
            print(f"📊 Loaded {len(questions)} questions")
            
            # Load explanations
            if not os.path.exists(explanations_file):
                raise FileNotFoundError(f"Explanations file not found: {explanations_file}")
            
            with open(explanations_file, 'r', encoding='utf-8') as f:
                explanations_data = json.load(f)
            
            explanations = explanations_data.get('explanations', [])
            print(f"📊 Loaded {len(explanations)} explanations")
            
            # Create explanation mapping
            explanation_mapping = {}
            for exp in explanations:
                exp_id = exp.get('id', '')
                if exp_id:
                    explanation_mapping[exp_id] = exp
            
            # Merge explanations into questions
            matched_count = 0
            
            for question in questions:
                question_id = question.get('id', '')
                
                if question_id in explanation_mapping:
                    explanation_data = explanation_mapping[question_id]
                    
                    # Merge explanation text (keep existing if present, otherwise use from explanations)
                    if not question.get('explanation'):
                        question['explanation'] = explanation_data.get('explanation', '')
                    
                    # Update correct_answer if not present or if explanation has one
                    if not question.get('correct_answer') or explanation_data.get('correct_answer'):
                        question['correct_answer'] = explanation_data.get('correct_answer', question.get('correct_answer', ''))
                    
                    matched_count += 1
                    
            print(f"✅ Matched {matched_count}/{len(questions)} explanations ({matched_count/len(questions)*100:.1f}%)")
            
            # Update metadata
            if 'metadata' not in questions_data:
                questions_data['metadata'] = {}
            
            questions_data['metadata'].update({
                'explanations_merged': True,
                'explanations_matched': matched_count,
                'explanations_total': len(explanations),
                'merge_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'automation_completed': True,
                'total_processing_time': f"{time.time() - self.start_time:.1f}s"
            })
            
            # Save merged result
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(questions_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ Merge completed successfully!")
            print(f"📄 Final output: {output_file}")
            
            return questions_data, matched_count
            
        except Exception as e:
            print(f"❌ Merge failed: {e}")
            return None, 0
    
    def run_automated_extraction(self, questions_dir, explanations_dir, output_file="automated_sat_complete.json", max_files=None):
        """Run complete automated pipeline"""
        
        print("🚀 AUTOMATED SAT EXTRACTION PIPELINE")
        print("=" * 60)
        print(f"📁 Questions directory: {questions_dir}")
        print(f"📁 Explanations directory: {explanations_dir}")
        print(f"📄 Final output: {output_file}")
        if max_files:
            print(f"🔢 Max files per directory: {max_files}")
        print(f"🕐 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        # Create temporary file names
        timestamp = int(time.time())
        questions_temp = f"temp_questions_{timestamp}.json"
        explanations_temp = f"temp_explanations_{timestamp}.json"
        
        try:
            # Step 1: Run parallel questions and explanations extraction
            print("\n🎯 STEP 1: PARALLEL EXTRACTION")
            
            questions_thread = threading.Thread(
                target=self.run_questions_extraction,
                args=(questions_dir, questions_temp, max_files)
            )
            
            explanations_thread = threading.Thread(
                target=self.run_explanations_extraction,
                args=(explanations_dir, explanations_temp, max_files)
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
            
            # Step 2: Merge results
            print(f"\n🎯 STEP 2: MERGING RESULTS")
            
            merged_data, matched_count = self.merge_results(
                questions_temp, explanations_temp, output_file
            )
            
            if not merged_data:
                return False
            
            # Step 3: Final summary
            print(f"\n🎉 AUTOMATION COMPLETED SUCCESSFULLY!")
            print("=" * 60)
            print(f"📄 Final file: {output_file}")
            print(f"📊 Statistics:")
            
            questions_count = len(merged_data.get('questions', []))
            print(f"   - Total questions: {questions_count}")
            print(f"   - With explanations: {matched_count}")
            print(f"   - Coverage: {matched_count/questions_count*100:.1f}%")
            print(f"   - Processing time: {time.time() - self.start_time:.1f}s")
            
            # Show sample
            questions = merged_data.get('questions', [])
            if questions:
                print(f"\n📝 SAMPLE QUESTION:")
                sample = questions[0]
                print(f"   ID: {sample.get('id', 'N/A')}")
                print(f"   Type: {sample.get('question_type', 'N/A')}")
                print(f"   Answer: {sample.get('correct_answer', 'N/A')}")
                print(f"   Question: {sample.get('question_text', '')[:100]}...")
                if sample.get('explanation'):
                    print(f"   Explanation: {sample.get('explanation', '')[:100]}...")
                print(f"   Options: {len(sample.get('options', []))}")
            
            return True
            
        except Exception as e:
            print(f"\n❌ AUTOMATION FAILED: {e}")
            return False
            
        finally:
            # Cleanup temp files
            print(f"\n🧹 Cleaning up temporary files...")
            for temp_file in [questions_temp, explanations_temp]:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        print(f"   Removed: {temp_file}")
                except Exception as e:
                    print(f"   ⚠️ Could not remove {temp_file}: {e}")

def main():
    """Main function with command line arguments"""
    
    parser = argparse.ArgumentParser(description='Automated SAT PDF Extraction Pipeline')
    parser.add_argument('questions_dir', help='Directory containing question PDF files')
    parser.add_argument('explanations_dir', help='Directory containing explanation PDF files')
    parser.add_argument('-o', '--output', default='automated_sat_complete.json', help='Output JSON file')
    parser.add_argument('--max-files', type=int, default=None, help='Maximum number of files to process per directory (for testing)')
    
    args = parser.parse_args()
    
    # Validate directories
    if not os.path.exists(args.questions_dir):
        print(f"❌ Questions directory not found: {args.questions_dir}")
        return
    
    if not os.path.exists(args.explanations_dir):
        print(f"❌ Explanations directory not found: {args.explanations_dir}")
        return
    
    # Check required scripts exist
    required_scripts = ['batch_extract_v2_questions.py', 'batch_extract_v2_explanations.py']
    for script in required_scripts:
        if not os.path.exists(script):
            print(f"❌ Required script not found: {script}")
            return
    
    # Run automation
    try:
        extractor = AutomatedSATExtractor()
        success = extractor.run_automated_extraction(
            args.questions_dir, 
            args.explanations_dir, 
            args.output,
            args.max_files
        )
        
        if success:
            print(f"\n🎉 PIPELINE COMPLETED SUCCESSFULLY!")
            print(f"📄 Final result: {args.output}")
        else:
            print(f"\n❌ PIPELINE FAILED!")
            
    except KeyboardInterrupt:
        print(f"\n⚠️ PIPELINE INTERRUPTED BY USER")
    except Exception as e:
        print(f"\n❌ PIPELINE ERROR: {e}")
        print("\n💡 Troubleshooting:")
        print("   - Check if .env file contains GEMINI_KEY")
        print("   - Verify API key is valid")
        print("   - Ensure both PDF directories exist")
        print("   - Make sure required scripts are present")

if __name__ == "__main__":
    main() 