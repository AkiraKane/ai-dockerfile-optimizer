# AI Dockerfile Optimizer 🔧🤖

A CLI tool that analyzes Dockerfiles for optimization opportunities and uses AI to suggest improvements for size, speed, and security.

## What It Does

1. **Analyzes** Dockerfiles for common issues (size, speed, security, best practices)
2. **Suggests** optimizations using AI (Ollama)
3. **Generates** optimized Dockerfile with explanations
4. **Detects** security risks, inefficient layers, and missing best practices

## Quick Start

```bash
# Analyze and optimize
python src/main.py Dockerfile

# Show analysis only (no AI)
python src/main.py Dockerfile --analyze

# Output as JSON
python src/main.py Dockerfile --json

# Save optimized version
python src/main.py Dockerfile --output optimized.Dockerfile
```

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Dockerfile    │────▶│    Analyzer     │────▶│   LLM Client    │
│   (input)       │     │  (rule-based)   │     │   (Ollama)      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                              │                         │
                              ▼                         ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │  AnalysisResult │────▶│  Optimized      │
                        │  .to_prompt()   │     │  Dockerfile     │
                        └─────────────────┘     └─────────────────┘
```

## Example

Input `Dockerfile`:
```dockerfile
FROM python:latest
ADD . /app
WORKDIR /app
RUN pip install flask gunicorn
ENV DATABASE_PASSWORD=supersecret
EXPOSE 80
CMD python app.py
```

Analysis:
```
Issues: 6
  Critical: 1 (secret in ENV)
  Warnings: 2 (latest tag, pip without --no-cache-dir)
  Suggestions: 3 (ADD vs COPY, privileged port, shell form CMD)
```

Optimized:
```dockerfile
FROM python:3.12-slim

# Create non-root user for security
RUN useradd -m appuser

WORKDIR /app

# Copy and install dependencies first (better caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Use non-root user
USER appuser

# Use high port
EXPOSE 8080

# Exec form for proper signal handling
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]
```

## Issues Detected

### Size
- Large base images (use slim/alpine variants)
- Missing `--no-install-recommends` for apt-get
- Missing `--no-cache-dir` for pip
- Missing `--production` for npm

### Speed
- COPY before dependency install (cache invalidation)
- Multiple RUN commands (should combine)

### Security
- Secrets in ENV variables
- Running as root
- Using ADD instead of COPY
- Privileged ports (< 1024)

### Best Practices
- Using `:latest` tag
- Shell form CMD/ENTRYPOINT
- Missing WORKDIR

## Requirements

- Python 3.11+
- Ollama running locally (or OPENAI_API_KEY)

## Installation

```bash
git clone https://github.com/AkiraKane/ai-dockerfile-optimizer.git
cd ai-dockerfile-optimizer
```

## Docker

```bash
docker build -t ai-dockerfile-optimizer .
docker run -v $(pwd):/app/input ai-dockerfile-optimizer
```

## Interview Talking Points

- **Build Optimization**: Reduces image size and build time
- **Security Hardening**: Detects secrets, root user, privileged ports
- **CI/CD Integration**: Can run in pipeline to enforce best practices
- **Developer Experience**: Automated code review for Dockerfiles

## License

MIT
