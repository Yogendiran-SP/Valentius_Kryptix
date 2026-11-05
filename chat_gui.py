import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from tkinter import Button, Entry, Label
import httpx
import threading
import queue


# FastAPI BAckend checking/starting
import subprocess
import sys
import time
from pathlib import Path

# Queue creation
response_queue = queue.Queue()

# For Backend process
backend_process = None
convo_id = None

# FastAPI URL
API_URL = "http://127.0.0.1:8000"

# COLOR PALETTE
BG = "#101218"
PANEL = "#222631"
TEXT = "#F3F4F6"
ACCENT = "#6366F1"

# Startup Worker function
def startup_worker():
    global backend_process

    try:
        # Check if FastAPI is already running
        try:
            response = httpx.get(
                f"{API_URL}/openapi.json",
                timeout=1.0
            )
            response.raise_for_status()
        except (httpx.ConnectError, httpx.ConnectTimeout):
            # Start FastAPI only if no server is reachable
            backend_process = subprocess.Popen(
                [
                    sys.executable,
                    "-m", "uvicorn",
                    "chatbot:app",
                    "--host", "127.0.0.1",
                    "--port", "8000"
                ],
                cwd=Path(__file__).resolve().parent
            )

        # Wait until FastAPI accepts request
        for attempt in range(50):
            try:
                response = httpx.get(
                    f"{API_URL}/openapi.json",
                    timeout=1.0
                )
                response.raise_for_status()

                cid = create_conversation()

                response_queue.put(("ready", cid))
                return
            
            except httpx.RequestError:
                if backend_process and backend_process.poll() is not None:
                    raise RuntimeError("FastAPI exited during startup")
                
                time.sleep(0.2)
        
        raise TimeoutError("FastAPI did not start in time")
    
    except (OSError, RuntimeError, TimeoutError, httpx.HTTPError, ValueError, KeyError) as e:
        response_queue.put(("startup_error", str(e)))

# Backend Shutdown
def on_close():
    if backend_process is not None:
        if backend_process.poll() is None:
            backend_process.terminate()
    window.destroy()

# Thread worker function
def gemini_worker(user_message):
    try:
        reply = ask_gemini(user_message)
        response_queue.put(("success", reply))

    except httpx.HTTPStatusError as e:
        status = e.response.status_code

        try:
            detail = e.response.json().get("detail", "Request Failed")
        except (ValueError, AttributeError):
            detail = "Request Failed"
        response_queue.put(
            ("error", f"HTTP {status}: {detail}")
        )
    
    except httpx.TimeoutException:
        response_queue.put(
            ("error", "Connection to FastAPI timed out.")
        )
    
    except httpx.RequestError:
        response_queue.put(
            ("error", "Cannot connect to FastAPI.")
        )

    except ValueError:
        response_queue.put(
            ("error", "Invalid JSON response from backend.")
        )

# Conversation creation
def create_conversation():
    response = httpx.post(
        f"{API_URL}/conversations",
        timeout=15.0
    )

    response.raise_for_status()
    return response.json()["conversation_id"]

# Ask Gemini function
def ask_gemini(user_message):
    response = httpx.post(
        f"{API_URL}/chat",
        json={
            "conversation_id": convo_id,
            "message": user_message
        },
        timeout=45.0
    )

    response.raise_for_status()
    return response.json()

# Gemini Response Event-Handler
def check_response():
    global convo_id

    try:
        result_type, reply = response_queue.get_nowait()
        # print(reply)

        if result_type == "ready":
            convo_id = reply
            message_entry.configure(state="normal")
            send_button.config(state="normal")
            message_entry.focus_set()
        
        elif result_type == "startup_error":
            chat_display.configure(state="normal")
            chat_display.insert(
                tk.END,
                f"Error: {reply}\n\n",
                "error"
            )

        else:
            chat_display.configure(state="normal")

            if result_type=="success":
                message_entry.configure(state="normal")

                chat_display.insert(
                    tk.END,
                    f"Gemini: {reply}\n\n",
                    "model"
                )
                message_entry.focus_set()
                send_button.config(state="normal")

            else:
                chat_display.insert(
                    tk.END,
                    f"Error: {reply}\n\n",
                    "error"
                )
                message_entry.configure(state="normal")
                send_button.config(state="normal")
                message_entry.focus_set()
        
        chat_display.configure(state="disabled")
        chat_display.see(tk.END)

    except queue.Empty:
        pass
    
    # Schedules every subsequent check
    window.after(100, check_response)

# User prompt Event-Handler Function
def send_message(event=None):
    if send_button.cget("state") == "disabled":
        return

    user_message = message_entry.get().strip()

    if not user_message:
        return
    
    chat_display.config(state="normal") # To enable direct writing
    # Inserting messages in the window
    chat_display.insert(
        tk.END,
        f"You: {user_message}\n\n",
        "user"
    )
    chat_display.config(state="disabled") # To disable direct writing
    chat_display.see(tk.END)
    message_entry.delete(0, tk.END)
    send_button.config(state="disabled")
    message_entry.config(state="disabled") # To disable direct sending using mouse button click

    # Worker creation
    worker = threading.Thread(
        target=gemini_worker,
        args=(user_message,),
        daemon=True
    )
    worker.start()

window = tk.Tk()
window.title("AI Learning Assistant")
window.geometry("650x500")
window.configure(bg=BG)

# # Conversation creation
# convo_id = create_conversation()
# print(f"Conversation ID: {convo_id}")

# Displaying text using Label
window_label = Label(
    window,
    text="My AI Chatbot",
    font=("Segoe UI", 22, "bold"),
    bg=BG,
    fg=TEXT
)
window_label.pack(pady=25)

# Scrolled Text widget for Sent text display
chat_display = ScrolledText(
    window,
    font=("Segoe UI", 11),
    bg=PANEL,
    fg=TEXT,
    wrap=tk.WORD,
    height=10,
    relief="flat",
    bd=0
)

chat_display.pack(padx=30, pady=10, fill="both", expand=True)
chat_display.config(state="disabled")

# Tag configuration
chat_display.tag_configure("user", foreground="#A5B4FC")
chat_display.tag_configure("model", foreground="#80D9BB")
chat_display.tag_configure("error", foreground="#F87171")


# User input Entry
message_entry = Entry(
    window,
    font=("Segoe UI", 12),
    bg="#132251",
    fg=TEXT,
    insertbackground=TEXT,
    relief="flat",
    bd=0
)
message_entry.pack(padx=30, pady=15, fill="x", ipady=12)
message_entry.bind("<Return>", send_message)
message_entry.config(state="disabled")

# Send Button
send_button = Button(
    window,
    text="Send",
    font=("Segoe UI", 11, "bold"),
    bg=ACCENT,
    fg="white",
    activebackground="#4F46E5",
    activeforeground="white",
    relief="flat",
    bd=0,
    cursor="hand2",
    command=send_message
)
send_button.pack(pady=10, ipadx=20, ipady=8)
send_button.config(state="disabled")

# # Testing
# response_queue.put(("success", "LOCAL QUEUE TEST"))

threading.Thread(
    target=startup_worker,
    daemon=True
).start()

window.after(100, check_response)

# Delete window
window.protocol("WM_DELETE_WINDOW", on_close)

window.mainloop()

# # Starts the first check
# window.after(100, check_response)