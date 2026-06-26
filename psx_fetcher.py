# pyproject.toml
[project]
name = "psx-ultimate-engine"
version = "32.3.0"
description = "Production-grade automated PSX trading system"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.5",
    "numpy>=1.26",
    "pandas>=2.1",
    "requests>=2.31",
    "matplotlib>=3.8",
    "feedparser>=6.0",
    "textblob>=0.17",
    "pyyaml>=6.0",
    "beautifulsoup4>=4.12",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-mock>=3.12",
    "mypy>=1.8",
    "ruff>=0.1",
    "structlog>=24.0",
    "tenacity>=8.2",
]

[tool.ruff]
target-version = "py312"
select = [
    "E", "F", "I", "N", "W",
    "UP", "B", "C4", "SIM",
    "TCH", "PT", "Q", "RUF",
]
ignore = ["E501"]
line-length = 100

[tool.mypy]
strict = true
warn_unreachable = true
plugins = ["pydantic.mypy"]

[tool.pytest.ini_options]
minversion = "8.0"
addopts = "-ra -q --strict-markers"
testpaths = ["tests"]
