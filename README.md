# SAT PDF Extraction Tool

A comprehensive tool for extracting SAT questions and explanations from PDF files using Google's Gemini AI. This tool can process individual files or batch process entire directories of PDFs.

## 🚀 Features

- **Batch Processing**: Extract from multiple PDF files automatically
- **Parallel Extraction**: Questions and explanations processed simultaneously for faster results
- **Smart Merging**: Automatically combines incomplete questions/explanations split across PDF pages
- **Duplicate Detection**: Removes duplicate content while keeping the most complete versions
- **Math Support**: Preserves LaTeX math expressions and table formatting
- **Robust Error Handling**: Retry mechanisms and detailed error reporting
- **Progress Tracking**: Real-time progress updates during processing

## 📋 Prerequisites

- Python 3.8 or higher
- Google Gemini API key
- PDF files containing SAT questions and/or explanations

## 🛠️ Installation

1. **Clone or download the project files**
   ```bash
   git clone <repository-url>
   cd sat-pdf-extractor
   ```

2. **Install required dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up your Google Gemini API key**
   
   Create a `.env` file in the project root:
   ```bash
   echo "GEMINI_KEY=your_api_key_here" > .env
   ```
   
   Or set it as an environment variable:
   ```bash
   export GEMINI_KEY=your_api_key_here
   ```

## 📁 Project Structure

```
sat-pdf-extractor/
├── batch_extract_v2_questions.py     # Extract questions from PDFs
├── batch_extract_v2_explanations.py  # Extract explanations from PDFs
├── automated_sat_extractor.py        # Automated pipeline (recommended)
├── merge_questions_explanations.py   # Merge separate files
├── sat_question_viewer.py            # Interactive quiz viewer
├── requirements.txt                  # Python dependencies
├── .env                              # API key configuration
└── README.md                         # This file
```

## 🎯 Quick Start

### Option 1: Automated Pipeline (Recommended)

Process questions and explanations simultaneously:

```bash
python automated_sat_extractor.py questions_folder explanations_folder -o complete_results.json
```

### Option 2: Individual Processing

Extract questions only:
```bash
python batch_extract_v2_questions.py pdf_folder -o questions.json
```

Extract explanations only:
```bash
python batch_extract_v2_explanations.py pdf_folder -o explanations.json
```

## 📖 Detailed Usage

### Automated Pipeline

The automated pipeline is the recommended approach as it processes both questions and explanations in parallel:

```bash
# Basic usage
python automated_sat_extractor.py questions_dir explanations_dir

# With custom output file
python automated_sat_extractor.py questions_dir explanations_dir -o my_results.json

# Limit processing (for testing)
python automated_sat_extractor.py questions_dir explanations_dir --max-files 5
```

**Parameters:**
- `questions_dir`: Directory containing PDF files with SAT questions
- `explanations_dir`: Directory containing PDF files with explanations
- `-o, --output`: Output JSON file name (default: `automated_sat_complete.json`)
- `--max-files`: Maximum number of files to process per directory (for testing)

### Individual Extraction Scripts

#### Questions Extraction

```bash
# Extract from all PDFs in directory
python batch_extract_v2_questions.py input_folder

# Custom output file
python batch_extract_v2_questions.py input_folder -o my_questions.json

# Limit files for testing
python batch_extract_v2_questions.py input_folder --max-files 3
```

#### Explanations Extraction

```bash
# Extract from all PDFs in directory
python batch_extract_v2_explanations.py input_folder

# Custom output file
python batch_extract_v2_explanations.py input_folder -o my_explanations.json

# Limit files for testing
python batch_extract_v2_explanations.py input_folder --max-files 3
```

## 📊 Output Format

The tool generates JSON files with the following structure:

