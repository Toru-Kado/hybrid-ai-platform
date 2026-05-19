#!/usr/bin/env python3
"""Package Lambda layer with application dependencies.

Installs project dependencies into the Lambda layer directory structure
expected by CDK (infra/lambda-layer/python/). This script should be run
before CDK synth/deploy for the serverless stack.

Usage:
    python scripts/package-lambda.py [--output-dir infra/lambda-layer]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "infra" / "lambda-layer"


def package_layer(output_dir: Path) -> None:
    """Install dependencies into the Lambda layer structure."""
    python_dir = output_dir / "python"

    # Clean existing layer content
    if python_dir.exists():
        shutil.rmtree(python_dir)
    python_dir.mkdir(parents=True, exist_ok=True)

    # Install the app package and its dependencies
    print(f"Installing dependencies to {python_dir}")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--target",
            str(python_dir),
            "--platform",
            "manylinux2014_x86_64",
            "--implementation",
            "cp",
            "--python-version",
            "3.12",
            "--only-binary=:all:",
            "--upgrade",
            "boto3",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    # Copy the app package into the layer
    app_src = PROJECT_ROOT / "app"
    app_dest = python_dir / "app"
    if app_dest.exists():
        shutil.rmtree(app_dest)

    shutil.copytree(
        app_src,
        app_dest,
        ignore=shutil.ignore_patterns(
            "__pycache__",
            "*.pyc",
            "*.pyo",
            ".pytest_cache",
        ),
    )

    # Remove unnecessary files to reduce layer size
    for pattern in ["*.dist-info", "*.egg-info", "__pycache__"]:
        for path in python_dir.rglob(pattern):
            if path.is_dir():
                shutil.rmtree(path)

    # Report size
    total_size = sum(f.stat().st_size for f in python_dir.rglob("*") if f.is_file())
    print(f"Layer size: {total_size / 1024 / 1024:.1f} MB")
    if total_size > 250 * 1024 * 1024:
        print("WARNING: Layer exceeds 250 MB limit!", file=sys.stderr)
        sys.exit(1)

    print("Lambda layer packaged successfully.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Package Lambda layer")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory for the layer",
    )
    args = parser.parse_args()

    try:
        package_layer(args.output_dir)
    except subprocess.CalledProcessError as exc:
        print(f"pip install failed: {exc.stderr}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
