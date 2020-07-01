#!/usr/bin/env python

from setuptools import setup, find_packages
from ackrep_core import __version__


with open('README.md') as readme_file:
    readme = readme_file.read()


with open("requirements.txt") as requirements_file:
    requirements = requirements_file.read()

setup_requirements = [ ]

main_package_name = "ackrep_core"
assert main_package_name in find_packages()


setup(
    author="Carsten Knoll",
    author_email='carsten.knoll@posteo.de',
    classifiers=[
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.7',
    ],
    description="xxx",
    install_requires=requirements,
    license="GNU General Public License v3",
    long_description=readme + '\n\n',
    long_description_content_type="text/markdown",
    include_package_data=True,
    keywords='knowledge mangement, repository based database',
    name='ackrep-core',
    packages=find_packages(),
    package_data={'ackrep_core': ['templates/*']},
    setup_requires=setup_requirements,
    # url='to be defined',
    version=__version__,
    entry_points={'console_scripts': ['ackrep=ackrep_core.script:main']}
)
