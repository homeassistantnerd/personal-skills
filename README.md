# Personal Skills Library

A personal library of reusable AI agent skills distilled from past LLM workflows, successful task patterns, and hard-won guardrails.

Each skill lives in its own folder under [`skills/`](./skills) using the standard `SKILL.md` format so it can be loaded on demand by Antigravity and compatible coding/browser agents.

## Skill Catalog

| Skill | What It Does | Path |
| :--- | :--- | :--- |
| [`fill-web-form`](./skills/fill-web-form/SKILL.md) | Scrape, answer, and fill web forms (Google Forms, Microsoft Forms, Typeform, etc.) via a two-phase browser workflow while leaving unknown or personal fields blank or asking the user first. | [`skills/fill-web-form/`](./skills/fill-web-form/SKILL.md) |
| [`obs-transcribe`](./skills/obs-transcribe/SKILL.md) | Extract & compress speech audio (<200MB) from large OBS recordings and transcribe in Vietnamese using Groq Whisper Large v3 for Google NotebookLM (imported from [`obs-to-transcript-skill`](https://github.com/homeassistantnerd/obs-to-transcript-skill)). | [`skills/obs-transcribe/`](./skills/obs-transcribe/SKILL.md) |

---

## Repository Structure

```text
personal-skills/
├── plugin.json                 # Antigravity plugin manifest (lets the whole library load as one bundle)
├── README.md                   # Library overview and skill catalog
├── templates/
│   └── skill-template/
│       └── SKILL.md            # Starter template for capturing new workflows
└── skills/
    └── <skill-name>/
        ├── SKILL.md            # Required: YAML frontmatter + step-by-step instructions
        ├── scripts/            # Optional: helper scripts
        ├── references/         # Optional: bulky docs or specs loaded on demand
        ├── examples/           # Optional: example inputs/outputs
        └── resources/          # Optional: templates or assets
```

---

## Using These Skills

### Option 1: Install the whole library as an Antigravity plugin
Clone this repository directly into your global plugins folder:

```bash
git clone https://github.com/homeassistantnerd/personal-skills.git ~/.gemini/config/plugins/personal-skills
```

On Windows (PowerShell):

```powershell
git clone https://github.com/homeassistantnerd/personal-skills.git "$env:USERPROFILE\.gemini\config\plugins\personal-skills"
```

Pulling updates (`git pull`) automatically keeps every skill in the library up to date.

### Option 2: Copy or link individual skills
Copy any folder from `skills/<skill-name>` into:
- **Global skills:** `~/.gemini/config/skills/<skill-name>`
- **Project-specific skills:** `<repo>/.agents/skills/<skill-name>`

---

## Adding a New Skill

When an LLM session produces a workflow worth keeping:

1. Copy [`templates/skill-template/SKILL.md`](./templates/skill-template/SKILL.md) to `skills/<skill-name>/SKILL.md` (lowercase, hyphenated directory name).
2. Set `name` to match `<skill-name>` and write a sharp `description` stating **what** the skill does and **when** an agent should trigger it.
3. Keep `SKILL.md` concise and procedural: ordered steps, clear completion criteria, explicit guardrails, and a verification step. Move long reference material into `references/`.
4. Add a row to the **Skill Catalog** table above and commit your changes.
