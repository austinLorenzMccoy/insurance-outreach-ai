from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from backend.core.config import settings
from backend.models.domain import Prospect, OutreachHistory


class ProspectDatabase:
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else Path(settings.DATA_FILE)
        self.prospects: Dict[str, Prospect] = {}
        self.history: Dict[str, OutreachHistory] = {}
        self._load_db()

    def _load_db(self):
        if self.db_path.exists():
            try:
                with open(self.db_path, "r") as f:
                    data = json.load(f)
                self.prospects = {k: Prospect(**v) for k, v in data.get("prospects", {}).items()}
                self.history = {k: OutreachHistory(**v) for k, v in data.get("history", {}).items()}
            except Exception:
                # reset on corruption
                self.prospects = {}
                self.history = {}
        self._save_db()

    def _save_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.db_path, "w") as f:
            json.dump(
                {
                    "prospects": {k: v.model_dump() for k, v in self.prospects.items()},
                    "history": {k: v.model_dump() for k, v in self.history.items()},
                },
                f,
                indent=2,
                default=str,
            )

    # Prospect ops
    def add_prospect(self, prospect: Prospect) -> str:
        self.prospects[prospect.id] = prospect
        self._save_db()
        return prospect.id

    def update_prospect(self, prospect_id: str, data: Dict) -> bool:
        if prospect_id in self.prospects:
            updated = self.prospects[prospect_id].model_dump()
            updated.update(data)
            self.prospects[prospect_id] = Prospect(**updated)
            self._save_db()
            return True
        return False

    def get_prospect(self, prospect_id: str) -> Optional[Prospect]:
        return self.prospects.get(prospect_id)

    def list_prospects(self) -> List[Prospect]:
        return list(self.prospects.values())

    # History ops
    def add_history(self, history: OutreachHistory) -> str:
        self.history[history.id] = history
        if history.prospect_id in self.prospects:
            self.prospects[history.prospect_id].last_contact = history.timestamp
        self._save_db()
        return history.id

    def update_history(self, history_id: str, data: Dict) -> bool:
        if history_id in self.history:
            updated = self.history[history_id].model_dump()
            updated.update(data)
            self.history[history_id] = OutreachHistory(**updated)
            self._save_db()
            return True
        return False

    def get_history(self, history_id: str) -> Optional[OutreachHistory]:
        return self.history.get(history_id)

    def get_prospect_history(self, prospect_id: str) -> List[OutreachHistory]:
        return [h for h in self.history.values() if h.prospect_id == prospect_id]
