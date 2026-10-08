import sys
from pathlib import Path
import tempfile
import unittest
import importlib.util

AVAILABLE = all(importlib.util.find_spec(m) for m in ("numpy", "matplotlib", "seaborn"))
if AVAILABLE:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from figure_tools import paper_style, export_figure, inspect_canvas, note


@unittest.skipUnless(AVAILABLE, "Plotting packages are not installed; base tools remain usable")
class FigureChecks(unittest.TestCase):
    def test_export_preserves_data_and_restores_style(self):
        before = matplotlib.rcParams["font.size"]
        with tempfile.TemporaryDirectory(prefix="mathorcup_figure_") as folder:
            with paper_style(font="DejaVu Sans", size=13):
                fig, ax = plt.subplots(figsize=(5, 3), layout="constrained")
                line, = ax.plot([0, 1, 2], [0, 3, -1])
                original = line.get_xydata().copy()
                note(ax, "observed", (1, 3), (12, -20))
                files = export_figure(fig, Path(folder) / "same_data")
                np.testing.assert_array_equal(line.get_xydata(), original)
                self.assertTrue(all(f.stat().st_size > 100 for f in files))
                self.assertIn("<text", (Path(folder) / "same_data.svg").read_text(encoding="utf-8"))
                plt.close(fig)
        self.assertEqual(matplotlib.rcParams["font.size"], before)

    def test_existing_exports_are_preserved(self):
        with tempfile.TemporaryDirectory(prefix="mathorcup_figure_") as folder:
            target = Path(folder) / "important.pdf"
            target.write_bytes(b"existing evidence")
            fig, ax = plt.subplots()
            try:
                with self.assertRaises(FileExistsError):
                    export_figure(fig, Path(folder) / "important")
                self.assertEqual(target.read_bytes(), b"existing evidence")
            finally:
                plt.close(fig)

    def test_text_outside_canvas_is_reported(self):
        fig, ax = plt.subplots()
        fig.text(1.2, .5, "outside")
        try:
            self.assertTrue(any("outside" in s for s in inspect_canvas(fig)))
        finally:
            plt.close(fig)


if __name__ == "__main__":
    unittest.main()
