"""The automatic accessibility check: axe-core, put into the page through
Playwright's own channel (page.evaluate), so the product's content policy is
never loosened for a test. It checks the rules of WCAG 2.1 levels A and AA."""

from axe_playwright_python.sync_playwright import Axe

WCAG_21_AA = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]
OPTIONS = {"runOnly": {"type": "tag", "values": WCAG_21_AA}, "resultTypes": ["violations"]}


class AccessibilityCheck:
    def __init__(self):
        self._axe = None
        self.findings = []  # (what was checked, its address, axe's violations)

    def check(self, what, page):
        """Checks the page as it is now and keeps what axe found."""
        if self._axe is None:
            self._axe = Axe()
        results = self._axe.run(page, options=OPTIONS)
        self.findings.append((what, page.url, results.response["violations"]))

    def problems(self):
        """One line per violation and element, on every page checked."""
        lines = []
        if not self.findings:
            return ["no page was checked"]
        for what, url, violations in self.findings:
            for violation in violations:
                for node in violation["nodes"]:
                    lines.append(
                        "%s (%s): %s [%s] %s at %s"
                        % (
                            what,
                            url,
                            violation["id"],
                            violation.get("impact"),
                            violation["help"],
                            ", ".join(str(t) for t in node["target"]),
                        )
                    )
        return lines
