from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

from backend.services.call import CallService

router = APIRouter()


class CallRequest(BaseModel):
    prospect: Dict[str, Any]
    script: Dict[str, Any]
    history_id: str


@router.post("/schedule_call")
async def schedule_call(call_request: CallRequest):
    try:
        service = CallService()
        return service.schedule_call(call_request.prospect, call_request.script, call_request.history_id)
    except Exception:
        raise HTTPException(status_code=500, detail="Call scheduling failed")
