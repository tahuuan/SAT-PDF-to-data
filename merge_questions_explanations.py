#!/usr/bin/env python3
"""
Merge Questions with Explanations - Updated Format
Combine extracted explanations into questions file following data_formatted.json structure
"""

import os
import json
import time

class QuestionExplanationMerger:
    def __init__(self):
        pass
    
    def load_questions(self, questions_file):
        """Load questions file"""
        try:
            with open(questions_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            questions = data.get('questions', [])
            print(f"📊 Loaded {len(questions)} questions from {questions_file}")
            return data, questions
            
        except Exception as e:
            print(f"❌ Error reading questions file: {e}")
            return None, None
    
    def load_explanations(self, explanations_file):
        """Load explanations file"""
        try:
            with open(explanations_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            explanations = data.get('explanations', [])
            print(f"📊 Loaded {len(explanations)} explanations from {explanations_file}")
            return explanations
            
        except Exception as e:
            print(f"❌ Error reading explanations file: {e}")
            return None
    
    def create_explanation_mapping(self, explanations):
        """Create mapping from ID to explanation"""
        mapping = {}
        
        for exp in explanations:
            exp_id = exp.get('id', '')
            if exp_id:
                mapping[exp_id] = exp
        
        print(f"📊 Created mapping for {len(mapping)} explanations")
        return mapping
    
    def transform_question_format(self, question, explanation_data=None):
        """Transform question to data_formatted.json format"""
        
        # Transform options format from [{"value": "A", "text": "..."}] to [{"id": "A", "text": "..."}]
        transformed_options = []
        original_options = question.get('options', [])
        
        for opt in original_options:
            transformed_opt = {
                "value": opt.get('value', opt.get('id', '')),  # Support both value and id fields
                "text": opt.get('text', '')
            }
            transformed_options.append(transformed_opt)
        
        # Create transformed question following data_formatted.json structure
        transformed_question = {
            "question_text": question.get('question_text', ''),
            "options": transformed_options,
            "correct_answer": question.get('correct_answer', ''),
            "explanation": explanation_data.get('explanation', '') if explanation_data else question.get('explanation', ''),
            "difficulty_level": question.get('difficulty_level', 'medium'),  # Default to medium if not specified
            "estimated_time_seconds": 60,  # Default time estimation
            "content_tier": "free",  # Default content tier
            "source": "admin_uploaded",  # Default source
            "has_figure": question.get('has_figure', False),
            "type": question.get('question_type', 'reading_and_writing'),  # Map question_type to type
            "domain": question.get('domain', ''),
            "skill": question.get('skill', ''),
        }
        
        # Add additional fields from questions file
        if question.get('question_page') is not None:
            transformed_question['question_page'] = question.get('question_page')
        
        if question.get('fields_by_ai_gen'):
            transformed_question['fields_by_ai_gen'] = question.get('fields_by_ai_gen')
        
        # Update correct_answer from explanation if available
        if explanation_data and explanation_data.get('correct_answer'):
            transformed_question['correct_answer'] = explanation_data['correct_answer']
        
        return transformed_question
    
    def merge_explanations_into_questions(self, questions_data, questions, explanations):
        """Merge explanations into questions following data_formatted.json format"""
        
        # Create mapping
        explanation_mapping = self.create_explanation_mapping(explanations)
        
        matched_count = 0
        transformed_questions = []
        
        for question in questions:
            question_id = question.get('id', '')
            explanation_data = None
            
            if question_id in explanation_mapping:
                explanation_data = explanation_mapping[question_id]
                matched_count += 1
                print(f"✅ Matched explanation for {question_id}")
            else:
                print(f"❌ No explanation found for {question_id}")
            
            # Transform question to new format
            transformed_question = self.transform_question_format(question, explanation_data)
            transformed_questions.append(transformed_question)
        
        print(f"📊 Matched {matched_count}/{len(questions)} explanations")
        
        # Create new data structure following data_formatted.json format
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
        """Merge two files and save result in data_formatted.json format"""
        
        print("🔄 MERGE QUESTIONS WITH EXPLANATIONS (DATA_FORMATTED FORMAT)")
        print("=" * 60)
        print(f"📄 Questions file: {questions_file}")
        print(f"📄 Explanations file: {explanations_file}")
        print(f"📄 Output file: {output_file}")
        print(f"🎯 Output format: Compatible with data_formatted.json")
        
        # Load questions
        questions_data, questions = self.load_questions(questions_file)
        if not questions:
            return None
        
        # Load explanations
        explanations = self.load_explanations(explanations_file)
        if not explanations:
            return None
        
        # Merge
        merged_data, matched_count = self.merge_explanations_into_questions(
            questions_data, questions, explanations
        )
        
        # Save result
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(merged_data, f, ensure_ascii=False, indent=2)
            
            print(f"\n✅ MERGE COMPLETED!")
            print(f"📄 Result file: {output_file}")
            print(f"📊 Statistics:")
            print(f"   - Total questions: {len(merged_data['questions'])}")
            print(f"   - With explanations: {matched_count}")
            print(f"   - Match rate: {matched_count/len(merged_data['questions'])*100:.1f}%")
            
            # Show field distribution
            questions_with_fields = merged_data['questions']
            
            # Count question types
            math_count = sum(1 for q in questions_with_fields if q.get('type') == 'math')
            reading_count = sum(1 for q in questions_with_fields if q.get('type') == 'reading_and_writing')
            
            print(f"\n📈 Question type distribution:")
            print(f"   - Math: {math_count} questions")
            print(f"   - Reading and Writing: {reading_count} questions")
            
            # Count fields_by_ai_gen
            with_ai_fields = sum(1 for q in questions_with_fields if q.get('fields_by_ai_gen'))
            print(f"   - With AI-generated fields: {with_ai_fields} questions")
            
            # Count question_page
            with_page_numbers = sum(1 for q in questions_with_fields if q.get('question_page') is not None)
            print(f"   - With page numbers: {with_page_numbers} questions")
            
            # Show examples
            questions_with_explanations = [q for q in questions_with_fields if q.get('explanation')]
            if questions_with_explanations:
                print(f"\n📝 SAMPLE MERGED QUESTIONS:")
                for i, q in enumerate(questions_with_explanations[:2], 1):
                    print(f"\n--- Example {i} ---")
                    print(f"Type: {q.get('type', 'N/A')}")
                    print(f"Domain: {q.get('domain', 'N/A')}")
                    print(f"Skill: {q.get('skill', 'N/A')}")
                    print(f"Correct Answer: {q.get('correct_answer', 'N/A')}")
                    print(f"Has Figure: {q.get('has_figure', False)}")
                    print(f"Difficulty: {q.get('difficulty_level', 'N/A')}")
                    
                    if q.get('question_page') is not None:
                        print(f"Page: {q.get('question_page')}")
                    
                    if q.get('fields_by_ai_gen'):
                        print(f"AI Generated Fields: {', '.join(q.get('fields_by_ai_gen', []))}")
                    
                    question_text = q.get('question_text', '')[:100]
                    print(f"Question: {question_text}...")
                    
                    explanation = q.get('explanation', '')[:200]
                    print(f"Explanation: {explanation}...")
                    
                    print(f"Options: {len(q.get('options', []))} choices")
                    print("-" * 40)
            
            return merged_data
            
        except Exception as e:
            print(f"❌ Error saving file: {e}")
            return None

def main():
    """Main function with updated default files"""
    
    # Updated default file paths
    questions_file = "questions_new.json"  # Updated to use question_new.json
    explanations_file = "explanations.json"  # Updated to use explanations.json
    output_file = "questions_explanations_formatted.json"
    
    # Check if files exist
    if not os.path.exists(questions_file):
        print(f"❌ Questions file not found: {questions_file}")
        print("💡 Available question files:")
        for f in os.listdir('.'):
            if f.endswith('.json') and 'question' in f.lower():
                print(f"   - {f}")
        return
    
    if not os.path.exists(explanations_file):
        print(f"❌ Explanations file not found: {explanations_file}")
        print("💡 Available explanation files:")
        for f in os.listdir('.'):
            if f.endswith('.json') and 'explan' in f.lower():
                print(f"   - {f}")
        return
    
    # Merge
    merger = QuestionExplanationMerger()
    result = merger.merge_files(questions_file, explanations_file, output_file)
    
    if result:
        print(f"\n🎉 Merge successful!")
        print(f"📄 Complete file: {output_file}")
        print(f"🎯 Format: Compatible with data_formatted.json")
        print(f"💡 Additional fields preserved: question_page, fields_by_ai_gen")
    else:
        print(f"\n❌ Merge failed!")

if __name__ == "__main__":
    main() 