try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

    config = {
        'description': 'Tools for processing ddsm',
        'author': 'Francisco Gimenez',
        'url': 'https://github.com/fjeg/ddsm_tools',
        'author_email': 'fgimenez@stanford.edu',
        'version': '0.1',
        'packages': ['ddsm_tools'],
        'name': 'ddsm_tools'
    }

setup(**config)
