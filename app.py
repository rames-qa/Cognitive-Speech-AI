from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
app = FastAPI()
# Crucial: Allow browser requests from local or remote origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
class CommandModel(BaseModel):
    command: str
@app.post("/api/command")
def handle_command(payload: CommandModel):
    user_command = payload.command.lower()      
    # Intent mapping for speech commands
    if "youtube" in user_command:
        return {
            "action": "Opening YouTube right now.",
            "url": "https://www.youtube.com"
        }
    elif "google" in user_command:
        return {
            "action": "Launching Google search engine.",
            "url": "https://www.google.com"
        }
    elif "status" in user_command:
        return {
            "action": "All cognitive neural arrays and vision matrix modules are operating at peak efficiency.",
            "url": None
        }  
    # General fallback response
    return {
        "action": f"Processed command string: {user_command}",
        "url": None
    }
@app.get("/")
def read_root():
    return {"status": "Cognitive Speech AI Engine Online"}
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)
