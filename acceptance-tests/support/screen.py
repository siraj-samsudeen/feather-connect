"""VIDEO=1 only: a terminal-like page of the test's own (about:blank, never
the product), for scenarios that open no web page. Commands typed and what
they printed, what a monitor asked and was answered, the log lines checked,
and the scenario's setup notes are added to it as they happen, so a person
watching the review video sees them under each step's caption.

Every call is a no-op without VIDEO=1. The page is the test's own, so it may
carry a <style> element; the product's pages never get one.
"""

import html

STYLE = (
    "body{margin:0;background:#0f172a;color:#e2e8f0;font:15px/1.45 Consolas,'Courier New',monospace}"
    "main{padding:56px 20px 20px}"
    ".block{margin:0 0 14px;padding:8px 12px;border-left:3px solid #334155;background:#111827}"
    ".prompt{color:#4ade80;font-weight:bold}.request{color:#60a5fa;font-weight:bold}"
    ".log{color:#fbbf24;font-weight:bold}.note{color:#94a3b8;font-style:italic}"
    ".ok{color:#4ade80}.bad{color:#f87171}pre{margin:4px 0 0;white-space:pre-wrap;word-break:break-all}"
)
MAX_BLOCKS = 6  # the newest stay on a 900px-high screen
MAX_LINES = 14  # per block


def _clip(text):
    lines = (text or "").rstrip("\n").splitlines()
    if len(lines) > MAX_LINES:
        lines = lines[:MAX_LINES] + ["... (%d more lines)" % (len(lines) - MAX_LINES)]
    return "\n".join(lines)


class Screen:
    def __init__(self, world):
        self.world = world
        self.blocks = []

    @property
    def recording(self):
        from support import world as world_module

        return world_module.VIDEO

    def open(self):
        """Opens the page now, so the scenario's first caption has somewhere to show."""
        if self.recording:
            self._render()

    def _render(self):
        page = self.world.signed_out("the terminal")
        body = "".join(self.blocks[-MAX_BLOCKS:]) or "<p class='note'>(nothing run yet)</p>"
        page.set_content("<!doctype html><title>Terminal</title><style>%s</style><main>%s</main>" % (STYLE, body))
        from support import captions

        captions.show(page, self.world.caption)

    def _add(self, block):
        if not self.recording:
            return
        block = "<div class='block'>%s</div>" % block
        if self.blocks and self.blocks[-1] == block:
            return  # a repeated poll with the same answer
        self.blocks.append(block)
        self._render()

    def note(self, text):
        self._add("<span class='note'># %s</span>" % html.escape(text))

    def command(self, command, output, exit_code):
        mark = "ok" if exit_code == 0 else "bad"
        self._add(
            "<span class='prompt'>$ %s</span><pre>%s</pre><span class='%s'>[exit code %s]</span>"
            % (html.escape(command), html.escape(_clip(output)) or "(no output)", mark, exit_code)
        )

    def request(self, method, path, status, body):
        mark = "ok" if 200 <= status < 300 else "bad"
        self._add(
            "<span class='request'>monitor: %s %s</span><pre><span class='%s'>%d</span> %s</pre>"
            % (html.escape(method), html.escape(path), mark, status, html.escape(_clip(body)) or "(no body)")
        )

    def log(self, wanted, lines):
        """The server log lines that hold the texts checked for."""
        hits = [line for line in lines if any(text in line for text in wanted)]
        self._add(
            "<span class='log'>server log, lines checked for: %s</span><pre>%s</pre>"
            % (html.escape(" / ".join(wanted)), html.escape(_clip("\n".join(hits))) or "(none found)")
        )
