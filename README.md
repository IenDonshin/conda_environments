# How to export the conda environments

## Windows 
```
conda env export --no-builds | findstr /v "prefix" > environment_name.yml
```
## MacOS/Linux
```
conda env export --no-builds | grep -v "prefix" > environment_name.yml
```
## Make .yml files usable across platfoms(optional)
```
python ../clean_yml.py environments_name.yml environments_name_cleaned.yml
```

# How to build the conda environments based on .yml
```
conda env create -f environment_name.yml
```
