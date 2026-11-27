"""Two checks on every page a scenario opens: accessibility, and how long the page took.

The accessibility check runs axe-core (the rules of WCAG 2.1 levels A and AA), put into the page
through Playwright's own channel, so the app's content policy is never loosened for a test.
Steps call `quality.check(what, page)` after each page they open; a final Then step asserts
`quality.problems()` is empty. The time budget is a spec's promise ("the overview opens within
a second"): `quality.load_ms(page)` gives how long the page took to load, for that step to
compare. Starting point from the process template: copy it, then fill in nothing - it needs no
project values.
"""

from dataclasses import dataclass, field
from typing import Any

from axe_playwright_python.sync_playwright import Axe

WCAG_21_AA = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]
AXE_OPTIONS = {"runOnly": {"type": "tag", "values": WCAG_21_AA}, "resultTypes": ["violations"]}


@dataclass
class Finding:
    """What axe found on one page: what the scenario called it, its address, the violations."""

    what: str
    url: str
    violations: list[dict[str, Any]]


@dataclass
class PageQuality:
    """The accessibility findings of every page checked in a run, kept until a step asks."""

    findings: list[Finding] = field(default_factory=list)
    _axe: Axe | None = None

    def check(self, what: str, page: Any) -> None:
        """Runs axe on the page as it is now and keeps what it found under `what`."""
        if self._axe is None:
            self._axe = Axe()  # loads axe-core once, on the first page checked
        results = self._axe.run(page, options=AXE_OPTIONS)
        self.findings.append(Finding(what, page.url, results.response["violations"]))

    def problems(self) -> list[str]:
        """One line per violation and element, on every page checked; a run that checked no page
        says so, so a missing call can't pass for a clean result."""
        if not self.findings:
            return ["no page was checked"]
        return [
            f"{finding.what} ({finding.url}): {violation['id']} [{violation.get('impact')}] "
            f"{violation['help']} at {', '.join(str(t) for t in node['target'])}"
            for finding in self.findings
            for violation in finding.violations
            for node in violation["nodes"]
        ]

    @staticmethod
    def load_ms(page: Any) -> float:
        """How long the page now open took to load, in milliseconds (the browser's own timing)."""
        return page.evaluate(
            "() => { const n = performance.getEntriesByType('navigation')[0];"
            " return n ? n.loadEventEnd - n.startTime : NaN; }"
        )
