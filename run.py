"""Permite usar el proyecto sin instalación editable en entornos sin conexión."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from arte_precio.__main__ import main  # noqa: E402

if __name__ == "__main__":
    main()
