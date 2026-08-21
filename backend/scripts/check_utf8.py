from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOTS = (ROOT / "frontend", ROOT / "backend")
TEXT_SUFFIXES = {".css", ".html", ".js", ".json", ".md", ".py", ".ts", ".vue", ".yaml", ".yml"}
SKIP_PARTS = {".nuxt", ".pytest_cache", "__pycache__", "node_modules"}
COMMON_MOJIBAKE = ("\u00c3", "\u00c2", "\u00e2\u20ac", "\u00f0\u0178")


def problems(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        return [f"不是有效 UTF-8：{error}"]

    issues: list[str] = []
    if "\ufffd" in text:
        issues.append("包含 Unicode replacement character U+FFFD")
    if any("\ue000" <= character <= "\uf8ff" for character in text):
        issues.append("包含常見於 Big5/UTF-8 轉碼錯誤的 Private Use 字元")
    if any(marker in text for marker in COMMON_MOJIBAKE):
        issues.append("包含常見 UTF-8 mojibake 字串")
    return issues


def main() -> int:
    failures: list[str] = []
    for source_root in SOURCE_ROOTS:
        for directory, child_directories, filenames in os.walk(source_root):
            child_directories[:] = [name for name in child_directories if name not in SKIP_PARTS]
            for filename in filenames:
                path = Path(directory) / filename
                if path.suffix.lower() not in TEXT_SUFFIXES:
                    continue
                for issue in problems(path):
                    failures.append(f"{path.relative_to(ROOT)}：{issue}")

    if failures:
        print("UTF-8 check failed:")
        print("\n".join(f"- {failure}" for failure in failures))
        return 1
    print("UTF-8 check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
