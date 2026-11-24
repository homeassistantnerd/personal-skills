---
name: fill-web-form
description: >-
  Scrape, answer, and fill web forms (Google Forms, Microsoft Forms, Typeform,
  Tally, custom HTML forms) using the built-in browser while leaving unknown or
  personal fields blank or asking the user first. Use when the user shares a
  form URL or asks to inspect, answer, or fill out an online form, quiz, or
  survey.
---

# Fill Web Form

Fill online forms accurately using a **scrape → resolve → input → verify** loop, keeping the same browser subagent tab open across turns and protecting personal or uncertain fields.

## 1. Open and Scrape the Form

Invoke the `browser` subagent (`Model: "flash"`) with the form URL:

1. **Gate checks:** If a login wall, permission prompt, or CAPTCHA/bot check appears, pause and ask the user to complete it directly in the browser pane, then resume via `send_message` to the same subagent.
2. **Responder vs. editor view:** On editor URLs (such as Google Forms `/edit`), verify whether it redirects to responder mode or opens an editor; read or preview the responder form without altering form structure.
3. **Full scrape of the current page/section:** Return the form title, description, and every visible field verbatim—label/prompt, field type (short text, paragraph, radio, checkbox, dropdown, grid, date, file upload), required status, all options, and any embedded tables, charts, or images. Leave the tab open and untouched.

## 2. Triage Fields and Resolve Answers

Before sending anything back to the browser subagent, classify every scraped item:

- **Solvable questions** (quiz, comprehension, data interpretation, objective prompts): Reason through each question carefully using the scraped text, tables, and chart descriptions, matching answers to exact option strings.
- **Personal information & unknown fields** (name, email, phone, ID numbers, addresses, credentials, subjective opinions, or anything you cannot verify): **Never guess or fabricate.**
  - If the user already specified to leave certain fields blank (or fill manually), keep them blank.
  - Otherwise, ask the user for the missing values—or confirm leaving them blank—before filling, especially if a required personal field blocks advancing to a "Next" page.

## 3. Input Answers in the Same Tab

Send the exact answer mapping to the **existing** `browser` subagent via `send_message`:

- Specify exact option labels or text values for every resolved field.
- Explicitly list which personal/unknown fields must remain blank.
- Keep submission manual by default: instruct the subagent **not** to click Submit (unless the user explicitly requested submission and every required field is resolved).
- **Multi-page / multi-section forms:** Fill the current section, click "Next" only if all required fields on that page are filled (ask the user first if a required personal field blocks advancing), then repeat Steps 1–3 for the newly revealed section.

## 4. Verify Before Reporting

Confirm in the subagent's report and `BROWSER_HOST_FACTS`:
- Every resolved field shows the exact intended selection or text.
- Excluded personal/unknown fields remain empty.
- The tab remains open on the form (unsubmitted unless requested) so the user can enter their personal details and submit.
