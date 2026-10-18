"""Render current results; semantic notes must match response hashes."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name("render_regression_report.py")),run_name="__main__")
