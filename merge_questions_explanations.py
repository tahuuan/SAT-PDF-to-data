#!/usr/bin/env python3
"""
Merge Questions with Explanations
Combine extracted explanations into questions file
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
        """Load file explanations"""
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
    
    def merge_explanations_into_questions(self, questions_data, questions, explanations):
        """Merge explanations into questions"""
        
        # Create mapping
        explanation_mapping = self.create_explanation_mapping(explanations)
        
        matched_count = 0
        
        for question in questions:
            question_id = question.get('id', '')
            
            if question_id in explanation_mapping:
                explanation_data = explanation_mapping[question_id]
                
                # Merge explanation
                question['explanation'] = explanation_data.get('explanation', '')
                
                # Update correct_answer if present in explanation
                if explanation_data.get('correct_answer'):
                    question['correct_answer'] = explanation_data['correct_answer']
                
                matched_count += 1
                print(f"✅ Matched explanation for {question_id}")
            else:
                print(f"❌ No explanation found for {question_id}")
        
        print(f"📊 Matched {matched_count}/{len(questions)} explanations")
        
        # Update metadata
        if 'metadata' not in questions_data:
            questions_data['metadata'] = {}
        
        questions_data['metadata']['explanations_merged'] = True
        questions_data['metadata']['explanations_matched'] = matched_count
        questions_data['metadata']['explanations_total'] = len(explanations)
        questions_data['metadata']['merge_date'] = time.strftime('%Y-%m-%d %H:%M:%S')
        
        return questions_data, matched_count
    
    def merge_files(self, questions_file, explanations_file, output_file):
        """Merge two files and save result"""
        
        print("🔄 MERGE QUESTIONS WITH EXPLANATIONS")
        print("=" * 50)
        print(f"📄 Questions file: {questions_file}")
        print(f"📄 Explanations file: {explanations_file}")
        print(f"📄 Output file: {output_file}")
        
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
            
            print(f"\n✅ COMPLETED!")
            print(f"📄 Result file: {output_file}")
            print(f"📊 Statistics:")
            print(f"   - Total questions: {len(questions)}")
            print(f"   - With explanations: {matched_count}")
            print(f"   - Match rate: {matched_count/len(questions)*100:.1f}%")
            
            # Show examples
            questions_with_explanations = [q for q in questions if q.get('explanation')]
            if questions_with_explanations:
                print(f"\n📝 SAMPLE QUESTIONS WITH EXPLANATIONS:")
                for i, q in enumerate(questions_with_explanations[:2], 1):
                    print(f"\n--- Example {i} ---")
                    print(f"ID: {q.get('id', 'N/A')}")
                    print(f"Type: {q.get('question_type', 'N/A')}")
                    print(f"Correct Answer: {q.get('correct_answer', 'N/A')}")
                    
                    question_text = q.get('question_text', '')[:100]
                    print(f"Question: {question_text}...")
                    
                    explanation = q.get('explanation', '')[:200]
                    print(f"Explanation: {explanation}...")
                    print("-" * 30)
            
            return merged_data
            
        except Exception as e:
            print(f"❌ Error saving file: {e}")
            return None

def main():
    """Main function with default files"""
    
    # Default file paths
    questions_file = "questions.json"
    explanations_file = "explanations.json"
    output_file = "questions_with_explanations.json"
    
    # Check if files exist
    if not os.path.exists(questions_file):
        print(f"❌ Questions file not found: {questions_file}")
        print("💡 Run batch_extract_v2.py first to create questions file")
        return
    
    if not os.path.exists(explanations_file):
        print(f"❌ Explanations file not found: {explanations_file}")
        print("💡 Run batch_extract_explanations.py first to create explanations file")
        return
    
    # Merge
    merger = QuestionExplanationMerger()
    result = merger.merge_files(questions_file, explanations_file, output_file)
    
    if result:
        print(f"\n🎉 Merge successful!")
        print(f"📄 Complete file: {output_file}")
    else:
        print(f"\n❌ Merge failed!")

if __name__ == "__main__":
    main() 