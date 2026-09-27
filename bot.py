import time
from datetime import datetime
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any, List, Optional
import uvicorn

from context_store import ContextStore
from conversation_state import ConversationManager
from composer import Composer

app = FastAPI()
START_TIME = time.time()

store = ContextStore()
conv_manager = ConversationManager()
composer = Composer()

class CtxBody(BaseModel):
    scope: str
    context_id: str
    version: int
    payload: dict[str, Any]
    delivered_at: str

@app.get("/v1/healthz")
async def healthz():
    return {
        "status": "ok", 
        "uptime_seconds": int(time.time() - START_TIME), 
        "contexts_loaded": store.get_counts()
    }

@app.get("/v1/metadata")
async def metadata():
    return {
        "team_name": "Vera Baseline",
        "team_members": ["Candidate"],
        "model": "rules-baseline",
        "approach": "Deterministic baseline",
        "contact_email": "candidate@example.com",
        "version": "1.0.0",
        "submitted_at": datetime.utcnow().isoformat() + "Z"
    }

@app.post("/v1/context")
async def push_context(body: CtxBody):
    success, current_version = store.update(body.scope, body.context_id, body.version, body.payload)
    if not success:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=409, content={"accepted": False, "reason": "stale_version", "current_version": current_version})
    
    return {
        "accepted": True, 
        "ack_id": f"ack_{body.context_id}_v{body.version}",
        "stored_at": datetime.utcnow().isoformat() + "Z"
    }

class TickBody(BaseModel):
    now: str
    available_triggers: List[str] = []

@app.post("/v1/tick")
async def tick(body: TickBody):
    actions = []
    
    for trg_id in body.available_triggers[:20]:
        trg = store.get("trigger", trg_id)
        if not trg: continue
        
        merchant_id = trg.get("merchant_id")
        merchant = store.get("merchant", merchant_id)
        if not merchant: continue
        
        category = store.get("category", merchant.get("category_slug"))
        customer_id = trg.get("customer_id")
        customer = store.get("customer", customer_id) if customer_id else None
        
        suppression_key = trg.get("suppression_key", "")
        if conv_manager.is_suppressed(merchant_id, suppression_key):
            continue
            
        action = composer.compose_tick(category, merchant, trg, customer)
        if action:
            conv_id = f"conv_{merchant_id}_{trg_id}"
            action["conversation_id"] = conv_id
            action["trigger_id"] = trg_id
            
            conv_manager.log_bot_message(conv_id, action["body"])
            actions.append(action)
            
    return {"actions": actions}

class ReplyBody(BaseModel):
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    from_role: str
    message: str
    received_at: str
    turn_number: int

@app.post("/v1/reply")
async def reply(body: ReplyBody):
    action = conv_manager.handle_reply(body.conversation_id, body.merchant_id, body.message, body.turn_number)
    
    if action["action"] == "send":
        action.update(composer.compose_reply(body.message, action.get("intent", "general")))
        
    return action

@app.post("/v1/teardown")
async def teardown():
    store.clear()
    conv_manager.clear()
    return {"status": "cleared"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)