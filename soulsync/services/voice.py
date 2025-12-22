import requests
from ..config import GOOGLE_API_KEY, GEMINI_MODEL_ID
from ..models import VoiceMessage
from sqlalchemy.orm import Session

def get_ai_response(user_id: int, user_text: str, context: str, db: Session):
    # Save user message
    db.add(VoiceMessage(user_id=user_id, role="user", text=user_text))
    db.commit()

    if not GOOGLE_API_KEY:
        response_text = "I'm listening! (AI features are currently in fallback mode because no API key was found, but I'm here to support you.)"
    else:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL_ID}:generateContent?key={GOOGLE_API_KEY}"
            headers = {'Content-Type': 'application/json'}
            payload = {
                "contents": [{
                    "parts": [{"text": f"Context: {context}\n\nUser: {user_text}\n\nRespond as a supportive student life coach."}]
                }]
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            if resp.status_code == 200:
                response_text = resp.json()['candidates'][0]['content']['parts'][0]['text']
            else:
                response_text = "I'm having trouble connecting to my brain right now, but I hear you!"
        except Exception as e:
            response_text = "I'm having a bit of trouble thinking clearly right now."

    # Save AI message
    db.add(VoiceMessage(user_id=user_id, role="assistant", text=response_text))
    db.commit()
    return response_text
