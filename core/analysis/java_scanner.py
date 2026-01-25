from pathlib import Path
from typing import Set
import re


# Detect hard-coded service URLs like http://service-name
SERVICE_CALL_PATTERN = re.compile(r"http://([a-zA-Z0-9\-]+)")

# Detect Feign clients like @FeignClient(name = "service-name")
FEIGN_PATTERN = re.compile(r'@FeignClient\s*\(\s*name\s*=\s*"([a-zA-Z0-9\-]+)"')


def scan_java_dependencies(service_path: Path, max_files: int = 20) -> Set[str]:
    """
    Scan a limited number of Java files to detect inter-service calls.
    """
    dependencies = set()
    java_root = service_path / "src" / "main" / "java"

    if not java_root.exists():
        return dependencies

    scanned = 0

    for java_file in java_root.rglob("*.java"):
        if scanned >= max_files:
            break

        try:
            content = java_file.read_text(encoding="utf-8", errors="ignore")

            for match in SERVICE_CALL_PATTERN.findall(content):
                dependencies.add(match)

            for match in FEIGN_PATTERN.findall(content):
                dependencies.add(match)

            scanned += 1

        except Exception:
            continue

    return dependencies
