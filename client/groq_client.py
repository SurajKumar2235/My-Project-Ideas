import os
import httpx

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - fallback for deployment images without python-dotenv
    def load_dotenv() -> bool:
        return False

# Load env variables
load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL_REASONING = os.environ.get("GROQ_MODEL_REASONING", "llama-3.3-70b-versatile")
GROQ_MODEL_SMALL = os.environ.get("GROQ_MODEL_SMALL", "llama-3.1-8b-instant")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

async def format_idea_to_markdown(raw_idea: str, use_reasoning: bool = True, previous_markdown: str = None, feedback: str = None) -> str:
    """
    Sends the raw idea to Groq and requests a structured project plan in markdown.
    """
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY environment variable is not set.")

    model = GROQ_MODEL_REASONING if use_reasoning else GROQ_MODEL_SMALL

    system_prompt = (
        "You are an expert product manager and technical architect.\n"
        "Your task is to convert a raw idea or a short description into a structured, production-ready implementation plan.\n"
        "Output ONLY the markdown content. Do not include any introductory conversational text (like 'Here is the plan') or wrap the markdown in an extra ```markdown code block unless it contains code blocks inside.\n"
        "The markdown document MUST follow this structure:\n"
        "# [Detailed Project Title]\n\n"
        "## Problem Statement\n"
        "[Explain the problem this idea solves]\n\n"
        "## Proposed Solution\n"
        "[Explain the solution and how it works]\n\n"
        "## Tech Stack\n"
        "[List recommended technologies, databases, frameworks and libraries with brief reasons why]\n\n"
        "## Milestones & Tasks\n"
        "- [ ] Phase 1: Core Foundation\n"
        "- [ ] Phase 2: Key Features\n"
        "- [ ] Phase 3: Integration & Testing\n\n"
        "## Open Questions\n"
        "[List potential roadblocks, design decisions, or unknown variables that need clarification]"
    )

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    messages = [{"role": "system", "content": system_prompt}]
    if previous_markdown and feedback:
        messages.append({"role": "user", "content": f"Here is the raw idea:\n{raw_idea}"})
        messages.append({"role": "assistant", "content": previous_markdown})
        messages.append({"role": "user", "content": f"Please update the project plan based on this feedback:\n{feedback}"})
    else:
        messages.append({"role": "user", "content": f"Here is the raw idea:\n{raw_idea}"})

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(GROQ_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        
        # Extract response content
        content = data["choices"][0]["message"]["content"]
        return content.strip()
