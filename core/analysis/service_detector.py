from pathlib import Path
from typing import List


def detect_microservices(project_path: str) -> List[str]:
    """
    Detect microservices by locating subdirectories
    that contain a build descriptor (pom.xml, build.gradle,
    build.gradle.kts, or package.json). Searches root and
    one level deeper to support monorepos (e.g., /src/*).
    """

    project_root = Path(project_path)

    if not project_root.exists():
        return []

    descriptors = {
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "package.json",
        "Dockerfile",
        "docker-compose.yml",
        "go.mod",
        "requirements.txt",
        "pyproject.toml",
        "setup.py",
        "build.sbt",
        "Cargo.toml",
    }
    infra_dirs = {
        "docker",
        "grafana",
        "prometheus",
        "monitoring",
        "observability",
        "k8s",
        "kubernetes",
        ".github",
        ".gitlab",
    }

    def has_descriptor(dir_path: Path) -> bool:
        return any((dir_path / name).exists() for name in descriptors)

    services = set()

    # First pass: immediate children
    for item in project_root.iterdir():
        if item.is_dir() and item.name not in infra_dirs and has_descriptor(item):
            services.add(item.name)

    # Second pass: one level deeper (e.g., /src/* or /services/*)
    for item in project_root.iterdir():
        if not item.is_dir():
            continue
        for sub in item.iterdir():
            if sub.is_dir() and sub.name not in infra_dirs and has_descriptor(sub):
                services.add(sub.name)

    return sorted(services)
