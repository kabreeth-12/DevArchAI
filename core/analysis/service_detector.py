from pathlib import Path
from typing import List


def detect_microservices(project_path: str) -> List[str]:
    """
    Detect microservices by locating subdirectories
    that contain a pom.xml file.
    """

    project_root = Path(project_path)

    if not project_root.exists():
        return []

    services = []

    for item in project_root.iterdir():
        if item.is_dir():
            pom_file = item / "pom.xml"
            if pom_file.exists():
                services.append(item.name)

    return services
