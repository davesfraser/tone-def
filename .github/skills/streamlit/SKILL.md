---
name: streamlit
description: >
  Use when building, editing, or debugging Streamlit applications. Activate
  for any file containing st.*, app.py, streamlit run, session state, st.sidebar,
  st.columns, st.tabs, multi-page apps, or Streamlit layout and component code.
  Triggers on: streamlit, st.write, st.form, st.session_state, app.py,
  st.sidebar, st.columns, st.tabs, pages/, rerun, widget, cached.
user-invocable: true
---

# Streamlit App Standards — ToneDef

---

# ai-assistant-quick-summary

- `app.py` at the repo root is the entry point — run with `uv run streamlit run app.py`
- All logic lives in `src/tonedef` — `app.py` and page files call functions, they do not implement logic
- All secrets come from `tonedef.settings` — never read `os.environ` or `.env` directly in app files
- All paths come from `tonedef.paths` — never construct paths with strings
- Session state is the only way to persist values across reruns — initialise all keys at the top of the file
- Never mutate session state inside a widget callback and also in the main script body — pick one place
- `st.cache_data` for data loading, `st.cache_resource` for connections and clients — never cache both with the same decorator

---

# app-structure

RULE: `app.py` lives at the repo root and is the sole Streamlit entry point.
RULE: `app.py` contains layout and wiring only — no business logic, no API calls, no data processing.
RULE: All logic is implemented as functions in `src/tonedef` and imported into `app.py`.
RULE: Run the app with `uv run streamlit run app.py` — never with a bare `streamlit run`.
RULE: Import settings and paths at the top of `app.py` before any `st.*` calls:
```python
from tonedef.paths import DOCS_DIR
from tonedef.settings import settings
```

---

# multi-page-layout

RULE: For multi-page apps, create a `pages/` directory at the repo root alongside `app.py`.
RULE: Page files are named with a numeric prefix for ordering — e.g. `pages/01_query.py`, `pages/02_results.py`.
RULE: Each page file follows the same rule as `app.py` — layout and wiring only, logic in `src/`.
RULE: Shared state between pages must go through `st.session_state` — page files cannot import from each other.
RULE: Use `st.sidebar` for navigation controls and filters that apply across the whole app.
RULE: Use `st.tabs` for alternative views within a single page — not for content that belongs on separate pages.
RULE: Use `st.columns` for side-by-side layout within a page — keep column splits simple (2–3 columns maximum).

---

# session-state

RULE: Initialise every session state key at the top of the file before any widget or logic that reads it:
```python
if "response" not in st.session_state:
    st.session_state.response = None
```
RULE: Never read a session state key without first checking it exists — missing keys raise KeyError on rerun.
RULE: Do not mutate the same session state key in both a widget `on_change` callback and the main script body — choose one place and be consistent.
RULE: Store expensive results (API responses, loaded documents) in session state to avoid recomputing on every rerun.
RULE: Do not store large binary objects in session state if they can be cached with `st.cache_resource` instead.

---

# caching

RULE: Use `@st.cache_data` for functions that load or transform data — results are serialised and stored per unique input.
RULE: Use `@st.cache_resource` for functions that create shared objects — API clients, database connections, loaded models. These are not serialised; the object is shared across all sessions.
RULE: Never use `@st.cache_data` for an API client or connection object — use `@st.cache_resource`.
RULE: Never use `@st.cache_resource` for a function that returns a mutable data structure that callers modify — use `@st.cache_data` instead.

```python
# correct — client is a shared resource, not data
@st.cache_resource
def get_anthropic_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.anthropic_api_key.get_secret_value())
```

---

# secrets-and-settings

RULE: All configuration and secrets are accessed through `tonedef.settings` — never call `os.environ`, `os.getenv`, or `dotenv` directly in app or page files.
RULE: Never read `st.secrets` — this template uses `pydantic-settings` and `.env` as the single configuration mechanism.
RULE: API keys must be typed as `SecretStr` in `Settings` — access the value with `.get_secret_value()` only at the call site, never store the unwrapped string.
RULE: Never log, print, or display secret values — `st.write(settings)` will expose them if `SecretStr` is not used correctly.

---

# src-integration

RULE: `app.py` and page files are wiring only — they import and call, they do not implement.
RULE: Any logic that could be unit tested belongs in `src/tonedef`, not in the app file.
RULE: All filesystem access uses constants from `tonedef.paths` — never construct a path with a string literal in an app file.
RULE: Functions in `src/` must not import `streamlit` — keeping `st` out of `src/` means the logic is testable without a running Streamlit app.

**ANTI-PATTERN — logic in the app file:**
```python
# app.py — wrong
response = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"]).messages.create(...)
```

**Correct — logic in src/, wiring in app.py:**
```python
# src/tonedef/client.py
def query(prompt: str) -> str:
    client = get_anthropic_client()
    ...

# app.py
from tonedef.client import query
response = query(prompt)
```
