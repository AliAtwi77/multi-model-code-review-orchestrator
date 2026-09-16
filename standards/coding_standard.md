# Project Coding Standard

## 1. Correctness
- Every public function must handle empty input, boundary indices, and `None`
  explicitly rather than relying on incidental exceptions.
- Off-by-one errors in loop bounds and slicing are blocking findings.
- Resource handles (files, sockets, DB connections, subprocesses) must be
  closed deterministically - use context managers, never rely on GC.

## 2. Security
- Never build SQL, shell commands, or file paths via string concatenation or
  f-strings with untrusted input. Use parameterized queries, `shlex`, or an
  allow-list.
- Never call `eval`, `exec`, `pickle.loads`, or `subprocess` with
  `shell=True` on untrusted input.
- Secrets must never be hard-coded or logged.

## 3. Error handling
- Do not use bare `except:`; catch specific exceptions.
- Do not silently swallow exceptions without at least a comment explaining why.

## 4. Style
- Follow PEP 8. Line length up to 110 is acceptable.
- Public functions should have type hints and a one-line docstring.
- Prefer explicit names over abbreviations (`index` not `idx`) in public APIs;
  short names are fine in tight local scopes (e.g. loop counters).

## 5. Testing
- Code that branches on input size or type must have a test for each branch.
- A defect that a provided test suite would catch is always a blocking finding.
- A missing test is advisory, not blocking, unless the task explicitly asked
  for tests to be written.

## 6. Review discipline (for the reviewer model)
- A finding must cite concrete evidence: a failing test name, a static
  analysis rule id, or a specific reproducing input/trace. Findings that
  are purely stylistic opinion must be marked `advisory`, never `blocking`.
- Do not re-raise, at higher severity, a finding you approved in a previous
  iteration unless the code at that location changed or new evidence
  (a new failing test, a new lint rule hit) appeared.
