# Kaleidoscope Frontend

Next.js + React + MUI frontend for the Kaleidoscope LLM evaluation platform.

## Tech Stack

- **Framework**: Next.js 16 (App Router)
- **Language**: TypeScript (strict mode)
- **UI Library**: Material-UI (MUI) v7
- **Frontend Library**: React 19
- **HTTP Client**: Axios (via `lib/api.ts`)
- **Icons**: Tabler Icons (`@tabler/icons-react`)

## Project Structure

```
frontend/
├── app/                          # Next.js App Router pages
│   ├── layout.tsx                # Root layout (MUI theme, navigation)
│   ├── page.tsx                  # Home — target list
│   ├── login/page.tsx
│   ├── admin/page.tsx
│   └── targets/[id]/             # Dynamic target detail route
│       ├── layout.tsx            # Tabbed layout
│       ├── page.tsx              # Overview tab
│       ├── questions/page.tsx
│       ├── annotation/page.tsx
│       ├── scoring/page.tsx
│       ├── metrics/page.tsx
│       ├── rubrics/page.tsx
│       └── report/page.tsx
├── components/                   # Reusable React components
│   ├── Navigation.tsx
│   ├── personas/
│   ├── questions/
│   ├── overview/
│   ├── annotation/
│   ├── scoring/
│   └── shared/
├── lib/
│   ├── api.ts                    # All API calls — never use fetch() directly
│   ├── types.ts                  # TypeScript interfaces (mirror backend models)
│   ├── theme.tsx                 # MUI theme
│   ├── modelIcons.ts             # Provider logo mapping
│   └── constants.ts
├── hooks/                        # Custom React hooks
└── public/                       # Static assets
```

## Getting Started

```bash
npm install

# Create .env.local
NEXT_PUBLIC_API_DOMAIN=http://localhost:8000
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1

npm run dev   # http://localhost:3000
```

The backend must be running first. See the [backend README](../backend/README.md) for setup.

## Theme

Edit `lib/theme.tsx` to change the colour palette or typography.

```typescript
// lib/theme.tsx
export const theme = createTheme({
  palette: {
    primary: { main: "#1d2766" },
    secondary: { main: "#dc004e" },
  },
});
```

**Styling rules:**
- Use the `sx` prop with theme variables — `sx={{ p: 2, color: "primary.main" }}`
- Never use inline hex colours — reference theme palette instead
- Responsive: `sx={{ flexDirection: { xs: "column", md: "row" } }}`

## Icons

**UI icons** — import directly per component from `@tabler/icons-react`:
```typescript
import { IconCheck, IconPlus } from "@tabler/icons-react";
```
Browse available icons at [tabler.io/icons](https://tabler.io/icons).

**Model / provider logos** — centralised in `lib/modelIcons.ts`. Add new provider mappings there.

## API Integration

All API calls go through `lib/api.ts` (Axios). Never call `fetch()` directly.

## Troubleshooting

**Cannot connect to backend** — check `NEXT_PUBLIC_API_URL` in `.env.local`; verify backend is running on port 8000.

**Questions not appearing after generation** — wait for the polling cycle to complete, or refresh manually. Confirm questions were approved in the review step.

**QA Job stuck** — check backend logs. Verify the target API endpoint is reachable and approved questions exist in the snapshot.
