from setuptools import setup, find_packages

setup(
    name="genec",
    version="1.0.0",
    description="GenEC: Generative Extract Class Refactoring Framework",
    author="GenEC Team",
    packages=find_packages(),
    install_requires=[
        "javalang==0.13.0",
        "gitpython>=3.1.42",
        "networkx>=3.2",  # 3.2+ required for NumPy 2.0 compatibility
        "python-louvain==0.16",
        "anthropic>=0.40.0,<1.0",
        "numpy>=1.24.0",
        "pyyaml>=6.0.0",
        "scikit-learn>=1.3.0",
        "leidenalg>=0.10.0",
        "python-igraph>=0.11.0",
        "pydantic>=2.0.0",
        "scipy>=1.11.0",
        "websockets>=12.0",
        "python-dotenv>=1.0.0",
    ],
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.10",
    ],
    entry_points={
        "console_scripts": [
            "genec=genec.cli:main",
        ],
    },
)
