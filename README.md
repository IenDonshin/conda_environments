# Command Lines

## Export the conda environments

### Windows 
```
conda env export --no-builds | findstr /v "prefix" > environment_name.yml
```
### MacOS/Linux
```
conda env export --no-builds | grep -v "prefix" > environment_name.yml
```
### Make .yml files usable across platfoms(optional)
```
python ../clean_yml.py environments_name.yml environments_name_cleaned.yml
```

## Build the conda environments based on .yml in another device
```
conda env create -f environment_name.yml
```

# Introduction

## computational_social_science
all package is run on cpu (intel or amd)


## deep_learning
install the cuda 12.9 to runing pytorch on nvidia 50 series gpu
machine learning and deep learning

## social psychology
design and run otree experiment


