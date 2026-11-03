import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PIPELINE_PATH = ROOT / "examples" / "pipeline.py"

spec = importlib.util.spec_from_file_location("pdf2md_pipeline", PIPELINE_PATH)
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


class PipelineTests(unittest.TestCase):
    def test_panel_prompt_uses_figure_rules_reference(self):
        expected = (ROOT / "references" / "figure_rules.md").read_text(encoding="utf-8")

        self.assertEqual(pipeline.load_panel_prompt(), expected)

    def test_full_image_name_uses_original_path_after_index_remap(self):
        renamed = {"pic_001.png": "Figure1_full.png"}

        self.assertEqual(
            pipeline.resolve_renamed_image(Path("pic_001.png"), renamed),
            "Figure1_full.png",
        )

    def test_import_does_not_force_offline_mode(self):
        code = f"""
import importlib.util
import os
spec = importlib.util.spec_from_file_location('pipeline_import_check', {str(PIPELINE_PATH)!r})
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print(f"{{os.environ.get('HF_HUB_OFFLINE')}}|{{os.environ.get('TRANSFORMERS_OFFLINE')}}")
"""
        env = os.environ.copy()
        env.pop("HF_HUB_OFFLINE", None)
        env.pop("TRANSFORMERS_OFFLINE", None)

        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-c", code],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )

        self.assertEqual(result.stdout.strip(), "None|None")

    def test_runtime_offline_setting_controls_model_download_mode(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            for offline, expected in ((False, None), (True, "1")):
                with self.subTest(offline=offline):
                    config_path.write_text(
                        "runtime:\n"
                        f"  offline: {str(offline).lower()}\n"
                        "vlm:\n"
                        "  model: test-model\n"
                        "  api_base: https://example.test/v1\n"
                        "  api_key: test-key\n",
                        encoding="utf-8",
                    )
                    config = pipeline.load_config(config_path)

                    with patch.dict(os.environ, {}, clear=True):
                        pipeline.configure_runtime(config)
                        self.assertEqual(os.environ.get("HF_HUB_OFFLINE"), expected)
                        self.assertEqual(os.environ.get("TRANSFORMERS_OFFLINE"), expected)

    def test_nonempty_output_directory_requires_overwrite(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "paper-with-csv"
            output_dir.mkdir()
            (output_dir / "old-result.txt").write_text("old", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                pipeline.prepare_output_dir(output_dir, "paper", overwrite=False)

    def test_overwrite_cleans_only_pipeline_managed_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "paper-with-csv"
            images_dir = output_dir / "images"
            panels_dir = output_dir / "panels"
            images_dir.mkdir(parents=True)
            panels_dir.mkdir()
            (images_dir / "old.png").write_bytes(b"old")
            (panels_dir / "old.png").write_bytes(b"old")
            (output_dir / "panels_data.json").write_text("{}", encoding="utf-8")
            (output_dir / "descriptions.json").write_text("{}", encoding="utf-8")
            (output_dir / "paper_complete.md").write_text("old", encoding="utf-8")
            unrelated = output_dir / "keep.txt"
            unrelated.write_text("keep", encoding="utf-8")

            pipeline.prepare_output_dir(output_dir, "paper", overwrite=True)

            self.assertEqual(list(images_dir.iterdir()), [])
            self.assertEqual(list(panels_dir.iterdir()), [])
            self.assertFalse((output_dir / "panels_data.json").exists())
            self.assertFalse((output_dir / "descriptions.json").exists())
            self.assertFalse((output_dir / "paper_complete.md").exists())
            self.assertTrue(unrelated.exists())

    def test_help_omits_deprecated_batch_option(self):
        result = subprocess.run(
            [sys.executable, "-X", "utf8", str(PIPELINE_PATH), "--help"],
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertNotIn("--batch", result.stdout)

    def test_vlm_request_uses_standard_payload_fields(self):
        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"choices": [{"message": {"content": "ok"}}]}

        with patch.dict(os.environ, {}, clear=True):
            with patch.object(pipeline.requests, "post", return_value=FakeResponse()) as post:
                pipeline.call_vlm(
                    img_b64="image-data",
                    prompt="describe",
                    model="test-model",
                    api_base="https://example.test/v1",
                    api_key="test-key",
                )

        payload = post.call_args.kwargs["json"]
        self.assertNotIn("enable_thinking", payload)

    def test_enable_thinking_config_controls_vlm_payload(self):
        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"choices": [{"message": {"content": "ok"}}]}

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            config_path.write_text(
                "runtime:\n"
                "  offline: false\n"
                "vlm:\n"
                "  model: test-model\n"
                "  api_base: https://example.test/v1\n"
                "  api_key: test-key\n"
                "  enable_thinking: false\n",
                encoding="utf-8",
            )
            config = pipeline.load_config(config_path)

            with patch.dict(os.environ, {}, clear=True):
                pipeline.configure_runtime(config)
                with patch.object(pipeline.requests, "post", return_value=FakeResponse()) as post:
                    pipeline.call_vlm(
                        img_b64="image-data",
                        prompt="describe",
                        model="test-model",
                        api_base="https://example.test/v1",
                        api_key="test-key",
                    )

        self.assertIs(post.call_args.kwargs["json"]["enable_thinking"], False)


if __name__ == "__main__":
    unittest.main()
