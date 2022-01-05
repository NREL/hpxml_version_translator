import setuptools

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()


setuptools.setup(
    name="hpxml_version_translator",
    version="1.0.1",
    author="Ben Park (NREL), Noel Merket (NREL), Scott Horowitz (NREL)",
    author_email="ben.park@nrel.gov",
    description="Convert HPXML to newer version",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/NREL/hpxml_version_translator",
    packages=setuptools.find_packages(include=["hpxml_version_translator"]),
    package_data={"hpxml_version_translator": ["schemas/*/*.xsd", "*.xsl"]},
    install_requires=[
        "lxml",
        "deprecated",
    ],
    extras_require={
        "dev": [
            "pytest>=6.2",
            "pytest-mock",
            "pytest-xdist",
            "pytest-cov",
            "flake8",
            "rope",
            "black",
        ]
    },
    python_requires=">=3.6",
    entry_points={
        "console_scripts": ["hpxml_version_translator=hpxml_version_translator:main"]
    },
)
