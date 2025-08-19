from setuptools import setup, find_packages

setup(
    name="insurance-outreach-backend",
    version="0.1.0",
    description="FastAPI backend for Insurance Outreach",
    packages=find_packages(include=["backend", "backend.*"]),
    install_requires=[
        "fastapi>=0.110.0",
        "uvicorn>=0.29.0",
        "pydantic>=2.6.0",
        "python-dotenv>=1.0.0",
        "email-validator>=1.3.1",
        "requests>=2.26.0",
        "httpx>=0.24.0",
    ],
    python_requires=">=3.10",
)
