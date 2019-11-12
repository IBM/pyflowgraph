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
        'pathlib2',
        'six',
        'astor',
        'funcsigs',
        'traitlets',
        'requests',
        'jsonpickle',
        'click',
        'networkx<=2.3',
        'cachetools==2.1.0',
        'blitzdb @ git+https://github.com/adewes/blitzdb.git',
        'sqlalchemy',
        'ipykernel>=4.3.0',
    ],
    'extras_require': {
        'integration_tests': [
            'numpy>=1.16',
            'scipy',
            'pandas',
            'sklearn',
            'statsmodels',
        ]
    },
}

setup(**setup_args)
