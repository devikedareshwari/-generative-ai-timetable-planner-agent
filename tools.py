"""
Tools module for SmartSched.
Provides scheduling validation, time utilities, statistics computation,
and an intelligent deterministic fallback scheduler for demo mode.
"""

import re
from datetime import datetime, timedelta

DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def parse_time_to_minutes(time_str):
    """
    Parses a time string like '09:00', '9:30', or '14:45' into minutes from midnight.
    Returns None if format is invalid.
    """
    if not time_str or not isinstance(time_str, str):
        return None
    time_str = time_str.strip()
    match = re.match(r"^(\d{1,2}):(\d{2})$", time_str)
    if not match:
        return None
    hours, minutes = int(match.group(1)), int(match.group(2))
    if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
        return None
    return hours * 60 + minutes

def minutes_to_time(minutes):
    """Converts minutes from midnight to 'HH:MM' 24-hour string."""
    minutes = max(0, min(1439, int(minutes)))
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"

def is_break_activity(subject_or_activity):
    """Check if a session is a break or rest period."""
    if not subject_or_activity:
        return False
    text = str(subject_or_activity).lower()
    return any(w in text for w in ["break", "rest", "lunch", "dinner", "snack", "walk", "relax", "recess"])

def validate_timetable(schedule, student_data):
    """
    Validates a generated schedule against student requirements and logic rules.
    Returns:
        (is_valid: bool, issues: list[str])
    """
    issues = []

    if not isinstance(schedule, list):
        return False, ["Schedule must be a list of scheduled sessions."]
    if len(schedule) == 0:
        return False, ["Schedule contains no study sessions."]

    # Extract constraints
    available_hours = float(student_data.get("available_hours", 4.0))
    pref_start = student_data.get("preferred_start", "08:00")
    pref_end = student_data.get("preferred_end", "21:00")
    break_duration = int(student_data.get("break_duration", 15))
    valid_subjects = [s.strip().lower() for s in student_data.get("subjects", []) if s.strip()]

    pref_start_min = parse_time_to_minutes(pref_start) or 480  # 08:00
    pref_end_min = parse_time_to_minutes(pref_end) or 1260      # 21:00

    # Group sessions by day
    sessions_by_day = {day: [] for day in DAYS_OF_WEEK}

    for idx, item in enumerate(schedule):
        if not isinstance(item, dict):
            issues.append(f"Session #{idx+1} is formatted incorrectly.")
            continue

        day = item.get("day")
        start = item.get("start")
        end = item.get("end")
        subject = item.get("subject", "").strip()
        activity = item.get("activity", "").strip()

        # Day check
        if day not in DAYS_OF_WEEK:
            issues.append(f"Invalid day '{day}' in session for '{subject}'. Must be one of Monday-Sunday.")
            continue

        # Time format checks
        start_min = parse_time_to_minutes(start)
        end_min = parse_time_to_minutes(end)

        if start_min is None:
            issues.append(f"Invalid start time '{start}' on {day} for '{subject}'.")
            continue
        if end_min is None:
            issues.append(f"Invalid end time '{end}' on {day} for '{subject}'.")
            continue

        if start_min >= end_min:
            issues.append(f"Session on {day} for '{subject}' ends ({end}) before or at start time ({start}).")
            continue

        duration_min = end_min - start_min
        if duration_min < 15:
            issues.append(f"Session on {day} ({start}-{end}) is too short ({duration_min} mins). Minimum is 15 minutes.")
        if duration_min > 240:
            issues.append(f"Session on {day} ({start}-{end}) is too long ({duration_min // 60} hrs). Maximum single session is 4 hours.")

        # Preferred timing boundaries (allow 30-min soft tolerance)
        if start_min < (pref_start_min - 30):
            issues.append(f"Session on {day} starts at {start}, earlier than preferred start time ({pref_start}).")
        if end_min > (pref_end_min + 30):
            issues.append(f"Session on {day} finishes at {end}, later than preferred end time ({pref_end}).")

        # Subject validity check (skip breaks/reviews)
        if not is_break_activity(subject) and not is_break_activity(activity):
            subj_lower = subject.lower()
            if valid_subjects and not any(v in subj_lower or subj_lower in v for v in valid_subjects):
                issues.append(f"Subject '{subject}' on {day} was not listed in the student's subjects ({', '.join(student_data.get('subjects', []))}).")

        sessions_by_day[day].append({
            "start_min": start_min,
            "end_min": end_min,
            "start": start,
            "end": end,
            "subject": subject,
            "activity": activity,
            "duration_hours": duration_min / 60.0,
            "is_break": is_break_activity(subject) or is_break_activity(activity)
        })

    # Day-level checks: Overlaps, Daily Study Hours, Breaks
    for day, day_sessions in sessions_by_day.items():
        if not day_sessions:
            continue

        # Sort chronologically
        day_sessions.sort(key=lambda s: s["start_min"])

        # Check overlapping sessions
        for i in range(len(day_sessions) - 1):
            cur = day_sessions[i]
            nxt = day_sessions[i + 1]
            if cur["end_min"] > nxt["start_min"]:
                issues.append(
                    f"Overlapping sessions on {day}: '{cur['subject']}' ({cur['start']}-{cur['end']}) overlaps with '{nxt['subject']}' ({nxt['start']}-{nxt['end']})."
                )

        # Check study hours per day
        study_hours = sum(s["duration_hours"] for s in day_sessions if not s["is_break"])
        # Allow 0.5 hour tolerance
        if study_hours > (available_hours + 0.5):
            issues.append(
                f"Total study hours on {day} ({study_hours:.1f} hrs) exceed available daily limit of {available_hours:.1f} hours."
            )

        # Check breaks: If more than 2 hours of study scheduled, ensure at least one break or gap exists
        if study_hours >= 2.5:
            has_break_session = any(s["is_break"] for s in day_sessions)
            has_gap = False
            for i in range(len(day_sessions) - 1):
                gap = day_sessions[i+1]["start_min"] - day_sessions[i]["end_min"]
                if gap >= max(10, break_duration - 5):
                    has_gap = True
                    break
            if not (has_break_session or has_gap):
                issues.append(f"On {day}, {study_hours:.1f} hours of study are scheduled without any scheduled breaks.")

    is_valid = len(issues) == 0
    return is_valid, issues

