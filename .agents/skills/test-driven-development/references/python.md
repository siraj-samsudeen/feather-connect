# Python and server-rendered pages

The rules in [patterns and anti-patterns](best-practices.md) and [collaborators](collaborators.md)
hold in every language; their examples are TypeScript. These are the same shapes in pytest, plus
what a server-rendered page adds.

## Good tests

Test observable behaviour through a public interface, with a known expected value.

```python
def test_calculates_the_line_item_total():
    assert calculate_total([{"price": 10}, {"price": 5}]) == 15
```

Use named parameters when cases share one behaviour and only their data differs.

```python
@pytest.mark.parametrize(
    ("title", "reason"),
    [("", "empty"), ("   ", "only spaces"), ("x" * 201, "too long")],
    ids=["empty", "only-spaces", "too-long"],
)
def test_refuses_a_title_it_cannot_keep(title, reason):
    with pytest.raises(InvalidTitle):
        capture_task(title)
```

## A page is a public interface

Call the app in the same process and assert on what the page shows a person, parsed as HTML.
Never match raw HTML with a regex or compare whole pages: both break on a change nobody sees.

```python
def test_a_captured_task_shows_in_the_inbox(client):   # client: fastapi.testclient.TestClient
    client.post("/tasks", data={"title": "Buy milk"})

    page = BeautifulSoup(client.get("/inbox").text, "html.parser")

    assert [item.get_text(strip=True) for item in page.select("#inbox li")] == ["Buy milk"]
```

A fragment an HTMX request gets is tested the same way: send the request with the `HX-Request`
header and assert on the fragment.

Keep logic out of templates. Coverage and mutation testing cannot see a template, so a condition
or a computed value there is untested by construction. Compute it in Python and hand the
template the result.

```python
# Good: the rule is a function with its own test; the template prints `badge`.
def delivery_badge(delivery):
    return "late" if delivery.due < delivery.done_at else "on time"
```

```html
<!-- Bad: the rule lives where no test can reach it. -->
{% if delivery.due < delivery.done_at %}late{% else %}on time{% endif %}
```

## JavaScript in a server-rendered page

The Python tools cannot see a script: no unit test, coverage figure or mutation run reaches it.
In a project with no JavaScript toolchain, these rules stand in for them:

- **Prefer no script.** A link, a form, or an HTML attribute (HTMX) that asks the server for a
  part of the page needs none.
- **Every hand-written line is mandated by a browser test** that fails without it: an acceptance
  scenario, or a Playwright test of the page. That failing browser test is the script's red.
- **A script holds no rule of the product**: no calculation, validation or decision a person
  relies on. Those stay on the server, where tests reach them. A script shows, hides, focuses
  and submits.
- **The page still works with the script off**, unless its spec says otherwise.
- **A vendored library** (`htmx.min.js`) is not the application's code: it is kept as one file
  at a known version, with its licence, and is not tested or edited.

Stop when a script needs logic a browser test cannot pin down cheaply: branches, state kept
across interactions, data reshaped in the browser. That is a design decision for the human, not
a bigger script: it is when a JavaScript toolchain, and its own test loop, comes in
(`CLAUDE.md` § Project).

## Collaborators

Mock only at system boundaries: a vendor's HTTP API, the clock, randomness. Use the real
database (a scratch one per test session) and real in-process collaborators.

Pass a boundary in, so a test can supply its substitute.

```python
def post_invoice(invoice, erp):          # erp: anything with .post(document)
    return erp.post(invoice.as_document())
```

```python
# Bad: the client is built inside, so a test can only reach it by patching.
def post_invoice(invoice):
    return ErpClient(os.environ["ERP_KEY"]).post(invoice.as_document())
```

- **A web app's dependencies**: replace the boundary through the framework's own seam
  (`app.dependency_overrides[get_erp] = lambda: fake_erp` in FastAPI), not `unittest.mock.patch`
  on a module path, which couples the test to where the code lives.
- **An outgoing HTTP call**: answer it at the transport (`respx` for httpx), so the application's
  own client code runs.
- **Time**: pass a clock in (a fixed one in tests), rather than patching `datetime`.

Do not patch a function, class or module the application owns, and do not assert that one of
them was called: assert what the caller gets back or what a person then sees.
