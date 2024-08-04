# setup.py
from setuptools import setup

setup(
    name="eavesdrop",
    version="0.9.0",
    author="Dominik Penk",
    description="A single-file, dependency-free Python event system.",
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
