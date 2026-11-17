"""
Generative AI Agent module for SmartSched.
Uses Google Gemini API and the official google-genai Python SDK.
Implements the 6-step agent workflow:
1. Understand -> 2. Analyze -> 3. Plan -> 4. Validate -> 5. Improve -> 6. Respond.
"""

import os
import json
import re
import logging
from dotenv import load_dotenv
from google import genai
from google.genai import types

import tools

# Load local environment variables from .env
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SmartSched.Agent")

def get_api_key():
    """Retrieve GEMINI_API_KEY from environment."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if key and key != "your_api_key_here" and len(key) > 8:
        return key
    return None

def get_model_name():
    """Retrieve GEMINI_MODEL or fallback to gemini-2.5-flash."""
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

def is_ai_available():
    """Check if a valid Gemini API key is configured."""
    return get_api_key() is not None

def clean_json_response(raw_text):
    """Safely extracts JSON from model response text, removing markdown fences if present."""
    if not raw_text:
        return None
    cleaned = raw_text.strip()
    # Strip markdown code blocks
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as err:
        logger.warning(f"Direct JSON parsing failed: {err}. Attempting regex extraction.")
        # Attempt to find the outermost JSON object { ... }
        match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
    return None

def build_planning_prompt(student_data):
    """Constructs prompt for Gemini to analyze and generate timetable."""
    name = student_data.get("name", "Student")
    subjects = student_data.get("subjects", [])
    difficulties = student_data.get("difficulties", {})
    exam_dates = student_data.get("exam_dates", "")
    available_hours = student_data.get("available_hours", 4.0)
    preferred_start = student_data.get("preferred_start", "08:00")
    preferred_end = student_data.get("preferred_end", "21:00")
    break_duration = student_data.get("break_duration", 15)
    instructions = student_data.get("instructions", "None")

    subj_details = []
    for s in subjects:
        diff = difficulties.get(s, "Medium")
        subj_details.append(f"- {s}: Difficulty = {diff}")

    prompt = f"""You are SmartSched AI, an expert academic planner and student timetable agent.
Create a personalized weekly study timetable for Monday through Sunday for:

Student Name: {name}
Subjects and Difficulty:
{chr(10).join(subj_details) if subj_details else 'None specified'}

Upcoming Exam Dates:
{exam_dates if exam_dates else 'No specific exam dates provided'}

Constraints & Preferences:
- Maximum Available Study Hours Per Day: {available_hours} hours
- Preferred Study Time Window: Between {preferred_start} and {preferred_end}
- Required Break Duration: {break_duration} minutes
- Additional Instructions: {instructions}

Agent Instructions:
1. Prioritize subjects with 'Hard' difficulty and subjects with imminent exam dates.
2. Schedule study blocks between 30 and 90 minutes.
3. Total study time per day MUST NOT exceed {available_hours} hours.
4. All sessions MUST occur strictly within the window {preferred_start} to {preferred_end}.
5. Insert '{break_duration}' minute breaks between consecutive study sessions (set subject to 'Break' and activity to a relaxation tip).
6. Ensure NO overlapping sessions. Each session must start at or after the previous session ends.
7. Only schedule the student's listed subjects: {', '.join(subjects)}.
8. Every day from Monday to Sunday must be covered.

You MUST respond strictly with a valid JSON object matching this exact schema:
{{
  "message": "A 2-3 sentence explanation of your scheduling strategy and prioritization rationale",
  "suggestions": [
    "Practical actionable study tip 1",
    "Practical actionable study tip 2",
    "Practical actionable study tip 3"
  ],
  "schedule": [
    {{
      "day": "Monday",
      "start": "09:00",
      "end": "10:00",
      "subject": "Subject Name",
      "activity": "Specific focused learning task or revision activity"
    }}
  ]
}}
"""
    return prompt

def generate_timetable_agent(student_data):
    """
    Executes the 6-step Generative AI Agent workflow:
    1. Understand -> 2. Analyze -> 3. Plan -> 4. Validate -> 5. Improve -> 6. Respond.
    """
    api_key = get_api_key()
    model_name = get_model_name()

    # If no Gemini API key is configured, use fallback scheduler gracefully
    if not api_key:
        logger.info("No GEMINI_API_KEY configured. Using intelligent demo fallback scheduler.")
        fallback = tools.generate_fallback_timetable(student_data)
        stats = tools.calculate_schedule_stats(fallback["schedule"])
        return {
            "status": "success",
            "generation_type": "Demo Timetable",
            "message": (
                "Notice: Gemini API key is not configured in .env. Running in Demo Mode using SmartSched's "
                "intelligent rule-based scheduler. Configure GEMINI_API_KEY to unlock full generative AI."
            ),
            "suggestions": fallback["suggestions"],
            "schedule": fallback["schedule"],
            "stats": stats,
            "issues": []
        }

    try:
        # Step 1: Understand & Step 2: Analyze & Step 3: Plan
        client = genai.Client(api_key=api_key)
        prompt = build_planning_prompt(student_data)

        logger.info(f"Calling Gemini model '{model_name}' for timetable generation...")
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3
            )
        )

        parsed_data = clean_json_response(response.text)
        if not parsed_data or "schedule" not in parsed_data:
            raise ValueError("Gemini returned invalid or empty JSON.")

        # Step 4: Validate
        schedule = parsed_data.get("schedule", [])
        is_valid, issues = tools.validate_timetable(schedule, student_data)

        # Step 5: Improve (Self-correction attempt if invalid)
        if not is_valid:
            logger.warning(f"Initial schedule failed validation with {len(issues)} issues. Requesting correction...")
            correction_prompt = f"""The generated timetable has validation issues that must be corrected:
{chr(10).join(f'- {issue}' for issue in issues)}

