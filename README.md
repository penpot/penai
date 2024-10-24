# Generative AI Capabilities for Penpot

We explore applications of generative AI for the purpose of creating an assistant for the graphic design space, 
particularly in the context of the open-source design software [Penpot](https://penpot.app). 
As initial assistance functions, we consider the generation of variations of vector shapes, 
improving the structure and semantic meta-data of design documents, 
and the transfer of design styles between different shapes. 

While some of the capabilities are specific to Penpot, core functionality is largely general, 
building on open standards such as SVG.

<!-- generated with `markdown-toc -i README.md` -->
***Table of Contents***

<!-- toc -->

- [Use Cases](#use-cases)
    * [Generating Variations of Vector Shapes](#generating-variations-of-vector-shapes)
    * [Variation Style Transfer](#variation-style-transfer)
    * [Naming Shapes Semantically](#naming-shapes-semantically)
    * [Hierarchy Inference](#hierarchy-inference)
- [Development Guide](#development-guide)
    * [Environment Setup](#environment-setup)
      * [Python Virtual Environment](#python-virtual-environment)
      * [Docker Setup](#docker-setup)
      * [Codespaces](#codespaces)
      * [Secrets, Configuration and Credentials](#secrets-configuration-and-credentials)
    * [Documentation](#documentation)
    * [Working with PenAI](#working-with-penai)
- [Troubleshooting](#troubleshooting)

<!-- tocstop -->

## Use Cases

Our use cases build upon state-of-the-art large language models/vision language
models.
Particularly Anthropic's *Claude 3.5 Sonnet* model proved to have a solid
understanding of vector
graphics and is therefore the model of choice for most our use cases.

### Generating Variations of Vector Shapes

As an inspirational starting point, we consider the problem of generating
variations of a given shape.

![shape variations](resources/images/use_case_variations.png)

In order to facilitate the generation of variations, it can be very helpful to
refactor the original
SVG representation in order to make shapes and cutouts more explicit, avoiding
less explicit SVG path
representations whenever possible.

Furthermore, we typically want to limit the scope of what is varied. For
instance, we might want to
vary only foreground colours or certain inner shapes.
Furthermore, we typically have constraints that shall guide the generation
process, e.g. to ensure
that the generated shapes remain close to the original shape, maintaining the
semantics, or to ensure
that colour variations respect the colour palette of the design project.

* Batch job:
    * Apply variation generation to registered
      shapes: [scripts/batch_svg_variations.py](scripts/batch_svg_variations.py)
    * Inspection of results: [scripts/web_server.py](scripts/web_server.py)
* Notebooks:
    * Variation generation for an
      icon/logo: [notebooks/svg_variations_icon.ipynb](notebooks/svg_variations_icon.ipynb)
    * Variation generation for a UI
      element: [notebooks/svg_variations_ui_widget.ipynb](notebooks/svg_variations_ui_widget.ipynb)

### Variation Style Transfer

In user interface design, the same principles are often applied to a wide
variety of
UI elements and other shapes, e.g. in order to indicate different UI states such
as
'hover', 'focus', or 'disabled'.

Given a template indicating how a given UI element is transformed, the task is
to apply
the same transformation to a different shape:

![shape variation style transfer](resources/images/use_case_variation_transfer.png)

Here are some results we obtained with Claude 3.5, showing the presented
template
and subsequently the applied transformation:

![shape variation style transfer/results](resources/videos/use_case_variation_transfer.gif)

* Batch job:
    * Apply variation transfer to registered
      shapes: [scripts/batch_variation_transfer.py](scripts/batch_svg_variation_transfer.py)
    * Inspection of results: [scripts/web_server.py](scripts/web_server.py)
* Notebooks:
    * Variation transfer for UI
      elements: [notebooks/svg_variation_transfer_ui_widget.ipynb](notebooks/svg_variation_transfer_ui_widget.ipynb)

### Naming Shapes Semantically (Work in Progress)

Associating shapes with meaningful names can be essential for discoverability,
especially
in large design projects.
We thus consider the problem of finding meaningful names for an existing
hierarchy of shapes:

![shape naming](resources/images/use_case_shape_naming.png)

### Hierarchy Inference

In larger projects, shapes may be grouped suboptimally.
We consider the problem of jointly inferring an updated hierarchy and naming the
shapes contained:

![hierarchy inference](resources/images/use_case_hierarchy_inference.png)

Notebooks:
* Hierarchy inference for an example frame: [notebooks/hierarchy_inference.ipynb](notebooks/hierarchy_inference.ipynb) 

## Development Guide

### Environment Setup

Clone the repository and run

```shell
git submodule update --init --recursive
```

to also pull the git submodules.

### Secrets, Configuration and Credentials

For pulling data or interacting with VLM providers, you will need secrets that
are to be
stored in the git-ignored file `config_local.json`. Please contact the project
maintainers
for the file's contents.

After adding the secrets and installing the dependencies, every script and
notebook
can be executed on any machine. The first execution will pull missing data from
the
remote storage, and hence might take a while, depending on what data is missing.

### Python Virtual Environment

Create a Python 3.11 environment and install the dependencies with

```shell
poetry install --with dev
```

You might have to run `jupyter trust ...` for some notebooks to be able to
display SVG content.

### Docker Setup

Build the docker image with

```shell
docker build -t penai .
```

and run it with the repository mounted as a volume:

```shell
docker run -it --shm-size=1g -p 8888:8888 --rm -v "$(pwd)":/workspaces/penai penai
```

(The `shm-size` option is necessary for google-webdriver to have enough space
for
rendering things.)

You can also just run `bash docker_build_and_run.sh`, which will do both things
for you.

To make a quick check if everything is working, you can run the `pytest`
command from the container. If you want to run jupyter in the container, you
should start the container with port forwarding
(e.g. adding `-p 8888:8888` to the `docker run` command)
and then start jupyter e.g. with

```shell
jupyter notebook --ip 0.0.0.0 --port 8888 --allow-root --no-browser
```

(the `--ip` option is needed to prevent jupyter from only listening to localhost
and the `--allow-root` option is because the container user is root.)

The Jupyter Notebook server can now be accessed via [localhost:8888](http://localhost:8888)
in the host environment. The token required for authentication can be found in the console logging
from the Jupyter instance within the container.

Note: When using the Windows subsystem for Linux (WSL), you might need to adjust
the path for the
volume.

### Codespaces

The fastest way to get running without any installation is to use GitHub
Codespaces. The repository has been set up to provide a fully functioning
Codespace with everything installed out of the box. You can either
paste your `config_local.json` file there or pass the secrets as env vars
when the codespace is created by using the `New with options` button:

<img src="images/codespaces.png" align="center" width="70%" style="margin: auto">

### Documentation

Run the following command to build the documentation:

```
poetry run poe doc-build
```

Note: This will require a prior setup of the local configuration (see [Secrets, Configuration and Credentials](#secrets-configuration-and-credentials)) to properly build some of the notebooks.

The main page of the documentation will be located at `docs/_build/index.html`.

### Working with PenAI

While Penpot is implemented in Closure and uses several custom data formants and representations, most AI and data science libraries are targetted for Python. To allow fast and easy exploration of AI use cases in Python, we implemented a Python binding for the most important Penpot data formats and several helper classes and functions to manipulate and render objects from within Python. These features include:

* Loading Penpot projects and representing Penpot data objects down to the level of shape elements
* Deriving bounding boxes for arbitrary shape elements within a Penpot page
* Rendering Penpot objects (pages or single shape elements) into raster graphics

A few examples on how to work with the `penai` package are provided in the `docs/02_notebooks/01_working_with_penai.ipynb` notebook.

## Troubleshooting

### "No module named 'pysqlite2'"

This may occur if Python hasn't been compiled with sqlite support in a Linux environment.

To fix this problem, use the following instructions. While Ubuntu-specific, they should be easy to adjust for other distros.

* If not done yet, install [pyenv](https://github.com/pyenv/pyenv) for installing/compiling Python versions
* `apt install libsqlite3-dev` (install missing lib)
* `pyenv install 3.11.10` (will compile and install 3.11.10)
* `pyenv local 3.11.10` (run within the penai repository; will set the local Python version)

Now proceed with the normal installation and usage instructions as provided above.