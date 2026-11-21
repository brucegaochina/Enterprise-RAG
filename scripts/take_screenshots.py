"""Capture portfolio screenshots of the running app into docs/screenshots.

    pip install playwright      # uses the locally installed Google Chrome
    python scripts/take_screenshots.py [--url http://localhost:8080]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8080")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))

        def shot(name: str) -> None:
            page.wait_for_timeout(400)
            page.screenshot(path=str(OUT / name))
            print("saved", name)

        def ask(question: str) -> None:
            done_before = page.locator(".meta-line").count()
            page.fill("#question", question)
            page.press("#question", "Enter")
            page.wait_for_function(f"document.querySelectorAll('.meta-line').length > {done_before}", timeout=120_000)

        page.goto(args.url)
        page.wait_for_selector("#stackPill.online, #stackPill.offline")
        shot("01_chat_home.png")

        ask("Does my plan cover annual eye exams?")
        shot("02_answer_supporting_content.png")

        ask("How about hearing?")
        page.click("#analysis .tab[data-tab='thought']")
        shot("03_thought_process.png")

        page.locator(".turn").last.locator(".chip").first.click()
        page.wait_for_selector("#hl")
        shot("04_citation_highlight.png")

        page.click(".nav-btn[data-view='docs']")
        page.wait_for_selector("#docRows tr")
        shot("05_knowledge_base.png")

        page.locator("[data-chunks]").nth(1).click()
        page.wait_for_selector("#chunkModal:not(.hidden) .chunk")
        shot("06_chunk_inspector.png")
        page.click("#closeChunkModal")

        page.click(".nav-btn[data-view='lab']")
        page.click("#labExamples button:nth-child(2)")
        page.wait_for_selector("#labGrid [data-chunk]")
        shot("07_retrieval_lab.png")

        browser.close()

    if errors:
        print("Browser errors:")
        for e in errors:
            print("  ", e)


if __name__ == "__main__":
    main()
