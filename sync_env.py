import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import cook_yml


def run_conda_command(conda_cmd: str, args: List[str], error_label: str) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(
            [conda_cmd, *args],
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
        print(f"Error: {error_label}.")
        sys.exit(exc.returncode or 1)

    return result


def list_env_paths(conda_cmd: str) -> List[Path]:
    result = run_conda_command(conda_cmd, ["env", "list", "--json"], "failed to list conda environments")
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        print(f"Error: failed to parse conda env list output ({exc}).")
        sys.exit(1)

    envs = data.get("envs", [])
    return [Path(path) for path in envs if path]


def env_exists(env_name: str, env_paths: List[Path]) -> bool:
    return any(path.name == env_name for path in env_paths)


def diff_expected_vs_actual(
    expected_deps: List[str], actual_deps: List[str]
) -> Tuple[Dict[str, str], Dict[str, str], List[str], List[str], List[str]]:
    expected_map = cook_yml.build_dep_map(expected_deps)
    actual_map = cook_yml.build_dep_map(actual_deps)
    missing = sorted(name for name in expected_map if name not in actual_map)
    mismatched = sorted(
        name
        for name in expected_map
        if name in actual_map
        and cook_yml.spec_has_version(expected_map[name])
        and expected_map[name] != actual_map[name]
    )
    extra = sorted(name for name in actual_map if name not in expected_map)
    return expected_map, actual_map, missing, mismatched, extra


def print_check_result(
    label: str,
    expected_map: Dict[str, str],
    actual_map: Dict[str, str],
    missing: List[str],
    mismatched: List[str],
    extra: List[str],
) -> None:
    if not (missing or mismatched or extra):
        print(f"{label}: up to date.")
        return

    if missing:
        print(f"{label} missing ({len(missing)}): {', '.join(missing)}")
    if mismatched:
        print(f"{label} version mismatches ({len(mismatched)}):")
        for name in mismatched:
            print(f"  {name}: expected {expected_map[name]}, current {actual_map[name]}")
    if extra:
        print(f"{label} extra ({len(extra)}): {', '.join(extra)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync a conda environment with the given yml file."
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Path to the environment yml file.",
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

    input_lines, _ = cook_yml.load_lines(str(input_path))
    try:
        env_name = cook_yml.extract_env_name(input_lines)
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    env_paths = list_env_paths(args.conda)

    if not env_exists(env_name, env_paths):
        print(f"Environment '{env_name}' not found. Creating from {input_path}.")
        run_conda_command(
            args.conda,
            ["env", "create", "-f", str(input_path)],
            f"failed to create conda environment '{env_name}'",
        )
        print(f"Environment '{env_name}' created.")
        return

    export_lines = cook_yml.run_conda_export(args.conda, env_name)
    expected_conda, expected_pip = cook_yml.parse_dependencies(input_lines)
    actual_conda, actual_pip = cook_yml.parse_dependencies(export_lines)

    (
        expected_conda_map,
        actual_conda_map,
        missing_conda,
        mismatched_conda,
        extra_conda,
    ) = diff_expected_vs_actual(expected_conda, actual_conda)
    (
        expected_pip_map,
        actual_pip_map,
        missing_pip,
        mismatched_pip,
        extra_pip,
    ) = diff_expected_vs_actual(expected_pip, actual_pip)

    print(f"Environment: {env_name}")
    print_check_result(
        "Conda dependencies",
        expected_conda_map,
        actual_conda_map,
        missing_conda,
        mismatched_conda,
        extra_conda,
    )
    print_check_result(
        "Pip dependencies",
        expected_pip_map,
        actual_pip_map,
        missing_pip,
        mismatched_pip,
        extra_pip,
    )

    if not (missing_conda or mismatched_conda or missing_pip or mismatched_pip):
        print("No update needed.")
        return

    print(f"Updating environment '{env_name}' from {input_path}.")
    run_conda_command(
        args.conda,
        ["env", "update", "--name", env_name, "--file", str(input_path)],
        f"failed to update conda environment '{env_name}'",
    )
    print(f"Environment '{env_name}' updated.")


if __name__ == "__main__":
    main()
