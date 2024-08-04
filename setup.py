# setup.py
from setuptools import setup

setup(
    name="eavesdrop",
    version="0.9.0",
    author="Dominik Penk",
    description="Single-file, dependency-free publisher-subscriber implementation.",
    py_modules=["eavesdrop"],
    url="https://github.com/DominikPenk/eavesdrop",
    install_requires=[],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.11",
)