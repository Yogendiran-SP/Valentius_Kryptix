from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google import genai
from google.genai import types, errors
from dotenv import load_dotenv
import httpx

# # Test cases
# from types import SimpleNamespace

load_dotenv()

app = FastAPI()
client = genai.Client(
    http_options=types.HttpOptions(timeout=30000)
)

conversations = {}

MAX_TURNS = 3

# # Test cases
# # "none"
# # "timeout"
# # "network"
# # "rate_limit"
# # "empty_summary"
# TEST_MODE = "empty_summary"

class ChatRequest(BaseModel):
    conversation_id: int
    message: str


@app.post("/chat")
def chat(request: ChatRequest):

    conversation_id = request.conversation_id

    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # memory = conversations[conversation_id] # Whole memory
    
    # Summary Generating
    memory = getContext(conversations[conversation_id])
    recent_turns = memory["turns"]
    content = []

    for turn in recent_turns:
        # User's prompt appending
        content.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=turn["user"])]
            )
        )
        
        # Model's response appending
        content.append(
            types.Content(
                role="model",
                parts=[types.Part.from_text(text=turn["model"])]
            )
        )
    
    # Current User's prompt appending
    content.append(
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=request.message)]
        )
    )

    response = call_gemini(
        contents=content,
        config=types.GenerateContentConfig(
            system_instruction=f"""
            You are a helpful AI learning assistant.

            Historical conversation summary (context only):
            {memory["summary"]}
            """
        )
    )

    if not response.text or not response.text.strip():
        raise HTTPException(
            status_code=502,
            detail="Gemini returned empty response."
        )

    conversations[conversation_id]["turns"].append({
        "user": request.message,
        "model": response.text
    })

    print(response)
    return response.text



def getContext(memory):
    older_turns = memory["turns"][:-MAX_TURNS]
    recent_turns = memory["turns"][-MAX_TURNS:]

    if older_turns:
        summary_prompt = f"""
        You are a conversation memory summarizer.

        Existing summary:
        {memory["summary"]}

        New older turns to incorporate:
        {older_turns}

        Create an updated, concise summary.

        Rules:
        - Preserve important facts & preferences.
        - Preserve ongoing tasks & decisions.
        - Do not invent information.
        - Avoid unnecessary conversation details
        - Return only the updated summary.
        """
        

        response = call_gemini(contents=summary_prompt)

        if not response.text or not (response.text).strip():
            raise HTTPException(
                status_code=502,
                detail="Failed to summarize conversation history."
            )
        
        memory["summary"] = response.text
        memory["turns"] = recent_turns
    
    return memory


@app.post("/conversations")
def create_conversations():
    new_id = max(conversations, default=0)+1
    conversations[new_id] = {
        "summary": "",
        "turns": []
    }

    return {
        "conversation_id": new_id,
        "message": "Conversation created successfully"
    }

def call_gemini(contents, config=None):
    try:
        # # Test cases
        # if TEST_MODE == "empty_summary" and config is None:
        #     return SimpleNamespace(text="")
        # if TEST_MODE == "timeout":
        #     raise httpx.ReadTimeout("Simulated timeout")

        # if TEST_MODE == "network":
        #     raise httpx.ConnectError("Simulated connection failure")

        # if TEST_MODE == "rate_limit":
        #     raise errors.APIError(
        #         429,
        #         {"message": "Simulated rate limit"}
        #     )

        return client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=contents,
            config=config
        )

    except httpx.TimeoutException as e:
        raise  HTTPException(
            status_code=504,
            detail="AI service timed out."
        )
    
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to AI service."
        )
    
    except errors.APIError as e:
        status = (
            504 if e.code in (408, 504)
            else 503 if e.code == 429
            else 502
        )
        raise HTTPException(
            status_code=status,
            detail="AI service request failed."
        ) from e