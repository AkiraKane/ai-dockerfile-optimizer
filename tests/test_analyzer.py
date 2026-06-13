"""Tests for Dockerfile analyzer."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest
from analyzer import analyze_dockerfile, parse_dockerfile, DockerfileIssue


class TestAnalyzeDockerfile:
    def test_empty_dockerfile(self):
        result = analyze_dockerfile("")
        assert result.total_lines == 1
        assert len(result.issues) == 0

    def test_simple_dockerfile(self):
        content = """FROM python:3.12
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "app.py"]"""
        result = analyze_dockerfile(content)
        assert result.base_image == "python:3.12"

    def test_detects_latest_tag(self):
        content = "FROM python:latest"
        result = analyze_dockerfile(content)
        assert any(i.category == "best_practice" and "latest" in i.description
                    for i in result.issues)

    def test_detects_pip_no_cache(self):
        content = """FROM python:3.12
RUN pip install flask"""
        result = analyze_dockerfile(content)
        assert any(i.category == "size" and "--no-cache-dir" in i.suggestion
                    for i in result.issues)

    def test_detects_apt_no_recommends(self):
        content = """FROM ubuntu:22.04
RUN apt-get update && apt-get install -y curl"""
        result = analyze_dockerfile(content)
        assert any(i.category == "size" and "--no-install-recommends" in i.suggestion
                    for i in result.issues)

    def test_detects_secret_in_env(self):
        content = "ENV DATABASE_PASSWORD=supersecret"
        result = analyze_dockerfile(content)
        assert any(i.category == "security" and i.severity == "critical"
                    for i in result.issues)

    def test_detects_add_instead_of_copy(self):
        content = "ADD . /app"
        result = analyze_dockerfile(content)
        assert any(i.category == "security" and "COPY" in i.suggestion
                    for i in result.issues)

    def test_detects_privileged_port(self):
        content = "EXPOSE 80"
        result = analyze_dockerfile(content)
        assert any(i.category == "security" and "privileged port" in i.description
                    for i in result.issues)

    def test_detects_shell_form_cmd(self):
        content = "CMD python app.py"
        result = analyze_dockerfile(content)
        assert any(i.category == "best_practice" and "exec form" in i.suggestion
                    for i in result.issues)

    def test_to_prompt(self):
        content = """FROM python:latest
RUN pip install flask"""
        result = analyze_dockerfile(content, "test.Dockerfile")
        prompt = result.to_prompt()
        assert "test.Dockerfile" in prompt
        assert "python:latest" in prompt


class TestParseDockerfile:
    def test_empty(self):
        result = parse_dockerfile("")
        assert result["base_images"] == []

    def test_simple(self):
        content = """FROM python:3.12
WORKDIR /app
COPY . .
EXPOSE 8080
CMD ["python", "app.py"]"""
        result = parse_dockerfile(content)
        assert "python:3.12" in result["base_images"]
        assert "8080" in result["exposed_ports"]

    def test_multi_stage(self):
        content = """FROM node:18 AS builder
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder dist /usr/share/nginx/html"""
        result = parse_dockerfile(content)
        assert len(result["stages"]) == 2
        assert result["stages"][0]["alias"] == "builder"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
