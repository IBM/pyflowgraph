# Flow graphs for Python

[![Build Status](https://travis-ci.org/IBM/pyflowgraph.svg?branch=master)](https://travis-ci.org/IBM/pyflowgraph) [![Python 2.7](https://img.shields.io/badge/python-2.7-blue.svg)](https://www.python.org/downloads/release/python-270/) [![Python 3.6](https://img.shields.io/badge/python-3.6-blue.svg)](https://www.python.org/downloads/release/python-360/) [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.1401682.svg)](https://doi.org/10.5281/zenodo.1401682)

**Record dataflow graphs of Python programs using dynamic program analysis.**

The package can be used standalone but is designed primarily to be used in
conjunction with our [semantic flow
graphs](https://github.com/IBM/semanticflowgraph). The main use case is
analyzing short scripts in data science and scientific computing. This package
is not appropriate for analyzing large-scale industrial software.

This is **alpha** software. Contributions are welcome!

## Command-line interface

The package ships with a minimal CLI, invokable as `python -m flowgraph`.
You can use the CLI to run and record a Python script as a raw flow graph.

```
python -m flowgraph input.py --out output.graphml
```

For a more comprehensive CLI, with support for recording, semantic enrichment,
and visualization of flow graphs, see the Julia package for [semantic flow
graphs](https://github.com/IBM/semanticflowgraph).