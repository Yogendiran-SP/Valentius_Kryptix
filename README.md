# AI-1 — Context-Aware AI Chatbot

**LLM API Integration | Valentius Kryptix AI Internship**

A Python desktop chatbot that integrates the **Google Gemini API** with a **FastAPI backend** and a **Tkinter frontend**. It supports separate conversations, multi-turn context, summarized older history, and user-facing error handling.

The application can launch its local FastAPI server automatically when the desktop interface starts. **Gemini inference requires an internet connection and a valid API key**; the model does not run locally.

## Features

- **Desktop chat interface:** Tkinter GUI with a scrollable, read-only chat history, colored user/model/error messages, and Enter-to-send support.
- **Multi-turn context:** Sends recent user/model exchanges with each new prompt.
- **Context-window management:** Maintains a rolling summary of older conversation turns while retaining the latest three completed exchanges (`MAX_TURNS = 3`).
- **Conversation isolation:** Associates each session with a separate numeric conversation ID.
- **System instruction:** Provides the assistant's role and historical conversation summary to Gemini.
- **Responsive UI:** Uses a background HTTP worker and `queue.Queue` so network requests do not block Tkinter's event loop.
- **Request guard:** Temporarily disables sending while a response is pending.
- **Error reporting:** Displays API/network errors in the chat interface and allows another request afterward.
- **Automatic local server management:** Starts Uvicorn when necessary and requests termination of the server process launched by the GUI when the window closes.

## Architecture

```text
                  ┌──────────────────────────┐
                  │      Tkinter GUI         │
                  │       chat_gui.py        │
                  └────────────┬─────────────┘
                               │ HTTPX (background worker)
                               │ POST /conversations, POST /chat
                               ▼
                  ┌──────────────────────────┐
                  │       FastAPI            │
                  │       chatbot.py         │
                  └────────────┬─────────────┘
                               │
                 ┌─────────────┴─────────────┐
                 ▼                           ▼
       Conversation memory            Google Gen AI SDK
       - summary                     - system instruction
       - latest 3 exchanges          - recent turns + prompt
                 │                           │
                 └─────────────┬─────────────┘
                               ▼
                         Gemini API
                               │
                               ▼
                     Response / API error
                               │
                               ▼
                Worker → queue.Queue → Tkinter
```

**Implementation note:** Conversation state is stored in a Python dictionary in the backend process. It is **not persisted** when the backend restarts.

## Technology Stack

| Layer | Technology |
| --- | --- |
| Language | Python |
| Desktop GUI | Tkinter (`tkinter.scrolledtext.ScrolledText`) |
| Backend API | FastAPI, Pydantic |
| ASGI server | Uvicorn |
| LLM provider | Google Gemini via `google-genai` |
| HTTP client | HTTPX |
| Configuration | `python-dotenv`, environment variables |
| Concurrency | Python `threading`, `queue`, `subprocess` |

## Project Structure

Place these files together in the project directory:

```text
Valentius_Kryptix/
├── chatbot.py          # FastAPI routes, Gemini integration, conversation memory
├── chat_gui.py         # Tkinter interface and automatic backend startup
├── README.md           # Project documentation
├── .env                # Local credentials; do not commit
└── .gitignore          # Excludes secrets and local environments
```

A `.venv/` virtual environment may also exist locally. The layout above describes the files used by the application; it is not a claim that they have all been pushed to GitHub.

## Requirements

- Python 3.10+ recommended, with Tkinter available in the installation.
- A Google Gemini API key with access to the configured model.
- Internet access for Gemini API requests.
- Available local port **8000** for FastAPI, unless the intended backend is already running there.

### 1. Clone and open the project branch

```bash
git clone https://github.com/Yogendiran-SP/Valentius_Kryptix.git
cd Valentius_Kryptix
git checkout ai-1_llm_api_integration
```

Ensure `chatbot.py` and `chat_gui.py` are present in this branch before running the following commands.

### 2. Create and activate a virtual environment

**Windows PowerShell:**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install fastapi uvicorn google-genai python-dotenv httpx
```

Tkinter is part of the standard Python distribution on many platforms and is not installed with the command above. Check availability with:

```bash
python -m tkinter
```

If Tkinter is missing, install the Tk bindings for your Python distribution or operating system.

### 4. Configure the API key

Create a local `.env` file in the project directory:

```dotenv
GOOGLE_API_KEY=your_gemini_api_key_here
```

The backend loads environment variables with `python-dotenv`. The Google Gen AI SDK can read `GOOGLE_API_KEY` from the environment.

**Never commit `.env` or a real API key to GitHub.** Confirm `.gitignore` excludes `.env`, `.venv/`, and other local-only files.

## Run the Application

### Recommended: Start from Tkinter

With the virtual environment activated:

```bash
python chat_gui.py
```

The GUI:

1. Opens with message input temporarily disabled.
2. Checks whether a FastAPI service is responding on `127.0.0.1:8000`.
3. Launches `python -m uvicorn chatbot:app --host 127.0.0.1 --port 8000` if the connection is refused.
4. Waits for API readiness, calls `POST /conversations`, and stores the returned ID.
5. Enables message input and sends subsequent messages to `POST /chat`.
6. Requests shutdown of the Uvicorn process **only if it was started by this GUI** when the window closes.

### Alternative: Start the backend manually

```bash
python -m uvicorn chatbot:app --reload
```

Then open `http://127.0.0.1:8000/docs` to explore the FastAPI Swagger interface. Launch `python chat_gui.py` separately to use the desktop client. The GUI will reuse a reachable service instead of launching another one.

