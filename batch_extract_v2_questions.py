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
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

# Load environment variables
load_dotenv()

# Pydantic models for structured output
class Option(BaseModel):
    value: str
    text: str

class DifficultyLevel(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"

class QuestionType(str, Enum):
    math = "math"
    reading_and_writing = "reading_and_writing"

class FieldByAiGen(str, Enum):
    difficulty_level = "difficulty_level"
    question_type = "question_type"
    domain = "domain"
    skill = "skill"

class SATQuestion(BaseModel):
    id: str
    question_text: str
    has_figure: bool
    difficulty_level: DifficultyLevel
    question_type: QuestionType
    domain: str
    skill: str
    is_complete: bool = True
    options: List[Option]
    fields_by_ai_gen: List[FieldByAiGen] = []
    question_page: Optional[int] = None

class QuestionsResponse(BaseModel):
    totalCount: int
    questions: List[SATQuestion]

class SimplifiedBatchSATExtractor:
    def __init__(self):
        self.api_key = os.getenv('GEMINI_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_KEY not found in environment variables.")
        
        # Initialize client với API key
        self.client = genai.Client(api_key=self.api_key)
        
        # Tracking
        self.total_questions_extracted = 0
        self.lock = threading.Lock()  # For thread-safe operations
        
    def extract_with_retry(self, pdf_path, file_index=1, max_retries=3):
        """Extract questions from PDF with retry logic for network errors"""
        
        for attempt in range(max_retries):
            try:
                result = self.extract_questions_from_pdf(pdf_path, file_index)
                
                # If successful (no error key), return the result
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
                return {"error": f"Failed after {max_retries} attempts: {str(e)}"}
        
        return {"error": "Unexpected error in retry logic"}
    
    def extract_questions_from_pdf(self, pdf_path, file_index=1):
        """Extract questions from PDF using structured output"""     
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        
        extraction_prompt = f"""
TASK: Extract ALL SAT questions from this PDF file ({os.path.basename(pdf_path)})

CRITICAL INSTRUCTIONS FOR SPLIT PDF HANDLING:
1. READ THE ENTIRE PDF CONTENT carefully - don't skip any text
2. When PDFs are split, question text may continue from previous files or continue to next files
3. Extract EVERYTHING that could be part of a question, even if it seems incomplete.
4. A question is COMPLETE if you can find BOTH the question text AND all 4 answer choices (A, B, C, D) within this PDF
5. A question is INCOMPLETE only if the question text or options are CUT OFF and continue to another file

WHAT TO EXTRACT:
- Complete questions with full text and 4 options (even question and options are not in the same page)
- Question fragments that start mid-sentence without typical question headers
- Isolated question text that might be continuations from previous files
- Text that looks like it could be part of a question, even without clear question markers
- Options (A, B, C, D) that appear without clear question text above them, 

DOMAIN AND SKILL CLASSIFICATION:
Based on content, classify into:

Domain: Information and Ideas
- Skills: Central Ideas and Details; Inferences; Command of Evidence

Domain: Craft and Structure  
- Skills: Text Structure and Purpose; Cross-Text Connections; Words in Context

Domain: Expression of Ideas
- Skills: Rhetorical Synthesis; Transitions

Domain: Standard English Conventions
- Skills: Boundaries; Form, Structure, and Sense

Domain: Algebra
- Skills: Linear equations for one variable; Linear functions; Linear equations for two variables; Systems of two linear equations in two variables; Linear inequalities in one or two variables

Domain: Advanced Math
- Skills: Nonlinear functions; Nonlinear equations in one variable and systems of equations in two variables; Equivalent expressions

Domain: Problem-Solving and Data Analysis
- Skills: Ratios/rates/proportional relationships/units; Percentages; One-variable data distributions; Two-variable data models; Probability; Statistical inference; Evaluating statistical claims

Domain: Geometry and Trigonometry
- Skills: Area and volume; Lines/angles/triangles; Right triangles and trigonometry; Circles

DIFFICULTY LEVELS: easy, medium, hard
QUESTION TYPES: ONLY "math" or "reading_and_writing"

FIELDS_BY_AI_GEN: If some fields are not in the question, you need to gen the fields_by_ai_gen list based on the content, list:
- difficulty_level
- question_type
- domain
- skill

QUESTION PAGE: The page number of the question which is displayed in the pdf NOT count the page number of the pdf

SPECIAL ATTENTION TO:
- Text at the very beginning of the PDF (might be continuation from previous file)
- Text at the very end of the PDF (might continue to next file)
- Any mathematical expressions or formulas that seem part of questions
- Answer choices that appear isolated
- Text fragments that don't have clear question structure but contain question-like content

IMPORTANT FORMATTING RULES:
1. Use MathJax \\(formula\\) for inline math, \\[formula\\] for display math
2. Use [FIGURE] placeholder for images/diagrams (not tables)
3. Generate LaTeX code for tables
4. Generate LaTeX code for bold, underline, italic text formatting
5. Create sequential question IDs starting from q_001, q_002, etc.
6. Set is_complete: false if question text ends abruptly or seems to continue elsewhere you don't see
7. Don't generate explanations (will be done separately)
8. Include fields_by_ai_gen list indicating which fields were AI-generated

COMPLETENESS DETECTION:
- is_complete: true if question has full text ending properly
- is_complete: false if:
  * Text seems to be a fragment or continuation that you don't see the full text in the whole pdf
  * Question starts mid-sentence without context

Extract all questions and question fragments from this PDF.
"""
        
        try:
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
                    response_schema=QuestionsResponse,
                )
            )
            
            if hasattr(response, 'parsed') and response.parsed:
                parsed_response = response.parsed
                questions = parsed_response.questions
                
                print(f"✅ Extracted {len(questions)} questions from {os.path.basename(pdf_path)}")
                
                # Convert to dict format for compatibility with existing code
                questions_dict = []
                for question in questions:
                    question_data = question.model_dump()
                    question_data['source_file'] = os.path.basename(pdf_path)
                    question_data['file_index'] = file_index
                    questions_dict.append(question_data)
                
                return {
                    "totalCount": parsed_response.totalCount,
                    "questions": questions_dict
                }
                
            else:
                print("❌ No parsed response available")
                return {"error": "No parsed response available"}
                
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
    
    def process_directory(self, input_dir, output_file="batch_questions_simplified.json", max_files=None, parallel=True):
        """Process all PDF files in directory"""
        
        print(f"🔄 SIMPLIFIED BATCH QUESTION EXTRACTION")
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
        all_questions = []
        successful_files = []
        failed_files = []
        
        if parallel:
            with ThreadPoolExecutor(max_workers=min(4, len(pdf_files))) as executor:
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
                        
                        if result and 'questions' in result:
                            questions = result['questions']
                            if questions:
                                with self.lock:  # Thread-safe access
                                    all_questions.extend(questions)
                                    successful_files.append(pdf_file)
                                print(f"✅ SUCCESS: {len(questions)} questions extracted")
                                
                                # Show sample
                                if questions:
                                    sample = questions[0]
                                    print(f"📝 Sample - Question: {sample.get('question_text', '')[:100]}...")
                            else:
                                print(f"❌ FAILED: No questions extracted")
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
                            print(f"📊 Total questions so far: {len(all_questions)}")
                            
                    except Exception as e:
                        print(f"❌ Exception processing {os.path.basename(pdf_file)}: {e}")
                        with self.lock:
                            failed_files.append(pdf_file)
        if not all_questions:
            print("❌ No questions extracted from any file!")
            return
        
        merged_questions = self.merge_incomplete_questions(all_questions)
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
        
        if successful_files:
            final_result["metadata"]["successful_files"] = [os.path.basename(f) for f in successful_files]
        if failed_files:
            final_result["metadata"]["failed_files"] = [os.path.basename(f) for f in failed_files]
        
        # Save results  
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(final_result, f, ensure_ascii=False, indent=2)
            
            
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
    parser.add_argument('--parallel', action='store_true', default=True, help='Use parallel processing (default)')
    parser.add_argument('--sequential', action='store_true', help='Use sequential processing instead of parallel')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input_dir):
        print(f"❌ Directory not found: {args.input_dir}")
        return
    
    # Determine processing mode
    parallel_mode = args.parallel and not args.sequential
    
    try:
        extractor = SimplifiedBatchSATExtractor()
        extractor.process_directory(args.input_dir, args.output, max_files=args.max_files, parallel=parallel_mode)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n💡 Troubleshooting:")
        print("   - Check if .env file contains GEMINI_KEY")
        print("   - Verify API key is valid")
        print("   - Ensure PDF directory exists")

if __name__ == "__main__":
    main()