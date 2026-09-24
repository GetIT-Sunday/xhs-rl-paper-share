#!/usr/bin/env python3
"""Build a downloadable Skill using an explicit allowlist, never runtime data."""
import argparse
from pathlib import Path
import zipfile
from paper2xhs import RUNTIME_SCRIPTS

ROOT = Path(__file__).resolve().parents[1]
FILES = ['SKILL.md', 'agents/openai.yaml', 'requirements.txt',
         'references/skill-content.md', 'references/skill-operations.md',
         'examples/creator_metrics.config.example.json', 'scripts/paper2xhs.py'] + [
             'scripts/' + name for name in RUNTIME_SCRIPTS]


def build(output):
    output = Path(output)
    # Validate all inputs before creating an archive. Symlinks cannot smuggle
    # external credentials into a public package.
    for name in FILES:
        source = ROOT / name
        if source.is_symlink() or not source.is_file() or ROOT not in source.resolve().parents:
            raise ValueError('Invalid package input: ' + name)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(FILES):
            archive.write(ROOT / name, 'paper2xhs/' + name)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist' / 'paper2xhs.zip')
    print(build(parser.parse_args().output))
