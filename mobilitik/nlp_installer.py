from __future__ import annotations

import subprocess
import sys


CPU_TORCH_INDEX = "https://download.pytorch.org/whl/cpu"
TRANSFORMERS_SPEC = "transformers>=4.46,<5"


def install_commands(python_executable: str | None = None) -> list[list[str]]:
    python = python_executable or sys.executable
    return [
        [
            python,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "torch",
            "--index-url",
            CPU_TORCH_INDEX,
        ],
        [
            python,
            "-m",
            "pip",
            "install",
            "--upgrade",
            TRANSFORMERS_SPEC,
        ],
    ]


def main():
    print("NLP_INSTALL_STATUS CPU için PyTorch kuruluyor…", flush=True)
    for index, command in enumerate(install_commands(), start=1):
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            print(f"NLP_INSTALL_ERROR Kurulum adımı {index} başarısız oldu.", flush=True)
            raise SystemExit(result.returncode)
        if index == 1:
            print("NLP_INSTALL_STATUS PyTorch hazır. Transformers kuruluyor…", flush=True)
    print("NLP_INSTALL_DONE NLP bileşenleri hazır.", flush=True)


if __name__ == "__main__":
    main()
