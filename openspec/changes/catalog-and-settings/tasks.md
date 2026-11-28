## 1. First-time setup — `acceptance-tests/` already exists; this change only adds to it

- [x] 1.1 The suite's support for the catalog, delivered by the red/green of the first step that needs it: a page object for `fcon catalog` and `fcon settings` (definitions files written for each scenario, `FCON_PROTECTED` passed when a scenario says the environment is protected), and the audit log reader extended to settings; every command, flag and text in page objects, none in steps

## 2. Step definitions — one task per pending step; each = fails for the right reason → implement → passes → commit

### Record what a package version declares

- [x] 2.1 catalog-and-settings: Given the package version "shop-flows 1.0" declares the flow …, the dataset … and the route … — red → green → commit
- [x] 2.2 catalog-and-settings: When the developer records "shop-flows 1.0" — red → green → commit
- [x] 2.3 catalog-and-settings: Then the catalog lists the flow …, the dataset … and the route …, each from "shop-flows 1.0" — red → green → commit

### A recorded package version never changes

- [x] 2.4 catalog-and-settings: Given "shop-flows 1.0" has been recorded — red → green → commit
- [x] 2.5 catalog-and-settings: When the developer records "shop-flows 1.0" again, with the dataset … declared differently — red → green → commit
- [x] 2.6 catalog-and-settings: Then the recording is refused, saying a recorded version never changes … / And the catalog still has the first definition — red → green → commit

### The operator's value is in force, else the code's

- [x] 2.7 catalog-and-settings: Given "shop-flows 1.0" has been recorded, its code giving the dataset … a look-back of "1d" (and a batch size of "5000"; no number of tries) — red → green → commit
- [x] 2.8 catalog-and-settings: When the operator sets the look-back of … to "3d" (with or without a reason) — red → green → commit
- [x] 2.9 catalog-and-settings: Then the settings of … show the look-back "3d", set by the operator / And they show the batch size "5000", set by the code — red → green → commit
- [x] 2.10 catalog-and-settings: When the operator looks at the settings of … / Then they show the number of tries "6", set by the product's default — red → green → commit
- [x] 2.11 catalog-and-settings: And the operator has set the look-back … / When the operator clears the look-back … / Then … "1d", set by the code — red → green → commit

### An operator's value outlives an upgrade; a rename is explicit

- [x] 2.12 catalog-and-settings: When the developer records "shop-flows 1.1", its code giving … a look-back of "2d" — red → green → commit
- [x] 2.13 catalog-and-settings: When the developer records "shop-flows 2.0", which renames … / And the catalog no longer lists "shop-flows.orders" — red → green → commit
- [x] 2.14 catalog-and-settings: When the developer records "shop-flows 2.0", which declares … without saying it replaces … / Then the settings of … show no value set by the operator — red → green → commit

### An operator's value the code no longer uses is flagged

- [x] 2.15 catalog-and-settings: When the developer records "shop-flows 2.0", which no longer declares … / Then the recording warns … / And the list of every value operators have set shows …, flagged — red → green → commit

### Only an operator's settings, to a valid value

- [x] 2.16 catalog-and-settings: When the operator sets the key of … / Then the change is refused, saying the key is decided by the code, and naming the settings a dataset has — red → green → commit
- [x] 2.17 catalog-and-settings: When the operator sets the look-back … to "three days" / Then the change is refused, saying a look-back is a length of time … / And … still show the look-back "1d", set by the code — red → green → commit

### Every change says who made it and why

- [x] 2.18 catalog-and-settings: Then the audit log records the change of the look-back … with the reason … — red → green → commit
- [x] 2.19 catalog-and-settings: Given a protected environment where "shop-flows 1.0" has been recorded / Then the change is refused, saying a protected environment needs a reason / And the audit log records the refusal — red → green → commit

## 3. What no scenario drives — each still arrives with the test or check that needs it

- [x] 3.1 The migration's four tables in `tables.py`, checked against the database by the existing table test; every index starting with `tenant_id`
- [x] 3.2 The definitions reader: names carry the package's name, duplicate names, kinds that change, renames across packages or kinds, a rename whose old name is still declared, an unknown or code-decided setting in the code, a file too large or not JSON: inner tests
- [x] 3.3 Each value type's parser (length of time, count, on/off, choice, time zone, schedule, a time with its offset, `none`): inner tests
- [x] 3.4 The rights: a viewer sees settings and can't change them; an operator can't record the catalog; refusals audited: inner tests
- [x] 3.5 Recording the same package version again with the same definitions writes nothing; a name the code no longer has comes back when a later version declares it again; a value can be cleared, not set, on a name no longer in the code: inner tests
- [x] 3.6 `FCON_PROTECTED` read and checked; `.env.example` and `deploy/.env.example`; `docs/architecture.md` (the catalog), `docs/runbook.md` (a flagged operator value), `docs/deploy.md` (the setting)
- [x] 3.7 `tzdata` as a direct dependency of `fcon-server`, with deptry told why it is never imported

## 4. Completion

- [x] 4.1 Run the full suite: every scenario passes, zero pending/undefined steps, HTML report generated
- [ ] 4.2 The end-of-change checks (ruff, format, pyright strict, vulture, deptry from each package, pytest at 100%), and CI green on the PR
- [x] 4.3 The code review by a different model (data, audit, permissions), findings triaged, at most 3 rounds
- [ ] 4.4 Review videos of the catalog and settings journey, watched by the owner
- [ ] 4.5 Run `openspec validate catalog-and-settings --type change` before archive
