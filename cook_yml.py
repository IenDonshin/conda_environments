import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Platform-specific or low-level packages that should not be pinned.
PLATFORM_KEYWORDS: List[str] = [
    "linux-64",
    "ld_impl",
    "libgcc",
    "libgomp",
    "libstdc",
    "libcxx",
    "_libgcc_mutex",
    "_openmp_mutex",
    "glibc",
    "win-64",
    "vc",
    "vs2015",
    "ucrt",
    "mingw",
    "hdf5",
    "zlib",
    "bzip2",
    "expat",
    "ffi",
    "uuid",
    "xz",
    "tk",
    "tcl",
    "openssl",
    "sqlite",
    "readline",
    "ncurses",
    "gfortran",
    "mkl",
]

# Keep these lines even if they contain '='.
CORE_EXCEPTIONS = ["python=", "pip=", "pip:", "channels:", "name:"]

# Encoding attempts in order; latin1 is last-resort to avoid decode crashes.
ENCODING_CANDIDATES: Tuple[str, ...] = ("utf-8", "utf-8-sig", "gbk", "cp936")

VERSION_OPERATORS = ("==", ">=", "<=", "~=", "!=", "=", ">", "<")


def _detect_bom(raw: bytes) -> str | None:
    if raw.startswith(b"\xff\xfe"):
        return "utf-16-le"
    if raw.startswith(b"\xfe\xff"):
        return "utf-16-be"
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    return None


def load_lines(input_file: str) -> Tuple[List[str], str]:
    with open(input_file, "rb") as handle:
        raw = handle.read()

    bom_encoding = _detect_bom(raw)
    if bom_encoding:
        decoded = raw.decode(bom_encoding)
    else:
        decoded = None

    last_error: Exception | None = None

    if decoded is None:
        for encoding in ENCODING_CANDIDATES:
            try:
                decoded = raw.decode(encoding)
                last_error = None
                break
            except UnicodeDecodeError as exc:
                last_error = exc

    if decoded is None:
        if last_error is not None:
            print(
                f"Warning: {input_file} could not be decoded as UTF-8/GBK (last error: {last_error})."
            )
            print("Using latin1 as a last resort; please verify the cleaned file manually.")
        decoded = raw.decode("latin1")
        used_encoding = "latin1"
    else:
        used_encoding = bom_encoding or (ENCODING_CANDIDATES[0] if last_error is None else "utf-8")

    if decoded.startswith("\ufeff"):
        decoded = decoded[1:]

    return decoded.splitlines(keepends=True), used_encoding


def is_platform_specific(line: str) -> bool:
    stripped_lower = line.strip().lower()

    if not stripped_lower or stripped_lower.startswith("#"):
        return False

    if any(stripped_lower.startswith(exc) for exc in CORE_EXCEPTIONS):
        return False

    if "=" in stripped_lower:
        if any(keyword in stripped_lower for keyword in PLATFORM_KEYWORDS):
            return True
        if re.search(r"=\w+(\d+)", stripped_lower) and stripped_lower.startswith("- "):
            return True

    return False


def spec_has_version(spec: str) -> bool:
    if " @ " in spec:
        return True
    return any(op in spec for op in VERSION_OPERATORS)


def extract_env_name(lines: List[str]) -> str:
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.lower().startswith("name:"):
            name = stripped.split(":", 1)[1].strip()
            if name:
                return name
    raise ValueError("Missing or empty 'name:' in the yml file.")


def parse_dependencies(lines: List[str]) -> Tuple[List[str], List[str]]:
    conda_deps: List[str] = []
    pip_deps: List[str] = []
    in_deps = False
    in_pip = False

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if line.lstrip() == line and not line.startswith("-"):
            if stripped.startswith("dependencies:"):
                in_deps = True
                in_pip = False
            else:
                in_deps = False
                in_pip = False
            continue

        if not in_deps:
            continue

        if not stripped.startswith("- "):
            continue

        item = stripped[2:].strip()
        indent = len(line) - len(line.lstrip(" "))

        if item == "pip:":
            in_pip = True
            continue

        if in_pip and indent <= 2:
            in_pip = False

        if in_pip:
            pip_deps.append(item)
        else:
            conda_deps.append(item)

    return conda_deps, pip_deps


def dep_name(spec: str) -> str:
    for marker in (" @ ", "==", ">=", "<=", "~=", "!=", "=", ">", "<"):
        if marker in spec:
            return spec.split(marker, 1)[0].strip()
    return spec.strip()


def _split_line_ending(line: str) -> Tuple[str, str]:
    trimmed = line.rstrip("\r\n")
    return trimmed, line[len(trimmed) :]


def strip_version_spec(spec: str) -> str:
    if " @ " in spec:
        return spec.strip()
    for op in VERSION_OPERATORS:
        idx = spec.find(op)
        if idx != -1:
            return spec[:idx].strip()
    return spec.strip()


