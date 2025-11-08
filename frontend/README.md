# Kaleidoscope Frontend

A React + Next.js frontend application for evaluating LLM applications. This application provides an intuitive interface for creating target applications, managing knowledge bases, generating evaluation personas and questions, and reviewing results.

## Features

- **Target Application Management**: Create and manage target applications with detailed configuration
- **Knowledge Base Management**: Upload, view, and manage documents (PDF, DOCX, TXT, MD) for each target
- **Persona Generation**: Automatically generate user personas for testing with approval workflow
- **Question Generation**: Generate evaluation questions based on selected personas
- **Question Review**: Review newly generated questions with automatic similarity detection
- **Advanced Filtering**: Filter questions by persona, type (typical/edge), and scope (in KB/out of KB)
- **Dashboard**: View target details, statistics, documents, and evaluation results
- **Real-time Job Polling**: Automatic polling for generation job completion with status updates

## Tech Stack

- **Framework**: Next.js 16 (App Router)
- **Language**: TypeScript
- **UI Library**: Material-UI (MUI) v7
- **Frontend Library**: React 19
- **HTTP Client**: Axios
- **Styling**: Material-UI components + Emotion CSS-in-JS

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
│   ├── layout.tsx           # Root layout with MUI theme & navigation
│   ├── page.tsx             # Home page (target list)
│   ├── globals.css          # Global CSS styles
│   └── targets/[id]/        # Dynamic route for target details
│       ├── layout.tsx       # Target layout with tabs
│       ├── page.tsx         # Target overview (default tab)
│       └── questions/
│           └── page.tsx     # Questions list & management
├── components/              # React components
│   ├── Navigation.tsx       # Sidebar navigation
│   ├── CreateTargetModal.tsx  # Modal for creating targets
│   ├── GenerateEvalsModal.tsx # Modal for persona/question generation
│   └── DocumentList.tsx     # Knowledge base document management
├── lib/                     # Utilities and configuration
│   ├── api.ts              # Axios-based API client
│   ├── types.ts            # TypeScript type definitions
│   ├── constants.ts        # Application constants
│   └── theme.tsx           # Material-UI theme configuration
├── hooks/                   # Custom React hooks
└── public/                  # Static assets
```

## User Flow

### 1. Home Page
- Displays all target applications as cards
- Shows "Get Started" button if no applications exist
- Click "New Target" to create a new application
- Click on any target card to view details

### 2. Create Target
- Fill in target application details:
  - Name (required)
  - Agency
  - Purpose
  - Target Users
  - API Endpoint
  - Knowledge Base Path (optional)
- **Optional**: Upload knowledge base documents (PDF, DOCX, TXT, MD)
  - Support for multiple files
  - Progress tracking for each file
- Click "Create" to save

### 3. Target Overview (Default Tab)
- View target application details and metadata
- See key statistics:
  - Accuracy (currently mocked)
  - Number of personas
  - Number of questions
- **Document Management**:
  - View list of uploaded documents with metadata
  - Upload additional documents
  - Delete existing documents
  - See document details (size, pages, upload date)
- Click "Delete Target" to remove the entire target
- Switch to "Questions" tab for question management

### 4. Questions Page
- View all generated questions in a filterable table
- **Filter questions by**:
  - Persona (multi-select)
  - Type (typical/edge)
  - Scope (in KB/out of KB)
- See question scores (currently mocked, 70-100%)
- Click "Generate Evals" to create new questions

### 5. Generate Evaluations
- **Step 1: Select Personas**
  - System generates 5 initial personas automatically
  - Review persona details (title, info, style, use case)
  - Accept or reject personas before question generation
  - Generate more personas if needed (generates 5 more)
  - Click "Generate Questions" when ready

- **Step 2: Generate Questions**
  - System generates 10 questions for selected personas
  - Real-time polling for job completion (10-second interval)
  - Status updates displayed in modal
  - Automatically proceeds to review when complete

### 6. Review Generated Questions
- **Automatic Similarity Detection**:
  - System checks new questions against existing ones
  - Shows similar questions side-by-side (0.7 threshold)
  - Helps prevent duplicate questions
- **Review workflow**:
  - Approve questions to add to question bank
  - Reject unwanted or duplicate questions
  - See similarity scores for context
- Questions page automatically refreshes after review

## API Integration

The frontend integrates with the Kaleidoscope backend API:

### Target Endpoints
- `POST /targets` - Create target (with optional document upload)
- `GET /targets` - List all targets
- `GET /targets/:id` - Get target details
- `GET /targets/:id/stats` - Get target statistics
- `DELETE /targets/:id` - Delete target

### Knowledge Base Document Endpoints
- `POST /targets/:id/kb-docs/upload` - Upload documents (multipart/form-data)
- `GET /targets/:id/kb-docs` - List all documents for target
- `GET /kb-docs/:id` - Get document details
- `DELETE /kb-docs/:id` - Delete document

### Persona Endpoints
- `POST /targets/:id/jobs/personas` - Create persona generation job
- `GET /jobs/:id/personas` - Get generated personas
- `POST /personas/bulk-approve` - Approve selected personas
- `POST /personas/:id/approve` - Approve single persona
- `POST /personas/:id/reject` - Reject single persona

### Question Endpoints
- `POST /targets/:id/jobs/questions` - Create question generation job (10 questions per job)
- `GET /jobs/targets/:id/questions` - Get questions for target
- `GET /jobs/:id` - Poll job status
- `POST /questions/find-similar` - Find similar questions (batch)
- `POST /questions/bulk-approve` - Approve multiple questions
- `POST /questions/:id/approve` - Approve single question
- `POST /questions/:id/reject` - Reject single question

### Job Endpoints
- `GET /jobs/:id` - Get job status and details
- `POST /targets/:id/jobs/personas` - Create persona generation job
- `POST /targets/:id/jobs/questions` - Create question generation job

## Configuration

### Constants (lib/constants.ts)

```typescript
APP_NAME = "Kaleidoscope"
JOB_POLLING_INTERVAL = 10000  // 10 seconds
DEFAULT_PERSONA_COUNT = 5
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
- Starts after persona or question generation is initiated
- Checks job status until completion or failure
- Displays real-time status updates in the UI
- Automatically proceeds to next step or refreshes data on completion
- Cleans up polling interval on component unmount

