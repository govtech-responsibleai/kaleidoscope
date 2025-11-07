# Kaleidoscope Frontend

A React + Next.js frontend application for evaluating LLM applications. This application provides an intuitive interface for creating target applications, generating evaluation personas and questions, and viewing results.

## Features

- **Target Application Management**: Create and manage target applications with detailed configuration
- **Persona Generation**: Automatically generate user personas for testing
- **Question Generation**: Generate evaluation questions based on selected personas
- **Dashboard**: View target details, statistics, and evaluation results
- **Real-time Job Polling**: Automatic polling for generation job completion

## Tech Stack

- **Framework**: Next.js 16 (App Router)
- **Language**: TypeScript
- **UI Library**: Material-UI (MUI) v6
- **HTTP Client**: Axios
- **Styling**: Material-UI components + CSS-in-JS

## Prerequisites

- Node.js 18+
- npm or yarn
- Backend API running (see [kaleidoscope-backend](../kaleidoscope-backend))

## Getting Started

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure Environment

Create a `.env.local` file in the root directory:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

### 3. Start Development Server

```bash
npm run dev
```

The application will be available at [http://localhost:3000](http://localhost:3000)

### 4. Build for Production

```bash
npm run build
npm start
```

## Project Structure

```
kaleidoscope-frontend/
├── app/                      # Next.js App Router pages
│   ├── layout.tsx           # Root layout with navigation
│   ├── page.tsx             # Home page (target list)
│   └── targets/
│       └── [id]/
│           └── page.tsx     # Target dashboard page
├── components/              # React components
│   ├── Navigation.tsx       # Sidebar navigation
│   ├── CreateTargetModal.tsx
│   └── GenerateEvalsModal.tsx
├── lib/                     # Utilities and configuration
│   ├── api.ts              # API client
│   ├── types.ts            # TypeScript types
│   ├── constants.ts        # App constants
│   └── theme.tsx           # Material-UI theme
└── public/                  # Static assets
```

## User Flow

### 1. Home Page
- Displays all target applications as cards
- Shows "Get Started" button if no applications exist
- Click "New Target" to create a new application

### 2. Create Target
- Fill in target application details:
  - Name (required)
  - Agency
  - Purpose
  - Target Users
  - API Endpoint
  - Knowledge Base Path
- Click "Create" to save

### 3. Target Dashboard
- View target application details
- See key statistics:
  - Accuracy (currently mocked)
  - Number of personas
  - Number of questions
- View list of generated questions with scores (currently mocked)
- Click "Generate Evals" if no data exists

### 4. Generate Evaluations
- **Step 1: Select Personas**
  - System generates 5 initial personas
  - Review persona details (title, info, style, use case)
  - Reject unwanted personas
  - Generate more personas if needed
  - Click "Generate Questions" when ready

- **Step 2: Generate Questions**
  - System generates questions for selected personas
  - Real-time polling for job completion
  - Automatically redirects when complete

## API Integration

The frontend integrates with the Kaleidoscope backend API:

### Target Endpoints
- `POST /targets` - Create target
- `GET /targets` - List all targets
- `GET /targets/:id` - Get target details
- `GET /targets/:id/stats` - Get target statistics

### Persona Endpoints
- `POST /targets/:id/jobs/personas` - Create persona generation job
- `GET /jobs/:id/personas` - Get generated personas
- `POST /personas/bulk-approve` - Approve selected personas

### Question Endpoints
- `POST /targets/:id/jobs/questions` - Create question generation job
- `GET /jobs/targets/:id/questions` - Get questions for target
- `GET /jobs/:id` - Poll job status

## Configuration

### Constants (lib/constants.ts)

```typescript
APP_NAME = "Kaleidoscope"
JOB_POLLING_INTERVAL = 10000  // 10 seconds
DEFAULT_PERSONA_COUNT = 5
DEFAULT_LLM_MODEL = "gpt-4o-mini"
```

### Theme (lib/theme.tsx)

Customize the Material-UI theme by editing `lib/theme.tsx`:

```typescript
export const theme = createTheme({
  palette: {
    primary: { main: "#1976d2" },
    secondary: { main: "#dc004e" },
  },
});
```

## Development Notes

### Mock Data

Currently, the following data is mocked:
- **Accuracy scores**: Fixed at 85.3% (dashboard)
- **Question scores**: Generated from question ID (70-100%)

These will be replaced with real data once the backend scoring service is implemented.

### Job Polling

The application polls job status every 10 seconds (configurable in `lib/constants.ts`). The polling:
- Starts after question generation is initiated
- Checks job status until completion or failure
- Automatically refreshes the dashboard on completion

### Error Handling

All API calls include error handling with console logging. Failed requests display user-friendly error messages.

## Scripts

```bash
# Development
npm run dev          # Start dev server with Turbopack

# Production
npm run build        # Build for production
npm start            # Start production server

# Linting
npm run lint         # Run ESLint
```

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## Future Enhancements

- [ ] Real accuracy and scoring metrics
- [ ] Question editing and approval workflow
- [ ] Persona editing and customization
- [ ] Export evaluation results
- [ ] Advanced filtering and search
- [ ] User authentication
- [ ] Real-time updates with WebSockets

## Troubleshooting

### Cannot connect to backend
- Ensure backend API is running on `http://localhost:8000`
- Check `NEXT_PUBLIC_API_URL` in `.env.local`
- Verify CORS is configured on the backend

### Questions not appearing after generation
- Check browser console for errors
- Verify job completed successfully in backend
- Refresh the page manually

### Styling issues
- Clear Next.js cache: `rm -rf .next`
- Reinstall dependencies: `rm -rf node_modules && npm install`

## License

[Your License Here]
