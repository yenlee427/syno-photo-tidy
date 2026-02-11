from setuptools import find_packages, setup

setup(
    name="syno-photo-tidy",
    version="0.2.0",
    description="Synology Photos 風格的安全整理工具",
    package_dir={"": "src"},
    packages=find_packages("src"),
    python_requires=">=3.10",
    install_requires=[],
)
