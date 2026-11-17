"""VIDEO=1 only: each Gherkin step's text as a banner over every open page of
the scenario, so a person watching a review video can follow the story, with a
pause after each checked outcome so its result stays on screen. Normal and CI
runs get no captions and no pauses.

The page keeps the caption itself. A server-rendered app loads a new document
on almost every step, which would wipe a banner put there from outside; so an
init script, run in every document, shows the current caption again from the
tab's sessionStorage. Copy verbatim.
"""

READ_MS = 700  # the caption is up before the step acts
HOLD_AFTER_OUTCOME_MS = 1500  # a Then (or its And) stays visible

# Runs in every document of a recorded browser context, before the page's own
# scripts. Nothing here needs the page's permission: no <style> or <script>
# element and no inline style attribute, so a strict Content-Security-Policy
# neither blocks it nor reports it (styles are set through the CSSOM, and the
# dot pulses through the Web Animations API).
INIT_SCRIPT = """
(() => {
  const ID = 'acceptance-step-caption';
  let label = null; // where the caption's text goes, in this document
  const render = (text) => {
    if (!text || !document.documentElement) return;
    if (!label || !label.isConnected) {
      const banner = document.createElement('div');
      banner.id = ID;
      banner.setAttribute('aria-hidden', 'true');
      // Over everything, clicks pass through it, and it sits at the top.
      banner.style.cssText = [
        'position:fixed', 'top:0', 'left:0', 'right:0', 'z-index:2147483647', 'pointer-events:none',
        'padding:8px 14px', 'background:rgba(17,24,39,0.82)', 'color:#fff',
        'font:600 16px/1.35 system-ui,-apple-system,sans-serif', 'text-align:center',
        'box-shadow:0 2px 6px rgba(0,0,0,0.25)',
      ].join(';');
      // The text lives in a closed shadow root, which the test's locators and
      // text checks cannot see. A step usually quotes the text it checks
      // ('Then the list shows "Buy bread"'): in the page itself the caption
      // would be a second match, and a recorded run would fail where a plain
      // run passes.
      const hidden = banner.attachShadow({ mode: 'closed' });
      // A dot that keeps pulsing: Playwright's video only gains frames when
      // the page repaints, so without it a pause on a still page would be cut
      // from the video, and so would the end of the scenario.
      const dot = document.createElement('i');
      dot.style.cssText = 'display:inline-block;width:8px;height:8px;margin-right:10px;' +
        'border-radius:50%;background:#60a5fa;vertical-align:middle';
      dot.animate([{ opacity: 0.25 }, { opacity: 1 }, { opacity: 0.25 }], { duration: 1000, iterations: Infinity });
      label = document.createElement('span');
      hidden.append(dot, label);
      // On <html>, not <body>: a body swapped by HTMX's hx-boost keeps it.
      document.documentElement.appendChild(banner);
    }
    label.textContent = text;
  };
  const remembered = () => {
    try { return sessionStorage.getItem(ID); } catch { return null; }
  };
  window.__acceptanceCaption = (text) => {
    try { sessionStorage.setItem(ID, text); } catch { /* storage refused: this document only */ }
    render(text);
  };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => render(remembered()));
  } else {
    render(remembered());
  }
})();
"""


def install(browser_context):
    """Every document this browser context loads shows the current caption."""
    browser_context.add_init_script(INIT_SCRIPT)


def show(page, text):
    """Puts the caption on one page; the page shows it again after it navigates."""
    if not text:
        return
    try:
        page.evaluate("(text) => window.__acceptanceCaption && window.__acceptanceCaption(text)", text)
    except Exception:  # noqa: BLE001 - a page mid-navigation shows it on its next load
        pass


def before_step(world, step):
    """The step as written in the spec, its own keyword included ("And", "Then")."""
    world.caption = ("%s %s" % (step.keyword, step.name)).strip()
    pages = world.open_pages()
    for page in pages:
        show(page, world.caption)
    if pages:
        pages[0].wait_for_timeout(READ_MS)


def after_step(world, step):
    """Holds a checked outcome on screen: a Then, or the And/But that follows one."""
    pages = world.open_pages()
    if step.step_type != "then" or not pages:
        return
    for page in pages:  # again, in case the step opened a page
        show(page, world.caption)
    pages[0].wait_for_timeout(HOLD_AFTER_OUTCOME_MS)
