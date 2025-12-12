import sys
import re

# 1. 扩展关键字列表：涵盖常见的Linux/macOS底层库、编译器和构建标识符
PLATFORM_KEYWORDS = [
    # Linux-specific (Common in conda-forge exports)
    "linux-64", "ld_impl", "libgcc", "libgomp", "libstdc", "libcxx",
    "_libgcc_mutex", "_openmp_mutex", "glibc", 
    # Windows/MSVC-specific (Common in Windows exports)
    "win-64", "vc", "vs2015", "ucrt", "mingw", 
    # General build identifiers (often unnecessary for cross-platform)
    "hdf5", "zlib", "bzip2", "expat", "ffi", "uuid", "xz", "tk", "tcl",
    "openssl", "sqlite", "readline", "ncurses", "gfortran", "mkl"
]

# 2. 定义例外：这些是核心组件或跨平台库，应保留版本号或包名
#    但我们不希望它们被基于关键词的过滤误删。
#    注意：对于 python, pip 可以在后续逻辑中保留。
CORE_EXCEPTIONS = ["python=", "pip=", "channels:", "name:"]


def is_platform_specific(line):
    """
    检查一行是否包含平台特有的底层依赖。
    如果包含'='，并且不属于核心例外，则视为底层依赖。
    """
    stripped_lower = line.strip().lower()

    # 1. 检查是否为注释或空行
    if not stripped_lower or stripped_lower.startswith("#"):
        return False
        
    # 2. 检查是否为核心例外
    if any(stripped_lower.startswith(exc) for exc in CORE_EXCEPTIONS):
        return False

    # 3. 检查是否包含精确版本号或构建字符串 (这是底层依赖的特征)
    #    且包含平台关键字
    if "=" in stripped_lower:
        # 如果包含等于号，并且包含任何一个平台关键词，则移除
        if any(keyword in stripped_lower for keyword in PLATFORM_KEYWORDS):
            return True
        
        # 额外规则：对于非核心包，如果带有精确的构建字符串（例如 package=1.0=py39_0），也视为底层依赖
        if re.search(r"=\w+(\d+)", stripped_lower):
            # 例外：保留 pip 安装的包，虽然它们可能包含=
            if stripped_lower.startswith("- "):
                 # 我们只处理 conda 依赖块
                 return False

    return False


def clean_yml(input_file, output_file):
    """
    清理 Conda YAML 文件，移除平台特定的底层依赖。
    """
    try:
        # 优先使用 UTF-8 编码读取
        with open(input_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        # 如果失败，尝试 latin1 或您常用的编码 (例如 gbk, 但 utf-8 更推荐)
        try:
            with open(input_file, "r", encoding="latin1") as f:
                lines = f.readlines()
        except Exception:
            print(f"Error: Could not decode file {input_file} with utf-8 or latin1.")
            return

    cleaned_lines = []
    in_pip_block = False
    
    for line in lines:
        stripped = line.strip()
        
        # 检查是否进入/离开 pip 块
        if stripped.startswith("pip:"):
            in_pip_block = True
            cleaned_lines.append(line)
            continue
        
        # 退出 pip 块的逻辑 (通常是缩进变化，但此处简化为遇到新顶级块)
        if in_pip_block and not stripped.startswith("- "):
            # 如果缩进变少或遇到非'- '开头的行（且不为空），可以视为退出pip块，但为了安全起见，先不处理
            pass

        # 核心逻辑：
        if in_pip_block:
            # 在 pip 块中，我们通常保留所有内容 (包括版本号)
            # 因为 pip 包通常具有跨平台性，或者版本号是项目严格要求的。
            cleaned_lines.append(line)
        elif is_platform_specific(line):
            # 在 Conda 依赖块中，如果识别为平台特定，则跳过
            continue
        else:
            # 保留所有其他行 (name, channels, comments, 以及未被过滤的包)
            cleaned_lines.append(line)

    with open(output_file, "w", encoding="utf-8") as f:
        f.writelines(cleaned_lines)

    print(f"\n✅ Cross-platform environment yml saved to {output_file}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python clean_yml.py <input.yml> <output.yml>")
        print("Example: python clean_yml.py sp.yml sp_clean.yml")
    else:
        # 添加 UTF-8 编码处理
        # 在 Windows 上，可能需要手动将命令行编码设为 UTF-8
        clean_yml(sys.argv[1], sys.argv[2])