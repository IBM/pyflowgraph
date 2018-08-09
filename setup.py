from setuptools import setup, find_packages

setup_args = {
    'name': 'flowgraph',
    'version': '0.1',
    'description': 'Flow graphs for Python',
    'license': 'ASL 2.0',
    'author': 'Evan Patterson',
    'author_email': 'epatters@stanford.edu',
    'include_package_data': True,
    'packages': find_packages(),
    'zip_safe': False,
    'install_requires': [
        # core package
        'pathlib2',
        'six',
        'traitlets',
        'requests',
        'jsonpickle',
        'networkx==1.11',
        'cachetools>=2.0.0',
        'blitzdb>=0.3',
        'sqlalchemy',
        'ipykernel>=4.3.0',
    ],
    'tests_require': [
        # integration tests
        'pandas',
        'scipy',
        'sklearn',
        'statsmodels',
    ],
}

setup(**setup_args)
