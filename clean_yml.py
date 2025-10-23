import sys

platform_keywords = [
    "win", "vc", "vs2015", "ucrt", "_openmp", "libgcc", "libgomp", "mingw"
]

def is_platform_specific(package_line):
    line = package_line.lower()
    if not line.strip() or line.strip().startswith("#"):
        return False
    return any(keyword in line for keyword in platform_keywords)

def clean_yml(input_file, output_file):
    with open(input_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    cleaned_lines = []
    pip_block = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("pip:"):
            pip_block = True
            cleaned_lines.append(line)
            continue
        if pip_block:
            cleaned_lines.append(line)
            continue
        if is_platform_specific(line):
            continue
        cleaned_lines.append(line)

    with open(output_file, "w", encoding="utf-8") as f:
        f.writelines(cleaned_lines)

    print(f"Cross-platform environment yml saved to {output_file}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python clean_conda_yml.py <input.yml> <output.yml>")
    else:
        clean_yml(sys.argv[1], sys.argv[2])
