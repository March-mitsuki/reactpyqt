from setuptools import setup, find_packages

setup(
    name="reactpyqt",
    version="0.1.0",
    packages=find_packages(include=["reactpyqt", "reactpyqt.*"]),
    package_dir={"reactpyqt": "reactpyqt"},
    install_requires=[
        "loguru>=0.7.0",
    ],
)
