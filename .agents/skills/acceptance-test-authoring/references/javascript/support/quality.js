// Two checks on every page a scenario opens: accessibility, and how long the page took.
//
// The accessibility check runs axe-core (the rules of WCAG 2.1 levels A and AA) through
// @axe-core/playwright, so the app's content policy is never loosened for a test. Steps call
// `quality.check(what, page)` after each page they open; a final Then step asserts
// `quality.problems()` is empty. The time budget is a spec's promise ("the overview opens within
// a second"): `PageQuality.loadMs(page)` gives how long the page took, for that step to compare.
// Starting point from the process template: copy it; it needs no project values.

const { AxeBuilder } = require("@axe-core/playwright");

const WCAG_21_AA = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

/** The accessibility findings of every page checked in a run, kept until a step asks. */
class PageQuality {
  constructor() {
    this.findings = []; // { what, url, violations }
  }

  /** Runs axe on the page as it is now and keeps what it found under `what`. */
  async check(what, page) {
    const results = await new AxeBuilder({ page }).withTags(WCAG_21_AA).analyze();
    this.findings.push({ what, url: page.url(), violations: results.violations });
  }

  /** One line per violation and element; a run that checked no page says so. */
  problems() {
    if (this.findings.length === 0) return ["no page was checked"];
    return this.findings.flatMap(({ what, url, violations }) =>
      violations.flatMap((v) =>
        v.nodes.map((node) => `${what} (${url}): ${v.id} [${v.impact}] ${v.help} at ${node.target.join(", ")}`),
      ),
    );
  }

  /** How long the page now open took to load, in milliseconds (the browser's own timing). */
  static async loadMs(page) {
    return page.evaluate(() => {
      const nav = performance.getEntriesByType("navigation")[0];
      return nav ? nav.loadEventEnd - nav.startTime : Number.NaN;
    });
  }
}

module.exports = { PageQuality, WCAG_21_AA };
