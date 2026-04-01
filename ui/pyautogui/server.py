from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
import traceback
import io
import pyautogui

app = FastAPI(title="Remote UI Control Server")

class ActionRequest(BaseModel):
    code: str

@app.get("/screenshot")
def take_screenshot():
    try:
        img = pyautogui.screenshot()
        byte_io = io.BytesIO()
        img.save(byte_io, format='PNG')
        return Response(content=byte_io.getvalue(), media_type="image/png")
    except Exception as e:
        error_msg = traceback.format_exc()
        raise HTTPException(status_code=500, detail=f"Screenshot failed:\n{error_msg}")

@app.post("/action")
def execute_action(req: ActionRequest):
    # This endpoint accepts python code with pyautogui commands and executes them.
    # We use exec() to run the provided python code string.
    try:
        # It's a good idea to pass a clean scope or provide explicitly what they need
        # e.g. import pyautogui is expected to be part of their request or provided here.
        local_scope = {}
        exec(req.code, globals(), local_scope)
        return {"status": "success", "message": "Code executed successfully."}
    except Exception as e:
        error_msg = traceback.format_exc()
        raise HTTPException(status_code=400, detail=f"Execution failed:\n{error_msg}")

if __name__ == "__main__":
    import uvicorn
    # Make the server accessible on the local network
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
