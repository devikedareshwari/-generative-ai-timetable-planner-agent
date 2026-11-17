"""
Unit tests for agent.py logic and JSON parsing resilience.
"""

import unittest
import agent
import tools

class AgentUnitTests(unittest.TestCase):
    def test_clean_json_response_clean(self):
        sample = '{"message": "Hello", "suggestions": ["Tip 1"], "schedule": []}'
        res = agent.clean_json_response(sample)
        self.assertIsNotNone(res)
        self.assertEqual(res["message"], "Hello")

    def test_clean_json_response_markdown_fence(self):
        sample = '```json\n{"message": "Fenced", "suggestions": [], "schedule": [{"day": "Monday"}]}\n```'
        res = agent.clean_json_response(sample)
        self.assertIsNotNone(res)
        self.assertEqual(res["message"], "Fenced")
        self.assertEqual(len(res["schedule"]), 1)

    def test_clean_json_response_dirty_text(self):
        sample = 'Here is your schedule:\n```\n{"message": "Embedded", "schedule": []}\n```\nHope this helps!'
        res = agent.clean_json_response(sample)
        self.assertIsNotNone(res)
        self.assertEqual(res["message"], "Embedded")

    def test_build_planning_prompt(self):
        student_data = {
            "name": "Jane Doe",
            "subjects": ["Biology", "Chemistry"],
            "difficulties": {"Biology": "Easy", "Chemistry": "Hard"},
            "exam_dates": "Chemistry: Nov 30",
            "available_hours": 3.5,
            "preferred_start": "10:00",
            "preferred_end": "18:00",
            "break_duration": 20,
            "instructions": "More Chemistry lab practice"
        }
        prompt = agent.build_planning_prompt(student_data)
        self.assertIn("Jane Doe", prompt)
        self.assertIn("Biology: Difficulty = Easy", prompt)
        self.assertIn("Chemistry: Difficulty = Hard", prompt)
        self.assertIn("3.5", prompt)
        self.assertIn("10:00", prompt)
        self.assertIn("18:00", prompt)

    def test_time_conversion_utilities(self):
        self.assertEqual(tools.parse_time_to_minutes("00:00"), 0)
        self.assertEqual(tools.parse_time_to_minutes("09:30"), 570)
        self.assertEqual(tools.parse_time_to_minutes("23:59"), 1439)
        self.assertIsNone(tools.parse_time_to_minutes("25:00"))
        self.assertIsNone(tools.parse_time_to_minutes("invalid"))

        self.assertEqual(tools.minutes_to_time(0), "00:00")
        self.assertEqual(tools.minutes_to_time(570), "09:30")
        self.assertEqual(tools.minutes_to_time(1439), "23:59")

if __name__ == "__main__":
    unittest.main()
