# Introduction

## Conda Environment

### computational_social_science

all package is run on cpu (intel or amd)

### deep_learning

install the cuda 12.9 to runing pytorch on nvidia 50 series gpu
machine learning and deep learning

### social_psychology

design and run otree experiment

## How to Use

### Export the conda environments

#### Windows

```bash
conda env export --no-builds | findstr /v "prefix" > environment_name.yml
```

#### MacOS/Linux

```bash
conda env export --no-builds | grep -v "prefix" > environment_name.yml
```

### Make .yml files usable across platfoms

```bash
python cook_yml.py --mode clean --input environments_name.yml
```

Optional keep versions:

```bash
python cook_yml.py --mode clean --input environments_name.yml --with-versions
```

### Update an existing .yml from the current conda environment

```bash
python cook_yml.py --mode update --input environment_name.yml
```

Optional keep versions:

```bash
python cook_yml.py --mode update --input environment_name.yml --with-versions
```

### Build the conda environments based on .yml in another device

```bash
conda env create -f environment_name.yml
```

### Sync a conda environment from a .yml on another device

```bash
python sync_env.py --input path\to\environment_name.yml
```
