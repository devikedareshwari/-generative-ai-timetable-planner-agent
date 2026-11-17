# SmartSched – Generative AI Student Timetable Planner Agent

SmartSched is an academic scheduling agent powered by Google Gemini AI and Flask. Designed specifically for college students and academic demonstrations, SmartSched takes your enrolled subjects, difficulty levels, exam dates, daily study limits, and timing preferences, then analyzes and plans a personalized, non-overlapping weekly study timetable from Monday to Sunday.

---

## 📖 Table of Contents
1. [Project Objectives](#-project-objectives)
2. [Key Features](#-key-features)
3. [Architecture & Agent Workflow](#-architecture--agent-workflow)
4. [Technology Stack](#-technology-stack)
5. [Folder Structure](#-folder-structure)
6. [Prerequisites & Installation](#-prerequisites--installation)
7. [Gemini API Key Setup](#-gemini-api-key-setup)
8. [Running Locally](#-running-locally)
9. [Running Automated Tests](#-running-automated-tests)
10. [Deploying to Vercel](#-deploying-to-vercel)
11. [GitHub Push Commands](#-github-push-commands)
12. [Common Errors & Troubleshooting](#-common-errors--troubleshooting)

---

## 🎯 Project Objectives
- **Solve Academic Fatigue:** Prevent student burnout by designing realistic study sessions with mandatory rest intervals.
- **Cognitive Load Balancing:** Allocate more focus, frequency, and optimal peak hours to challenging subjects.
- **Genuine Generative AI Integration:** Utilize the official Google Gen AI Python SDK (`google-genai`) with structured JSON schema outputs and self-correction.
- **Fail-Safe Reliability:** Provide a robust, verified deterministic fallback scheduler so the application functions seamlessly even without an API key or during network disruptions.
- **Production-Ready Simplicity:** Avoid bloated UI libraries while maintaining a responsive, clean, and modern layout that runs identically in local environments and on Vercel serverless deployments.

---

## ✨ Key Features
- **Intelligent Student Profiler:** Input courses, individual difficulty ratings (Easy, Medium, Hard), exam dates, and daily study hour caps.
- **Constraint-Aware Agent:** Enforces realistic study windows, valid start/end boundaries, and non-overlapping sessions.
- **Automated Rest Breaks:** Integrates customizable recovery breaks (10, 15, 20, or 30 minutes) between intensive study blocks.
- **Natural Language Rescheduling:** Easily modify existing schedules by typing requests (e.g., *"Give more time to Mathematics"* or *"Shift Physics to the evening"*).
- **Dual Operating Modes:**
  - `AI Generated`: Full generative reasoning via Google Gemini API (`gemini-2.5-flash`).
  - `Demo Timetable`: Intelligent deterministic scheduler for offline or demo use without an API key.
- **Weekly Overview & Day Filters:** Filter study sessions day-by-day (Monday through Sunday) or view the full week at a glance.
- **Local Persistence:** Saves student timetables in an SQLite database for history retrieval and reloading.
- **Print & PDF Export:** Clean CSS `@media print` rules format the timetable for paper handouts or PDF downloads without screen clutter.

---

## 🧠 Architecture & Agent Workflow

SmartSched implements a 6-step Generative AI Agent pipeline:

```
[Student Input]
       │
       ▼
1. UNDERSTAND ──> Ingest courses, difficulty ratings, exam dates & daily constraints
       │
       ▼
2. ANALYZE    ──> Gemini AI evaluates workload, prioritizing difficult subjects & near deadlines
       │
       ▼
3. PLAN       ──> Generates Monday–Sunday study blocks with structured JSON schema
       │
       ▼
4. VALIDATE   ──> Python tools verify: zero overlaps, study hour caps, break intervals
       │
       ├───> [If Valid] ───────────────┐
       │                               ▼
5. IMPROVE    ──> (Self-Correction)   6. RESPOND
       │          Prompt Gemini with       Render complete weekly timetable,
       │          validation issues.       metrics, and AI strategy
       │          Fallback if needed
```

---

## 🛠 Technology Stack

### Frontend
- **HTML5:** Semantic structure and accessible forms.
- **CSS3:** Custom responsive styling using a clean blue/purple student palette (no bulky dependencies).
- **JavaScript (Vanilla ES6+):** Dynamic subject management, real-time feedback, asynchronous API interaction, day filtering.

### Backend
- **Python 3.10+ / 3.12:** Clean modular backend.
- **Flask (v3.0+):** Lightweight WSGI web framework configured with `public/` static routing for Vercel compatibility.
- **python-dotenv:** Environment configuration.

### Generative AI
- **Official Google Gen AI SDK (`google-genai`):** Modern Python SDK for Gemini models.
- **Model:** `gemini-2.5-flash` (or user-configurable via `GEMINI_MODEL`).

### Database
- **SQLite3:** Embedded relational storage for student profiles, schedules, and history.
- **Serverless Ephemeral Storage Handling:** Automatically routes SQLite database to `/tmp/smartsched.db` when running on Vercel's ephemeral serverless infrastructure.

---

## 📁 Folder Structure

```
SmartSched/
│
├── app.py              # Main Flask application and API route controllers
├── agent.py            # Gemini Generative AI Agent with 6-step workflow
├── tools.py            # Scheduling validation, statistics, and fallback scheduler
├── database.py         # SQLite persistence layer and environment detector
├── test_app.py         # End-to-end unit and integration test suite
├── test_agent.py       # Agent and JSON resilience test suite
├── requirements.txt    # Python package dependencies
├── vercel.json         # Vercel serverless deployment routing
├── .env                # Local secrets (never committed to git)
├── .env.example        # Template for environment configuration
├── .gitignore          # Excludes secrets, caches, and database files
├── README.md           # Project documentation
│
├── templates/
│   ├── index.html      # Landing page & student profile input form
│   └── timetable.html  # Timetable view, day filters & rescheduling interface
│
└── public/
    ├── style.css       # Unified stylesheet with print support
    ├── script.js       # Client-side dynamic form & interaction logic
    └── images/
        └── logo.svg    # Vector application logo & favicon
```

---

## 🚀 Prerequisites & Installation

### 1. Prerequisites
- Python 3.10 or higher installed on your machine (`python --version`)
- Git installed (`git --version`)

### 2. Clone or Enter Project Directory
```bash
cd "c:\FAI PROJECT"
```

### 3. Create a Virtual Environment (Recommended)
```bash
# Windows PowerShell
python -m venv venv
.\venv\Scripts\Activate.ps1

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 🔑 Gemini API Key Setup

1. Obtain a free API key from [Google AI Studio](https://aistudio.google.com/).
2. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
3. Open `.env` in any text editor and paste your API key:
   ```env
   GEMINI_API_KEY=AIzaSy...YourActualKeyHere
   GEMINI_MODEL=gemini-2.5-flash
   PORT=5000
   ```

> **Note:** If no key is set or the API is unavailable, SmartSched will automatically operate in **Demo Mode**, utilizing the built-in rule-based fallback scheduler.

---

## 💻 Running Locally

Start the Flask application:
```bash
python app.py
```

Open your browser and navigate to:
```
http://localhost:5000
```

---

## 🧪 Running Automated Tests

SmartSched comes with complete test coverage verifying routing, static asset serving, schedule validation, database storage, and AI response sanitization.

To run the entire test suite:
```bash
python -m unittest discover
```

Expected output:
```
Ran 18 tests in 0.1s
OK
```

---

## ☁️ Deploying to Vercel

SmartSched is pre-configured for seamless deployment to Vercel using `@vercel/python`.

### Why Static Assets Work on Vercel
Vercel requires static files (CSS, JS, images) to be served either directly by Vercel's edge network from a root-level `public/` directory or explicitly mapped in `vercel.json`.

In SmartSched:
1. All static files live in `public/style.css`, `public/script.js`, and `public/images/`.
2. `vercel.json` maps `/style.css`, `/script.js`, and `/images/*` directly to `public/`.
3. Flask also initializes `static_folder="public"` and includes explicit routes as a dual safeguard.
4. Database storage routes to `/tmp/smartsched.db` in serverless mode to accommodate read-only environments.

### Deployment Steps

1. Install the Vercel CLI (or connect via GitHub repository in the Vercel Dashboard):
   ```bash
   npm install -g vercel
   ```
2. Log in and deploy:
   ```bash
   vercel
   ```
3. Add your environment variables in the Vercel project settings:
   - `GEMINI_API_KEY`: Your Google Gemini API key
   - `GEMINI_MODEL`: `gemini-2.5-flash`
4. Deploy to production:
   ```bash
   vercel --prod
   ```

---

## 🐙 GitHub Push Commands

To commit and push the project to your GitHub repository:

```bash
# 1. Initialize git (if not already initialized)
git init

# 2. Add all files
git add .

# 3. Commit changes
git commit -m "Initial commit: SmartSched AI Student Timetable Planner"

# 4. Set branch to main
git branch -M main

# 5. Link your remote GitHub repository
# Replace <username> and <repo-name> with your actual details
git remote add origin https://github.com/<username>/<repo-name>.git

# 6. Push code to GitHub
git push -u origin main
```

---

## ❓ Common Errors & Troubleshooting

### 1. CSS / Styling Missing on Vercel
- **Cause:** Static assets located inside `templates/` or referenced with relative paths.
- **Solution:** SmartSched isolates all CSS and JS inside the root `public/` directory and configures explicit rewrites in `vercel.json`. Verify that links use `/style.css` and `/script.js`.

### 2. "Gemini API key is not configured"
- **Cause:** The `.env` file does not contain a valid `GEMINI_API_KEY`.
- **Solution:** Verify that `.env` exists in the project root with `GEMINI_API_KEY=your_key`. Ensure there are no surrounding quotes or trailing spaces.

### 3. SQLite Database Write Error on Vercel
- **Cause:** Vercel serverless functions have a read-only filesystem except for `/tmp`.
- **Solution:** `database.py` automatically detects when running under Vercel or AWS Lambda and routes database connections to `/tmp/smartsched.db`.

### 4. Port 5000 Already in Use
- **Cause:** Another process or background Python server is running on port 5000.
- **Solution:** Run on another port:
  ```bash
  python -c "import app; app.app.run(port=5050)"
  ```
  or update `PORT=5050` in `.env`.

---

## 📜 License
Developed as an open-source educational project. Free to modify and adapt for college demonstrations and learning.
