from pathlib import Path
import yaml

SKILL_PATH = Path(__file__).resolve().parents[1]/"skill"/"squat_skill.yaml"

def load_skill(path: Path=SKILL_PATH) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    ids=[item["id"] for item in data["criteria"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate criteria IDs found")
    return data


if __name__ == "__main__":
    skill = load_skill()
    print(f"{len(skill['criteria'])} criteria")
    for item in skill["criteria"]:
        pages=",".join(str(page) for page in item["source_pages"])
        print(f"{item["id"]}: pages={pages}; side_view={item["side_view"]}")