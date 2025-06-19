#!/usr/bin/env python3
"""
Batch Explanation Extractor - Simplified Version
Extract all explanations from PDF, then select longest version when duplicates exist
"""

import os
import json
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load environment variables
load_dotenv()

class SimplifiedBatchExplanationExtractor:
    def __init__(self):
        self.api_key = os.getenv('GEMINI_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_KEY not found in environment variables.")
        
        # Initialize client với API key
        self.client = genai.Client(api_key=self.api_key)
        
        # Tracking
        self.total_explanations_extracted = 0
        
    def extract_with_retry(self, pdf_path, file_index=1, max_retries=3):
        """Extract explanations from PDF with retry logic for network errors"""
        
        for attempt in range(max_retries):
            try:
                print(f"🔄 Attempt {attempt + 1}/{max_retries} for {os.path.basename(pdf_path)}")
                result = self.extract_explanations_from_pdf(pdf_path, file_index)
                
                # If successful (no error key), return the result
                if 'error' not in result:
                    return result
                
                # If there's an error but it's not the last attempt, retry
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # 2, 4, 6 seconds
                    print(f"⏳ Error occurred, waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"❌ All {max_retries} attempts failed for {os.path.basename(pdf_path)}")
                    return result
                    
            except KeyboardInterrupt:
                print(f"⚠️ User interrupted processing")
                raise
            except Exception as e:
                print(f"❌ Attempt {attempt + 1} failed: {str(e)}")
                
                # If it's the last attempt, return error
                if attempt == max_retries - 1:
                    print(f"❌ All {max_retries} attempts failed for {os.path.basename(pdf_path)}")
                    return {"error": f"Failed after {max_retries} attempts: {str(e)}"}
                
                # Wait before retry
                wait_time = (attempt + 1) * 2  # 2, 4, 6 seconds
                print(f"⏳ Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
        
        return {"error": "Unexpected error in retry logic"}
    
    def extract_explanations_from_pdf(self, pdf_path, file_index=1):
        """Extract explanations from PDF - simple, no merging"""
        
        print(f"📄 Processing file {file_index}: {os.path.basename(pdf_path)}")
        
        # Read PDF file
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        
        print(f"📊 File size: {len(pdf_data)} bytes")
        
        # Prompt with detection for incomplete explanations
        extraction_prompt = f"""
TASK: Extract ALL SAT explanations from this PDF file ({os.path.basename(pdf_path)})

CRITICAL INSTRUCTIONS:
1. Extract EVERY explanation you can find in this PDF, even if it is incomplete, each explanation is recognized by the title of the question.
2. READ THE ENTIRE PDF CAREFULLY - scan through all pages to find complete explanations
3. For each explanation, FIND THE COMPLETE TEXT from start to finish within this PDF
4. If an explanation starts on one page and continues on another page within this PDF, COMBINE them into one complete explanation
5. LOOK FOR TEXT FRAGMENTS that could be continuation of explanations from previous files:
   - Text that starts mid-sentence without "Choice A is..." header
   - Text that seems to continue an explanation (like "provide the best solution...")
   - Isolated paragraphs that explain why answers are correct/incorrect
6. CAREFULLY CHECK each explanation for completeness:
   - COMPLETE explanations end with proper punctuation (. ! ?) and provide full reasoning
   - INCOMPLETE explanations end abruptly with words like "may", "might", "would", "could", "because", "since", etc.
   - INCOMPLETE explanations may continue on the next page/file
7. Create sequential explanation IDs starting from q_001, q_002, etc.
8. If you find an explanation that starts mid-sentence (continuing from previous page), try to extract the COMPLETE version of the question from this page
9. If an explanation appears incomplete at the beginning or end of the page, still extract it, mark it as incomplete. DON'T IGNORE IT.
10. If you find text that looks like explanation content but doesn't have a clear question number, still extract it as a separate explanation.

EXPLANATION DETECTION RULES:
- Each explanation typically starts with "Choice [A/B/C/D] is..." or "The answer is [A/B/C/D]..."
- BUT ALSO look for text that continues explanations: "provide the best solution", "be the correct answer because", "result in the most accurate"
- Explanations often include phrases like "Choice A is correct because...", "Choice B is wrong because..."
- Look for complete reasoning that explains WHY an answer is correct AND why other choices are wrong
- Some explanations may span multiple paragraphs or pages within this PDF
- **IMPORTANT**: Don't ignore text fragments that seem to be explanation content even without headers

COMPLETENESS DETECTION:
- COMPLETE: Ends with period, explains the full reasoning, mentions why the correct answer is right
- INCOMPLETE: Ends abruptly mid-sentence, missing conclusion, ends with connecting words
- SCAN AHEAD: If an explanation seems incomplete, look for its continuation on the next page of this PDF

SPECIAL CASES TO WATCH FOR:
- Text at the beginning of the PDF that starts mid-sentence (likely continuation from previous file)
- Text fragments between questions that could be explanation content
- Paragraphs that explain answer choices without clear "Choice A is..." headers

FORMAT: Always return JSON in this EXACT format:
{{
    "explanations": [
        {{
            "id": "q_XXX",
            "correct_answer": "A|B|C|D", 
            "explanation": "Complete explanation with \\\\(MathJax\\\\) support - FIND THE FULL TEXT",
            "is_complete": true,
            "notes": "Optional: mention if this continues from previous file or will continue to next"
        }}
    ]
}}

CRITICAL RULES:
1. FORMAT: Use exactly "id", "correct_answer", "explanation" fields + optional "is_complete", "notes"
2. MATH: Use MathJax \\\\( \\\\) for inline, \\\\[ \\\\] for display math
3. IDs: Sequential q_001, q_002, q_003... 
4. ANSWERS: Must be exactly "A", "B", "C", or "D"
5. COMPLETENESS: Set "is_complete": false ONLY if explanation truly ends abruptly and continues elsewhere
6. THOROUGHNESS: Read through ALL pages of this PDF to find complete explanations AND text fragments
7. Return only valid JSON - no markdown, no extra text

EXAMPLES OF WHAT TO LOOK FOR:
- TYPICAL: "Choice A is correct because it provides the most logical solution. Choice B is wrong because..."
- FRAGMENT: "provide the best solution to the problem. Choice B is incorrect because it ignores..." (extract this too!)
- CONTINUATION: "be the most accurate representation of the data shown in the graph." (extract as separate explanation)
- INCOMPLETE: "Choice A is correct because it may" (clearly cut off - mark as incomplete)

SPECIAL ATTENTION:
- Don't just extract the first few lines of an explanation - find the COMPLETE explanation
- If an explanation spans multiple pages within this PDF, combine them
- Extract ALL explanation content, even fragments without clear headers
- Only mark as incomplete if the explanation truly continues in another file
- Each explanation should be as complete as possible from the content available in this PDF

Extract explanations from this PDF:
"""
        
        try:
            print("🤖 Processing with Gemini...")
            
            # Call API
            response = self.client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=[
                    types.Part.from_bytes(
                        data=pdf_data,
                        mime_type='application/pdf',
                    ),
                    extraction_prompt
                ],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=50000
                )
            )
            
            # Extract response text
            content = None
            if hasattr(response, 'text') and response.text:
                content = response.text
            elif hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and candidate.content:
                    if hasattr(candidate.content, 'parts') and candidate.content.parts:
                        part = candidate.content.parts[0]
                        if hasattr(part, 'text'):
                            content = part.text
            
            if not content:
                print("❌ Empty response")
                return {"error": "Empty response"}
            
            content = content.strip()
            print(f"📄 Response length: {len(content)} characters")
            
            # Clean response
            if content.startswith('```json'):
                content = content.replace('```json', '').replace('```', '').strip()
            elif content.startswith('```'):
                content = content.replace('```', '').strip()
            
            # Parse JSON
            try:
                parsed_json = json.loads(content)
                explanations = parsed_json.get('explanations', [])
                
                print(f"✅ Extracted {len(explanations)} explanations from {os.path.basename(pdf_path)}")
                
                # Add file info to each explanation for tracking
                for explanation in explanations:
                    explanation['source_file'] = os.path.basename(pdf_path)
                    explanation['file_index'] = file_index
                
                return parsed_json
                
            except json.JSONDecodeError as e:
                print(f"❌ JSON parsing failed: {e}")
                print(f"📄 Raw content (first 500 chars): {content[:500]}")
                
                # Save debug file
                debug_file = f"debug_explanation_{file_index}_{int(time.time())}.txt"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"🐛 Raw response saved to: {debug_file}")
                
                return {"error": f"JSON parsing failed: {e}"}
            
        except Exception as e:
            print(f"❌ Error calling Gemini API: {e}")
            return {"error": str(e)}
    
    def find_similar_explanations(self, explanations):
        """Find similar/duplicate explanations based on text content"""
        
        print("🔍 Finding similar explanations...")
        
        similar_groups = []
        processed_indices = set()
        
        for i, exp1 in enumerate(explanations):
            if i in processed_indices:
                continue
                
            similar_group = [i]
            exp1_text = exp1.get('explanation', '').lower().strip()
            
            # So sánh với các explanations còn lại
            for j, exp2 in enumerate(explanations[i+1:], i+1):
                if j in processed_indices:
                    continue
                    
                exp2_text = exp2.get('explanation', '').lower().strip()
                
                # Check similarity
                if self.are_explanations_similar(exp1_text, exp2_text):
                    similar_group.append(j)
                    processed_indices.add(j)
            
            if len(similar_group) > 1:
                print(f"   Found similar group: {len(similar_group)} explanations")
                similar_groups.append(similar_group)
            
            processed_indices.add(i)
        
        print(f"✅ Found {len(similar_groups)} groups of similar explanations")
        return similar_groups
    
    def are_explanations_similar(self, text1, text2):
        """Check if 2 explanation texts are similar (likely same explanation)"""
        
        if not text1 or not text2:
            return False
        
        # Exact match
        if text1 == text2:
            return True
        
        # One is substring of the other (likely incomplete vs complete)
        if len(text1) > 50 and len(text2) > 50:
            shorter = text1 if len(text1) < len(text2) else text2
            longer = text2 if len(text1) < len(text2) else text1
            
            # If shorter is 80%+ of longer, likely same explanation
            if len(shorter) / len(longer) > 0.8:
                if shorter in longer or longer in shorter:
                    return True
        
        # Check for significant overlap in words
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if len(words1) > 20 and len(words2) > 20:
            overlap = len(words1.intersection(words2))
            min_words = min(len(words1), len(words2))
            
            # If 70%+ words overlap, likely similar
            if overlap / min_words > 0.7:
                return True
        
            return False
        
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
                    
                    # Use answer from complete explanation if available
                    if next_complete and next_exp.get('correct_answer'):
                        merged_answer = next_exp.get('correct_answer')
                    
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
                    'is_complete': True,  # Now it should be complete after merging
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
    
    def remove_duplicates(self, explanations):
        """Remove duplicate explanations, keeping the longest version"""
        
        print(f"🧹 Removing duplicates from {len(explanations)} explanations...")
        
        # Find similar explanation groups
        similar_groups = self.find_similar_explanations(explanations)
        
        # Track which explanations to keep
        explanations_to_keep = []
        explanations_to_remove = set()
        
        # For each group of similar explanations, keep the best one (prioritize complete ones)
        for group_indices in similar_groups:
            group_explanations = [explanations[i] for i in group_indices]
            
            # Separate complete vs incomplete explanations
            complete_explanations = []
            incomplete_explanations = []
            
            for i, explanation in enumerate(group_explanations):
                explanation_length = len(explanation.get('explanation', ''))
                is_complete = explanation.get('is_complete', True)  # Default to True for backward compatibility
                
                print(f"   Explanation {group_indices[i]}: length={explanation_length}, complete={is_complete}")
                
                if is_complete:
                    complete_explanations.append((group_indices[i], explanation, explanation_length))
                else:
                    incomplete_explanations.append((group_indices[i], explanation, explanation_length))
            
            # Choose the best explanation
            selected_index = -1
            selected_explanation = None
            
            # Priority 1: If we have complete explanations, choose the longest complete one
            if complete_explanations:
                complete_explanations.sort(key=lambda x: x[2], reverse=True)  # Sort by length desc
                selected_index, selected_explanation, selected_length = complete_explanations[0]
                print(f"   ✅ Selected COMPLETE explanation {selected_index} (length: {selected_length} chars)")
                
            # Priority 2: If only incomplete explanations, choose the longest one
            elif incomplete_explanations:
                incomplete_explanations.sort(key=lambda x: x[2], reverse=True)  # Sort by length desc
                selected_index, selected_explanation, selected_length = incomplete_explanations[0]
                print(f"   ⚠️ Selected INCOMPLETE explanation {selected_index} (length: {selected_length} chars)")
            
            # Mark others for removal
            for j in group_indices:
                if j != selected_index:
                    explanations_to_remove.add(j)
        
        # Keep explanations that are not duplicates + longest explanations from duplicate groups
        for i, explanation in enumerate(explanations):
            if i not in explanations_to_remove:
                explanations_to_keep.append(explanation)
        
        print(f"📊 After removing duplicates: {len(explanations)} → {len(explanations_to_keep)} explanations")
        return explanations_to_keep
    
    def reassign_explanation_ids(self, explanations):
        """Reassign sequential explanation IDs"""
        
        print("🔢 Reassigning explanation IDs sequentially...")
        
        for i, explanation in enumerate(explanations, 1):
            explanation['id'] = f"q_{i:03d}"
        
        return explanations
    
    def process_directory(self, input_dir, output_file="batch_explanations_simplified.json", max_files=None):
        """Process all PDF files in directory"""
        
        print(f"🔄 SIMPLIFIED BATCH EXPLANATION EXTRACTION")
        print(f"📁 Input directory: {input_dir}")
        print(f"📄 Output file: {output_file}")
        
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
        
        for i, pdf_file in enumerate(pdf_files, 1):
            print(f"\n{'='*60}")
            print(f"PROCESSING FILE {i}/{len(pdf_files)}")
            print(f"{'='*60}")
            
            result = self.extract_with_retry(pdf_file, i)
            
            if result and 'explanations' in result:
                explanations = result['explanations']
                if explanations:
                    all_explanations.extend(explanations)
                    successful_files.append(pdf_file)
                    print(f"✅ SUCCESS: {len(explanations)} explanations extracted")
                    
                    # Show sample
                    if explanations:
                        sample = explanations[0]
                        print(f"📝 Sample - Explanation: {sample.get('explanation', '')[:100]}...")
                else:
                    print(f"❌ FAILED: No explanations extracted")
                    failed_files.append(pdf_file)
            else:
                print(f"❌ FAILED: Error processing file")
                failed_files.append(pdf_file)
                if result and 'error' in result:
                    print(f"🐛 Error: {result['error']}")
            
            # Show progress
            print(f"📊 Total explanations so far: {len(all_explanations)}")
            
            # Wait between files to avoid rate limiting
            if i < len(pdf_files):
                print("⏳ Waiting 3 seconds...")
                time.sleep(3)
        
        if not all_explanations:
            print("❌ No explanations extracted from any file!")
            return
        
        # Post-processing pipeline
        print(f"\n📝 POST-PROCESSING...")
        
        # Step 1: ONLY merge incomplete explanations (is_complete: false)
        # Keep all other explanations unchanged
        merged_explanations = self.merge_incomplete_explanations(all_explanations)
        
        # Step 2: Skip duplicate removal - only merge incomplete explanations
        # Note: We keep all explanations, including similar ones, unless they were specifically incomplete
        
        # Reassign sequential IDs
        final_explanations = self.reassign_explanation_ids(merged_explanations)
        
        # Create final result
        final_result = {
            "explanations": final_explanations,
            "metadata": {
                "total_files_processed": len(pdf_files),
                "total_files_successful": len(successful_files),
                "total_files_failed": len(failed_files),
                "total_raw_explanations": len(all_explanations),
                "total_unique_explanations": len(final_explanations),
                "extraction_date": time.strftime('%Y-%m-%d %H:%M:%S'),
                "extraction_method": "simplified_batch",
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
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input_dir):
        print(f"❌ Directory not found: {args.input_dir}")
        return
    
    try:
        extractor = SimplifiedBatchExplanationExtractor()
        extractor.process_directory(args.input_dir, args.output, max_files=args.max_files)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n💡 Troubleshooting:")
        print("   - Check if .env file contains GEMINI_KEY")
        print("   - Verify API key is valid")
        print("   - Ensure PDF directory exists")

if __name__ == "__main__":
    main() 