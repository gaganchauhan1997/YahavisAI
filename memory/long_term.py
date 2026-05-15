"""
YAHAVIS — memory/long_term.py
Persistent JSON-based memory store.
Survives restarts — facts, preferences, learned patterns.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("yahavis.long_term")


class LongTermMemory:
    """
    Persistent key-value + semantic memory store.
    Backed by a JSON file — simple, no external DB needed.

    Categories:
    - facts:       General remembered information
    - preferences: User preferences and settings
    - skills:      Learned shortcuts and custom behaviors
    - contacts:    People and their details
    - tasks:       Long-running or recurring tasks
    """

    def __init__(self, db_path: Path = None):
        self.db_path = db_path or Path("memory/yahavis_memory.json")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._data: Dict = self._load()
        log.info(f"Long-term memory loaded: {sum(len(v) for v in self._data.values())} records")

    def _load(self) -> Dict:
        if self.db_path.exists():
            try:
                return json.loads(self.db_path.read_text(encoding="utf-8"))
            except Exception as e:
                log.warning(f"Memory load failed: {e} — starting fresh")
        return {
            "facts": {},
            "preferences": {},
            "skills": {},
            "contacts": {},
            "tasks": {},
            "meta": {"created": datetime.now().isoformat(), "version": "1.0"},
        }

    def save(self):
        """Persist memory to disk."""
        self._data["meta"]["last_saved"] = datetime.now().isoformat()
        self.db_path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        log.debug("Long-term memory saved.")

    def save_fact(self, key: str, value: Any, category: str = "facts"):
        """Store a fact."""
        if category not in self._data:
            self._data[category] = {}
        self._data[category][key] = {
            "value": value,
            "saved_at": datetime.now().isoformat(),
        }
        self.save()
        log.info(f"Remembered [{category}] {key}")

    def recall(self, key: str, category: str = None) -> Optional[Any]:
        """Retrieve a fact by key. Searches all categories if none specified."""
        if category:
            record = self._data.get(category, {}).get(key)
            return record["value"] if record else None

        # Search all categories
        for cat, items in self._data.items():
            if isinstance(items, dict) and key in items:
                record = items[key]
                if isinstance(record, dict) and "value" in record:
                    return record["value"]
        return None

    def search(self, query: str) -> List[dict]:
        """Fuzzy search across all memory categories."""
        results = []
        query_lower = query.lower()
        for category, items in self._data.items():
            if not isinstance(items, dict):
                continue
            for key, record in items.items():
                if isinstance(record, dict):
                    value_str = str(record.get("value", "")).lower()
                    key_str = key.lower()
                    if query_lower in key_str or query_lower in value_str:
                        results.append({
                            "category": category,
                            "key": key,
                            "value": record.get("value"),
                            "saved_at": record.get("saved_at"),
                        })
        return results

    def forget(self, key: str, category: str = "facts") -> bool:
        """Remove a specific memory."""
        if key in self._data.get(category, {}):
            del self._data[category][key]
            self.save()
            log.info(f"Forgot [{category}] {key}")
            return True
        return False

    def set_preference(self, key: str, value: Any):
        self.save_fact(key, value, category="preferences")

    def get_preference(self, key: str, default: Any = None) -> Any:
        return self.recall(key, category="preferences") or default

    def remember_person(self, name: str, details: dict):
        self.save_fact(name, details, category="contacts")

    def get_person(self, name: str) -> Optional[dict]:
        return self.recall(name, category="contacts")

    def all_facts(self, category: str = "facts") -> dict:
        items = self._data.get(category, {})
        return {k: v["value"] for k, v in items.items()
                if isinstance(v, dict) and "value" in v}

    def stats(self) -> dict:
        return {
            cat: len(items)
            for cat, items in self._data.items()
            if isinstance(items, dict) and cat != "meta"
        }

    def export(self) -> str:
        """Export full memory as JSON string."""
        return json.dumps(self._data, indent=2, ensure_ascii=False)

    def import_data(self, json_str: str):
        """Import memory from JSON string (merges with existing)."""
        new_data = json.loads(json_str)
        for category, items in new_data.items():
            if category in self._data and isinstance(items, dict):
                self._data[category].update(items)
        self.save()
