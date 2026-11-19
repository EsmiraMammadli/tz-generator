# Changelog

## 1. More client questions
- New questions: existing site / redesign (+ link), domain and hosting (+ domain name), SEO and analytics,
  contact details, social links (only when the module exists), map address (only when the module exists),
  competitors, approver, number of revision rounds.
- Per-page content: after the structure is confirmed the bot asks what goes on each page. A button marks all
  remaining pages as open questions. Pages added later are asked on their own; renaming keeps the content.
- Answers feed the document: domain/hosting and redesign add technical requirements; the analytics requirement now
  follows the client's answer ("not needed" removes it) instead of always being written.
- Page content shows in the page card, the summary, the DOCX and the PDF; pages without content appear in the open questions.
- Tests updated for the longer flow and 8 new engine tests added.

## 2. Making the LLM more useful
- Long answers fill several fields at once (prompt `extract_v3`): the bot skips questions that were already answered and
  tells the client what it noted. Fields that do not apply yet (their module is missing, or the field they depend on is
  unanswered) are dropped instead of stored; text slots are never filled with a whole sentence when other fields were extracted.
- A short "why we ask" line under every question (all three languages), also returned by the API (`why`) and kept in history.
- Provider trace: each turn's log has `llm_order`, `llm_tried` and `answered_by`; `llm.STATS` counts ok/fail per model.
- 12 new tests (multi-field, applicability and flow order, engine-only keys, why lines, provider trace).

## 3. Logo and brand
- Several files per session: logo variants (PNG/JPG), brand guide (PDF), design reference screenshots (new question
  `reference_screenshots`). Batch upload is all-or-nothing; per-kind, count and size limits; delete from the summary screen.
- New API: `/files` (POST/GET), `/files/{id}` (GET/DELETE), `download?format=assets` (ZIP). Old `/logo` endpoints kept.
- Chosen HEX colors appear as swatches in the summary, DOCX (shaded cells) and PDF.
- Logos and screenshots are embedded in the DOCX/PDF design section.
- Chat: logo widget has logo and brand guide buttons; the paperclip opens a menu to choose the file type.
- 14 new tests; UI smoke-tested in headless Chrome.

## 4. Edit answers from the summary screen
- New `POST /sessions/{id}/answers`: change fields, page content or mark fields as open questions without going back to the chat.
  Values are validated exactly like chat answers; invalid values are never written. Blocked after confirmation (409).
- Fields that stop applying after a change are removed (e.g. existing-site link after switching to "new site"); if a change
  opens new questions, the next one is added to the chat and the summary shows a "Back to chat" notice.
- UI: pencil on every editable answer and page content, inline editor (dropdown + "Other", text box), "I will clarify with the developer".
- Fixes found while checking earlier sections: budget `kw: [1000]` (YAML ints) crashed keyword matching, which broke 29 tests;
  typing a `.az` link (e.g. https://atlas.az) was read as the language "AZ" and silently filled the languages field;
  the stale 2000-character test now matches the 4000 limit.
- 9 new tests (65 → 74), UI smoke-tested with jsdom against the live backend.

## 5. Notify on confirm (e-mail / Telegram)
- `app/notify.py`: on the first confirmation the agency gets a summary (project, site type, contact, budget range, open questions)
  plus the DOCX, by SMTP e-mail and/or Telegram. Runs as a background task after the response; each channel is independent,
  failures are only logged (token and password are redacted) and never break the client's confirmation. Repeated confirms do not resend.
- Header-injection safe subject; no config = nothing sent. 7 new tests.

## 6. Postgres
- `DATABASE_URL` accepts `postgres://` / `postgresql://` (auto-converted to psycopg 3), free-tier-friendly pool settings,
  pgbouncer-safe (`prepare_threshold=None`). `psycopg[binary]` added to requirements.
- Whole suite (86 tests) verified on a real Postgres as well as SQLite (`TEST_DATABASE_URL`).

## 7. The generated document: "Open questions" at the top + company header
- DOCX and PDF open with the agency banner (name, tagline, colour, optional logo), then a highlighted **Open questions** block
  *before* section 1, so the developer sees what to clarify first. Without open questions the block says so.
  Headings follow the session language (AZ / EN / RU). Everything inserted into the PDF is HTML-escaped.
- Configure via `AGENCY_NAME`, `AGENCY_TAGLINE`, `AGENCY_COLOR`, `AGENCY_LOGO_PATH` (default `static/agency-logo.png`, PNG/JPG).
  A missing or broken logo never breaks the document.
- Removed an unused duplicate translation key. 11 new tests (`tests/test_document.py`), PDF rendered and checked visually.

## 8. More modules and site templates
- 32 modules and 9 site types: news, school / education, directory and service / booking were added to the original four, with
  modules `events`, `timetable`, `courses`, `admissions`, `documents`, `listings`, `listing_detail`.
- Fixed while verifying: three YAML lines with unquoted commas inside `{az: ..., en: ...}` split the text into bogus keys.
  The **school** template crashed the chat as soon as the site type was chosen, and the `courses` / `documents` module
  descriptions were broken. All three are quoted now.
- New data-integrity tests: every module/template reference resolves, every title/description exists in AZ, EN and RU,
  no duplicate ids, each new site type starts a chat and offers its page structure.

## 9. Admin page (`/admin`)
- Off by default: with `ADMIN_TOKEN` empty, `/admin` and `/admin/api/*` answer 404 (the page does not even appear to exist).
  Set a long random token to turn it on (a warning is logged if it is shorter than 16 characters).
- Overview: session totals (active / confirmed / last 7 days), how many have open questions, average feedback,
  the **most-skipped questions** (what clients answer "I don't know" to most), LLM provider table (ok / fail / fail % / last error,
  worst first) and system info (database backend, e-mail / Telegram configured).
- Session list: filter by status, "only with open questions", search by project / e-mail / id, pagination.
- Session detail: open questions, the full TZ summary, the whole chat, uploaded files, versions, feedback; download DOCX / PDF / ZIP
  of files and delete the session (with its files) from the page.
- Security: token only in the `Authorization: Bearer` header (never in the URL), constant-time compare, 10 failed attempts per
  minute per IP then 429, `Cache-Control: no-store`, the page ships no data, and the UI writes every client-supplied string with
  `textContent` (checked in a real browser with `<script>` / `<img onerror>` payloads; a test forbids `innerHTML` in `admin.js`).
- Found while testing in the browser: the first version of the detail view threw because the DOM helper did not accept arrays.
- 18 new tests (119 in total).
