import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
sys.path.insert(0, str(EXAMPLES))

from assemble_md import assemble_and_validate
import retry_failures
from run_manifest import RunManifest
from vlm_client import VLMClient


class _FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body
        self.text = json.dumps(body)

    def json(self):
        return self._body


class _FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


class ManifestTests(unittest.TestCase):
    def test_manifest_round_trip_and_stage_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            pdf_path = output_dir / "paper.pdf"
            pdf_path.write_bytes(b"pdf")

            manifest = RunManifest.create(output_dir, pdf_path)
            manifest.set_stage("parse", "completed")
            manifest.set_artifact("source_markdown", "docling.md")

            loaded = RunManifest.load(output_dir)
            self.assertTrue(loaded.stage_completed("parse"))
            self.assertEqual(loaded.artifact("source_markdown"), "docling.md")
            self.assertEqual(
                list(output_dir.glob(".run_manifest.json.*.tmp")),
                [],
            )


class VLMClientTests(unittest.TestCase):
    def test_retries_retryable_status_and_normalizes_content(self):
        session = _FakeSession(
            [
                _FakeResponse(429, {"error": "rate limit"}),
                _FakeResponse(
                    200,
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": [{"type": "text", "text": "YES"}],
                                }
                            }
                        ],
                        "usage": {
                            "prompt_tokens": 3,
                            "completion_tokens": 2,
                            "total_tokens": 5,
                        },
                    },
                ),
            ]
        )
        client = VLMClient(
            model="test",
            api_base="https://example.test/v1",
            api_key="key",
            session=session,
            sleep=lambda _: None,
        )

        self.assertEqual(client.analyze_b64("image", "prompt"), "YES")
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(client.usage["total_tokens"], 5)

    def test_json_array_retries_invalid_response(self):
        session = _FakeSession(
            [
                _FakeResponse(
                    200,
                    {"choices": [{"message": {"content": "not json"}}]},
                ),
                _FakeResponse(
                    200,
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": (
                                        '[{"fig_type":"plot","data_type":"none","content":""}]'
                                    )
                                }
                            }
                        ]
                    },
                ),
            ]
        )
        client = VLMClient(
            model="test",
            api_base="https://example.test/v1",
            api_key="key",
            enable_thinking=False,
            session=session,
            sleep=lambda _: None,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "panel.png"
            Image.new("RGB", (16, 16), "white").save(image_path)
            result = client.analyze_json_array(image_path, "prompt")

        self.assertEqual(result[0]["fig_type"], "plot")
        self.assertIs(session.calls[-1][1]["json"]["enable_thinking"], False)


class AssemblerTests(unittest.TestCase):
    def _prepare_run(self, output_dir):
        pdf_path = output_dir / "paper.pdf"
        pdf_path.write_bytes(b"pdf")
        (output_dir / "docling.md").write_text(
            "Title\n\n<!-- image -->\n\nEnd text\n",
            encoding="utf-8",
        )
        panel_dir = output_dir / "panels"
        panel_dir.mkdir()
        (panel_dir / "Figure1_PanelA.png").write_bytes(b"image")
        manifest = RunManifest.create(output_dir, pdf_path)
        manifest.set_artifact("paper_name", "paper")
        manifest.set_artifact("source_markdown", "docling.md")
        manifest.set_artifact("figures", [
            {
                "docling_index": 0,
                "picture_index": 0,
                "figure_number": 1,
                "panels": [
                    {"label": "A", "path": "panels/Figure1_PanelA.png"},
                ],
                "full_image": None,
            }
        ])
        manifest.set_artifact("descriptions", {"Figure1_PanelA.png": "caption"})
        manifest.set_artifact("extracted_tables", {})
        (output_dir / "panels_data.json").write_text(
            json.dumps({
                "Figure1_PanelA.png": [
                    {
                        "fig_type": "plot",
                        "data_type": "num_table",
                        "content": 'Group,Value\n"A","1,2"',
                    }
                ]
            }),
            encoding="utf-8",
        )
        return manifest

    def test_assembly_uses_current_panel_data_and_quality_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            manifest = self._prepare_run(output_dir)
            result = assemble_and_validate(output_dir, manifest)

            markdown = result["markdown_path"].read_text(encoding="utf-8")
            self.assertIn("Figure1_PanelA.png", markdown)
            self.assertIn("| A | 1,2 |", markdown)
            self.assertNotIn("<!-- image -->", markdown)
            self.assertTrue(result["report"]["ok"])

    def test_quality_gate_reports_missing_image(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            manifest = self._prepare_run(output_dir)
            (output_dir / "panels" / "Figure1_PanelA.png").unlink()

            result = assemble_and_validate(output_dir, manifest)

            self.assertFalse(result["report"]["ok"])
            self.assertTrue(result["report"]["errors"])

    def test_successful_retry_reassembles_and_passes_quality_gate(self):
        class _FakeClient:
            usage = {
                "calls": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }

            def analyze_json_array(self, *_args, **_kwargs):
                return [
                    {
                        "fig_type": "plot",
                        "data_type": "description",
                        "content": "repaired",
                    }
                ]

            def snapshot_usage(self):
                return dict(self.usage)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            self._prepare_run(output_dir)
            panels_path = output_dir / "panels_data.json"
            panels_data = json.loads(panels_path.read_text(encoding="utf-8"))
            panels_data["Figure1_PanelA.png"] = [
                {
                    "fig_type": "error",
                    "data_type": "description",
                    "content": "simulated",
                }
            ]
            panels_path.write_text(json.dumps(panels_data), encoding="utf-8")
            args = SimpleNamespace(
                max_retries=1,
                delay=0,
                parallel=1,
                dry_run=False,
                verbose=False,
            )

            success, failed, errors = retry_failures.process_pdf(
                output_dir,
                "{caption}",
                _FakeClient(),
                args,
            )

            manifest = RunManifest.load(output_dir)
            quality = json.loads(
                (output_dir / "quality_report.json").read_text(encoding="utf-8")
            )
            self.assertEqual((success, failed, errors), (1, 0, []))
            self.assertEqual(
                manifest.data["panels"]["Figure1_PanelA.png"]["status"],
                "completed",
            )
            self.assertTrue(quality["ok"])


if __name__ == "__main__":
    unittest.main()