Original Student Requirements:
- Maximum Available Study Hours Per Day: {student_data.get('available_hours')} hours
- Preferred Window: {student_data.get('preferred_start')} to {student_data.get('preferred_end')}
- Break Duration: {student_data.get('break_duration')} minutes
- Subjects: {', '.join(student_data.get('subjects', []))}

Please return a corrected, strictly valid JSON timetable resolving all issues:
{response.text}
"""
            correction_response = client.models.generate_content(
                model=model_name,
                contents=correction_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2
                )
            )

            corrected_data = clean_json_response(correction_response.text)
            if corrected_data and "schedule" in corrected_data:
                c_valid, c_issues = tools.validate_timetable(corrected_data["schedule"], student_data)
                if c_valid:
                    parsed_data = corrected_data
                    is_valid = True
                    issues = []
                else:
                    logger.warning(f"Schedule still invalid after correction ({len(c_issues)} issues).")

        # If still invalid after 1 correction attempt, fallback safely to demo scheduler
        if not is_valid:
            logger.warning("Falling back to deterministic scheduler due to validation failure.")
            fallback = tools.generate_fallback_timetable(student_data)
            stats = tools.calculate_schedule_stats(fallback["schedule"])
            return {
                "status": "success",
                "generation_type": "Demo Timetable",
                "message": (
                    "AI timetable failed constraint validation after correction. "
                    "SmartSched safely generated a verified fallback timetable adhering to all your parameters."
                ),
                "suggestions": fallback["suggestions"],
                "schedule": fallback["schedule"],
                "stats": stats,
                "issues": issues
            }

        # Step 6: Respond
        stats = tools.calculate_schedule_stats(parsed_data["schedule"])
        return {
            "status": "success",
            "generation_type": "AI Generated",
            "message": parsed_data.get("message", "Personalized weekly timetable generated successfully with Gemini AI."),
            "suggestions": parsed_data.get("suggestions", [
                "Stay consistent with your daily study start times.",
                "Review session goals before starting each subject block."
            ]),
            "schedule": parsed_data["schedule"],
            "stats": stats,
            "issues": []
        }

    except Exception as ex:
        logger.error(f"Error during Gemini generation: {ex}", exc_info=True)
        fallback = tools.generate_fallback_timetable(student_data)
        stats = tools.calculate_schedule_stats(fallback["schedule"])
        return {
            "status": "success",
            "generation_type": "Demo Timetable",
            "message": f"Gemini API returned an error ({str(ex)}). Using SmartSched's intelligent demo timetable.",
            "suggestions": fallback["suggestions"],
            "schedule": fallback["schedule"],
            "stats": stats,
            "issues": [str(ex)]
        }

def reschedule_agent(current_schedule, user_request, student_data):
    """
    Applies natural language rescheduling instructions to an existing timetable.
    Validates the modified schedule before returning.
    """
    api_key = get_api_key()
    model_name = get_model_name()

    if not api_key:
        return {
            "status": "error",
            "generation_type": "Demo Timetable",
            "message": "Gemini API key is required for Natural Language Rescheduling. Please configure GEMINI_API_KEY in .env.",
            "schedule": current_schedule,
            "stats": tools.calculate_schedule_stats(current_schedule)
        }

    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""You are SmartSched AI. A student wants to adjust their existing weekly study timetable.

Student's Change Request:
"{user_request}"

Student Constraints:
- Available Daily Hours: {student_data.get('available_hours', 4.0)}
- Preferred Window: {student_data.get('preferred_start', '08:00')} to {student_data.get('preferred_end', '21:00')}
- Break Duration: {student_data.get('break_duration', 15)} mins
- Registered Subjects: {', '.join(student_data.get('subjects', []))}

Current Timetable JSON:
{json.dumps(current_schedule)}

Agent Task:
1. Update the timetable to fulfill the student's request (e.g. increase time for a subject, shift sessions to evening, add breaks, etc.).
2. Keep sessions non-overlapping and within preferred timings.
3. Maintain realistic session durations.
4. Respond strictly with a JSON object matching this schema:
{{
  "message": "Brief summary of how the schedule was adapted to fulfill the request",
  "suggestions": ["Updated suggestion 1", "Updated suggestion 2"],
  "schedule": [
    {{
      "day": "Monday",
      "start": "HH:MM",
      "end": "HH:MM",
      "subject": "Subject Name",
      "activity": "Activity description"
    }}
  ]
}}
"""
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3
            )
        )

        parsed_data = clean_json_response(response.text)
        if not parsed_data or "schedule" not in parsed_data:
            raise ValueError("Invalid response from Gemini for rescheduling.")

        new_schedule = parsed_data["schedule"]
        is_valid, issues = tools.validate_timetable(new_schedule, student_data)

        if not is_valid:
            logger.warning(f"Rescheduled timetable had validation issues: {issues}. Keeping current timetable.")
            return {
                "status": "warning",
                "generation_type": "AI Generated",
                "message": f"Could not safely apply changes without violating constraints: {', '.join(issues[:2])}.",
                "schedule": current_schedule,
                "stats": tools.calculate_schedule_stats(current_schedule)
            }

        stats = tools.calculate_schedule_stats(new_schedule)
        return {
            "status": "success",
            "generation_type": "AI Generated",
            "message": parsed_data.get("message", "Timetable updated successfully according to your request."),
            "suggestions": parsed_data.get("suggestions", []),
            "schedule": new_schedule,
            "stats": stats
        }

    except Exception as ex:
        logger.error(f"Error during reschedule: {ex}", exc_info=True)
        return {
            "status": "error",
            "generation_type": "AI Generated",
            "message": f"Failed to reschedule: {str(ex)}",
            "schedule": current_schedule,
            "stats": tools.calculate_schedule_stats(current_schedule)
        }