```json
{
  "totalCount": 150,
  "questions": [
    {
      "id": "q_001",
      "question_text": "What is the value of x in the equation 2x + 5 = 13?",
      "options": [
        {"id": "A", "text": "3"},
        {"id": "B", "text": "4"},
        {"id": "C", "text": "5"},
        {"id": "D", "text": "6"}
      ],
      "correct_answer": "B",
      "explanation": "To solve 2x + 5 = 13, subtract 5 from both sides: 2x = 8, then divide by 2: x = 4",
      "question_type": "math",
      "domain": "Algebra",
      "skill": "Linear Equations",
      "difficulty_level": "easy",
      "has_figure": false,
      "is_complete": true,
      "source_file": "practice_test_1.pdf"
    }
  ],
  "metadata": {
    "total_files_processed": 10,
    "total_files_successful": 9,
    "total_files_failed": 1,
    "extraction_date": "2024-01-15 14:30:25",
    "model_used": "gemini-2.5-flash-preview-05-20"
  }
}
```

## 🔧 Advanced Features

### Smart Processing

- **Incomplete Question Merging**: Automatically combines questions split across PDF pages
- **Duplicate Removal**: Detects and removes duplicate content, keeping the most complete version
- **Math Preservation**: Maintains LaTeX formatting for mathematical expressions
- **Table Support**: Preserves table structures in LaTeX format

### Error Recovery

- **Retry Mechanism**: Automatically retries failed API calls
- **Graceful Degradation**: Continues processing even if some files fail
- **Debug Output**: Saves problematic responses for manual review

### Batch Processing

- **Progress Tracking**: Real-time updates on processing status
- **File Validation**: Checks file existence and format before processing
- **Memory Efficient**: Processes files sequentially to manage memory usage

## 🎮 Interactive Viewer

After extraction, use the interactive quiz viewer:

```bash
python sat_question_viewer.py
```

Features:
- Browse extracted questions
- Take practice quizzes
- View explanations
- Filter by type/domain
- Track your progress

## ⚙️ Configuration

### API Settings

The tool uses Google's Gemini AI model. Configure in your `.env` file:

```env
GEMINI_KEY=your_api_key_here
```

### Processing Parameters

You can modify these in the script files:
- `temperature=0.1`: AI creativity level (lower = more consistent)
- `max_output_tokens=50000`: Maximum response length
- `max_retries=3`: Number of retry attempts for failed requests

## 🐛 Troubleshooting

### Common Issues

**"GEMINI_KEY not found"**
- Ensure your `.env` file contains the API key
- Check that the `.env` file is in the same directory as the scripts

**"No PDF files found"**
- Verify the directory path is correct
- Ensure PDF files have `.pdf` extension
- Check file permissions

**"JSON parsing failed"**
- This usually indicates an API response issue
- Check the generated debug files for details
- Verify your API key is valid and has sufficient quota

**Rate limiting errors**
- The tool includes automatic delays between requests
- Consider reducing batch size with `--max-files`
- Check your API quota and limits

### Debug Information

The tool generates debug files when errors occur:
- `debug_response_*.txt`: Raw API responses for failed parsing
- Console output includes detailed progress and error information

## 📝 File Requirements

### Input PDFs

- **Questions PDFs**: Should contain SAT questions with multiple choice options
- **Explanations PDFs**: Should contain detailed explanations for answers
- **Format**: Standard PDF format, text-based (not scanned images)
- **Organization**: Files can be in any order; the tool handles sequencing

### Optimal PDF Structure

For best results, ensure PDFs have:
- Clear question numbering
- Well-formatted multiple choice options (A, B, C, D)
- Readable text (not heavily formatted or image-based)
- Consistent formatting across pages

## 🔄 Workflow Recommendations

1. **Organize your PDFs**: Separate questions and explanations into different folders
2. **Test with small batches**: Use `--max-files 2` first to verify everything works
3. **Use automated pipeline**: It's more efficient than running scripts separately
4. **Review the output**: Check the generated JSON for completeness and accuracy
5. **Use the viewer**: Test your extracted content with the interactive quiz tool

## 📈 Performance Tips

- **Parallel Processing**: Use the automated pipeline for faster results
- **Batch Size**: Process 10-20 files at a time for optimal performance
- **Network**: Ensure stable internet connection for API calls
- **Resources**: Monitor memory usage with very large PDF collections

## 🆘 Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review the console output for specific error messages
3. Examine generated debug files
4. Verify your API key and quota
5. Test with a small sample of files first

## 📜 License

This tool is provided as-is for educational purposes. Please ensure compliance with Google's Gemini API terms of service and any applicable terms for the PDF content you're processing.

---

**Happy extracting! 🎓✨** 