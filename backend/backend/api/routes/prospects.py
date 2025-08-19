from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Optional, List

from backend.models.domain import Prospect
from backend.services.db import ProspectDatabase
from backend.services.workflow import OutreachWorkflow

router = APIRouter()


@router.post("/")
async def create_prospect(prospect: Prospect, background_tasks: BackgroundTasks):
    db = ProspectDatabase()
    prospect_id = db.add_prospect(prospect)
    workflow = OutreachWorkflow(db=db)
    background_tasks.add_task(workflow.process_prospect, prospect=prospect)
    return {"message": "Prospect added and processing started", "prospect_id": prospect_id}


@router.get("/{prospect_id}")
async def get_prospect(prospect_id: str):
    db = ProspectDatabase()
    prospect = db.get_prospect(prospect_id)
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    return prospect


@router.get("/{prospect_id}/history")
async def get_prospect_history(prospect_id: str):
    db = ProspectDatabase()
    return db.get_prospect_history(prospect_id)


@router.get("")
async def list_prospects() -> List[Prospect]:
    db = ProspectDatabase()
    return db.list_prospects()
