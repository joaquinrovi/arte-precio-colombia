from pathlib import Path
import tomllib

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_config(path: str | Path | None = None) -> dict:
    config_path = Path(path) if path else PROJECT_ROOT / "configs/default.toml"
    with config_path.open("rb") as handle:
        return tomllib.load(handle)


def project_path(value: str | Path) -> Path:
    value = Path(value)
    return value if value.is_absolute() else PROJECT_ROOT / value
