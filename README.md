# QuensultingAI AI Voice Agent Internship Submission

This repository contains the deliverables for the QuensultingAI AI Voice Agent internship assignment.

## Deliverables

1. **RetellAI Agent JSON:** Located in `retell_agent_config.json`. This file represents the Conversational Flow state machine, including all intents, nodes, fallback handlers, and Custom Tool definitions.
2. **Python Automation Backend:** Located in the `/backend` folder. Built with FastAPI.
3. **Integrations:**
   - **Airtable**: Used for robust and instant database tracking of Caller Info & Appointments.
   - **SMTP Email**: Used for sending a confirmation email immediately upon a successful booking.

---

## 1. Setup Instructions

### Prerequisites
- Python 3.9+
- An Airtable account
- A Gmail account (with App Passwords enabled)
- [ngrok](https://ngrok.com/) for exposing the local webhook to Retell AI

### Installation
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up Environment Variables:
   Copy `.env.example` to `.env` and fill in your credentials.
   ```bash
   cp .env.example .env
   ```
   **To set up Airtable:**
   - Create a base and a table named `Appointments`.
   - Add columns: `Name` (Single line text), `Phone` (Phone number), `Service` (Single line text), `Date` (Single line text), `Time` (Single line text), `Email` (Email).
   - Get your Personal Access Token from Airtable Developer Hub.

   **To set up Email:**
   - Go to your Google Account -> Security -> App Passwords, and generate a new password. Use this in `SMTP_PASSWORD`.

### Running the Server
Start the FastAPI server:
```bash
uvicorn main:app --reload
```
The server will run on `http://127.0.0.1:8000`.

### Exposing the Webhook via ngrok
In a new terminal, run:
```bash
ngrok http 8000
```
Copy the forwarding URL (e.g., `https://1234-abcd.ngrok-free.app`).

---

## 2. Retell AI Configuration

In your Retell AI dashboard, create a new Conversational Flow agent.

1. **Flow Structure:** Follow the node structure defined in `retell_agent_config.json` to build out your conversation tree (Greeting -> Collect Service -> Collect Date/Time -> Collect Details -> Trigger Tool).
2. **Custom Tools:** Add a custom tool named `book_appointment`.
   - Set the webhook URL to your ngrok URL + `/webhook/retell_custom_tool` (e.g., `https://1234-abcd.ngrok-free.app/webhook/retell_custom_tool`).
   - Define the parameters as specified in the JSON file.

---

## 3. Architecture & Design Decisions

- **Conversational Flow (Retell)**: The flow is explicitly modeled as a state machine instead of a prompt-only approach. This ensures high reliability and predictability when collecting necessary booking details.
- **FastAPI**: Chosen over Flask/Django for its async capabilities and built-in data validation (Pydantic), which is ideal for handling webhooks.
- **Airtable**: Used over Google Sheets because it provides a cleaner, developer-friendly API (`pyairtable`), requires fewer authentication steps (no OAuth flow needed for simple integrations), and serves as a highly visual CMS for the clinic staff.
- **Graceful Failures**: If the database save fails, the backend instructs the agent to gracefully apologize and transition to the escalation node.
- **Escalation Protocol**: Handled natively via a dedicated `escalate_call` tool, ensuring users are never stuck in an infinite loop.

---

## Loom Walkthrough
*[Insert your Loom video link here]*
