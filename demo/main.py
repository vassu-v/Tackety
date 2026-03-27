import os
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Tackety Demo Frontend")

# Get the directory where this file is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.get("/")
def serve_home():
    """Serves the main chat UI."""
    return FileResponse(os.path.join(BASE_DIR, "index.html"))

# If you have separate CSS/JS files later, you can mount them here:
# app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

if __name__ == "__main__":
    import uvicorn
    print("\n  Tackety Demo UI — Running independently")
    print("  http://localhost:3000\n")
    uvicorn.run(app, host="0.0.0.0", port=3000)
