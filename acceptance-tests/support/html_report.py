"""The HTML report formatter, fixed for behave 1.3: behave-html-formatter
writes the report into its stream but never flushes or closes it, so the file
was left empty. This one closes it, and when the run stopped before the first
scenario (a before_all error, such as the database not being up) it still
writes a page saying so, instead of an empty file."""

from html import escape

from behave_html_formatter import HTMLFormatter as _Upstream

_NOTHING_RAN = (
    "<!DOCTYPE HTML><html><head><meta charset='utf-8'><title>%s</title></head>"
    "<body><h1>%s</h1><p>No scenario ran: the run stopped before the first one. "
    "The console output says why.</p></body></html>"
)


class HTMLFormatter(_Upstream):
    def close(self):
        super().close()
        if not getattr(self, "all_features", None):
            title = escape(self.title)
            self.stream.write(_NOTHING_RAN % (title, title))
        self.stream.flush()
        self.close_stream()
