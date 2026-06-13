"""Analyze Dockerfiles for optimization opportunities."""

import re
from dataclasses import dataclass, field


@dataclass
class DockerfileIssue:
    """A single optimization issue."""
    line_number: int
    category: str  # size, speed, security, best_practice
    severity: str  # critical, warning, suggestion
    description: str
    suggestion: str
    current_line: str = ""


@dataclass
class AnalysisResult:
    """Dockerfile analysis results."""
    filepath: str
    issues: list[DockerfileIssue] = field(default_factory=list)
    base_image: str = ""
    total_lines: int = 0

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "critical")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    @property
    def suggestion_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "suggestion")

    def to_prompt(self) -> str:
        """Convert to prompt for LLM optimization."""
        parts = [
            f"Dockerfile: {self.filepath}",
            f"Base image: {self.base_image}",
            f"Lines: {self.total_lines}",
            f"Issues found: {len(self.issues)}",
            f"  Critical: {self.critical_count}",
            f"  Warnings: {self.warning_count}",
            f"  Suggestions: {self.suggestion_count}",
            "",
        ]

        # Group by category
        for category in ["size", "speed", "security", "best_practice"]:
            issues = [i for i in self.issues if i.category == category]
            if not issues:
                continue

            parts.append(f"## {category.replace('_', ' ').title()}")
            parts.append("")

            for issue in issues:
                parts.append(f"### Line {issue.line_number} ({issue.severity})")
                parts.append(f"Current: `{issue.current_line.strip()}`")
                parts.append(f"Issue: {issue.description}")
                parts.append(f"Suggestion: {issue.suggestion}")
                parts.append("")

        return "\n".join(parts)


def analyze_dockerfile(content: str, filepath: str = "Dockerfile") -> AnalysisResult:
    """Analyze a Dockerfile for optimization opportunities."""
    result = AnalysisResult(filepath=filepath)
    lines = content.split("\n")
    result.total_lines = len(lines)

    # Track state
    has_multi_stage = False
    stage_count = 0
    apt_get_updated = False
    apt_get_installed = False
    copy_before_run = False
    run_count = 0
    last_from_line = 0

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Skip comments and empty lines
        if not stripped or stripped.startswith("#"):
            continue

        # Check base image
        if stripped.startswith("FROM "):
            result.base_image = stripped.split()[1] if len(stripped.split()) > 1 else ""
            stage_count += 1
            if stage_count > 1:
                has_multi_stage = True
            last_from_line = i

        # Check for size issues
        _check_size_issues(stripped, i, result)

        # Check for speed issues
        _check_speed_issues(stripped, i, result, locals())

        # Check for security issues
        _check_security_issues(stripped, i, result)

        # Check for best practices
        _check_best_practices(stripped, i, result)

        # Track RUN commands
        if stripped.startswith("RUN "):
            run_count += 1

    return result


def _check_size_issues(line: str, line_num: int, result: AnalysisResult):
    """Check for image size optimization opportunities."""
    # Large base images
    if line.startswith("FROM "):
        image = line.split()[1] if len(line.split()) > 1 else ""
        large_images = ["ubuntu:latest", "debian:latest", "python:latest", "node:latest"]
        if any(img in image for img in large_images):
            result.issues.append(DockerfileIssue(
                line_number=line_num,
                category="size",
                severity="suggestion",
                description=f"Large base image: {image}",
                suggestion="Consider using slim or alpine variants (e.g., python:3.12-slim, node:18-alpine)",
                current_line=line
            ))

    # apt-get without cleanup
    if "apt-get install" in line and "--no-install-recommends" not in line:
        result.issues.append(DockerfileIssue(
            line_number=line_num,
            category="size",
            severity="warning",
            description="apt-get install without --no-install-recommends",
            suggestion="Add --no-install-recommends to reduce installed packages",
            current_line=line
        ))

    # Missing apt-get cleanup
    if "apt-get install" in line and "rm -rf /var/lib/apt/lists/*" not in line:
        result.issues.append(DockerfileIssue(
            line_number=line_num,
            category="size",
            severity="warning",
            description="apt-get install without cleaning apt cache",
            suggestion="Add '&& rm -rf /var/lib/apt/lists/*' to reduce image size",
            current_line=line
        ))

    # pip install without --no-cache-dir
    if "pip install" in line and "--no-cache-dir" not in line:
        result.issues.append(DockerfileIssue(
            line_number=line_num,
            category="size",
            severity="warning",
            description="pip install without --no-cache-dir",
            suggestion="Add --no-cache-dir to reduce image size",
            current_line=line
        ))

    # npm install without --production
    if "npm install" in line and "--production" not in line and "devDependencies" not in line:
        result.issues.append(DockerfileIssue(
            line_number=line_num,
            category="size",
            severity="suggestion",
            description="npm install without --production",
            suggestion="Add --production to skip devDependencies",
            current_line=line
        ))