def strip_versions_from_lines(lines: List[str]) -> List[str]:
    cleaned_lines: List[str] = []
    in_deps = False
    in_pip = False
    pip_indent: int | None = None

    for line in lines:
        stripped = line.strip()

        if line.lstrip() == line and not line.startswith("-"):
            if stripped.startswith("dependencies:"):
                in_deps = True
                in_pip = False
            else:
                in_deps = False
                in_pip = False
            cleaned_lines.append(line)
            continue

        if not in_deps or not stripped.startswith("- "):
            cleaned_lines.append(line)
            continue

        item = stripped[2:].strip()
        indent = len(line) - len(line.lstrip(" "))
        line_body, line_ending = _split_line_ending(line)
        leading = line_body[: indent]

        if item == "pip:":
            in_pip = True
            pip_indent = indent
            cleaned_lines.append(line)
            continue

        if in_pip:
            if pip_indent is not None and indent <= pip_indent:
                in_pip = False
                pip_indent = None
            else:
                new_item = strip_version_spec(item)
                cleaned_lines.append(f"{leading}- {new_item}{line_ending}")
                continue

        new_item = strip_version_spec(item)
        cleaned_lines.append(f"{leading}- {new_item}{line_ending}")

    return cleaned_lines


def build_dep_map(deps: List[str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for dep in deps:
        name = dep_name(dep)
        if name:
            mapping[name] = dep
    return mapping


def print_changes(label: str, old_deps: List[str], new_deps: List[str]) -> None:
    old_map = build_dep_map(old_deps)
    new_map = build_dep_map(new_deps)
    added = sorted(set(new_map) - set(old_map))
    removed = sorted(set(old_map) - set(new_map))
    changed = sorted(
        name for name in (set(new_map) & set(old_map)) if old_map[name] != new_map[name]
    )

    if not (added or removed or changed):
        print(f"{label}: no changes.")
        return

    print(f"{label} changes:")
    if added:
        print(f"  added ({len(added)}): {', '.join(added)}")
    if removed:
        print(f"  removed ({len(removed)}): {', '.join(removed)}")
    if changed:
        print(f"  updated ({len(changed)}):")
        for name in changed:
            print(f"    {name}: {old_map[name]} -> {new_map[name]}")


def run_conda_export(conda_cmd: str, env_name: str) -> List[str]:
    try:
        result = subprocess.run(
            [conda_cmd, "env", "export", "--no-builds", "--name", env_name],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        print(f"Error: conda executable '{conda_cmd}' not found.")
        sys.exit(1)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip()
        if stderr:
            print(stderr)
        print(f"Error: failed to export conda environment '{env_name}'.")
        sys.exit(exc.returncode or 1)

    return result.stdout.splitlines(keepends=True)


def clean_lines(lines: List[str], drop_prefix: bool) -> List[str]:
    cleaned_lines: List[str] = []
    in_pip_block = False
    pip_indent: int | None = None

    for line in lines:
        stripped = line.strip()
        if drop_prefix and stripped.startswith("prefix:"):
            continue

        if stripped == "pip:" or stripped == "- pip:":
            in_pip_block = True
            pip_indent = len(line) - len(line.lstrip(" "))
            cleaned_lines.append(line)
            continue

        if in_pip_block:
            current_indent = len(line) - len(line.lstrip(" "))
            if stripped.startswith("- ") and pip_indent is not None and current_indent <= pip_indent:
                in_pip_block = False
                pip_indent = None
            else:
                cleaned_lines.append(line)
                continue

        if is_platform_specific(line):
            continue

        cleaned_lines.append(line)

    return cleaned_lines


def write_output(path: Path, lines: List[str]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.writelines(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update or clean a conda environment yml file."
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Path to the environment yml file.",
    )
    parser.add_argument(
        "--mode",
        choices=("update", "clean"),
        default="update",
        help="update: refresh from conda env; clean: remove platform-specific deps.",
    )
    parser.add_argument(
        "--with-versions",
        action="store_true",
        help="Keep versions in the output yml.",
    )
    parser.add_argument(
        "--conda",
        default="conda",
        help="Conda executable to use (default: conda).",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file not found: {input_path}")
        sys.exit(1)

    input_lines, _ = load_lines(str(input_path))

    if args.mode == "clean":
        cleaned_lines = clean_lines(input_lines, drop_prefix=False)
        if not args.with_versions:
            cleaned_lines = strip_versions_from_lines(cleaned_lines)
        write_output(input_path, cleaned_lines)
        print(f"Cleaned environment yml saved to {input_path}")
        return

    try:
        env_name = extract_env_name(input_lines)
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    export_lines = run_conda_export(args.conda, env_name)
    cleaned_lines = clean_lines(export_lines, drop_prefix=True)
    if not args.with_versions:
        cleaned_lines = strip_versions_from_lines(cleaned_lines)

    write_output(input_path, cleaned_lines)

    compare_input_lines = input_lines
    if not args.with_versions:
        compare_input_lines = strip_versions_from_lines(input_lines)

    old_conda, old_pip = parse_dependencies(compare_input_lines)
    new_conda, new_pip = parse_dependencies(cleaned_lines)

    print(f"Environment: {env_name}")
    print_changes("Conda dependencies", old_conda, new_conda)
    print_changes("Pip dependencies", old_pip, new_pip)
    print(f"Updated environment yml saved to {input_path}")


if __name__ == "__main__":
    main()
