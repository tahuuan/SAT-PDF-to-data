#!/usr/bin/env python3
"""
Batch Explanation Extractor - Simplified Version with Structured Output
Extract all explanations from PDF, then select longest version when duplicates exist
"""

import os
import json
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from pydantic import BaseModel
from typing import List, Optional

# Load environment variables
load_dotenv()

# Pydantic models for structured output
class Explanation(BaseModel):
    id: str
    correct_answer: str
    explanation: str
    is_complete: bool = True

class ExplanationsResponse(BaseModel):
    explanations: List[Explanation]

class SimplifiedBatchExplanationExtractor:
    def __init__(self):
        self.api_key = os.getenv('GEMINI_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_KEY not found in environment variables.")
        
        # Initialize client với API key
        self.client = genai.Client(api_key=self.api_key)
        
        # Tracking
        self.total_explanations_extracted = 0
        self.lock = threading.Lock()  # For thread-safe operations
        
    def extract_with_retry(self, pdf_path, file_index=1, max_retries=3):
        """Extract explanations from PDF with retry logic for network errors"""
        
        for attempt in range(max_retries):
            try:
                result = self.extract_explanations_from_pdf(pdf_path, file_index)
                
                if 'error' not in result:
                    return result
                
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # 2, 4, 6 seconds
                    print(f"⏳ Error occurred, waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"❌ All {max_retries} attempts failed for {os.path.basename(pdf_path)}")
                    return result

            except Exception as e:
                if attempt == max_retries - 1:
                    return {"error": f"Failed after {max_retries} attempts: {str(e)}"}
                
                wait_time = (attempt + 1) * 2
                time.sleep(wait_time)
        
        return {"error": "Unexpected error in retry logic"}
    
    def extract_explanations_from_pdf(self, pdf_path, file_index=1):
        """Extract explanations from PDF using structured output"""
        
        print(f"📄 Processing file {file_index}: {os.path.basename(pdf_path)}")
        
        # Read PDF file
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        
        print(f"📊 File size: {len(pdf_data)} bytes")
        
        # Enhanced extraction prompt for structured output - matching questions complexity
        extraction_prompt = f"""
TASK: Extract ALL SAT explanations from this PDF file ({os.path.basename(pdf_path)})

You will get a list of PDF files that are splited from a single PDF file containing SAT explanations for questions. You will need to extract all explanations from each PDF file.

CRITICAL INSTRUCTIONS FOR SPLIT PDF HANDLING:
1. READ THE ENTIRE PDF CONTENT carefully - don't skip any text
2. When PDFs are split, explanation text may continue from previous files or continue to next files
3. If a text paragraph is started with a Question tag and followed by a choice, that is a new question and you create a new object for it. Otherwise, it is the remaining part of the previous explanation.
- If the explanation is fully completed, you should mark is_complete is true.
- In case the explanation is not fully meaning that may be continued in the next file, you should mark is_complete is false.
- With the remaining part, you should consider it as a new question with is_complete is true, this is a special case for the remaining part of the previous explanation.
4. SCAN EVERY PAGE thoroughly - explanations can appear anywhere in the document

SPECIAL ATTENTION TO:
- Text at the very beginning of the PDF (might be continuation from previous file)
- Text at the very end of the PDF (might continue to next file)
- Mathematical expressions, formulas, and calculations that are part of explanations
- Answer choice comparisons and eliminations
- Text fragments that don't have clear explanation structure but contain reasoning content
- Multi-paragraph explanations that span across pages within this PDF
- Tables or structured data that support answer explanations

COMPLETENESS DETECTION:
- is_complete: true if explanation has full reasoning ending properly with conclusion
- is_complete: false if:
  * Text seems to be a fragment or continuation
  * Explanation starts mid-sentence without context
  * Missing conclusion or final answer justification

IMPORTANT FORMATTING RULES:
1. Use MathJax \\(formula\\) for inline math, \\[formula\\] for display math
2. Use [FIGURE] placeholder for images/diagrams referenced in explanations
3. Generate LaTeX code for tables that support explanations
4. Generate LaTeX code for bold, underline, italic text formatting
5. Create sequential explanation IDs starting from q_001, q_002, etc.

Extract all explanations and explanation fragments from this PDF with maximum accuracy and completeness.
"""
        
        try:
            print("🤖 Processing with Gemini using structured output...")
            
            # Call API with structured output
            response = self.client.models.generate_content(
                model="gemini-2.5-pro",
                contents=[
                    types.Part.from_bytes(
                        data=pdf_data,
                        mime_type='application/pdf',
                    ),
                ],
                config=types.GenerateContentConfig(
                    system_instruction=extraction_prompt,
                    temperature=0.7,
                    max_output_tokens=65536,
                    response_mime_type="application/json",
                    response_schema=ExplanationsResponse,
                )
            )
            
            print(f"✅ Structured output received successfully")
            
            # Access parsed response directly
            if hasattr(response, 'parsed') and response.parsed:
                parsed_response = response.parsed
                explanations = parsed_response.explanations
                
                print(f"✅ Extracted {len(explanations)} explanations from {os.path.basename(pdf_path)}")
                
                # Convert to dict format for compatibility with existing code
                explanations_dict = []
                for explanation in explanations:
                    explanation_data = explanation.model_dump()
                    explanation_data['source_file'] = os.path.basename(pdf_path)
                    explanation_data['file_index'] = file_index
                    explanations_dict.append(explanation_data)
                
                return {
                    "explanations": explanations_dict
                }
                
            else:
                return {"error": "No parsed response available"}
            
        except Exception as e:
            return {"error": str(e)}
    
    def merge_incomplete_explanations(self, explanations):
        """Merge consecutive explanations when is_complete=false with subsequent explanations until is_complete=true"""
        
        print(f"🔗 Merging incomplete explanations from {len(explanations)} explanations...")
        
        # Check how many incomplete explanations we have
        incomplete_count = sum(1 for exp in explanations if not exp.get('is_complete', True))
        print(f"🔍 Found {incomplete_count} incomplete explanations to process")
        
        # Sort explanations by file_index first, then by id to ensure proper order
        explanations_sorted = sorted(explanations, key=lambda x: (x.get('file_index', 0), x.get('id', '')))
        
        merged = []
        i = 0
        
        while i < len(explanations_sorted):
            current = explanations_sorted[i]
            
            # Check if current explanation is incomplete
            if not current.get('is_complete', True):
                print(f"🔍 Found incomplete explanation: {current.get('id')} from {current.get('source_file', 'unknown')}")
                
                # Start merging - collect all consecutive explanations until we find a complete one
                merged_explanation_text = current.get('explanation', '').strip()
                merged_id = current.get('id')
                merged_answer = current.get('correct_answer')
                source_files = [current.get('source_file', '')]
                merged_notes = []
                
                # Look ahead for continuation
                j = i + 1
                merged_count = 1
                
                while j < len(explanations_sorted):
                    next_exp = explanations_sorted[j]
                    next_text = next_exp.get('explanation', '').strip()
                    next_complete = next_exp.get('is_complete', True)
                    next_id = next_exp.get('id', '')
                    
                    print(f"   Checking next explanation {next_id}: complete={next_complete}")
                    
                    # Add the next explanation text
                    if merged_explanation_text and not merged_explanation_text.endswith(' '):
                        merged_explanation_text += ' '
                    merged_explanation_text += next_text
                    
                    source_files.append(next_exp.get('source_file', ''))
                    merged_notes.append(f"Merged with {next_id}")
                    merged_count += 1
                    
                    print(f"     ✅ Merged explanation from {next_id}")
                    
                    # If this explanation is complete, we're done merging
                    if next_complete:
                        print(f"   ✅ Found complete explanation, finished merging {merged_count} parts")
                        break
                    
                    j += 1
                
                # Create merged explanation
                merged_explanation = {
                    'id': merged_id,
                    'correct_answer': merged_answer,
                    'explanation': merged_explanation_text,
                    'is_complete': True,
                    'source_file': ' + '.join(source_files) if len(source_files) > 1 else source_files[0],
                    'file_index': current.get('file_index', 1)
                }
                
                if merged_count > 1:
                    merged_explanation['merged_from'] = f"{merged_count} explanations"
                    merged_explanation['notes'] = f"Merged {merged_count} explanations: " + '; '.join(merged_notes)
                
                merged.append(merged_explanation)
                print(f"   ✅ Created merged explanation from {merged_count} parts")
                
                # Skip all the explanations we just merged
                i = j + 1
                
            else:
                # Complete explanation, add as-is
                merged.append(current)
                i += 1
        
        print(f"📊 After merging incomplete: {len(explanations)} → {len(merged)} explanations")
        return merged
    
    def reassign_explanation_ids(self, explanations):
        """Reassign sequential explanation IDs"""
        
        print("🔢 Reassigning explanation IDs sequentially...")
        
        for i, explanation in enumerate(explanations, 1):
            explanation['id'] = f"q_{i:03d}"
        
        return explanations
    
    def process_directory(self, input_dir, output_file="batch_explanations_simplified.json", max_files=None, parallel=True):
        """Process all PDF files in directory"""
        
        print(f"🔄 SIMPLIFIED BATCH EXPLANATION EXTRACTION")
        print(f"📁 Input directory: {input_dir}")
        print(f"📄 Output file: {output_file}")
        print(f"⚡ Processing mode: {'Parallel' if parallel else 'Sequential'}")
        
        # Find all PDF files
        pdf_files = []
        if os.path.exists(input_dir):
            for file in os.listdir(input_dir):
                if file.lower().endswith('.pdf'):
                    pdf_files.append(os.path.join(input_dir, file))
        
        if not pdf_files:
            print(f"❌ No PDF files found in {input_dir}")
            return
        
        # Sort files to ensure order
        pdf_files.sort()
        
        # Limit files if max_files is specified
        if max_files and max_files > 0:
            pdf_files = pdf_files[:max_files]
            print(f"📊 Found {len(pdf_files)} PDF files (limited to first {max_files})")
        else:
            print(f"📊 Found {len(pdf_files)} PDF files")
        
        # Process each file
        all_explanations = []
        successful_files = []
        failed_files = []
        
        if parallel:
            # PARALLEL PROCESSING
            print(f"🚀 Starting parallel processing with {min(4, len(pdf_files))} workers...")
            
            with ThreadPoolExecutor(max_workers=min(4, len(pdf_files))) as executor:
                # Submit all tasks
                future_to_file = {}
                for i, pdf_file in enumerate(pdf_files, 1):
                    future = executor.submit(self.extract_with_retry, pdf_file, i)
                    future_to_file[future] = (pdf_file, i)
                
                # Process completed tasks
                completed_count = 0
                for future in as_completed(future_to_file):
                    pdf_file, file_index = future_to_file[future]
                    completed_count += 1
                    
                    print(f"\n{'='*60}")
                    print(f"COMPLETED FILE {completed_count}/{len(pdf_files)}: {os.path.basename(pdf_file)}")
                    print(f"{'='*60}")
                    
                    try:
                        result = future.result()
                        
                        if result and 'explanations' in result:
                            explanations = result['explanations']
                            if explanations:
                                with self.lock:  # Thread-safe access
                                    all_explanations.extend(explanations)
                                    successful_files.append(pdf_file)
                            else:
                                with self.lock:
                                    failed_files.append(pdf_file)
                        else:
                            print(f"❌ FAILED: Error processing file")
                            with self.lock:
                                failed_files.append(pdf_file)
                            if result and 'error' in result:
                                print(f"🐛 Error: {result['error']}")
                        
                        # Show progress
                        with self.lock:
                            print(f"📊 Total explanations so far: {len(all_explanations)}")
                            
                    except Exception as e:
                        print(f"❌ Exception processing {os.path.basename(pdf_file)}: {e}")
                        with self.lock:
                            failed_files.append(pdf_file)
        
        if not all_explanations:
            print("❌ No explanations extracted from any file!")
            return
        
        # SIMPLIFIED Post-processing pipeline - ONLY merge incomplete explanations
        print(f"\n📝 POST-PROCESSING...")
        
        # IMPORTANT: Parallel processing works because:
        # 1. Each explanation is tagged with file_index for proper ordering
        # 2. merge_incomplete_explanations() sorts by file_index before merging
        # 3. The merge logic only depends on sorted order, not processing order
        print(f"🔄 Sorting explanations by file order before merging...")
        
        # Step 1: ONLY merge incomplete explanations (is_complete: false)
        # This handles explanations that are split across PDF files
        merged_explanations = self.merge_incomplete_explanations(all_explanations)
        
        # Step 2: Reassign sequential IDs
        final_explanations = self.reassign_explanation_ids(merged_explanations)
        
        # Create final result
        final_result = {
            "explanations": final_explanations,
            "metadata": {
                "total_files_processed": len(pdf_files),
                "total_files_successful": len(successful_files),
                "total_files_failed": len(failed_files),
                "total_raw_explanations": len(all_explanations),
                "total_final_explanations": len(final_explanations),
                "incomplete_explanations_merged": len(all_explanations) - len(final_explanations),
                "extraction_date": time.strftime('%Y-%m-%d %H:%M:%S'),
                "extraction_method": "simplified_parallel_batch",
                "model_used": "gemini-2.5-flash-preview-05-20"
            }
        }
        
        # Add file lists
        if successful_files:
            final_result["metadata"]["successful_files"] = [os.path.basename(f) for f in successful_files]
        if failed_files:
            final_result["metadata"]["failed_files"] = [os.path.basename(f) for f in failed_files]
        
        # Save results
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(final_result, f, ensure_ascii=False, indent=2)
            
            print(f"\n{'='*60}")
            print(f"✅ EXTRACTION COMPLETED SUCCESSFULLY!")
            print(f"{'='*60}")
            print(f"📄 Output file: {output_file}")
            print(f"📊 Total explanations: {len(final_explanations)}")
            print(f"📊 Raw explanations extracted: {len(all_explanations)}")
            print(f"📊 Incomplete explanations merged: {len(all_explanations) - len(final_explanations)}")
            print(f"✅ Successful files: {len(successful_files)}")
            print(f"❌ Failed files: {len(failed_files)}")
            
            if final_explanations:
                print(f"\n📝 Sample explanation:")
                sample = final_explanations[0]
                print(f"   ID: {sample.get('id', 'N/A')}")
                print(f"   Answer: {sample.get('correct_answer', 'N/A')}")
                print(f"   Explanation: {sample.get('explanation', '')[:150]}...")
            
        except Exception as e:
            print(f"❌ Failed to save results: {e}")

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Simplified batch SAT explanation extraction')
    parser.add_argument('input_dir', help='Directory containing PDF files')
    parser.add_argument('-o', '--output', default='batch_explanations_simplified.json', help='Output JSON file')
    parser.add_argument('--max-files', type=int, default=None, help='Maximum number of files to process (for testing)')
    parser.add_argument('--parallel', action='store_true', default=True, help='Use parallel processing (default)')
    parser.add_argument('--sequential', action='store_true', help='Use sequential processing instead of parallel')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input_dir):
        print(f"❌ Directory not found: {args.input_dir}")
        return
    
    # Determine processing mode
    parallel_mode = args.parallel and not args.sequential
    
    try:
        extractor = SimplifiedBatchExplanationExtractor()
        extractor.process_directory(args.input_dir, args.output, max_files=args.max_files, parallel=parallel_mode)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n💡 Troubleshooting:")
        print("   - Check if .env file contains GEMINI_KEY")
        print("   - Verify API key is valid")
        print("   - Ensure PDF directory exists")

if __name__ == "__main__":
    main() 