def _check_speed_issues(line: str, line_num: int, result: AnalysisResult, state: dict):
    """Check for build speed optimization opportunities."""
    # COPY before RUN (cache invalidation)
    if line.startswith("COPY "):
        # Check if this is early in the Dockerfile
        if line_num < 10:
            result.issues.append(DockerfileIssue(
                line_number=line_num,
                category="speed",
                severity="suggestion",
                description="COPY early may invalidate cache frequently",
                suggestion="Copy only dependency files first (e.g., package.json, requirements.txt), install deps, then copy source",
                current_line=line
            ))

    # Multiple RUN commands (should combine)
    if line.startswith("RUN "):
        # This is simplified; real analysis would track across lines
        pass


def _check_security_issues(line: str, line_num: int, result: AnalysisResult):
    """Check for security issues."""
    # Running as root
    if line.startswith("USER root") or (line.startswith("RUN ") and "sudo" in line):
        result.issues.append(DockerfileIssue(
            line_number=line_num,
            category="security",
            severity="warning",
            description="Running as root user",
            suggestion="Create and use a non-root user: RUN useradd -m appuser && USER appuser",
            current_line=line
        ))

    # Secrets in ENV
    if line.startswith("ENV ") and any(s in line.lower() for s in ["password", "secret", "key", "token"]):
        result.issues.append(DockerfileIssue(
            line_number=line_num,
            category="security",
            severity="critical",
            description="Possible secret in ENV variable",
            suggestion="Use build secrets or runtime environment variables instead of baking secrets into the image",
            current_line=line
        ))

    # ADD instead of COPY
    if line.startswith("ADD ") and not line.startswith("ADD --"):
        result.issues.append(DockerfileIssue(
            line_number=line_num,
            category="security",
            severity="suggestion",
            description="Using ADD instead of COPY",
            suggestion="Use COPY unless you need ADD's tar extraction or URL fetching features",
            current_line=line
        ))

    # EXPOSE with privileged ports
    if line.startswith("EXPOSE "):
        ports = re.findall(r'\d+', line)
        for port in ports:
            if int(port) < 1024:
                result.issues.append(DockerfileIssue(
                    line_number=line_num,
                    category="security",
                    severity="suggestion",
                    description=f"Exposing privileged port {port}",
                    suggestion="Consider using ports >= 1024 and mapping at runtime",
                    current_line=line
                ))


def _check_best_practices(line: str, line_num: int, result: AnalysisResult):
    """Check for Dockerfile best practices."""
    # Missing HEALTHCHECK
    if line.startswith("EXPOSE ") or line.startswith("CMD "):
        # Can't easily check if HEALTHCHECK exists elsewhere, so just note
        pass

    # Using latest tag
    if line.startswith("FROM ") and ":latest" in line:
        result.issues.append(DockerfileIssue(
            line_number=line_num,
            category="best_practice",
            severity="warning",
            description="Using :latest tag",
            suggestion="Pin to a specific version for reproducible builds (e.g., python:3.12-slim)",
            current_line=line
        ))

    # Missing WORKDIR
    if line.startswith("COPY ") and "/app" not in line and line_num < 5:
        result.issues.append(DockerfileIssue(
            line_number=line_num,
            category="best_practice",
            severity="suggestion",
            description="COPY without explicit WORKDIR",
            suggestion="Set WORKDIR /app before COPY commands",
            current_line=line
        ))

    # Shell form vs exec form for CMD/ENTRYPOINT
    if line.startswith("CMD ") or line.startswith("ENTRYPOINT "):
        if not line.split(maxsplit=1)[1].startswith("["):
            result.issues.append(DockerfileIssue(
                line_number=line_num,
                category="best_practice",
                severity="suggestion",
                description="Using shell form instead of exec form",
                suggestion="Use exec form: CMD [\"executable\", \"param1\"] for proper signal handling",
                current_line=line
            ))


def parse_dockerfile(content: str) -> dict:
    """Parse Dockerfile into structured data."""
    result = {
        "base_images": [],
        "stages": [],
        "exposed_ports": [],
        "env_vars": [],
        "copies": [],
        "runs": [],
    }

    current_stage = None

    for i, line in enumerate(content.split("\n"), 1):
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("FROM "):
            parts = stripped.split()
            image = parts[1] if len(parts) > 1 else ""
            alias = parts[3] if len(parts) > 3 and parts[2].upper() == "AS" else ""
            current_stage = {"line": i, "image": image, "alias": alias}
            result["stages"].append(current_stage)
            result["base_images"].append(image)

        elif stripped.startswith("EXPOSE "):
            ports = re.findall(r'\d+', stripped)
            result["exposed_ports"].extend(ports)

        elif stripped.startswith("ENV "):
            result["env_vars"].append(stripped[4:].strip())

        elif stripped.startswith("COPY "):
            result["copies"].append(stripped[5:].strip())

        elif stripped.startswith("RUN "):
            result["runs"].append(stripped[4:].strip())

    return result
