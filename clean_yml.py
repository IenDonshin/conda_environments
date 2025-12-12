import re
import sys
from typing import List, Tuple

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


def _detect_bom(raw: bytes) -> str | None:
    """Detect simple BOM encodings (utf-16 variants we care about)."""
    if raw.startswith(b"\xff\xfe"):
        return "utf-16-le"
    if raw.startswith(b"\xfe\xff"):
        return "utf-16-be"
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    return None


def load_lines(input_file: str) -> Tuple[List[str], str]:
    """Read file content with a small encoding fallback list."""
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
            print(f"Warning: {input_file} could not be decoded as UTF-8/GBK (last error: {last_error}).")
            print("Using latin1 as a last resort; please verify the cleaned file manually.")
        decoded = raw.decode("latin1")
        used_encoding = "latin1"
    else:
        used_encoding = bom_encoding or (ENCODING_CANDIDATES[0] if last_error is None else "utf-8")

    if decoded.startswith("\ufeff"):
        decoded = decoded[1:]

    return decoded.splitlines(keepends=True), used_encoding


def is_platform_specific(line: str) -> bool:
    """Return True if the line looks platform-specific and should be dropped."""
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


def clean_yml(input_file: str, output_file: str) -> None:
    """Remove platform-specific dependencies and emit UTF-8 output."""
    lines, _ = load_lines(input_file)

    cleaned_lines: List[str] = []
    in_pip_block = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("pip:"):
            in_pip_block = True
            cleaned_lines.append(line)
            continue

        if in_pip_block:
            cleaned_lines.append(line)
            continue

        if is_platform_specific(line):
            continue

        cleaned_lines.append(line)

    with open(output_file, "w", encoding="utf-8", newline="") as handle:
        handle.writelines(cleaned_lines)

    print(f"Cross-platform environment yml saved to {output_file}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python clean_yml.py <input.yml> <output.yml>")
        print("Example: python clean_yml.py sp.yml sp_clean.yml")
    else:
        clean_yml(sys.argv[1], sys.argv[2])
