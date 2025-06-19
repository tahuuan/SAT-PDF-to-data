#!/usr/bin/env python3
"""
Batch SAT PDF Extractor - Simplified Version
Extract all questions from PDF, then select most complete version when duplicates exist
"""

import os
import json
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from difflib import SequenceMatcher
import fitz  # PyMuPDF
import re

# Load environment variables
load_dotenv()

class SimplifiedBatchSATExtractor:
    def __init__(self):
        self.api_key = os.getenv('GEMINI_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_KEY not found in environment variables.")
        
        # Initialize client với API key
        self.client = genai.Client(api_key=self.api_key)
        
        # Tracking
        self.total_questions_extracted = 0
        
    def extract_with_retry(self, pdf_path, file_index=1, max_retries=3):
        """Extract questions from PDF with retry logic for network errors"""
        
        for attempt in range(max_retries):
            try:
                print(f"🔄 Attempt {attempt + 1}/{max_retries} for {os.path.basename(pdf_path)}")
                result = self.extract_questions_from_pdf(pdf_path, file_index)
                
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
    
    def extract_questions_from_pdf(self, pdf_path, file_index=1):
        """Extract questions from PDF - simple, no merging"""
        
        print(f"📄 Processing file {file_index}: {os.path.basename(pdf_path)}")
        
        # Read PDF file
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        
        print(f"📊 File size: {len(pdf_data)} bytes")
        
        # Enhanced prompt for better extraction of question fragments and continuations
        extraction_prompt = f"""
TASK: Extract ALL SAT questions from this PDF file ({os.path.basename(pdf_path)})

CRITICAL INSTRUCTIONS FOR SPLIT PDF HANDLING:
1. READ THE ENTIRE PDF CONTENT carefully - don't skip any text
2. Look for BOTH complete questions AND question fragments/continuations
3. When PDFs are split, question text may continue from previous files or continue to next files
4. Extract EVERYTHING that could be part of a question, even if it seems incomplete

WHAT TO EXTRACT:
- Complete questions with full text and 4 options
- Incomplete questions that end abruptly (like "may", "might", "would", "can", "the")  
- Question fragments that start mid-sentence without typical question headers
- Isolated question text that might be continuations from previous files
- Text that looks like it could be part of a question, even without clear question markers
- Options (A, B, C, D) that appear without clear question text above them

SPECIAL ATTENTION TO:
- Text at the very beginning of the PDF (might be continuation from previous file)
- Text at the very end of the PDF (might continue to next file)
- Any mathematical expressions or formulas that seem part of questions
- Answer choices that appear isolated
- Text fragments that don't have clear question structure but contain question-like content

RETURN FORMAT - MUST be valid JSON only:
{{
    "totalCount": <number>,
    "questions": [
        {{
      "id": "q_001",
      "question_text": "Complete question with \\\\(MathJax\\\\) support and [FIGURE] placeholders",
      "has_figure": true/false,
      "figure_description": "Brief description if has_figure is true",
      "figure_position": "inline",
      "correct_answer": "A|B|C|D",
      "explanation": "Complete explanation",
      "difficulty_level": "easy|medium|hard",
      "question_type": "math|reading_and_writing",
      "domain": "Algebra|Geometry|etc",
      "skill": "Linear Equations|etc",
      "is_complete": true/false,
      "notes": "Brief note if incomplete",
      "options": [
        {{"id": "A", "text": "Option A text"}},
        {{"id": "B", "text": "Option B text"}},
        {{"id": "C", "text": "Option C text"}},
        {{"id": "D", "text": "Option D text"}}
            ]
        }}
    ]
}}

COMPLETENESS DETECTION:
- is_complete: true if question has full text ending properly
- is_complete: false if:
  * Question text ends abruptly (like "may", "might", "would", "can", "the", "a", "an")
  * Text seems to be a fragment or continuation
  * Question starts mid-sentence without context
- Add detailed notes explaining why incomplete

CRITICAL RULES:
1. Return ONLY valid JSON - no markdown, no extra text
2. Use MathJax \\\\( \\\\) for inline math, \\\\[ \\\\] for display math
3. Use [FIGURE] placeholder for images/diagrams not table
4. If there is a table on question or options, gen code latex for table
5. If in text has some words in bold, underline, italic, etc, gen code latex for that
5. Correct answer must be exactly "A", "B", "C", or "D" (if available)
6. Extract EVERYTHING - better to over-extract than miss question fragments
7. Create sequential question IDs starting from q_001, q_002, etc.
8. Don't worry about merging - just extract all content that could be questions
9. Don't need generate explanation for each question, because we will generate explanation later   

EXAMPLES:
- "What is the value of x?" with 4 options = is_complete: true
- "The value of x may" (cut off) = is_complete: false, notes: "Question text incomplete, continues on next page"
- "be greater than 5 in this equation" (fragment) = is_complete: false, notes: "Question fragment, likely continuation from previous page"

Extract all questions and question fragments from this PDF:
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
            
            # Additional cleaning for JSON parsing issues
            # Remove any control characters that could cause parsing errors
            content = re.sub(r'[\x00-\x1f\x7f]', '', content)
            
            # Try to extract only the JSON part if there's extra content
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                content = content[json_start:json_end]
            
            # Parse JSON
            try:
                parsed_json = json.loads(content)
                questions = parsed_json.get('questions', [])
                
                print(f"✅ Extracted {len(questions)} questions from {os.path.basename(pdf_path)}")
                
                # Add file info to each question for tracking
                for question in questions:
                    question['source_file'] = os.path.basename(pdf_path)
                    question['file_index'] = file_index
                
                return parsed_json
                
            except json.JSONDecodeError as e:
                print(f"❌ JSON parsing failed: {e}")
                print(f"📄 Raw content (first 500 chars): {content[:500]}")
                
                # Try to fix common JSON issues
                try:
                    # Fix common issues like missing commas, extra commas, etc.
                    import json5  # More lenient JSON parser
                    parsed_json = json5.loads(content)
                    questions = parsed_json.get('questions', [])
                    
                    print(f"✅ Recovered with JSON5: {len(questions)} questions from {os.path.basename(pdf_path)}")
                    
                    # Add file info to each question for tracking
                    for question in questions:
                        question['source_file'] = os.path.basename(pdf_path)
                        question['file_index'] = file_index
                    
                    return parsed_json
                    
                except Exception as e2:
                    print(f"❌ JSON5 parsing also failed: {e2}")
                
                # Save debug file
                debug_file = f"debug_response_{file_index}_{int(time.time())}.txt"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"🐛 Raw response saved to: {debug_file}")
                
                return {"error": f"JSON parsing failed: {e}"}
                
        except Exception as e:
            print(f"❌ Error calling Gemini API: {e}")
            return {"error": str(e)}
    

    def find_similar_questions(self, questions):
        """Find similar/duplicate questions based on text content"""
        
        print("🔍 Finding similar questions...")
        
        similar_groups = []
        processed_indices = set()
        
        for i, q1 in enumerate(questions):
            if i in processed_indices:
                continue
                
            similar_group = [i]
            q1_text = q1.get('question_text', '').lower().strip()
            
            # So sánh với các questions còn lại
            for j, q2 in enumerate(questions[i+1:], i+1):
                if j in processed_indices:
                    continue
                    
                q2_text = q2.get('question_text', '').lower().strip()
                
                # Check similarity
                if self.are_questions_similar(q1_text, q2_text):
                    similar_group.append(j)
                    processed_indices.add(j)
            
            if len(similar_group) > 1:
                print(f"   Found similar group: {len(similar_group)} questions")
                similar_groups.append(similar_group)
            
            processed_indices.add(i)
        
        print(f"✅ Found {len(similar_groups)} groups of similar questions")
        return similar_groups
    
    def are_questions_similar(self, text1, text2):
        """Check if 2 question texts are similar (likely same question)"""
        
        if not text1 or not text2:
            return False
        
        # Exact match
        if text1 == text2:
            return True
        
        # One is substring of the other (likely incomplete vs complete)
        if len(text1) > 30 and len(text2) > 30:
            shorter = text1 if len(text1) < len(text2) else text2
            longer = text2 if len(text1) < len(text2) else text1
            
            # If shorter is 80%+ of longer, likely same question
            if len(shorter) / len(longer) > 0.8:
                if shorter in longer or longer in shorter:
                    return True
        
        # Check for significant overlap in words
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if len(words1) > 10 and len(words2) > 10:
            overlap = len(words1.intersection(words2))
            min_words = min(len(words1), len(words2))
            
            # If 70%+ words overlap, likely similar
            if overlap / min_words > 0.7:
                return True
        
        return False
    
    def merge_incomplete_questions(self, questions):
        """Merge consecutive questions when is_complete=false with subsequent questions until is_complete=true"""
        
        print(f"🔗 Merging incomplete questions from {len(questions)} questions...")
        
        # Check how many incomplete questions we have
        incomplete_count = sum(1 for q in questions if not q.get('is_complete', True))
        print(f"🔍 Found {incomplete_count} incomplete questions to process")
        
        # Sort questions by file_index first, then by id to ensure proper order
        questions_sorted = sorted(questions, key=lambda x: (x.get('file_index', 0), x.get('id', '')))
        
        merged = []
        i = 0
        
        while i < len(questions_sorted):
            current = questions_sorted[i]
            
            # Check if current question is incomplete
            if not current.get('is_complete', True):
                print(f"🔍 Found incomplete question: {current.get('id')} from {current.get('source_file', 'unknown')}")
                
                # Start merging - collect all consecutive questions until we find a complete one
                merged_question_text = current.get('question_text', '').strip()
                merged_id = current.get('id')
                merged_answer = current.get('correct_answer')
                merged_options = current.get('options', [])
                merged_explanation = current.get('explanation', '')
                source_files = [current.get('source_file', '')]
                merged_notes = []
                
                # Look ahead for continuation
                j = i + 1
                merged_count = 1
                
                while j < len(questions_sorted):
                    next_q = questions_sorted[j]
                    next_text = next_q.get('question_text', '').strip()
                    next_complete = next_q.get('is_complete', True)
                    next_id = next_q.get('id', '')
                    
                    print(f"   Checking next question {next_id}: complete={next_complete}")
                    
                    # Add the next question text
                    if merged_question_text and not merged_question_text.endswith(' '):
                        merged_question_text += ' '
                    merged_question_text += next_text
                    
                    # Use options from complete question if available
                    if next_complete and len(next_q.get('options', [])) == 4:
                        merged_options = next_q.get('options', [])
                        merged_answer = next_q.get('correct_answer', merged_answer)
                        merged_explanation = next_q.get('explanation', merged_explanation)
                    
                    source_files.append(next_q.get('source_file', ''))
                    merged_notes.append(f"Merged with {next_id}")
                    merged_count += 1
                    
                    print(f"     ✅ Merged question from {next_id}")
                    
                    # If this question is complete, we're done merging
                    if next_complete:
                        print(f"   ✅ Found complete question, finished merging {merged_count} parts")
                        break
                    
                    j += 1
                
                # Create merged question
                merged_question = {
                    'id': merged_id,
                    'question_text': merged_question_text,
                    'options': merged_options,
                    'correct_answer': merged_answer,
                    'explanation': merged_explanation,
                    'is_complete': True,  # Now it should be complete after merging
                    'source_file': ' + '.join(source_files) if len(source_files) > 1 else source_files[0],
                    'file_index': current.get('file_index', 1),
                    'has_figure': current.get('has_figure', False),
                    'figure_description': current.get('figure_description', ''),
                    'figure_position': current.get('figure_position', ''),
                    'difficulty_level': current.get('difficulty_level', ''),
                    'question_type': current.get('question_type', ''),
                    'domain': current.get('domain', ''),
                    'skill': current.get('skill', '')
                }
                
                if merged_count > 1:
                    merged_question['merged_from'] = f"{merged_count} questions"
                    merged_question['notes'] = f"Merged {merged_count} questions: " + '; '.join(merged_notes)
                
                merged.append(merged_question)
                print(f"   ✅ Created merged question from {merged_count} parts")
                
                # Skip all the questions we just merged
                i = j + 1
                        
            else:
                # Complete question, add as-is
                merged.append(current)
                i += 1
        
        print(f"📊 After merging incomplete: {len(questions)} → {len(merged)} questions")
        return merged
    
    def remove_duplicates(self, questions):
        """Remove duplicate questions, keeping the longest version"""
        
        print(f"🧹 Removing duplicates from {len(questions)} questions...")
        
        # Find similar question groups
        similar_groups = self.find_similar_questions(questions)
        
        # Track which questions to keep
        questions_to_keep = []
        questions_to_remove = set()
        
        # For each group of similar questions, keep the longest one
        for group_indices in similar_groups:
            group_questions = [questions[i] for i in group_indices]
            
            # Find the longest question text in this group
            longest_question = None
            longest_index = -1
            max_length = 0
            
            for i, question in enumerate(group_questions):
                question_length = len(question.get('question_text', ''))
                print(f"   Question {group_indices[i]}: length={question_length}")
                
                if question_length > max_length:
                    max_length = question_length
                    longest_question = question
                    longest_index = group_indices[i]
            
            print(f"   ✅ Selected question {longest_index} (longest: {max_length} chars)")
            
            # Mark others for removal
            for j in group_indices:
                if j != longest_index:
                    questions_to_remove.add(j)
        
        # Keep questions that are not duplicates + longest questions from duplicate groups
        for i, question in enumerate(questions):
            if i not in questions_to_remove:
                questions_to_keep.append(question)
        
        print(f"📊 After removing duplicates: {len(questions)} → {len(questions_to_keep)} questions")
        return questions_to_keep
    
    def reassign_question_ids(self, questions):
        """Reassign sequential question IDs"""
        
        print("🔢 Reassigning question IDs sequentially...")
        
        for i, question in enumerate(questions, 1):
            question['id'] = f"q_{i:03d}"
        
        return questions
    
    def process_directory(self, input_dir, output_file="batch_questions_simplified.json", max_files=None):
        """Process all PDF files in directory"""
        
        print(f"🔄 SIMPLIFIED BATCH QUESTION EXTRACTION")
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
        all_questions = []
        successful_files = []
        failed_files = []
        
        for i, pdf_file in enumerate(pdf_files, 1):
            print(f"\n{'='*60}")
            print(f"PROCESSING FILE {i}/{len(pdf_files)}")
            print(f"{'='*60}")
            
            result = self.extract_with_retry(pdf_file, i)
            
            if result and 'questions' in result:
                questions = result['questions']
                if questions:
                    all_questions.extend(questions)
                    successful_files.append(pdf_file)
                    print(f"✅ SUCCESS: {len(questions)} questions extracted")
                    
                    # Show sample
                    if questions:
                        sample = questions[0]
                    print(f"📝 Sample - Question: {sample.get('question_text', '')[:100]}...")
                else:
                    print(f"❌ FAILED: No questions extracted")
                    failed_files.append(pdf_file)
            else:
                print(f"❌ FAILED: Error processing file")
                failed_files.append(pdf_file)
                if result and 'error' in result:
                    print(f"🐛 Error: {result['error']}")
            
            # Show progress
            print(f"📊 Total questions so far: {len(all_questions)}")
            
            # Wait between files to avoid rate limiting
            if i < len(pdf_files):
                print("⏳ Waiting 3 seconds...")
                time.sleep(3)
        
        if not all_questions:
            print("❌ No questions extracted from any file!")
            return
        
        # Post-processing pipeline
        print(f"\n📝 POST-PROCESSING...")
        
        # Step 1: ONLY merge incomplete questions (is_complete: false)
        # Keep all other questions unchanged
        merged_questions = self.merge_incomplete_questions(all_questions)
        
        # Step 2: Skip duplicate removal - only merge incomplete questions
        # Note: We keep all questions, including similar ones, unless they were specifically incomplete
        
        # Reassign sequential IDs
        final_questions = self.reassign_question_ids(merged_questions)
        
        # Create final result
        final_result = {
            "totalCount": len(final_questions),
            "questions": final_questions,
            "metadata": {
                "total_files_processed": len(pdf_files),
                "total_files_successful": len(successful_files),
                "total_files_failed": len(failed_files),
                "total_raw_questions": len(all_questions),
                "total_unique_questions": len(final_questions),
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
            print(f"📊 Total questions: {len(final_questions)}")
            print(f"📊 Raw questions extracted: {len(all_questions)}")
            print(f"📊 Incomplete questions merged: {len(all_questions) - len(final_questions)}")
            print(f"✅ Successful files: {len(successful_files)}")
            print(f"❌ Failed files: {len(failed_files)}")
            
            if final_questions:
                # Show question type distribution
                math_count = sum(1 for q in final_questions if q.get('question_type') == 'math')
                reading_count = sum(1 for q in final_questions if q.get('question_type') == 'reading_and_writing')
                
                print(f"\n📈 Question type distribution:")
                print(f"   - Math: {math_count} questions")
                print(f"   - Reading and writing: {reading_count} questions")
                print(f"   - Other: {len(final_questions) - math_count - reading_count} questions")
                
                print(f"\n📝 Sample question:")
                sample = final_questions[0]
                print(f"   ID: {sample.get('id', 'N/A')}")
                print(f"   Type: {sample.get('question_type', 'N/A')}")
                print(f"   Question: {sample.get('question_text', '')[:150]}...")
                print(f"   Options: {len(sample.get('options', []))}")
                print(f"   Answer: {sample.get('correct_answer', 'N/A')}")
                
        except Exception as e:
            print(f"❌ Failed to save results: {e}")

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Simplified batch SAT question extraction')
    parser.add_argument('input_dir', help='Directory containing PDF files')
    parser.add_argument('-o', '--output', default='batch_questions_simplified.json', help='Output JSON file')
    parser.add_argument('--max-files', type=int, default=None, help='Maximum number of files to process (for testing)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input_dir):
        print(f"❌ Directory not found: {args.input_dir}")
        return
    
    try:
        extractor = SimplifiedBatchSATExtractor()
        extractor.process_directory(args.input_dir, args.output, max_files=args.max_files)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n💡 Troubleshooting:")
        print("   - Check if .env file contains GEMINI_KEY")
        print("   - Verify API key is valid")
        print("   - Ensure PDF directory exists")

if __name__ == "__main__":
    main()