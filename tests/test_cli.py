from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from project_skeleton.cli import main


def test_main_prints_hello(capsys):
    main()
    captured = capsys.readouterr()
    assert captured.out == "Hello, world!\n"
