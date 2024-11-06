import os
from setuptools import setup, find_packages

setup(
    name="KineticAI",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        # List your project dependencies here
        # For example:
        # "numpy>=1.19.0",
        # "pandas>=1.2.0",
    ],
    author="Aiden Gindin",
    author_email="aiden@aidengindin.com",
    description="A short description of your project",
    long_description=open("README.md").read() if os.path.exists("README.md") else "",
    long_description_content_type="text/markdown",
    url="https://github.com/aidengindin/KineticAI",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
)