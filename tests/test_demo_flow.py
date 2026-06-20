import json
import unittest
from pathlib import Path

import app


class DemoFlowTest(unittest.TestCase):
    def setUp(self):
        self.state_path = Path(__file__).resolve().parent / "test_state.json"
        app.save_state(app.initial_state(), self.state_path)
        self.state = app.load_state(self.state_path)
        self.original_record_agent_turn = app.record_agent_turn
        self.original_build_capsule_asset = app.build_capsule_asset
        self.original_build_evolution_event = app.build_evolution_event
        app.record_agent_turn = lambda *args, **kwargs: None
        app.build_capsule_asset = lambda *args, **kwargs: {
            "ok": True,
            "asset": {"asset_id": "sha256:" + "a" * 64},
        }
        app.build_evolution_event = lambda *args, **kwargs: {"ok": True}

    def tearDown(self):
        app.record_agent_turn = self.original_record_agent_turn
        app.build_capsule_asset = self.original_build_capsule_asset
        app.build_evolution_event = self.original_build_evolution_event

    def test_complete_evolution_flow_and_persistence(self):
        app.submit_source_query(self.state, app.SOURCE_QUERY)
        self.assertEqual(self.state["session"]["source_answer"], app.INITIAL_ANSWER)
        self.assertEqual(
            self.state["session"]["source_knowledge"]["id"],
            "KB-WM-SHAKE-001",
        )

        _, reused_before_approval = app.answer_query(self.state, app.SIMILAR_QUERY)
        self.assertFalse(reused_before_approval)

        app.mark_for_evolution(self.state)
        app.submit_correction(self.state, app.DEFAULT_CORRECTION)
        app.generate_candidate(self.state)
        self.assertEqual(self.state["capsule"]["status"], "待批准")
        self.assertEqual(self.state["capsule"]["gep_asset_id"], "")

        app.approve_capsule(self.state)
        self.assertEqual(self.state["capsule"]["status"], "待验证")
        reused = app.submit_similar_query(self.state, app.SIMILAR_QUERY)
        self.assertTrue(reused)
        self.assertEqual(self.state["session"]["similar_answer"], app.EVOLVED_ANSWER)
        self.assertEqual(self.state["capsule"]["reuse_count"], 1)

        validation = app.run_golden_validation(self.state)
        self.assertEqual(validation["passed"], validation["total"])
        self.assertEqual(self.state["capsule"]["status"], "已验证")
        self.assertTrue(self.state["capsule"]["gep_asset_id"].startswith("sha256:"))

        app.save_state(self.state, self.state_path)
        reloaded = app.load_state(self.state_path)
        self.assertEqual(reloaded["capsule"]["status"], "已验证")
        self.assertEqual(reloaded["capsule"]["reuse_count"], 1)
        self.assertEqual(
            [event["type"] for event in reloaded["events"]],
            ["发现", "标记", "纠正", "生成", "批准", "复用", "验证"],
        )

    def test_non_matching_question_does_not_reuse_capsule(self):
        app.approve_capsule(self.state)
        answer, reused = app.answer_query(self.state, "冰箱不制冷怎么办？")
        self.assertFalse(reused)
        self.assertEqual(answer, app.FALLBACK_ANSWER)

    def test_high_risk_query_stops_self_service(self):
        app.approve_capsule(self.state)
        answer, reused = app.answer_query(self.state, "洗衣机一脱水就晃，而且漏水")
        self.assertTrue(reused)
        self.assertIn("断电并停止使用", answer)
        self.assertIn("人工售后", answer)

    def test_state_file_is_valid_json(self):
        app.save_state(self.state, self.state_path)
        with self.state_path.open("r", encoding="utf-8") as file:
            parsed = json.load(file)
        self.assertEqual(parsed["capsule"]["id"], "CAP-WM-001")


if __name__ == "__main__":
    unittest.main()
