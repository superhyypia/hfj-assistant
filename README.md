# hfj-assistant

Here’s a clean, professional README.md you can drop straight into your repo.

⸻

🛡️ HFJ Assistant (Hope for Justice AI Assistant)

A location-aware, safety-focused AI assistant designed to provide trusted guidance, support routes, and educational information on human trafficking and modern slavery.

This project combines:
	•	Trusted NGO/government content (RAG)
	•	Location-aware support routing
	•	AI-assisted fallback for coverage gaps
	•	Frontend chat experience (Ask Hope)

⸻

🎯 Purpose

The goal is to create a safe, responsible assistant that:
	•	Helps users understand human trafficking risks and signs
	•	Provides official support routes based on location
	•	Avoids misinformation and unsafe advice
	•	Uses AI carefully to augment, not replace, trusted sources

⸻

🧠 System Overview

Hybrid Architecture

User → API → Decision Engine
                 ↓
      ┌───────────────┬────────────────┐
      │               │                │
 Location Routing   Retrieval (RAG)   AI Fallback
      │               │                │
 Official Support   Trusted Content   OpenAI
      │               │                │
      └──────→ Unified Response ←──────┘


⸻

⚙️ Core Features

1. 📍 Location-Aware Support
	•	Detects:
	•	US states (e.g. “California”)
	•	Countries (e.g. “Ireland”, “Estonia”)
	•	Routes to:
	•	National hotlines
	•	Local support services
	•	Uses:
	•	Structured DB (hfj_support_routes)
	•	AI fallback for missing countries (marked Unverified)

⸻

2. 📚 Retrieval-Augmented Generation (RAG)

Content is scraped, cleaned, chunked, and stored in PostgreSQL.

Sources include:
	•	Hope for Justice
	•	HSE (Ireland)
	•	UK Modern Slavery reporting
	•	National Human Trafficking Hotline (US)

Retrieval features:
	•	Phrase-aware scoring
	•	Section-aware ranking
	•	Source prioritisation (e.g. hotline for US)
	•	Region-aware boosting
	•	Confidence scoring (high / medium / low)

⸻

3. 🤖 AI Augmentation

Used only when needed:
	•	Low-confidence retrieval
	•	Missing country support routes
	•	General guidance queries

Features:
	•	Structured contact cards
	•	“Verify before use” labeling
	•	Multi-language support (English / Spanish)

⸻

4. 💬 Ask Hope UI

Custom chat interface with:
	•	Immediate help buttons:
	•	“Immediate danger”
	•	“I need help now”
	•	Suggested prompts
	•	Structured responses
	•	AI contact cards
	•	Safety messaging

⸻

5. 🌍 Multi-language Support
	•	Auto-detects language (EN / ES)
	•	Translates:
	•	Retrieval answers
	•	Support routes
	•	AI responses

⸻

🧩 Key Components

Backend (FastAPI)

File	Purpose
main.py	API + orchestration
retrieval.py	RAG scoring + matching
ingest.py	Web scraping + chunking
support.py	Location-based responses
ai.py	OpenAI integration
utils.py	Detection, cleaning, session logic
db.py	PostgreSQL connection


⸻

Frontend

File	Purpose
askhope.html	Chat UI


⸻

Database

Tables:

hfj_content_chunks
Stores:
	•	scraped content
	•	chunked text
	•	metadata (source, region, type)

hfj_support_routes
Stores:
	•	official support routes
	•	phone numbers
	•	websites

hfj_ai_cache
Caches:
	•	AI-generated country support responses

⸻

🧠 Intelligent Behaviour

Confidence-Based Routing

Confidence	Behaviour
High	Use retrieval
Medium	Use retrieval
Low	Fall back to AI


⸻

Intent Detection

The system distinguishes between:
	•	Help requests
	•	Educational questions
	•	Location queries
	•	Emergency scenarios

⸻

Safety Design
	•	No investigative advice
	•	Encourages official support
	•	Emergency escalation messaging
	•	AI content clearly marked

⸻

🚀 Running the App

Install dependencies

pip install -r requirements.txt

Run locally

uvicorn main:app --reload

Render deployment

Start command:

uvicorn main:app --host 0.0.0.0 --port $PORT


⸻

🔄 Data Ingestion

Reingest all sources:

curl -X POST https://<your-app>/reingest-all

Check content:

curl https://<your-app>/content-check


⸻

🧪 Testing

Example queries:

# Educational
what are the signs of trafficking

# Support
I need help in California

# Hotline
what is the human trafficking hotline

# General distress
something bad is happening and i am not sure what it means


⸻

📈 What’s Working Well
	•	Accurate location routing
	•	Trusted-source prioritisation
	•	Good retrieval precision with confidence scoring
	•	AI fills gaps without overriding official content
	•	Strong foundation for real-world use

⸻

⚠️ Known Limitations
	•	Not all countries have verified support routes
	•	AI-generated contacts require verification
	•	Some long answers need summarisation
	•	Retrieval still improving for edge cases

⸻

🔮 Next Steps

High impact improvements:
	•	✅ Short answer extraction (cleaner UI responses)
	•	🔄 Admin review system for AI contacts
	•	📍 Expanded global support coverage
	•	🧠 Better intent classification
	•	🎯 Retrieval fine-tuning (semantic + embeddings)
	•	📊 Analytics / usage tracking

⸻

🧭 Vision

This project is evolving toward:

A trusted, global, AI-assisted support system
for human trafficking awareness, prevention, and response

Combining:
	•	Verified data
	•	Responsible AI
	•	Context-aware guidance

⸻

❤️ Acknowledgements
	•	Hope for Justice
	•	National Human Trafficking Hotline
	•	HSE Ireland
	•	UK Modern Slavery Reporting

⸻