### Document Upload

File upload implementation:
- Supports multiple file selection
- Accepted formats: PDF, DOCX, TXT, MD
- Client-side validation before upload
- Progress tracking for each file
- Sequential upload (not parallel)
- Error handling per file with user feedback
- Uses FormData for multipart/form-data requests

### Similarity Detection

Question similarity features:
- Batch processing for efficiency (checks all new questions at once)
- 0.7 similarity threshold for flagging similar questions
- Shows side-by-side comparison during review
- Helps prevent duplicate or near-duplicate questions
- Powered by backend vector similarity search

### Question Filtering

Advanced filtering capabilities:
- **Persona filter**: Multi-select dropdown to filter by persona
- **Type filter**: Filter by typical vs edge case questions
- **Scope filter**: Filter by in-knowledge-base vs out-of-knowledge-base
- Filters persist during the session
- Real-time filter application (no "Apply" button needed)

### Error Handling

All API calls include comprehensive error handling:
- Try-catch blocks with console logging for debugging
- User-friendly error messages displayed via alerts
- Loading states to prevent duplicate requests
- Cleanup on component unmount to prevent memory leaks

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

- [ ] Real accuracy and scoring metrics from backend
- [x] Question approval/rejection workflow (implemented)
- [x] Advanced filtering by persona, type, and scope (implemented)
- [x] Document upload and management (implemented)
- [x] Similarity detection for questions (implemented)
- [ ] Question editing capabilities
- [ ] Persona editing and customization
- [ ] Export evaluation results (CSV, JSON, PDF)
- [ ] Batch operations for questions (bulk delete, bulk edit)
- [ ] Search functionality for questions and personas
- [ ] Question versioning and history
- [ ] Analytics and insights dashboard

## Troubleshooting

### Cannot connect to backend
- Ensure backend API is running on `http://localhost:8000`
- Check `NEXT_PUBLIC_API_URL` in `.env.local`
- Verify CORS is configured on the backend
- Check network tab in browser DevTools for failed requests

### Questions not appearing after generation
- Check browser console for errors
- Verify job completed successfully in backend logs
- Wait for polling to complete (check job status in modal)
- Refresh the page manually if needed
- Verify questions were approved (not rejected during review)

### Document upload failing
- Check file format is supported (PDF, DOCX, TXT, MD)
- Verify file size is within backend limits
- Check backend logs for processing errors
- Ensure target exists before uploading documents

### Similarity detection not working
- Verify backend vector search is configured
- Check that embeddings are being generated for questions
- Review backend logs for similarity calculation errors

### Filters not working on Questions page
- Ensure questions have the required metadata (persona, type, scope)
- Check browser console for JavaScript errors
- Clear browser cache and refresh
- Verify questions are loaded before applying filters

### Styling issues
- Clear Next.js cache: `rm -rf .next`
- Reinstall dependencies: `rm -rf node_modules && npm install`
- Check for Material-UI version conflicts
- Ensure Emotion is properly configured

## Architecture Notes

### Page Navigation
The application uses a tabbed interface for target details:
- **Overview Tab**: Target metadata, statistics, and document management
- **Questions Tab**: Question list with filtering and generation

Navigation flow:
```
Home (/)
  → Target Overview (/targets/[id])
  → Questions (/targets/[id]/questions)
```

### State Management
- **Local component state** using React hooks (useState, useEffect)
- **No global state library** - data fetched fresh on page load
- **Polling mechanism** for async job tracking
- **Filter state** persists during session but not across page reloads

### Component Patterns
- **Modal dialogs** for create/generate workflows
- **Confirmation dialogs** for destructive actions
- **Loading states** with Material-UI CircularProgress
- **Empty states** with calls-to-action
- **Error boundaries** with try-catch and user feedback

### API Client Design
- Single Axios instance with base URL configuration
- Organized by resource (targets, jobs, personas, questions, documents)
- Type-safe responses using TypeScript generics
- FormData support for file uploads
- Consistent error handling across all endpoints

## License

[Your License Here]
