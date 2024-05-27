# penai

Welcome to the penai project.

## Getting Started

Clone the repository and run 

```shell
git submodule update --init --recursive
```

to also pull the git submodules.

You can install the dependencies with

```shell
poetry install --with dev
```


For pulling data or interacting with VLM providers, you will need secrets that are to be
stored in the git-ignored file `config_local.json`. Please contact the project maintainers
for the file's contents.

After adding the secrets and installing the dependencies, every script and notebook
can be executed on any machine. The first execution will pull missing data from the
remote storage, and hence might take a while, depending on what data is missing.
