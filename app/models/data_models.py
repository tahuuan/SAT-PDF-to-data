from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class UploadType(str, Enum):
    COMBINED = "combined"
    SEPARATE = "separated"

class Option(BaseModel):
    value: str
    text: str

class DifficultyLevel(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

class QuestionType(str, Enum):
    MATH = "math"
    READING_AND_WRITING = "reading_and_writing"

class FieldByAiGen(str, Enum):
    difficulty_level = "difficulty_level"
    question_type = "question_type"
    domain = "domain"
    skill = "skill"

class Question(BaseModel):
    id: str
    question_text: str
    options: List[Option]
    correct_answer: str
    explanation: Optional[str] = None
    difficulty_level: DifficultyLevel
    question_type: QuestionType
    domain: str
    skill: str
    is_complete: bool
    source_file: Optional[str] = None
    file_index: Optional[int] = None
    fields_by_ai_gen: Optional[List[str]] = None
    question_page: Optional[int] = None

class ExtractionRequest(BaseModel):
    upload_type: UploadType
    questions_pdf_url: str
    explanations_pdf_url: Optional[str] = None

    @model_validator(mode='after')
    def check_urls(self) -> 'ExtractionRequest':
        if self.upload_type == UploadType.SEPARATE and not self.explanations_pdf_url:
            raise ValueError('explanations_pdf_url is required for separate upload type')
        return self

class QuestionsResponse(BaseModel):
    totalCount: int
    questions: List[Question]

class Explanation(BaseModel):
    id: str
    correct_answer: str
    explanation: str
    is_complete: bool
    source_file: Optional[str] = None
    file_index: Optional[int] = None

class ExplanationsResponse(BaseModel):
    explanations: List[Explanation]

class PDFLinks(BaseModel):
    questions_pdf_url: str = Field(..., description="URL to the PDF containing the questions.")
    explanations_pdf_url: Optional[str] = Field(None, description="URL to the PDF containing the explanations. If omitted, the questions PDF is used for both.")

class ExtractionResponse(BaseModel):
    message: str
    request_id: str
    output_path: str