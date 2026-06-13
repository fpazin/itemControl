from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path


def build_release(source: Path, version: str, output: Path) -> Path:
    source = source.resolve()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    work_dir = output.parent / "pyinstaller-work"
    work_dir.mkdir(parents=True, exist_ok=True)
    entrypoint = work_dir / "release_entry.py"
    entrypoint.write_text(
        "\n".join(
            [
                "import sys",
                f'VERSION = "{version}"',
                "if '--version' in sys.argv:",
                "    print(f'ItemControl {VERSION}')",
                "    raise SystemExit(0)",
                "from itemcontrol.ui import main",
                "raise SystemExit(main())",
                "",
            ]
        ),
        encoding="utf-8",
    )

    artifact_name = f"ItemControl-v{version}-windows-x64"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name",
        artifact_name,
        "--paths",
        str(source / "src"),
        "--distpath",
        str(output),
        "--workpath",
        str(work_dir / "build"),
        "--specpath",
        str(work_dir),
    ]
    if importlib.util.find_spec("sqlcipher3") is not None:
        command.extend(["--collect-all", "sqlcipher3"])
    command.append(str(entrypoint))
    subprocess.run(command, check=True)
    return output / f"{artifact_name}.exe"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, default=Path("dist"))
    args = parser.parse_args()
    artifact = build_release(args.source, args.version, args.output)
    print(artifact)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
