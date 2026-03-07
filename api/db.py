import json
import os
from typing import Any, Dict, List, Optional


class ChannelStore:
    def __init__(self, path: str) -> None:
        self.path = path
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            self._write([])

    def _read(self) -> List[Dict[str, Any]]:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _write(self, items: List[Dict[str, Any]]) -> None:
        tmp = f"{self.path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def list(self) -> List[Dict[str, Any]]:
        return self._read()

    def get(self, channel_id: str) -> Optional[Dict[str, Any]]:
        for item in self._read():
            if item.get("id") == channel_id:
                return item
        return None

    def upsert(self, item: Dict[str, Any]) -> Dict[str, Any]:
        items = self._read()
        for idx, existing in enumerate(items):
            if existing.get("id") == item.get("id"):
                items[idx] = item
                self._write(items)
                return item
        items.append(item)
        self._write(items)
        return item

    def delete(self, channel_id: str) -> bool:
        items = self._read()
        new_items = [x for x in items if x.get("id") != channel_id]
        changed = len(new_items) != len(items)
        if changed:
            self._write(new_items)
        return changed
