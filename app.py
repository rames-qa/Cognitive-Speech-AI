
from fastapi import FastAPI



app = FastAPI(title="Cognitive Speech AI API")



@app.get("/")

def read_root():

    return {"message": "Cognitive Speech AI Backend is running successfully!"}



@app.get("/health")

def health_check():

    return {"status": "healthy"}

