"""Check student exercise pages against the files they teach."""

from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
import re


ROOT = Path(__file__).resolve().parents[1]


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []
        self.ids = set()
        self.details = 0

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if "href" in attributes:
            self.hrefs.append(attributes["href"])
        if "id" in attributes:
            self.ids.add(attributes["id"])
        if tag == "details":
            self.details += 1


def main():
    labs = sorted(
        folder for folder in ROOT.iterdir()
        if folder.is_dir() and folder.name[:1].isdigit()
    )
    failures = []
    checked_scripts = 0

    for folder in labs:
        pages = list(folder.glob("lab_*_exercise.html"))
        if len(pages) != 1:
            failures.append(f"{folder.name}: expected one HTML exercise, found {len(pages)}")
            continue
        page = pages[0]
        source = page.read_text(encoding="utf-8")
        parser = PageParser()
        parser.feed(source)
        for href in parser.hrefs:
            parsed = urlsplit(href)
            if parsed.scheme in {"http", "https"}:
                continue
            if parsed.scheme or parsed.netloc:
                failures.append(f"{page.name}: unsupported link {href}")
                continue
            if not parsed.path and parsed.fragment:
                if parsed.fragment not in parser.ids:
                    failures.append(f"{page.name}: missing section #{parsed.fragment}")
                continue
            target = (page.parent / unquote(parsed.path)).resolve()
            if not target.exists():
                failures.append(f"{page.name}: broken link {href}")
                continue
            if target.parent == folder and target.suffix in {".py", ".ps1", ".json"}:
                script = target.read_text(encoding="utf-8")
                if escape(script) not in source:
                    failures.append(f"{page.name}: embedded {target.name} is missing or stale")
                checked_scripts += 1
        if parser.details == 0:
            failures.append(f"{page.name}: no embedded source blocks")
        print(f"{folder.name}: {page.name}, {len(parser.hrefs)} links, {parser.details} source blocks")

    course_index = (ROOT / "README.md").read_text(encoding="utf-8")
    for folder in labs:
        if folder.name not in unquote(course_index):
            failures.append(f"README.md: no link for {folder.name}")

    sequence_index = ROOT.parent / "exercise instruction" / "index.html"
    sequence_source = sequence_index.read_text(encoding="utf-8")
    sequence_parser = PageParser()
    sequence_parser.feed(sequence_source)
    for href in sequence_parser.hrefs:
        parsed = urlsplit(href)
        if parsed.scheme in {"http", "https"}:
            continue
        if not parsed.path and parsed.fragment:
            if parsed.fragment not in sequence_parser.ids:
                failures.append(f"index.html: missing section #{parsed.fragment}")
            continue
        target = (sequence_index.parent / unquote(parsed.path)).resolve()
        if not target.exists():
            failures.append(f"index.html: broken link {href}")
    for folder in labs:
        original = next(folder.glob("lab_*_exercise.html"))
        collected = sequence_index.parent / original.name
        if original.name not in sequence_source:
            failures.append(f"index.html: no link for {original.name}")
        if not collected.exists():
            failures.append(f"index.html: missing collected {original.name}")
            continue
        expected = original.read_text(encoding="utf-8").replace(
            'href="./', f'href="../Labs/{folder.name.replace(" ", "%20")}/'
        )
        expected = re.sub(r'href="\.\./(?!Labs/)', 'href="../Labs/', expected)
        if collected.read_text(encoding="utf-8") != expected:
            failures.append(f"{original.name}: collected copy is stale")
        collected_parser = PageParser()
        collected_parser.feed(expected)
        for href in collected_parser.hrefs:
            parsed = urlsplit(href)
            if parsed.scheme in {"http", "https"} or (not parsed.path and parsed.fragment):
                continue
            if not (collected.parent / unquote(parsed.path)).exists():
                failures.append(f"{original.name}: broken collected link {href}")
    for filename in ["Exercise_1.html", "Exercise_02.html", "behind_transformers_pipeline.ipynb"]:
        if filename not in sequence_source:
            failures.append(f"index.html: missing {filename}")
    for filename in ["Exercise_1.html", "Exercise_02.html"]:
        copied_page = sequence_index.parent / filename
        copied_parser = PageParser()
        copied_parser.feed(copied_page.read_text(encoding="utf-8"))
        for href in copied_parser.hrefs:
            parsed = urlsplit(href)
            if parsed.scheme in {"http", "https"} or (not parsed.path and parsed.fragment):
                continue
            if not (copied_page.parent / unquote(parsed.path)).exists():
                failures.append(f"{filename}: broken link {href}")

    if failures:
        raise SystemExit("\n".join(failures))
    print(f"Validated {len(labs)} RAG pages, {checked_scripts} embedded source files, and course index links.")


if __name__ == "__main__":
    main()
