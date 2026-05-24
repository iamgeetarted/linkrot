from setuptools import setup, find_packages
from pathlib import Path

long_description = (Path(__file__).parent / "README.md").read_text(encoding="utf-8")

setup(
    name="linkrot",
    version="2.1.0",
    author="iamgeetarted",
    author_email="marktimothydorsey@gmail.com",
    description="Find broken links in Markdown and HTML files",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/iamgeetarted/linkrot",
    packages=find_packages(),
    python_requires=">=3.11",
    entry_points={
        "console_scripts": [
            "linkrot=linkrot.cli:entry_point",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Documentation",
        "Topic :: Utilities",
        "Environment :: Console",
    ],
    keywords="links markdown html broken deadlink linkchecker",
)
