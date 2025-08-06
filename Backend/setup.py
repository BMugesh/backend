"""
ArogyaMitra Backend Setup Configuration
Healthcare AI Assistant Backend Package
"""

from setuptools import setup, find_packages

with open("requirements.txt") as f:
    requirements = f.read().splitlines()
    # Filter out comments and empty lines
    requirements = [req for req in requirements if req and not req.startswith("#")]

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="arogyamitra-backend",
    version="1.0.0",
    author="ArogyaMitra Team",
    author_email="team@arogyamitra.com",
    description="AI-powered healthcare assistant backend",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/arogyamitra/backend",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Healthcare Industry",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Framework :: Flask",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    extras_require={
        "dev": [
            "black>=24.1.1",
            "flake8>=7.0.0",
            "pytest>=8.0.0",
            "pytest-flask>=1.3.0",
            "coverage>=7.4.0",
            "mypy>=1.8.0",
            "isort>=5.13.2",
        ],
        "prod": [
            "gunicorn>=21.2.0",
            "gevent>=23.9.1",
            "sentry-sdk[flask]>=1.40.0",
            "redis>=5.0.1",
            "psycopg2-binary>=2.9.9",
        ],
        "monitoring": [
            "prometheus-client>=0.19.0",
            "structlog>=23.2.0",
            "python-json-logger>=2.0.7",
        ],
    },
    entry_points={
        "console_scripts": [
            "arogyamitra=backend:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
    keywords="healthcare ai assistant medical flask api",
    project_urls={
        "Bug Reports": "https://github.com/arogyamitra/backend/issues",
        "Source": "https://github.com/arogyamitra/backend",
        "Documentation": "https://docs.arogyamitra.com",
    },
)
