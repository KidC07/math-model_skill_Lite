import importlib.util
import json
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
spec = importlib.util.spec_from_file_location("evidence", SCRIPTS / "evidence.py")
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)
check_spec = importlib.util.spec_from_file_location("local_check", SCRIPTS / "local_check.py")
local_check = importlib.util.module_from_spec(check_spec)
check_spec.loader.exec_module(local_check)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mathorcup_test_")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "输入 数据.csv").write_text("x,y\n1,3\n", encoding="utf-8-sig")

    def make_snapshot(self):
        return evidence.snapshot(self.root, ["输入 数据.csv"], "results/evidence.json", "python solve.py")

    def test_unchanged_then_changed_then_missing(self):
        self.make_snapshot()
        self.assertTrue(evidence.verify(self.root, "results/evidence.json")["ok"])
        source = self.root / "输入 数据.csv"
        source.write_text("x,y\n1,999\n", encoding="utf-8-sig")
        self.assertFalse(evidence.verify(self.root, "results/evidence.json")["ok"])
        source.unlink()
        self.assertFalse(evidence.verify(self.root, "results/evidence.json")["ok"])

    def test_relative_manifest_survives_project_move(self):
        self.make_snapshot()
        destination = self.root / "移动后的项目"
        destination.mkdir()
        (self.root / "输入 数据.csv").rename(destination / "输入 数据.csv")
        (self.root / "results").rename(destination / "results")
        self.assertTrue(evidence.verify(destination, "results/evidence.json")["ok"])

    def test_existing_output_is_not_overwritten(self):
        self.make_snapshot()
        before = (self.root / "results/evidence.json").read_bytes()
        with self.assertRaises(FileExistsError):
            self.make_snapshot()
        self.assertEqual(before, (self.root / "results/evidence.json").read_bytes())

    def test_escape_and_absolute_paths_are_rejected(self):
        for path in ["../outside.csv", str(self.root / "输入 数据.csv")]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                evidence.snapshot(self.root, [path], "record.json")
        with self.assertRaises(ValueError):
            evidence.snapshot(self.root, ["输入 数据.csv"], "../record.json")

    def test_malicious_manifest_cannot_read_outside(self):
        self.make_snapshot()
        target = self.root / "results/evidence.json"
        data = json.loads(target.read_text(encoding="utf-8"))
        data["files"][0]["path"] = "../../outside.txt"
        target.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(ValueError):
            evidence.verify(self.root, "results/evidence.json")

    def test_cli_handles_unicode_and_spaces(self):
        run = subprocess.run([sys.executable, "-B", "-X", "utf8", str(SCRIPTS / "evidence.py"),
                              "snapshot", "--root", str(self.root), "--files", "输入 数据.csv",
                              "--output", "结果 清单.json"], capture_output=True, text=True, encoding="utf-8", timeout=15)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertTrue(evidence.verify(self.root, "结果 清单.json")["ok"])


class OfflineChecks(unittest.TestCase):
    def test_default_check_fails_without_latex(self):
        with patch.object(local_check, "module_info", return_value={"available": True}), \
             patch.object(local_check, "find_xelatex", return_value=None):
            report = local_check.probe(local_check.parse_features(local_check.DEFAULT))
        self.assertFalse(report["ok"])
        self.assertFalse(report["features"]["latex"]["available"])

    def test_failed_second_latex_pass_is_not_hidden_by_first_pdf(self):
        with tempfile.TemporaryDirectory(prefix="mathorcup_latex_") as temporary:
            output = Path(temporary)
            calls = 0

            def fake_run(command, **kwargs):
                nonlocal calls
                if "--version" in command:
                    return subprocess.CompletedProcess(command, 0, "XeTeX (TeX Live)\n", "")
                calls += 1
                (output / "synthetic_latex.pdf").write_bytes(b"first-pass-output")
                return subprocess.CompletedProcess(command, 0 if calls == 1 else 1, "", "second pass failed" if calls == 2 else "")

            with patch.object(local_check, "find_xelatex", return_value="xelatex"), \
                 patch.object(local_check.subprocess, "run", side_effect=fake_run):
                with self.assertRaisesRegex(RuntimeError, "pass 2 failed"):
                    local_check.latex(output)
            self.assertTrue((output / "synthetic_latex.pdf").exists())

    def test_inaccessible_binary_is_not_reported_as_usable(self):
        with patch.object(local_check.importlib, "import_module", side_effect=ImportError("DLL access denied")):
            result = local_check.module_info("numpy")
        self.assertFalse(result["available"])
        self.assertIn("access denied", result["reason"])

    def test_package_works_after_copy_to_another_directory(self):
        package = SCRIPTS.parents[3]
        with tempfile.TemporaryDirectory(prefix="mathorcup_portable_") as temporary:
            moved = Path(temporary) / "队友电脑 副本"
            shutil.copytree(package, moved, ignore=shutil.ignore_patterns("验证记录", "__pycache__"))
            script = moved / ".agents/skills/mathorcup-modeling/scripts/validate_package.py"
            run = subprocess.run([sys.executable, "-B", "-X", "utf8", str(script)], cwd=temporary,
                                 capture_output=True, text=True, encoding="utf-8", timeout=15)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            checker = script.with_name("local_check.py")
            run = subprocess.run([sys.executable, "-B", "-X", "utf8", str(checker), "check", "--features", "base"],
                                 cwd=temporary, capture_output=True, text=True, encoding="utf-8", timeout=15)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_base_check_needs_no_optional_packages(self):
        run = subprocess.run([sys.executable, "-B", "-X", "utf8", str(SCRIPTS / "local_check.py"),
                              "check", "--features", "base"], capture_output=True, text=True, encoding="utf-8", timeout=15)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertTrue(json.loads(run.stdout)["ok"])

    def test_smoke_refuses_existing_directory(self):
        with tempfile.TemporaryDirectory(prefix="mathorcup_guard_") as directory:
            marker = Path(directory) / "original.txt"
            marker.write_text("keep", encoding="utf-8")
            run = subprocess.run([sys.executable, "-B", "-X", "utf8", str(SCRIPTS / "local_check.py"),
                                  "smoke", "--features", "base", "--out", directory],
                                 capture_output=True, text=True, encoding="utf-8", timeout=15)
            self.assertEqual(run.returncode, 2)
            self.assertEqual(marker.read_text(), "keep")
            self.assertEqual(len(list(Path(directory).iterdir())), 1)


if __name__ == "__main__":
    unittest.main()