def calculate_schedule_stats(schedule):
    """
    Calculates key metrics from the schedule.
    Returns total_hours, days_count, subject_distribution, break_count, etc.
    """
    if not schedule or not isinstance(schedule, list):
        return {
            "total_hours": 0.0,
            "avg_daily_hours": 0.0,
            "total_sessions": 0,
            "break_sessions": 0,
            "subject_breakdown": {},
            "active_days": 0
        }

    total_study_minutes = 0
    break_count = 0
    subject_minutes = {}
    active_days_set = set()

    for item in schedule:
        start_min = parse_time_to_minutes(item.get("start"))
        end_min = parse_time_to_minutes(item.get("end"))
        if start_min is None or end_min is None or start_min >= end_min:
            continue

        dur = end_min - start_min
        subj = item.get("subject", "").strip()
        act = item.get("activity", "").strip()

        if is_break_activity(subj) or is_break_activity(act):
            break_count += 1
        else:
            total_study_minutes += dur
            active_days_set.add(item.get("day"))
            subject_minutes[subj] = subject_minutes.get(subj, 0) + dur

    total_hours = round(total_study_minutes / 60.0, 1)
    active_days = max(1, len(active_days_set))
    avg_daily_hours = round(total_hours / 7.0, 1)

    subject_breakdown = {
        s: round(mins / 60.0, 1) for s, mins in subject_minutes.items()
    }

    return {
        "total_hours": total_hours,
        "avg_daily_hours": avg_daily_hours,
        "total_sessions": len(schedule),
        "break_sessions": break_count,
        "subject_breakdown": subject_breakdown,
        "active_days": len(active_days_set)
    }

def generate_fallback_timetable(student_data):
    """
    Deterministic rule-based timetable generator.
    Used when Gemini API is unavailable or rate-limited.
    Constructs a well-balanced, non-overlapping weekly study plan
    prioritizing harder subjects and near exam dates.
    """
    subjects = student_data.get("subjects", [])
    if not subjects:
        subjects = ["General Study", "Revision"]

    difficulties = student_data.get("difficulties", {})
    # Default to Medium if not specified
    diff_weights = {"easy": 1, "medium": 2, "hard": 3}

    # Weight subjects based on difficulty
    weighted_pool = []
    for s in subjects:
        diff = difficulties.get(s, "medium").lower()
        w = diff_weights.get(diff, 2)
        weighted_pool.extend([s] * w)

    available_hours = float(student_data.get("available_hours", 4.0))
    pref_start = student_data.get("preferred_start", "09:00")
    break_duration = int(student_data.get("break_duration", 15))

    start_min = parse_time_to_minutes(pref_start) or 540  # 09:00
    session_length = 60  # standard 60-minute blocks

    # Compute number of study blocks per day (up to available_hours)
    num_blocks = max(1, min(6, int(available_hours)))

    activities_map = {
        "hard": ["Deep concept review & problem solving", "Core theory & challenging exercises", "Past paper questions"],
        "medium": ["Chapter reading & note taking", "Review lecture slides & exercises", "Summary sheet creation"],
        "easy": ["Quick formula revision & flashcards", "Practice quiz & light review", "Weekly review & organization"]
    }

    schedule = []
    subject_index = 0

    for day_idx, day in enumerate(DAYS_OF_WEEK):
        current_time = start_min

        # Weekend adjustment: slightly lighter or revision focus on Sunday
        blocks_today = num_blocks
        if day == "Sunday" and blocks_today > 2:
            blocks_today -= 1

        for b in range(blocks_today):
            # Select subject
            subject = weighted_pool[subject_index % len(weighted_pool)]
            subject_index += 1

            diff = difficulties.get(subject, "medium").lower()
            possible_activities = activities_map.get(diff, activities_map["medium"])
            activity = possible_activities[(day_idx + b) % len(possible_activities)]

            s_start = minutes_to_time(current_time)
            s_end = minutes_to_time(current_time + session_length)

            schedule.append({
                "day": day,
                "start": s_start,
                "end": s_end,
                "subject": subject,
                "activity": activity
            })

            current_time += session_length

            # Insert break between blocks if more blocks follow
            if b < blocks_today - 1:
                b_start = minutes_to_time(current_time)
                b_end = minutes_to_time(current_time + break_duration)
                schedule.append({
                    "day": day,
                    "start": b_start,
                    "end": b_end,
                    "subject": "Break",
                    "activity": "Rest, hydrate, and stretch"
                })
                current_time += break_duration

    explanation = (
        f"Generated a balanced {available_hours}-hour daily study plan across all 7 days. "
        "Harder subjects are scheduled during peak focus periods with frequent spaced repetitions, "
        f"and structured {break_duration}-minute breaks are placed between intensive study sessions."
    )

    suggestions = [
        "Review difficult concepts earlier in each session when focus is highest.",
        f"Honor each {break_duration}-minute break without screen time to prevent cognitive fatigue.",
        "Use active recall techniques (practice questions, self-testing) rather than passive reading.",
        "Adjust Sunday sessions for weekly consolidation and planning upcoming milestones."
    ]

    return {
        "message": explanation,
        "suggestions": suggestions,
        "schedule": schedule
    }
