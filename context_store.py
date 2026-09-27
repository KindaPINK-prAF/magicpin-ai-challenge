class ContextStore:
    def __init__(self):
        self._store = {}

    def update(self, scope: str, context_id: str, version: int, payload: dict) -> tuple[bool, int]:
        key = (scope, context_id)
        current = self._store.get(key)
        
        # Only reject if we already possess a STRICTLY HIGHER version
        if current and current["version"] > version:
            return False, current["version"]
            
        self._store[key] = {"version": version, "payload": payload}
        return True, version

    def get(self, scope: str, context_id: str) -> dict:
        data = self._store.get((scope, context_id))
        return data["payload"] if data else None

    def get_counts(self) -> dict:
        counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
        for (scope, _) in self._store.keys():
            if scope in counts:
                counts[scope] += 1
        return counts

    def clear(self):
        self._store.clear()