import re

class ConversationManager:
    def __init__(self):
        self.conversations = {}
        self.merchant_auto_replies = {}
        self.suppressions = set()

    def log_bot_message(self, conv_id: str, text: str):
        if conv_id not in self.conversations:
            self.conversations[conv_id] = {"turns": [], "last_bot_msg": ""}
        self.conversations[conv_id]["last_bot_msg"] = text

    def handle_reply(self, conv_id: str, merchant_id: str, message: str, turn: int) -> dict:
        if conv_id not in self.conversations:
            self.conversations[conv_id] = {"turns": [], "last_bot_msg": ""}
            
        history = self.conversations[conv_id]["turns"]
        history.append(message)
        msg_lower = message.lower()

        # 1. Hostile / Opt-out Detection
        if re.search(r'\b(stop|spam|useless|not interested|unsubscribe|leave me alone)\b', msg_lower):
            if merchant_id:
                self.suppressions.add(f"global_opt_out_{merchant_id}")
            return {"action": "end", "rationale": "Merchant explicitly opted out or is hostile. Ending thread."}

        # 2. WhatsApp Business Canned Auto-Reply Detection
        canned_patterns = [
            r"thank you for contacting",
            r"will respond shortly",
            r"automated assistant",
            r"currently unavailable",
            r"hamari team tak pahuncha",
            r"auto-reply"
        ]
        is_canned = any(re.search(pat, msg_lower) for pat in canned_patterns)
        
        m_key = merchant_id or "default"
        if is_canned:
            self.merchant_auto_replies[m_key] = self.merchant_auto_replies.get(m_key, 0) + 1
            auto_count = self.merchant_auto_replies[m_key]
            if auto_count >= 3:
                return {
                    "action": "end",
                    "rationale": "Repeated WhatsApp Business auto-replies detected 3+ times. Gracefully ending conversation."
                }
            return {
                "action": "wait",
                "wait_seconds": 14400,
                "rationale": f"Detected WhatsApp Business canned greeting (occurrence {auto_count}). Waiting 4 hours for human owner."
            }

        # Reset auto-reply counter if genuine reply arrives
        self.merchant_auto_replies[m_key] = 0

        # Check for repetition of identical message within same conversation
        if len(history) >= 3 and history[-1] == history[-2] == history[-3]:
            return {"action": "end", "rationale": "Detected continuous verbatim loop. Exiting gracefully."}
        if len(history) >= 2 and history[-1] == history[-2]:
            return {"action": "wait", "wait_seconds": 14400, "rationale": "Repeated canned phrase detected. Backing off 4 hours."}

        # 3. Intent Transition Detection
        if re.search(r'\b(yes|let\'s do it|sure|ok|send|proceed|start|draft)\b', msg_lower):
            return {"action": "send", "intent": "action_commit", "rationale": "Clear merchant buy-in. Moving immediately to action."}

        # 4. Off-topic redirection
        if re.search(r'\b(gst|loan|taxes|tax|unrelated|accountant)\b', msg_lower):
            return {"action": "send", "intent": "redirect", "rationale": "Off-topic query detected. Redirecting to core mission."}

        return {"action": "send", "intent": "general", "rationale": "Continuing standard engagement."}

    def is_suppressed(self, merchant_id: str, suppression_key: str) -> bool:
        if f"global_opt_out_{merchant_id}" in self.suppressions:
            return True
        return suppression_key in self.suppressions

    def clear(self):
        self.conversations.clear()
        self.merchant_auto_replies.clear()
        self.suppressions.clear()