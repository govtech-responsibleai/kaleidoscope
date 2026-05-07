# kaleidoscope-docs — Agent Guide

Documentation site for Kaleidoscope, the Singapore Government's AI evaluation platform.
Separate from the product itself — this site hosts docs, guides, and a landing page that bridges
the open-source project and the gov-internal product.

---

## Site Purpose

| Audience | What they get |
|----------|---------------|
| Government agencies (product teams) | Access the live SG Gov product (restricted) |
| Open-source community / external | Open-source repo (GitHub) and public docs |

The docs site is **not** the product. It is a public-facing information and navigation layer.

---

## Site Structure

```
/                                  Landing page (src/pages/index.tsx + src/css/landing.css)

/docs/
  how-it-works.md                  Five-stage pipeline overview (standalone)

  getting-started/
    why-evaluate.md                Why systematic LLM evaluation matters
    quickstart.md                  Docker setup — clone, start, login

  user-guide.md                    End-to-end evaluation walkthrough (links to config pages)

  configuration/
    1_providers.md                   LLM providers
    2_environment_variables.md       Environment variables set up
    3_connect-your-target.md         Connecting your AI application (includes custom connectors)
    4_defining-rubrics.md            Defining evaluation rubrics
    5_creating-evaluation-set.md     Personas and question generation
    6_scoring-and-judges.md          Scoring, annotations, and judge reliability
    7_error-analysis.md              Interpreting results and improving
```

---

## Landing Page (`/`)

**Implementation**: `src/pages/index.tsx` + `src/css/landing.css`

**Goal**: Orient first-time visitors. Two exit paths only:

- **Left CTA** — "Read More" (→ `/docs/`) + "View on GitHub"
  (audience: developers, researchers, external contributors)
- **Right CTA** — "Find out more" → WOG evaluation platform
  (audience: government agencies with platform access)

**Hero section** conveys in one glance:
1. What Kaleidoscope is (AI evaluation tool)
2. Who built it (GovTech Singapore)
3. Three animated feature cards (Define Criteria, Generate & Test, Score)
4. Two paths forward (OSS docs vs. product)

No sign-in flow, no FAQ, no feature grid — those live on the product side.
Keep the landing page lightweight and navigational.

---

## Design System

Follow **GovTech Brand Guidelines (Oct 2025)**.
Stay visually cohesive with the landing page design tokens in `src/css/landing.css`:

| Token | Value |
|-------|-------|
| Primary accent | `#7c3aed` (violet-700) |
| Background | `#ffffff` |
| Text primary | `#0f172a` |
| Text muted | `#64748b` |
| Border | `#e2e8f0` |
| Accent bg | `#f5f3ff` |
| Font | Inter |
| Border radius | 8–12px cards, 999px pills |

GovTech PBGT logo lives at `static/img/govtech-logo.png`.
Kaleidoscope logo at `static/img/kaleidoscope-logo.png`.

---

## Links

| Destination | URL |
|-------------|-----|
| Open-source repo | https://github.com/govtech-responsibleai/kaleidoscope |
| Product landing page | (internal — configure per deployment env) |
| Interest registration form | https://form.gov.sg/69e83290aeb614f9009112a5 |

---

## Agent Conventions

### Writing Style
- Action-oriented, second person ("you"), concise
- Each page answers "what is this" AND "how do I use it" — no pure theory pages
- Open every page with a 1-2 sentence summary, then interleave explanation with practical steps
- Default to product-team language; add engineer-specific callouts where needed (e.g., custom connectors, backend claim-level rubrics)

### Navigation & Structure
- Pages within each section follow the evaluation journey (top to bottom)
- `how-it-works.md` is standalone at docs root — it's the foundational mental model, not nested
- Do not add navigation links to docs pages that don't exist yet

### Exclusions (do not include in public docs)
- Agency names or specific agency use cases
- WOG/AIBots connector internals or protocol details
- Internal deployment specifics (infra, cluster configs)

### Technical
- Do not replicate product features (pipeline UI, FAQ, feature grid) — link to product instead
- Static HTML or Next.js — match whatever framework is already in use
- No auth, no API calls, no global state needed on this site
- When adding new doc pages: update the Site Structure section above
