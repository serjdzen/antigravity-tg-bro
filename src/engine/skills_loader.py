import logging
from pathlib import Path
from typing import Dict, List, Optional
from src.config import settings

logger = logging.getLogger(__name__)


def parse_skill_md(skill_file: Path) -> Dict[str, str]:
    name = skill_file.parent.name
    description = "No description provided"

    try:
        content = skill_file.read_text(encoding="utf-8")
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = parts[1]
                for line in frontmatter.strip().split("\n"):
                    if line.startswith("name:"):
                        name = line.split(":", 1)[1].strip()
                    elif line.startswith("description:"):
                        description = line.split(":", 1)[1].strip()
        else:
            for line in content.split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    description = line[:120]
                    break
    except Exception as e:
        logger.warning(f"Ошибка чтения {skill_file}: {e}")

    return {"name": name, "description": description}


def get_skills_paths(project_dir: Optional[Path] = None) -> List[str]:
    paths: List[str] = []

    # Глобальные скиллы
    global_skills = Path(settings.SKILLS_DIR_PATH)
    if global_skills.exists() and global_skills.is_dir():
        paths.append(str(global_skills))

    # Локальные скиллы проекта
    if project_dir and project_dir.exists():
        proj_agents = project_dir / ".agents" / "skills"
        if proj_agents.exists() and proj_agents.is_dir():
            paths.append(str(proj_agents))
        proj_skills = project_dir / "skills"
        if proj_skills.exists() and proj_skills.is_dir():
            paths.append(str(proj_skills))

    return paths


def get_skills_summary(project_dir: Optional[Path] = None) -> Dict[str, str]:
    summary: Dict[str, str] = {}
    paths_to_scan = get_skills_paths(project_dir)

    for base_path_str in paths_to_scan:
        base_path = Path(base_path_str)
        if not base_path.exists():
            continue
        try:
            for item in base_path.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    skill_file = item / "SKILL.md"
                    if skill_file.exists():
                        info = parse_skill_md(skill_file)
                        summary[info["name"]] = info["description"]
        except Exception as e:
            logger.warning(f"Ошибка сканирования скиллов в {base_path}: {e}")

    return summary
