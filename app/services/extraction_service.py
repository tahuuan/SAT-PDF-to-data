import os
import json
import time
import threading
import shutil
import math
import re
from datetime import datetime
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

import PyPDF2
from dotenv import load_dotenv
from google import genai
from google.genai import types
from app.models.data_models import QuestionsResponse, ExplanationsResponse

load_dotenv()

def download_pdf(url: str, destination: str):
    """Downloads a PDF from a URL to a local destination."""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(destination, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
    except requests.RequestException as e:
        raise Exception(f"Failed to download PDF from {url}. Error: {e}")

class SimplifiedBatchSATExtractor:
    def __init__(self):
        self.api_key = os.getenv('GEMINI_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_KEY not found in environment variables.")
        
        self.client = genai.Client(api_key=self.api_key)
        self.total_questions_extracted = 0
        self.lock = threading.Lock()
        
    def extract_with_retry(self, pdf_path, file_index=1, max_retries=3):
        for attempt in range(max_retries):
            try:
                result = self.extract_questions_from_pdf(pdf_path, file_index)
                if 'error' not in result:
                    return result
                if attempt < max_retries - 1:
                    time.sleep((attempt + 1) * 2)
            except Exception as e:
                return {"error": f"Failed after {max_retries} attempts: {str(e)}"}
        return {"error": "Unexpected error in retry logic"}
    
    def extract_questions_from_pdf(self, pdf_path, file_index=1):
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
                questions_dict = [q.model_dump() for q in parsed_response.questions]
                for q in questions_dict:
                    q['source_file'] = os.path.basename(pdf_path)
                    q['file_index'] = file_index
                return {"totalCount": parsed_response.totalCount, "questions": questions_dict}
            else:
                return {"error": "No parsed response available"}
        except Exception as e:
            return {"error": str(e)}

    def find_similar_questions(self, questions):
        similar_groups = []
        processed_indices = set()
        for i, q1 in enumerate(questions):
            if i in processed_indices:
                continue
            similar_group = [i]
            q1_text = q1.get('question_text', '').lower().strip()
            for j, q2 in enumerate(questions[i+1:], i+1):
                if j in processed_indices:
                    continue
                q2_text = q2.get('question_text', '').lower().strip()
                if self.are_questions_similar(q1_text, q2_text):
                    similar_group.append(j)
                    processed_indices.add(j)
            if len(similar_group) > 1:
                similar_groups.append(similar_group)
            processed_indices.add(i)
        return similar_groups

    def are_questions_similar(self, text1, text2):
        return SequenceMatcher(None, text1, text2).ratio() > 0.85

    def merge_incomplete_questions(self, questions):
        questions.sort(key=lambda x: x.get('file_index', 0))
        merged = []
        i = 0
        while i < len(questions):
            current_q = questions[i]
            if not current_q.get('is_complete') and (i + 1) < len(questions):
                next_q = questions[i+1]
                current_q['question_text'] += " " + next_q['question_text']
                current_q['options'] = next_q['options']
                current_q['is_complete'] = next_q['is_complete']
                i += 1
            merged.append(current_q)
            i += 1
        return merged

    def remove_duplicates(self, questions):
        similar_groups = self.find_similar_questions(questions)
        to_remove = set()
        for group in similar_groups:
            best_q_idx = group[0]
            for idx in group[1:]:
                if len(questions[idx]['question_text']) > len(questions[best_q_idx]['question_text']):
                    to_remove.add(best_q_idx)
                    best_q_idx = idx
                else:
                    to_remove.add(idx)
        return [q for i, q in enumerate(questions) if i not in to_remove]

    def reassign_question_ids(self, questions):
        for i, q in enumerate(questions, 1):
            q['id'] = f"q_{i:03d}"
        return questions

    def process_directory(self, input_dir, output_file, max_files=None, parallel=True):
        pdf_files = sorted([os.path.join(input_dir, f) for f in os.listdir(input_dir) if f.endswith(".pdf")])
        if max_files:
            pdf_files = pdf_files[:max_files]
        all_questions = []
        if parallel:
            with ThreadPoolExecutor() as executor:
                future_to_file = {executor.submit(self.extract_with_retry, path, i): path for i, path in enumerate(pdf_files)}
                for future in as_completed(future_to_file):
                    result = future.result()
                    if 'questions' in result:
                        all_questions.extend(result['questions'])
        else:
            for i, path in enumerate(pdf_files):
                result = self.extract_with_retry(path, i)
                if 'questions' in result:
                    all_questions.extend(result['questions'])
        
        merged_q = self.merge_incomplete_questions(all_questions)
        final_q = self.remove_duplicates(merged_q)
        final_q = self.reassign_question_ids(final_q)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({"totalCount": len(final_q), "questions": final_q}, f, indent=2)

class SimplifiedBatchExplanationExtractor:
    def __init__(self):
        self.api_key = os.getenv('GEMINI_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_KEY not found in environment variables.")
        self.client = genai.Client(api_key=self.api_key)
        self.lock = threading.Lock()
        self.total_explanations_extracted = 0

    def extract_with_retry(self, pdf_path, file_index=1, max_retries=3):
        for attempt in range(max_retries):
            try:
                result = self.extract_explanations_from_pdf(pdf_path, file_index)
                if 'error' not in result:
                    return result
                if attempt < max_retries - 1:
                    time.sleep((attempt + 1) * 2)
            except Exception as e:
                if attempt == max_retries - 1:
                    return {"error": f"Failed after {max_retries} attempts: {str(e)}"}
                time.sleep((attempt + 1) * 2)
        return {"error": "Unexpected error in retry logic"}

    def extract_explanations_from_pdf(self, pdf_path, file_index=1):
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
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
            if hasattr(response, 'parsed') and response.parsed:
                parsed_response = response.parsed
                explanations_dict = [e.model_dump() for e in parsed_response.explanations]
                for e in explanations_dict:
                    e['source_file'] = os.path.basename(pdf_path)
                    e['file_index'] = file_index
                return {"explanations": explanations_dict}
            else:
                return {"error": "No parsed response available"}
        except Exception as e:
            return {"error": str(e)}

    def merge_incomplete_explanations(self, explanations):
        explanations_sorted = sorted(explanations, key=lambda x: (x.get('file_index', 0), x.get('id', '')))
        merged = []
        i = 0
        while i < len(explanations_sorted):
            current = explanations_sorted[i]
            if not current.get('is_complete', True):
                merged_explanation_text = current.get('explanation', '').strip()
                j = i + 1
                while j < len(explanations_sorted):
                    next_exp = explanations_sorted[j]
                    merged_explanation_text += ' ' + next_exp.get('explanation', '').strip()
                    if next_exp.get('is_complete', True):
                        break
                    j += 1
                current['explanation'] = merged_explanation_text
                current['is_complete'] = True
                i = j
            merged.append(current)
            i += 1
        return merged

    def reassign_explanation_ids(self, explanations):
        for i, exp in enumerate(explanations):
            exp['id'] = f"q_{i+1:03d}"
        return explanations

    def process_directory(self, input_dir, output_file, max_files=None, parallel=True):
        pdf_files = sorted([os.path.join(input_dir, f) for f in os.listdir(input_dir) if f.endswith(".pdf")])
        if max_files:
            pdf_files = pdf_files[:max_files]
        all_explanations = []
        if parallel:
            with ThreadPoolExecutor() as executor:
                future_to_file = {executor.submit(self.extract_with_retry, path, i): path for i, path in enumerate(pdf_files)}
                for future in as_completed(future_to_file):
                    result = future.result()
                    if 'explanations' in result:
                        all_explanations.extend(result['explanations'])
        else:
            for i, path in enumerate(pdf_files):
                result = self.extract_with_retry(path, i)
                if 'explanations' in result:
                    all_explanations.extend(result['explanations'])
        
        merged_exp = self.merge_incomplete_explanations(all_explanations)
        final_exp = self.reassign_explanation_ids(merged_exp)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({"explanations": final_exp}, f, indent=2)

class QuestionExplanationMerger:
    def __init__(self):
        pass
    
    def load_questions(self, questions_file):
        try:
            with open(questions_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data, data.get('questions', [])
        except Exception as e:
            return None, None
    
    def load_explanations(self, explanations_file):
        try:
            with open(explanations_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('explanations', [])
        except Exception as e:
            return None
    
    def create_explanation_mapping(self, explanations):
        mapping = {}
        for exp in explanations:
            exp_id = exp.get('id', '')
            if exp_id:
                mapping[exp_id] = exp
        return mapping
    
    def transform_question_format(self, question, explanation_data=None):
        transformed_options = [{"value": opt.get('value', opt.get('id', '')), "text": opt.get('text', '')} for opt in question.get('options', [])]
        transformed_question = {
            "question_text": question.get('question_text', ''),
            "options": transformed_options,
            "correct_answer": question.get('correct_answer', ''),
            "explanation": explanation_data.get('explanation', '') if explanation_data else question.get('explanation', ''),
            "difficulty_level": question.get('difficulty_level', 'medium'),
            "estimated_time_seconds": 60,
            "content_tier": "free",
            "source": "admin_uploaded",
            "has_figure": question.get('has_figure', False),
            "type": question.get('question_type', 'reading_and_writing'),
            "domain": question.get('domain', ''),
            "skill": question.get('skill', ''),
        }
        if question.get('question_page') is not None:
            transformed_question['question_page'] = question.get('question_page')
        if question.get('fields_by_ai_gen'):
            transformed_question['fields_by_ai_gen'] = question.get('fields_by_ai_gen')
        if explanation_data and explanation_data.get('correct_answer'):
            transformed_question['correct_answer'] = explanation_data['correct_answer']
        return transformed_question
    
    def merge_explanations_into_questions(self, questions_data, questions, explanations):
        explanation_mapping = self.create_explanation_mapping(explanations)
        matched_count = 0
        transformed_questions = []
        for question in questions:
            question_id = question.get('id', '')
            explanation_data = explanation_mapping.get(question_id)
            if explanation_data:
                matched_count += 1
            transformed_questions.append(self.transform_question_format(question, explanation_data))
        
        merged_data = {
            "questions": transformed_questions,
            "metadata": {
                "total_questions": len(transformed_questions),
                "explanations_merged": True,
                "explanations_matched": matched_count,
                "explanations_total": len(explanations),
                "merge_date": time.strftime('%Y-%m-%d %H:%M:%S'),
                "format_version": "data_formatted_compatible",
                "original_questions_metadata": questions_data.get('metadata', {})
            }
        }
        return merged_data, matched_count
    
    def merge_files(self, questions_file, explanations_file, output_file):
        questions_data, questions = self.load_questions(questions_file)
        if not questions:
            return
        
        explanations = self.load_explanations(explanations_file)
        if not explanations:
            explanations = []

        merged_data, matched_count = self.merge_explanations_into_questions(questions_data, questions, explanations)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(merged_data, f, ensure_ascii=False, indent=2)

class CompleteSATAutomation:
    def __init__(self):
        self.start_time = time.time()
        self.questions_completed = False
        self.explanations_completed = False
        self.questions_result = None
        self.explanations_result = None
        self.questions_error = None
        self.explanations_error = None
        self.question_extractor = SimplifiedBatchSATExtractor()
        self.explanation_extractor = SimplifiedBatchExplanationExtractor()
        self.merger = QuestionExplanationMerger()

    def extract_test_number(self, path):
        patterns = [r'test[\s_-]*(\d+)', r'(\d+)']
        path_str = str(path).lower()
        for pattern in patterns:
            match = re.search(pattern, path_str)
            if match:
                return match.group(1)
        return "1"

    def split_pdf(self, input_file, pages_per_file=10):
        try:
            with open(input_file, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pages = len(pdf_reader.pages)
                num_files = math.ceil(total_pages / pages_per_file)
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
            return None

    def run_questions_extraction(self, questions_dir, questions_output, max_files=None):
        try:
            self.question_extractor.process_directory(questions_dir, questions_output, max_files)
            self.questions_result = questions_output
        except Exception as e:
            self.questions_error = str(e)
        finally:
            self.questions_completed = True
    
    def run_explanations_extraction(self, explanations_dir, explanations_output, max_files=None, retry_attempt=1):
        try:
            self.explanation_extractor.process_directory(explanations_dir, explanations_output, max_files)
            self.explanations_result = explanations_output
        except Exception as e:
            self.explanations_error = str(e)
        finally:
            self.explanations_completed = True
            
    def wait_for_completion(self):
        """Waits for both extraction threads to complete, with progress updates"""
        print("\n🚀 STARTING AUTOMATED SAT EXTRACTION...")
        while not (self.questions_completed and self.explanations_completed):
            elapsed = time.time() - self.start_time
            q_status = "✅" if self.questions_completed else "🏃"
            e_status = "✅" if self.explanations_completed else "🏃"
            
            if self.questions_error: q_status = "❌"
            if self.explanations_error: e_status = "❌"

            print(f"\r📊 Status | Questions: {q_status} | Explanations: {e_status} | Elapsed: {elapsed:.1f}s", end="", flush=True)
            time.sleep(2)
        print("\n") # Newline after loop finishes

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
        try:
            if self.questions_result and self.explanations_result:
                self.merger.merge_files(questions_file, explanations_file, output_file)
                return True
            return False
        except Exception as e:
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

    def run_complete_automation(self, questions_pdf, explanations_pdf, output_file, pages_per_file=10, max_files=None, enable_retry=True, max_retries=2):
        print(f"\n🔪 SPLITTING PDFs...")
        questions_dir = self.split_pdf(questions_pdf, pages_per_file)
        if questions_dir:
            print(f"   - Questions PDF split into: {questions_dir}")
        else:
            print(f"   - ❌ Failed to split Questions PDF")
            return

        if explanations_pdf and questions_pdf != explanations_pdf:
            explanations_dir = self.split_pdf(explanations_pdf, pages_per_file)
            if explanations_dir:
                print(f"   - Explanations PDF split into: {explanations_dir}")
            else:
                print(f"   - ❌ Failed to split Explanations PDF")
                shutil.rmtree(questions_dir)
                return
        else:
            explanations_dir = questions_dir
            print(f"   - Using same directory for explanations: {explanations_dir}")
        
        if not questions_dir or not explanations_dir:
            return

        temp_questions_output = "temp_q.json"
        temp_explanations_output = "temp_e.json"

        q_thread = threading.Thread(target=self.run_questions_extraction, args=(questions_dir, temp_questions_output, max_files))
        e_thread = threading.Thread(target=self.run_explanations_extraction, args=(explanations_dir, temp_explanations_output, max_files))
        q_thread.start()
        e_thread.start()
        self.wait_for_completion()

        print("\n🏁 EXTRACTION COMPLETE!")
        if self.questions_error:
            print(f"   - ❌ Questions extraction failed: {self.questions_error}")
        else:
            print(f"   - ✅ Questions extraction successful: {self.questions_result}")
        if self.explanations_error:
            print(f"   - ❌ Explanations extraction failed: {self.explanations_error}")
        else:
            print(f"   - ✅ Explanations extraction successful: {self.explanations_result}")

        if self.questions_result and self.explanations_result:
            is_covered, _ = self.analyze_coverage(self.questions_result, self.explanations_result)
            if not is_covered and enable_retry:
                print("\n⚠️ Coverage is not 100%. Initiating retry for explanations...")
                retry_success = self.retry_explanations_extraction(explanations_dir, temp_explanations_output, max_retries)
                if retry_success:
                    print("   - ✅ Retry successful. Re-analyzing coverage...")
                    self.analyze_coverage(self.questions_result, temp_explanations_output)
                else:
                    print("   - ❌ Retry failed. Proceeding with initial results.")

        print(f"\n🔄 MERGING RESULTS...")
        merge_success = self.merge_results_with_updated_format(self.questions_result, self.explanations_result, output_file)
        if merge_success:
            print(f"   - ✅ Merge successful. Output at: {output_file}")
        else:
            print(f"   - ❌ Merge failed.")

        final_path = self.organize_output(output_file, questions_dir)
        
        print(f"\n🧹 CLEANING UP TEMP FILES...")
        if os.path.exists(questions_dir): 
            shutil.rmtree(questions_dir)
            print(f"   - Removed: {questions_dir}")
        if explanations_dir != questions_dir and os.path.exists(explanations_dir): 
            shutil.rmtree(explanations_dir)
            print(f"   - Removed: {explanations_dir}")
        if os.path.exists(temp_questions_output): 
            os.remove(temp_questions_output)
            print(f"   - Removed: {temp_questions_output}")
        if os.path.exists(temp_explanations_output): 
            os.remove(temp_explanations_output)
            print(f"   - Removed: {temp_explanations_output}")

        total_time = time.time() - self.start_time
        print(f"\n🎉 AUTOMATION FINISHED in {total_time:.2f} seconds.")
        if final_path:
            print(f"👉 Final output file: {final_path}")

def run_full_extraction(questions_pdf_path: str, explanations_pdf_path: str, output_path: str):
    automation = CompleteSATAutomation()
    automation.run_complete_automation(
        questions_pdf=questions_pdf_path,
        explanations_pdf=explanations_pdf_path,
        output_file=output_path
    ) 