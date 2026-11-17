"""
Flask application for SmartSched – Generative AI Student Timetable Planner Agent.
Serves static assets from public/ and templates from templates/.
Compatible with local development and Vercel serverless deployment.
"""

import os
import logging
from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for
from dotenv import load_dotenv

import database
import agent
import tools

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SmartSched.App")

# Base directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "public")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# Initialize Flask with absolute public/ as static_folder
app = Flask(
    __name__,
    static_folder=STATIC_DIR,
    static_url_path="",
    template_folder=TEMPLATES_DIR
)

class VercelPathMiddleware:
    """
    WSGI middleware that restores original PATH_INFO from Vercel's x-matched-path
    header when using serverless catch-all rewrites.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        matched_path = environ.get("HTTP_X_MATCHED_PATH") or environ.get("HTTP_X_VERCEL_MATCHED_PATH")
        if matched_path and not matched_path.startswith("/api/index"):
            path_only = matched_path.split("?")[0]
            environ["PATH_INFO"] = path_only
        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathMiddleware(app.wsgi_app)

def get_static_content(filename):
    """Safely reads static file content for inline fallback rendering."""
    try:
        filepath = os.path.join(STATIC_DIR, filename)
        if os.path.isfile(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
    except Exception as e:
        logger.error(f"Error reading static file {filename}: {e}")
    return ""

# Ensure database tables exist on startup
database.init_db()

# Explicit routes for static assets to ensure HTTP 200 locally and on Vercel
@app.route("/style.css")
def serve_css():
    """Serves the main CSS file with correct MIME type."""
    return send_from_directory(STATIC_DIR, "style.css", mimetype="text/css")

@app.route("/script.js")
def serve_js():
    """Serves the main JavaScript file with correct MIME type."""
    return send_from_directory(STATIC_DIR, "script.js", mimetype="application/javascript")

@app.route("/images/<path:filename>")
def serve_images(filename):
    """Serves static image assets."""
    return send_from_directory(os.path.join(STATIC_DIR, "images"), filename)

@app.route("/api/debug", methods=["GET", "POST"])
@app.route("/debug", methods=["GET", "POST"])
def debug_route():
    return jsonify({
        "path": request.path,
        "method": request.method,
        "environ_path_info": request.environ.get("PATH_INFO"),
        "headers": dict(request.headers)
    })

# HTML Page Routes
@app.route("/")
def index():
    """Home page with hero section and student input form."""
    ai_status = agent.is_ai_available()
    model_name = agent.get_model_name()
    is_ephemeral = database.is_ephemeral_storage()
    css_content = get_static_content("style.css")
    js_content = get_static_content("script.js")
    return render_template(
        "index.html",
        ai_status=ai_status,
        model_name=model_name,
        is_ephemeral=is_ephemeral,
        css_content=css_content,
        js_content=js_content
    )

@app.route("/timetable")
def timetable_view():
    """Timetable display page."""
    timetable_id = request.args.get("id")
    timetable_data = None
    if timetable_id:
        try:
            timetable_data = database.get_timetable_by_id(int(timetable_id))
        except Exception as e:
            logger.error(f"Error loading timetable {timetable_id}: {e}")

    ai_status = agent.is_ai_available()
    model_name = agent.get_model_name()
    is_ephemeral = database.is_ephemeral_storage()
    css_content = get_static_content("style.css")
    js_content = get_static_content("script.js")

    return render_template(
        "timetable.html",
        timetable=timetable_data,
        timetable_id=timetable_id,
        ai_status=ai_status,
        model_name=model_name,
        is_ephemeral=is_ephemeral,
        css_content=css_content,
        js_content=js_content
    )

@app.route("/timetable/<int:timetable_id>")
def timetable_detail(timetable_id):
    """Convenience direct route to load a saved timetable."""
    return redirect(url_for("timetable_view", id=timetable_id))

# API Endpoints
@app.route("/api/generate", methods=["POST"])
def api_generate():
    """
    Generate a personalized weekly timetable using Generative AI or fallback.
    Expects JSON student input.
    """
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"status": "error", "message": "Invalid JSON body provided."}), 400

    # Validate required fields
    student_name = (data.get("name") or "").strip()
    if not student_name:
        return jsonify({"status": "error", "message": "Student name is required."}), 400

    subjects_raw = data.get("subjects", "")
    if isinstance(subjects_raw, str):
        subjects = [s.strip() for s in subjects_raw.split(",") if s.strip()]
    elif isinstance(subjects_raw, list):
        subjects = [str(s).strip() for s in subjects_raw if str(s).strip()]
    else:
        subjects = []

    if not subjects:
        return jsonify({"status": "error", "message": "At least one subject is required."}), 400

    # Validate numbers and times
    try:
        available_hours = float(data.get("available_hours", 4.0))
        if available_hours <= 0 or available_hours > 16:
            return jsonify({"status": "error", "message": "Daily study hours must be between 1 and 16."}), 400
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid study hours value."}), 400

    pref_start = (data.get("preferred_start") or "08:00").strip()
    pref_end = (data.get("preferred_end") or "21:00").strip()

    start_min = tools.parse_time_to_minutes(pref_start)
    end_min = tools.parse_time_to_minutes(pref_end)

    if start_min is None or end_min is None:
        return jsonify({"status": "error", "message": "Preferred study start and end times must be valid (HH:MM)."}), 400

    if start_min >= end_min:
        return jsonify({"status": "error", "message": "Preferred start time must be before end time."}), 400

    try:
        break_duration = int(data.get("break_duration", 15))
        if break_duration < 5 or break_duration > 120:
            break_duration = 15
    except ValueError:
        break_duration = 15

    # Process difficulties
    difficulties = data.get("difficulties", {})
    if not isinstance(difficulties, dict):
        difficulties = {}
        for s in subjects:
            difficulties[s] = "Medium"

    student_data = {
        "name": student_name,
        "subjects": subjects,
        "difficulties": difficulties,
        "exam_dates": (data.get("exam_dates") or "").strip(),
        "available_hours": available_hours,
        "preferred_start": pref_start,
        "preferred_end": pref_end,
        "break_duration": break_duration,
        "instructions": (data.get("instructions") or "").strip()
    }

    # Execute AI agent
    result = agent.generate_timetable_agent(student_data)

    # Save to database
    try:
        timetable_id = database.save_timetable(
            student_name=student_name,
            subjects=subjects,
            schedule=result.get("schedule", []),
            suggestions=result.get("suggestions", []),
            message=result.get("message", ""),
            generation_type=result.get("generation_type", "AI Generated"),
            stats=result.get("stats"),
            student_data=student_data
        )
    except Exception as db_err:
        logger.error(f"Failed to persist timetable: {db_err}")
        timetable_id = None

    return jsonify({
        "status": "success",
        "timetable_id": timetable_id,
        "generation_type": result.get("generation_type"),
        "message": result.get("message"),
        "suggestions": result.get("suggestions"),
        "schedule": result.get("schedule"),
        "stats": result.get("stats"),
        "student_data": student_data
    })

@app.route("/api/reschedule", methods=["POST"])
def api_reschedule():
    """
    Natural Language rescheduling: adjusts an existing schedule based on student text prompt.
    """
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"status": "error", "message": "Invalid JSON body provided."}), 400

    user_request = (data.get("request") or "").strip()
    if not user_request:
        return jsonify({"status": "error", "message": "Please specify instructions for rescheduling."}), 400

    current_schedule = data.get("current_schedule", [])
    student_data = data.get("student_data", {})
    timetable_id = data.get("timetable_id")

    # If student_data is missing, attempt to retrieve from DB
    if timetable_id and not student_data:
        saved = database.get_timetable_by_id(int(timetable_id))
        if saved:
            student_data = saved.get("student_data", {})
            if not current_schedule:
                current_schedule = saved.get("schedule", [])

    result = agent.reschedule_agent(current_schedule, user_request, student_data)

    # If successfully updated and we have an ID, update the DB record
    if result.get("status") == "success" and timetable_id:
        try:
            database.save_timetable(
                student_name=student_data.get("name", "Student"),
                subjects=student_data.get("subjects", []),
                schedule=result.get("schedule", []),
                suggestions=result.get("suggestions", []),
                message=result.get("message", ""),
                generation_type=result.get("generation_type", "AI Generated"),
                stats=result.get("stats"),
                student_data=student_data
            )
        except Exception as e:
            logger.error(f"Error saving updated timetable: {e}")

    return jsonify(result)

@app.route("/api/timetables", methods=["GET"])
def api_get_timetables():
    """Returns recent saved timetables."""
    limit = request.args.get("limit", 15, type=int)
    timetables = database.get_recent_timetables(limit=limit)
    return jsonify({
        "status": "success",
        "timetables": timetables,
        "is_ephemeral": database.is_ephemeral_storage()
    })

@app.route("/api/timetables/<int:timetable_id>", methods=["GET"])
def api_get_timetable(timetable_id):
    """Returns details of a specific saved timetable."""
    record = database.get_timetable_by_id(timetable_id)
    if not record:
        return jsonify({"status": "error", "message": "Timetable not found."}), 404
    return jsonify({"status": "success", "timetable": record})

@app.route("/api/timetables/<int:timetable_id>", methods=["DELETE"])
def api_delete_timetable(timetable_id):
    """Deletes a saved timetable."""
    success = database.delete_timetable(timetable_id)
    return jsonify({"status": "success" if success else "not_found"})

@app.route("/api/status", methods=["GET"])
def api_status():
    """Returns application status, AI configuration, and storage info."""
    return jsonify({
        "status": "healthy",
        "ai_configured": agent.is_ai_available(),
        "model": agent.get_model_name(),
        "ephemeral_storage": database.is_ephemeral_storage(),
        "db_path": database.get_db_path()
    })

# Local server entry point
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"SmartSched running at http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
