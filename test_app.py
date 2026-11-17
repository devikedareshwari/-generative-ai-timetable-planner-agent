"""
Comprehensive test suite for SmartSched application.
Verifies all 13 points outlined in Section 15 of user request.
"""

import os
import json
import unittest
from app import app
import database
import tools
import agent

class SmartSchedTestCase(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_01_static_css_loads(self):
        """Verify that /style.css returns 200 and text/css."""
        response = self.client.get("/style.css")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/css", response.content_type)
        self.assertIn(b"SmartSched", response.data)

    def test_02_static_js_loads(self):
        """Verify that /script.js returns 200 and javascript."""
        response = self.client.get("/script.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn("javascript", response.content_type)
        self.assertIn(b"SmartSched", response.data)

    def test_02b_static_image_loads(self):
        """Verify that /images/logo.svg returns 200."""
        response = self.client.get("/images/logo.svg")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<svg", response.data)

    def test_03_home_page_loads(self):
        """Verify that home page loads with required headings and elements."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"SmartSched", response.data)
        self.assertIn(b"AI Student Timetable Planner", response.data)
        self.assertIn(b"Create My Timetable", response.data)
        self.assertIn(b"href=\"/style.css\"", response.data)
        self.assertIn(b"src=\"/script.js\"", response.data)

    def test_04_timetable_page_loads(self):
        """Verify that timetable page loads correctly."""
        response = self.client.get("/timetable")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"SmartSched", response.data)
        self.assertIn(b"Ask SmartSched AI to Change Your Timetable", response.data)

    def test_05_api_status(self):
        """Verify status API response."""
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("ai_configured", data)
        self.assertIn("model", data)

    def test_06_form_validation_rejects_empty(self):
        """Verify that missing student name or subjects produces 400 error."""
        resp1 = self.client.post("/api/generate", json={"name": ""})
        self.assertEqual(resp1.status_code, 400)

        resp2 = self.client.post("/api/generate", json={"name": "Alice", "subjects": []})
        self.assertEqual(resp2.status_code, 400)

        resp3 = self.client.post("/api/generate", json={
            "name": "Alice",
            "subjects": ["Math"],
            "preferred_start": "21:00",
            "preferred_end": "09:00"
        })
        self.assertEqual(resp3.status_code, 400)

    def test_07_timetable_generation_demo_fallback(self):
        """Verify timetable generation and structure."""
        payload = {
            "name": "Alex Smith",
            "subjects": ["Mathematics", "Physics", "Chemistry"],
            "difficulties": {"Mathematics": "Hard", "Physics": "Medium", "Chemistry": "Easy"},
            "exam_dates": "Mathematics: Dec 1, Physics: Dec 10",
            "available_hours": 4.0,
            "preferred_start": "09:00",
            "preferred_end": "20:00",
            "break_duration": 15,
            "instructions": "More focus on Mathematics"
        }
        response = self.client.post("/api/generate", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(len(data["schedule"]) > 0)
        self.assertIn("generation_type", data)
        self.assertIn("stats", data)
        self.assertTrue(data["stats"]["total_hours"] > 0)

        # Verify timetable validation on generated output
        is_valid, issues = tools.validate_timetable(data["schedule"], data["student_data"])
        self.assertTrue(is_valid, f"Validation issues found: {issues}")

        # Verify saved in database
        timetable_id = data["timetable_id"]
        self.assertIsNotNone(timetable_id)
        saved = database.get_timetable_by_id(timetable_id)
        self.assertIsNotNone(saved)
        self.assertEqual(saved["student_name"], "Alex Smith")

    def test_08_database_history_and_detail(self):
        """Verify history retrieval from SQLite."""
        response = self.client.get("/api/timetables")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(isinstance(data["timetables"], list))

    def test_09_schedule_stats_calculation(self):
        """Verify statistics computation."""
        sample_schedule = [
            {"day": "Monday", "start": "09:00", "end": "10:30", "subject": "Math", "activity": "Algebra"},
            {"day": "Monday", "start": "10:30", "end": "10:45", "subject": "Break", "activity": "Walk"},
            {"day": "Monday", "start": "10:45", "end": "12:00", "subject": "Physics", "activity": "Optics"}
        ]
        stats = tools.calculate_schedule_stats(sample_schedule)
        self.assertAlmostEqual(stats["total_hours"], 2.8, delta=0.1)
        self.assertEqual(stats["break_sessions"], 1)
        self.assertEqual(stats["total_sessions"], 3)

    def test_10_tools_validation_catches_overlaps(self):
        """Verify that overlap detection works properly."""
        overlapping_schedule = [
            {"day": "Monday", "start": "09:00", "end": "10:30", "subject": "Math", "activity": "Algebra"},
            {"day": "Monday", "start": "10:00", "end": "11:30", "subject": "Physics", "activity": "Optics"}
        ]
        student_data = {
            "subjects": ["Math", "Physics"],
            "available_hours": 4.0,
            "preferred_start": "08:00",
            "preferred_end": "20:00",
            "break_duration": 15
        }
        is_valid, issues = tools.validate_timetable(overlapping_schedule, student_data)
        self.assertFalse(is_valid)
        self.assertTrue(any("Overlapping" in issue for issue in issues))

    def test_11_reschedule_endpoint(self):
        """Verify rescheduling API endpoint."""
        # Empty request string should fail
        resp_empty = self.client.post("/api/reschedule", json={"request": ""})
        self.assertEqual(resp_empty.status_code, 400)

        # Call with reschedule request
        resp = self.client.post("/api/reschedule", json={
            "request": "Give more time to Mathematics",
            "current_schedule": [
                {"day": "Monday", "start": "09:00", "end": "10:00", "subject": "Mathematics", "activity": "Practice"}
            ],
            "student_data": {"subjects": ["Mathematics"], "available_hours": 2}
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("status", data)

    def test_12_timetable_by_id_and_delete(self):
        """Verify fetching timetable by ID and deletion."""
        # Create a timetable
        timetable_id = database.save_timetable(
            student_name="Test Student",
            subjects=["History"],
            schedule=[{"day": "Monday", "start": "10:00", "end": "11:00", "subject": "History", "activity": "Reading"}],
            suggestions=["Take notes"],
            message="Test message",
            generation_type="Demo Timetable"
        )
        self.assertIsNotNone(timetable_id)

        # Fetch detail
        detail_resp = self.client.get(f"/api/timetables/{timetable_id}")
        self.assertEqual(detail_resp.status_code, 200)
        detail_data = detail_resp.get_json()
        self.assertEqual(detail_data["timetable"]["student_name"], "Test Student")

        # Delete
        del_resp = self.client.delete(f"/api/timetables/{timetable_id}")
        self.assertEqual(del_resp.status_code, 200)
        self.assertEqual(del_resp.get_json()["status"], "success")

        # Fetch after delete
        not_found_resp = self.client.get(f"/api/timetables/{timetable_id}")
        self.assertEqual(not_found_resp.status_code, 404)

if __name__ == "__main__":
    unittest.main()