## API Reference

**Base URL:** `http://127.0.0.1:8000`

### `POST /conversations`

Creates a new conversation with an empty summary and turn history.

Example response:

```json
{
  "conversation_id": 1,
  "message": "Conversation created successfully"
}
```

### `POST /chat`

Sends a user message to an existing conversation.

Example request:

```json
{
  "conversation_id": 1,
  "message": "Explain retrieval-augmented generation in one sentence."
}
```

The current backend returns the model answer as a **JSON string**, rather than an object with a `response` key. For example:

```json
"RAG combines retrieval of external information with language-model generation."
```

The wording varies by model response.

### Error behavior

| HTTP status | Typical condition |
| --- | --- |
| `404` | Unknown conversation ID |
| `502` | Gemini/upstream API failure or unusable model/summary response |
| `503` | Upstream connection failure or a rate-limit error mapped by the backend |
| `504` | Upstream request timeout |

The GUI also handles client-side HTTP errors, connection errors, timeouts, and invalid JSON responses. These codes describe the current application's mapping; they are not a guarantee of the exact cause of every upstream failure.

## How Conversation Memory Works

For each conversation ID, the backend stores:

```python
{
    "summary": "",
    "turns": [
        {"user": "...", "model": "..."}
    ]
}
```

Before generating a new reply, the backend checks for completed exchanges older than the latest three. When older turns exist, it asks Gemini to update the running summary using the existing summary and the expired exchanges. The backend then sends:

- The **historical summary** as context in the system instruction.
- The **latest three completed user/model exchanges** as alternating Gemini conversation messages.
- The **current user message** as the newest message.

A completed exchange contains one user message and the corresponding model response. The summary supports long-range recall without repeatedly sending the entire transcript.

**Limitations:** Summaries can omit details, and model recall may be imperfect. A factual error or incorrect recollection is still possible even when memory management is functioning.

## Manual Test Checklist

The following scenarios have been exercised during local development; repeat them after modifying the application:

- [ ] Start `chat_gui.py` without manually starting Uvicorn.
- [ ] Confirm input becomes available after a conversation is created.
- [ ] Exchange at least **five user messages** in the same conversation.
- [ ] Confirm the assistant remembers information supplied earlier (for example, a preferred name).
- [ ] Ask about an earlier technical topic after several unrelated messages to exercise summarization.
- [ ] Create two conversation IDs through Swagger and confirm information remains isolated.
- [ ] Verify both Enter and Send work without duplicate submissions.
- [ ] Verify input is cleared and temporarily locked while a request is pending.
- [ ] Verify errors appear in the GUI and subsequent requests can succeed.
- [ ] Close the GUI and verify that a Uvicorn process it started is no longer running.

Developer fault-injection tests have also been used to exercise timeout, connectivity, and empty-summary handling. These are **manual tests**, not an included automated test suite. An intermittent `502` response was observed during testing; later requests succeeded.

## Security and Known Limitations

- **Cloud processing:** User messages and supplied context are sent to the Gemini API. This is not an offline LLM.
- **In-memory history:** Conversation data is lost when the backend process restarts.
- **Local demo:** The API has no user authentication and is intended for local use, not unrestricted public deployment.
- **Port ownership:** Checking `/openapi.json` shows that a service responds, but does not guarantee it is this chatbot if another service occupies port 8000.
- **Shutdown race:** Closing the GUI while the backend is still starting may need additional process-lifecycle safeguards.
- **Response quality:** The LLM can hallucinate or inaccurately recall older turns.
- **Provider reliability:** Network errors, API limits, and model timeouts may affect availability.

## Future Improvements

- Persist conversations and summaries in SQLite.
- Add a dedicated backend health endpoint and stronger server-identity checks.
- Add automated tests for API routes, memory summarization, and GUI worker failures.
- Add retry/backoff handling for appropriate transient upstream errors.
- Improve startup cancellation and child-process shutdown behavior.

## Project and Attribution

Developed for **Valentius Kryptix — AI Internship, Task AI-1: LLM API Integration**.

**Repository:** [Yogendiran-SP/Valentius_Kryptix](https://github.com/Yogendiran-SP/Valentius_Kryptix)  
**Project branch:** [`ai-1_llm_api_integration`](https://github.com/Yogendiran-SP/Valentius_Kryptix/tree/ai-1_llm_api_integration)

The application uses the Google Gemini API through the Google Gen AI SDK. Gemini-generated answers may vary between requests.
