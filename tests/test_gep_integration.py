import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import gep_integration


class GepIntegrationTest(unittest.TestCase):
    def test_sanitize_text_masks_phone_and_long_ids(self):
        text = gep_integration.sanitize_text("电话13812345678，订单1234567890123456")
        self.assertNotIn("13812345678", text)
        self.assertNotIn("1234567890123456", text)

    def test_build_capsule_uses_verified_sdk_asset(self):
        capsule = {
            "id": "CAP-TEST-001",
            "title": "测试 Capsule",
            "trigger": "脱水晃动",
            "steps": ["先检查地面", "再检查衣物偏载"],
            "boundary": "异常时转人工",
        }
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(gep_integration, "ASSET_DIR", Path(directory)):
                result = gep_integration.build_capsule_asset(capsule, "按顺序排查")
        self.assertTrue(result["ok"], result.get("error"))
        self.assertRegex(result["asset"]["asset_id"], r"^sha256:[a-f0-9]{64}$")
        self.assertRegex(result["asset"]["schema_version"], r"^\d+\.\d+\.\d+$")

    def test_record_agent_turn_writes_sanitized_openclaw_jsonl(self):
        with tempfile.TemporaryDirectory() as directory:
            sessions_dir = Path(directory)
            with patch.object(gep_integration, "EVOLVER_SESSIONS_DIR", sessions_dir):
                gep_integration.record_agent_turn(
                    "user",
                    "手机号13812345678，机器脱水乱跳",
                    "customer_query",
                )
            lines = [
                json.loads(line)
                for line in (sessions_dir / "the-pearl-session.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
        self.assertEqual(lines[0]["type"], "session")
        self.assertEqual(lines[1]["type"], "message")
        self.assertNotIn("13812345678", lines[1]["message"]["content"])

    def test_evolver_parses_recorded_session(self):
        with tempfile.TemporaryDirectory() as directory:
            sessions_dir = Path(directory)
            with patch.object(gep_integration, "EVOLVER_SESSIONS_DIR", sessions_dir):
                gep_integration.record_agent_turn("user", "脱水时机器晃动", "customer_query")
                gep_integration.record_agent_turn("assistant", "请先检查地面。", "initial_answer")
                result = gep_integration.run_evolver_once()
        self.assertTrue(result["ok"], result.get("error"))
        self.assertIn("解析消息：2 条", result["output"])
        self.assertIn("脱水时机器晃动", result["output"])


if __name__ == "__main__":
    unittest.main()
