import os
import uuid
from fastapi import APIRouter, BackgroundTasks, HTTPException
from app.services.extraction_service import run_full_extraction, download_pdf
from app.models.data_models import ExtractionRequest, UploadType

router = APIRouter()
jobs = {}

# Ensure temp_data directory exists
temp_data_dir = "temp_data"
if not os.path.exists(temp_data_dir):
    os.makedirs(temp_data_dir)

@router.post("/extract")
async def extract(request: ExtractionRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "starting", "result": None}

    questions_pdf_url = request.questions_pdf_url
    if request.upload_type == UploadType.COMBINED:
        explanations_pdf_url = questions_pdf_url
    else:
        # The model validator ensures this exists for SEPARATE type
        explanations_pdf_url = request.explanations_pdf_url

    output_filename = f"{job_id}_output.json"
    output_path = os.path.join(temp_data_dir, output_filename)

    def run_extraction_task(q_url, e_url):
        try:
            jobs[job_id]["status"] = "downloading"
            
            questions_pdf_path = os.path.join(temp_data_dir, f"{job_id}_questions.pdf")
            download_pdf(q_url, questions_pdf_path)

            if q_url == e_url:
                explanations_pdf_path = questions_pdf_path
            else:
                explanations_pdf_path = os.path.join(temp_data_dir, f"{job_id}_explanations.pdf")
                download_pdf(e_url, explanations_pdf_path)

            jobs[job_id]["status"] = "processing"
            run_full_extraction(questions_pdf_path, explanations_pdf_path, output_path)

            jobs[job_id]["status"] = "completed"
            jobs[job_id]["result"] = f"/data-raw/{output_filename}"

        except Exception as e:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["result"] = str(e)

    background_tasks.add_task(run_extraction_task, questions_pdf_url, explanations_pdf_url)
    
    return {"job_id": job_id, "status": "processing"}

@router.get("/status/{job_id}")
async def get_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job 