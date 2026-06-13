#!/usr/bin/env python3
"""AI Dockerfile Optimizer — analyze and optimize Dockerfiles using AI."""

import argparse
import sys
import os

from analyzer import analyze_dockerfile, parse_dockerfile, AnalysisResult
from llm import optimize_dockerfile, check_ollama


def main():
    parser = argparse.ArgumentParser(
        description="Analyze and optimize Dockerfiles using AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s Dockerfile              # Analyze and suggest optimizations
  %(prog)s Dockerfile --analyze    # Show analysis only (no AI)
  %(prog)s Dockerfile --output optimized.dockerfile  # Save optimized version
  %(prog)s Dockerfile --json       # Output analysis as JSON
        """,
    )
    parser.add_argument("file", help="Path to Dockerfile")
    parser.add_argument("--ollama-url", default="http://localhost:11434",
                        help="Ollama API URL")
    parser.add_argument("--model", default="llama3.2",
                        help="Ollama model to use")
    parser.add_argument("--analyze", action="store_true",
                        help="Show analysis only (no AI optimization)")
    parser.add_argument("--json", action="store_true",
                        help="Output analysis as JSON")
    parser.add_argument("--output", "-o", help="Save optimized Dockerfile to file")

    args = parser.parse_args()

    # Read Dockerfile
    if not os.path.exists(args.file):
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    with open(args.file) as f:
        content = f.read()

    # Analyze
    result = analyze_dockerfile(content, args.file)

    # Show summary
    print(f"Dockerfile: {result.filepath}")
    print(f"Base image: {result.base_image}")
    print(f"Lines: {result.total_lines}")
    print(f"Issues: {len(result.issues)}")
    print(f"  Critical: {result.critical_count}")
    print(f"  Warnings: {result.warning_count}")
    print(f"  Suggestions: {result.suggestion_count}")
    print()

    # JSON output
    if args.json:
        import json
        data = {
            "filepath": result.filepath,
            "base_image": result.base_image,
            "total_lines": result.total_lines,
            "issues": [
                {
                    "line": i.line_number,
                    "category": i.category,
                    "severity": i.severity,
                    "description": i.description,
                    "suggestion": i.suggestion,
                }
                for i in result.issues
            ],
        }
        print(json.dumps(data, indent=2))
        return

    # Analysis only
    if args.analyze:
        print(result.to_prompt())
        return

    # Check Ollama
    if not check_ollama(args.ollama_url):
        if not os.environ.get("OPENAI_API_KEY"):
            print("Error: Neither Ollama nor OPENAI_API_KEY available.",
                  file=sys.stderr)
            print("Use --analyze to see issues without AI.", file=sys.stderr)
            sys.exit(1)

    # Generate optimization
    print("Generating optimization suggestions...")
    try:
        optimization = optimize_dockerfile(
            result.to_prompt(),
            ollama_url=args.ollama_url,
            model=args.model,
        )
    except ConnectionError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(optimization)

    # Save if requested
    if args.output:
        # Extract Dockerfile from markdown response
        dockerfile_content = _extract_dockerfile(optimization)
        if dockerfile_content:
            with open(args.output, "w") as f:
                f.write(dockerfile_content)
            print(f"\n✅ Optimized Dockerfile saved to {args.output}")
        else:
            print("\n⚠️  Could not extract Dockerfile from response", file=sys.stderr)


def _extract_dockerfile(response: str) -> str | None:
    """Extract Dockerfile content from markdown response."""
    import re

    # Look for code blocks with dockerfile or Dockerfile
    patterns = [
        r'```dockerfile\n(.*?)```',
        r'```Dockerfile\n(.*?)```',
        r'```\n(FROM.*?)```',
    ]

    for pattern in patterns:
        match = re.search(pattern, response, re.DOTALL)
        if match:
            return match.group(1).strip()

    # Look for FROM instruction
    lines = response.split("\n")
    dockerfile_lines = []
    in_dockerfile = False

    for line in lines:
        if line.strip().startswith("FROM "):
            in_dockerfile = True
        if in_dockerfile:
            if line.strip() and not line.startswith("#") and not line.startswith("**"):
                dockerfile_lines.append(line)

    return "\n".join(dockerfile_lines) if dockerfile_lines else None


if __name__ == "__main__":
    main()
