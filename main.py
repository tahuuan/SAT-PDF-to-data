from fastapi import FastAPI
from app.controllers import api_controller

app = FastAPI()

app.include_router(api_controller.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 