"""
Setup configuration for THEO backend package.

This allows pytest to properly import modules and run all tests.
"""

from setuptools import setup, find_packages

setup(
    name="theo-backend",
    version="0.1.0",
    description="THEO AI Assistant - Backend",
    author="Danny Black",
    packages=find_packages(exclude=["tests", "tests.*"]),
    python_requires=">=3.9",
    install_requires=[
        "flask>=2.3.0",
        "sqlalchemy>=2.0.0",
        "anthropic>=0.18.0",
        "openai>=1.12.0",
        "boto3>=1.34.0",
        "python-dotenv>=1.0.0",
    ],
    extras_require={
        "test": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "pytest-mock>=3.12.0",
            "pytest-flask>=1.3.0",
        ],
    },
)
