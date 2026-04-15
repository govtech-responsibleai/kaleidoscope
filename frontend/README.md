# Kaleidoscope Frontend

A comprehensive React + Next.js frontend application for **systematically evaluating LLM target applications**. Kaleidoscope provides an end-to-end evaluation workflow from question generation to human-in-the-loop annotation and multi-judge scoring, enabling rigorous assessment of target application accuracy and reliability.

The platform automates the creation of diverse evaluation questions across user personas, collects target application responses, performs claim-based accuracy evaluation using LLM judges, facilitates human annotation with judge assistance, and provides detailed metrics including judge alignment scores (F1, precision, recall) for validating evaluation quality.

## Features

- **Target Application Management**: Create and manage target applications with detailed configuration
- **Knowledge Base Management**: Upload, view, and manage documents (PDF, DOCX, TXT, MD) for each target with informational guidance text
- **Persona Generation**: Automatically generate user personas with Singapore contextualisation and audience handling, plus manual creation and Nemotron sampling
- **Question Generation**: Generate evaluation questions with configurable input style (brief/regular/detailed) and automatic web search context
- **Question Review**: Review newly generated questions with automatic similarity detection
- **Advanced Filtering**: Filter questions by persona, type (typical/edge), and scope (in KB/out of KB)
- **Snapshot Management**: Version control for target application iterations to track improvements over time
- **Answer Generation & Annotation**: Automated collection of target application responses with claim-based evaluation
- **Judge-Assisted Labeling**: Claim highlighting with explanations to assist human annotation
- **Custom Rubric Evaluation**: Define custom evaluation criteria (relevance, tone, etc.) with configurable options per target
- **Rubric Annotation**: Human annotation for custom rubrics alongside accuracy labeling
- **Multi-Judge Scoring**: Run multiple judge configurations for accuracy and rubric evaluation with category-based judge assignment
- **Judge Alignment Metrics**: F1 score, precision, recall comparing judge vs. human annotations (for both accuracy and rubric judges)
- **Label Overrides**: Manually correct aggregated accuracy labels when judge consensus is wrong
- **Results Export**: Export evaluation results to CSV or ZIP (with evaluator JSON) for analysis and reporting
- **Real-time Job Polling**: Automatic polling for generation, annotation, and scoring jobs with status updates

## Tech Stack

- **Framework**: Next.js 16 (App Router)
- **Language**: TypeScript
- **UI Library**: Material-UI (MUI) v7
- **Frontend Library**: React 19
- **HTTP Client**: Axios
- **Styling**: Material-UI components + Emotion CSS-in-JS
- **Data Visualization**: D3.js (for snapshot accuracy charts)
- **PDF Generation**: html2canvas + jsPDF (for report export)

## Prerequisites

- Node.js 18+
- npm or yarn
- Backend API running (see [kaleidoscope-backend](../kaleidoscope-backend))
- User account (created by admin via backend scripts)

## Getting Started

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure Environment

Create a `.env.local` file in the root directory:

```env
NEXT_PUBLIC_API_DOMAIN=http://localhost:8000
NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_DOMAIN}/api/v1

```

### 3. Start Development Server

```bash
npm run dev
```

The application will be available at [http://localhost:3000](http://localhost:3000)

**Note:** You'll be redirected to `/login`. Create a user account via the backend first:

```bash
curl -X POST http://localhost:8000/api/v1/auth/admin/create-user \
  -H "X-Admin-Key: <your-ADMIN_API_KEY-from-backend-.env>" \
  -H "Content-Type: application/json" \
  -d '{"username": "dev", "password": "yourpassword", "is_admin": false}'
```

See the [backend README](../kaleidoscope-backend/README.md) for full auth setup details.

### 4. Build for Production

```bash
npm run build
npm start
```

## Project Structure

```
kaleidoscope-frontend/
├── app/                          # Next.js App Router pages
│   ├── layout.tsx               # Root layout with MUI theme & navigation
│   ├── page.tsx                 # Home page (target list)
│   ├── globals.css              # Global CSS styles
│   ├── login/                   # Login page
│   │   └── page.tsx
│   ├── admin/                   # Admin panel
│   │   └── page.tsx
│   └── targets/[id]/            # Dynamic route for target details
│       ├── layout.tsx           # Target layout with tabs
│       ├── page.tsx             # Target overview (default tab)
│       ├── questions/
│       │   └── page.tsx         # Questions list & management
│       ├── annotation/
│       │   └── page.tsx         # Annotation workflow page
│       ├── scoring/
│       │   └── page.tsx         # Scoring & judge management page
│       ├── metrics/
│       │   └── page.tsx         # Detailed metrics & judge alignment
│       └── report/
│           └── page.tsx         # PDF report generation & export
├── components/                  # React components
│   ├── Navigation.tsx           # Sidebar navigation
│   ├── GenerateEvalsModal.tsx   # Modal for persona/question generation (with input style selector)
│   ├── personas/               # Persona generation components
│   ├── questions/              # Question generation components
│   ├── overview/                # Overview page components
│   │   ├── CreateTargetModal.tsx        # Modal for creating targets
│   │   ├── DocumentList.tsx             # Knowledge base document management
│   │   ├── SnapshotAccuracyChart.tsx    # D3.js chart for snapshot accuracy trends
│   │   └── LatestSnapshotMetricsCard.tsx # Latest snapshot metrics with judge reliability
│   ├── annotation/              # Annotation page components
│   │   ├── QAJobControl.tsx     # Start/pause/resume controls with status
│   │   ├── QAList.tsx           # List of Q&A items with claim highlighting
│   │   ├── QAItem.tsx           # Individual Q&A item
│   │   ├── QAContent.tsx        # Answer content renderer
│   │   ├── QAJobProgress.tsx    # Job progress indicator per question
│   │   ├── ClaimHighlighter.tsx # Highlights claims with tooltips
│   │   └── AnnotationForm.tsx   # Manual annotation form
│   ├── scoring/                 # Scoring page components
│   │   ├── JudgeCards.tsx       # Horizontal scrollable judge list
│   │   ├── JudgeCard.tsx        # Individual judge card with metrics (accuracy)
│   │   ├── RubricJudgeCard.tsx  # Judge card for custom rubric evaluation
│   │   ├── CreateJudgeDialog.tsx # Create/edit/duplicate judge modal
│   │   └── ResultsTable.tsx     # Aggregated results table with export
│   └── shared/                  # Shared components
│       ├── SnapshotHeader.tsx   # Snapshot selector/creator
│       └── CreateSnapshotDialog.tsx # Create snapshot modal
├── lib/                         # Utilities and configuration
│   ├── api.ts                  # Axios-based API client
│   ├── types.ts                # TypeScript type definitions
│   ├── constants.ts            # Application constants
│   └── theme.tsx               # Material-UI theme configuration
├── hooks/                       # Custom React hooks
└── public/                      # Static assets
```

## User Flow

The Kaleidoscope evaluation system follows a **3-phase workflow**: Question Generation → Annotation → Scoring.

---

### **Phase 1: Question Generation**

#### 1. Home Page
- Displays all target applications as cards
- Shows "Get Started" button if no applications exist
- Click "New Target" to create a new application
- Click on any target card to view details

#### 2. Create Target
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

#### 3. Target Overview (Default Tab)
- View target application details and metadata
- See key statistics:
  - Number of personas
  - Number of questions
  - Number of snapshots
  - Number of judges
- **Document Management**:
  - View list of uploaded documents with metadata
  - Upload additional documents
  - Delete existing documents
  - See document details (size, pages, upload date)
- **Snapshot Performance Tracking**:
  - View accuracy trends across snapshots with interactive D3.js bar chart
  - View aggregated accuracy based on majority vote from aligned judges with judge reliability indicators
- **Report Export**:
  - Download PDF report of overview with all metrics and visualizations
  - One-click export for sharing evaluation results
- Click "Delete Target" to remove the entire target
- Navigate to Questions, Annotation, or Scoring tabs

#### 4. Questions Page
- View all generated questions in a filterable table
- **Filter questions by**:
  - Persona (multi-select)
  - Type (typical/edge)
  - Scope (in KB/out of KB)
- Click "Generate Evals" to create new questions

#### 5. Generate Evaluations
- **Step 1: Select Personas**
  - System generates 5 initial personas automatically
  - Review persona details (title, info, style, use case)
  - Accept or reject personas before question generation
  - Generate more personas if needed (generates 5 more)
  - Click "Generate Questions" when ready

- **Step 2: Generate Questions**
  - Select **Input Style**: brief (terse, slang), regular (natural language), or detailed (professional)
  - System automatically runs web search for contextual grounding (indicator shown in UI)
  - System generates questions for selected personas
  - Real-time polling for job completion
  - Status updates displayed in modal
  - Automatically proceeds to review when complete

#### 6. Review Generated Questions
- **Automatic Similarity Detection**:
  - System checks new questions against existing ones
  - Shows similar questions side-by-side (0.7 threshold)
  - Helps prevent duplicate questions
- **Review workflow**:
  - Approve questions to add to question bank
  - Reject unwanted or duplicate questions
  - See similarity scores for context
- Questions page automatically refreshes after review

---

### **Phase 2: Annotation**

#### 7. Annotation Page
- **Create Snapshot**: Version control for target application iteration
  - Name the snapshot (e.g., "v1.0", "Production - Jan 2025")
  - Specify number of questions to evaluate (e.g., N=100)
  - System randomly selects N approved questions

- **Answer Generation & Claim Extraction**:
  - Click "Start" to begin QA job
  - System calls target application API to generate N answers
  - Automatically extracts claims from each answer
  - Real-time progress tracking per question

- **Baseline Judge Scoring**:
  - System runs baseline judge automatically after answer generation
  - Judge evaluates each claim against knowledge base
  - Aggregates claim scores to response-level accuracy
  - Shows loading indicators per Q&A item

- **Select Answers for Annotation**:
  - System auto-selects 20% of answers (minimum 1) for manual annotation
  - User can adjust selection as needed
  - Selected answers marked with "Selected for Annotation" badge

- **Judge-Assisted Annotation**:
  - Each selected answer displays:
    - **Claim Highlighting**: Claims highlighted in red (hallucinated) or green (accurate)
    - **Hover Explanations**: Tooltip shows judge's reasoning for each claim
    - **Judge's Overall Label**: Aggregated assessment (Accurate/Inaccurate)
  - User makes independent annotation decision (Yes/No)
  - **Rubric Annotation**: If custom rubrics are defined, annotate each rubric by selecting from its options
  - Submit all annotations when complete

- **Job Controls**:
  - Start/Pause/Resume controls for QA job
  - Status chips show job state (starting, generating_answers, processing_claims, scoring, completed)
  - Completed rows not re-evaluated on resume

---

### **Phase 3: Scoring**

#### 8. Scoring Page
- **Accuracy Judges**:
  - View all accuracy judges as cards (Baseline + custom judges)
  - Each judge card shows:
    - Judge name, model, and temperature settings
    - Run status with real-time progress
    - Two key metrics after completion:
      1. **Judge Reliability (F1 Score)**: Compares judge vs. human annotations on selected subset
      2. **Accuracy**: Percentage of accurate responses across all N answers
  - Create new judge with custom configuration
  - Duplicate and modify existing judges
  - Delete custom judges (baseline cannot be deleted)

- **Custom Rubric Judges**:
  - For each custom rubric defined on the target, a collapsible section shows assigned judges
  - Judges are assigned by category (e.g., `relevance` rubric shows relevance judges + common judges)
  - Each rubric judge card shows:
    - Accuracy (% of answers where the judge chose the best option)
    - Reliability (F1 score comparing judge vs. human rubric annotations)
  - Rubric score gauge shows aggregated performance across reliable judges via majority vote

- **Results Table**:
  - View all N Q&A pairs with scores
  - Columns: Question, Answer, Aggregated Accuracy (majority vote from reliable judges)
  - Hover over accuracy label to see judge breakdown
  - Manual label overrides for correcting judge consensus
  - Filter for disagreements between judges
  - Sort by various fields

- **Export Results**:
  - Export to CSV for external analysis (calls `GET /targets/snapshots/:snapshotId/export`)
  - Pass `?include_evaluators=true` to download a ZIP with the CSV plus judge-level JSON for deeper analysis

## API Integration

The frontend integrates with the Kaleidoscope backend API:

### Target Endpoints
- `POST /targets` - Create target
- `GET /targets` - List all targets
- `GET /targets/:id` - Get target details
- `PUT /targets/:id` - Update target
- `DELETE /targets/:id` - Delete target
- `GET /targets/:id/stats` - Get target statistics
- `GET /targets/:id/personas` - List personas for target
- `GET /targets/:id/questions` - List questions for target
- `GET /targets/:id/snapshots` - List snapshots for target

### Knowledge Base Document Endpoints
- `POST /targets/:id/knowledge-base/upload` - Upload documents (multipart/form-data)
- `GET /targets/:id/knowledge-base/documents` - List all documents for target
- `GET /targets/:id/knowledge-base/text` - Get compiled text from all KB documents
- `GET /knowledge-base/documents/:id` - Get specific KB document with text
- `DELETE /knowledge-base/documents/:id` - Delete KB document

### Job Endpoints
- `POST /jobs/personas` - Create persona generation job
- `POST /jobs/questions` - Create question generation job
- `GET /jobs?target_id={id}` - List jobs for target (query parameter)
- `GET /jobs/:id` - Get job status and details
- `GET /jobs/:id/personas` - Get personas from completed job
- `GET /jobs/:id/questions` - Get questions from completed job

### Persona Endpoints
- `GET /personas/:id` - Get single persona
- `PUT /personas/:id` - Update persona
- `POST /personas` - Manually create a persona
- `POST /personas/:id/approve` - Approve single persona
- `POST /personas/:id/reject` - Reject single persona
- `POST /personas/bulk-approve` - Approve multiple personas
- `POST /personas/sample-nemotron` - Sample general personas from Nemotron dataset
- `GET /personas/:id/questions` - List questions for persona

### Question Endpoints
- `GET /questions/:id` - Get single question
- `PUT /questions/:id` - Update question
- `POST /questions/:id/approve` - Approve single question
- `POST /questions/:id/reject` - Reject single question
- `POST /questions/bulk-approve` - Approve multiple questions
- `POST /questions/similar` - Find similar questions (batch)

### Snapshot Endpoints
- `POST /snapshots` - Create new snapshot
- `GET /snapshots/:id` - Get snapshot details
- `PUT /snapshots/:id` - Update snapshot
- `DELETE /snapshots/:id` - Delete snapshot
- `GET /snapshots/:id/stats` - Get snapshot statistics
- `GET /snapshots/:id/questions/approved/without-answers` - Get approved questions without answers for judge
- `GET /snapshots/:id/questions/approved/without-scores` - Get approved questions without scores for judge

### Answer Endpoints
- `POST /answers` - Generate answer for a question
- `GET /answers/:id` - Get answer by ID
- `DELETE /answers/:id` - Delete answer
- `GET /snapshots/:id/answers` - List all answers for snapshot
- `GET /answers/:id/scores/:judgeId` - Get answer scores from specific judge
- `GET /answers/:id/claims?judge_id={id}` - Get answer claims with scores
- `PUT /answers/:id/selection` - Update answer selection status
- `POST /answers/bulk-selection` - Bulk update answer selections
- `POST /snapshots/:id/answers/select-default` - Auto-select default answers for annotation

### Annotation Endpoints
- `POST /annotations` - Create annotation
- `POST /annotations/bulk` - Bulk create annotations
- `GET /snapshots/:id/annotations` - List annotations for snapshot
- `GET /snapshots/:id/annotations/completion-status` - Check annotation completion status
- `GET /answers/:id/annotations` - Get annotation for specific answer
- `GET /annotations/:id` - Get annotation by ID
- `PUT /annotations/:id` - Update annotation
- `DELETE /annotations/:id` - Delete annotation

### Custom Rubric Endpoints
- `GET /targets/:id/rubrics` - List all rubrics for target
- `POST /targets/:id/rubrics` - Create a rubric
- `PUT /targets/:id/rubrics/:rubricId` - Update a rubric
- `DELETE /targets/:id/rubrics/:rubricId` - Delete a rubric

### Judge Endpoints
- `POST /judges/seed` - Seed default judges
- `GET /judges` - List all judges
- `POST /judges` - Create custom judge
- `GET /judges/baseline` - Get baseline judge
- `GET /judges/available-models` - Get available models
- `GET /judges/by-category/:category` - Get judges for a rubric category
- `GET /judges/:id` - Get judge details
- `PUT /judges/:id` - Update judge configuration (if editable)
- `DELETE /judges/:id` - Delete judge (if editable)

### QA Job Endpoints
- `POST /snapshots/:id/qa-jobs/start` - Start accuracy QA jobs
- `POST /snapshots/:id/rubric-qa-jobs/start` - Start rubric evaluation jobs
- `POST /qa-jobs/pause` - Pause running QA jobs
- `GET /snapshots/:id/qa-jobs` - List QA jobs for snapshot
- `GET /qa-jobs/:id` - Get QA job details and status

### Annotation Endpoints
- `POST /annotations` - Create annotation
- `POST /annotations/bulk` - Bulk create annotations
- `GET /snapshots/:id/annotations` - List annotations for snapshot
- `GET /snapshots/:id/annotations/completion-status` - Check annotation completion status
- `GET /answers/:id/annotations` - Get annotation for specific answer
- `GET /annotations/:id` - Get annotation by ID
- `PUT /annotations/:id` - Update annotation
- `DELETE /annotations/:id` - Delete annotation
- `GET /answers/:id/rubric-annotations` - Get rubric annotations for an answer
- `PUT /answers/:id/rubric-annotations/:rubricId` - Upsert a rubric annotation

### Metrics & Export Endpoints
- `GET /snapshots/:id/judges/:judgeId/alignment` - Get judge alignment metrics (F1, precision, recall, accuracy)
- `GET /snapshots/:id/judges/:judgeId/accuracy` - Get judge accuracy on all responses
- `GET /snapshots/:id/judges/:judgeId/rubrics/:rubricId/alignment` - Rubric judge alignment (F1)
- `GET /snapshots/:id/judges/:judgeId/rubrics/:rubricId/accuracy` - Rubric judge accuracy
- `GET /snapshots/:id/results` - Get aggregated results with judge breakdown
- `GET /targets/snapshots/:id/export` - Export snapshot results (CSV by default; pass `?include_evaluators=true` to receive a ZIP with CSV + judge JSON)
- `GET /targets/:id/snapshot-metrics` - Get aggregated metrics for all snapshots of a target
- `GET /targets/:id/rubric-snapshot-metrics?snapshot_id=:id` - Get aggregated rubric metrics for a snapshot

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
    primary: { main: "#1d2766" },
    secondary: { main: "#dc004e" },
  },
});
```

## Development Notes

### Job Polling

The application uses real-time job polling for long-running operations (configurable in `lib/constants.ts`). The polling:
- **Persona/Question Generation**: Polls every 10 seconds until job completion
- **QA Jobs (Annotation)**: Polls for answer generation and baseline scoring progress
- **Judge Scoring**: Polls for individual judge evaluation progress
- Displays real-time status updates in the UI with progress indicators
- Automatically proceeds to next step or refreshes data on completion
- Cleans up polling interval on component unmount to prevent memory leaks

### Answer Scoring

All scores are **real values** calculated by LLM judges:
- **Claim-level scoring**: Each claim evaluated against knowledge base (accuracy judges)
- **Response-level scoring**: Holistic answer evaluation in a single LLM call
- **Rubric scoring**: Answer evaluated against custom criteria, judge selects from defined options
- **Judge metrics**: F1 score, precision, recall calculated from human annotations (for both accuracy and rubric judges)
- **Target accuracy**: Percentage of accurate responses across full evaluation set
- **Rubric scores**: Percentage of answers where judges chose the best option, aggregated via majority vote from reliable judges

### Document Upload

File upload implementation:
- Supports multiple file selection
- Accepted formats: PDF, DOCX, TXT, MD
- Client-side validation before upload
- Progress tracking for each file
- Sequential upload (not parallel)
- Error handling per file with user feedback
- Uses FormData for multipart/form-data requests

### Snapshot Metrics Visualization

The Overview page provides comprehensive performance tracking across snapshot iterations:

**Snapshot Accuracy Chart:**
- D3.js-powered interactive bar chart showing accuracy trends
- X-axis: Snapshot names
- Y-axis: Aggregated accuracy percentage (0-100%)

**Latest Snapshot Metrics Card:**
- Displays most recent snapshot's performance at a glance
- Shows aggregated accuracy percentage (majority vote from aligned judges)
- Judge reliability indicators:
  - **Green badge**: Reliable judges found (F1 ≥ 0.5)
  - **Warning badge**: No aligned judges (needs more annotation)
- Displays judge alignment range (min-max F1 scores)
- Shows count of reliable evaluators

**Metrics Calculation:**
- `aggregated_accuracy`: Percentage of accurate responses based on majority vote from judges with F1 ≥ 0.5
- `accurate_count` / `inaccurate_count` / `pending_count`: Breakdown by aggregated label
- `judge_alignment_range`: Min and max F1 scores of judges that aligned with human annotations
- `aligned_judges`: List of judges meeting the reliability threshold (F1 ≥ 0.5)
- Only judges with sufficient annotation alignment contribute to aggregated accuracy
- Same metrics structure applies to custom rubric evaluations (where "accurate" = judge chose the best option)

**PDF Report Export:**
- One-click export of entire overview page as PDF
- Includes all metrics, charts, and statistics

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

## Airbase Deployment

### Prerequisites
- [Airbase CLI](https://console.v2.airbase.sg/docs/get-started/installation) installed and configured

### Setup

1. Create a `.env.local` file in the root directory:
```env
NEXT_PUBLIC_API_DOMAIN=<your-public-api-url>
```

2. Build and deploy:
```bash
export TEAM_HANDLE=<your-team-handle>
export API_PROJECT_HANDLE=<your-project-handle>
export FE_PROJECT_HANDLE=<your-project-handle>

# Build the Docker image
docker build --platform linux/amd64 -f Dockerfile-airbase -t airbase-kaleidoscope-frontend .

# Deploy to Airbase
airbase container deploy \
--project $TEAM_HANDLE/$FE_PROJECT_HANDLE \
--image airbase-kaleidoscope-frontend 
```

To switch back to local development, set `NEXT_PUBLIC_API_DOMAIN` back to `http://localhost:8000`.

### Notes
- `middleware.ts` configures CSP (Content Security Policy) headers for Next.js. 

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

### QA Job stuck or failing
- Check browser console and backend logs for errors
- Verify target application API endpoint is accessible
- Ensure sufficient approved questions exist in target
- Try pausing and resuming the job
- Check if baseline judge is properly configured

### Annotation not saving
- Verify all selected answers have annotations
- Check browser console for API errors
- Ensure snapshot exists and is not deleted
- Verify annotation completion status endpoint is working

### Judge scoring not running
- Ensure annotations are completed first (required for F1 score calculation)
- Check judge configuration is valid (model, temperature, prompt)
- Verify LiteLLM backend is properly configured
- Review backend logs for LLM API errors
- Check if judge has sufficient context (knowledge base documents)

### Results export failing
- Verify snapshot has completed evaluations
- Check that at least one judge has finished scoring
- Ensure browser allows file downloads
- Check backend logs for export generation errors

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
The application uses a tabbed interface for target details with 6 main tabs:
- **Overview Tab**: Target metadata, statistics, and document management
- **Questions Tab**: Question list with filtering and generation
- **Annotation Tab**: Snapshot-based answer generation and human annotation
- **Scoring Tab**: Multi-judge evaluation and results export
- **Metrics Tab**: Detailed judge alignment metrics across snapshots
- **Report Tab**: PDF report generation and export of evaluation results

Navigation flow:
```
Home (/)
  ├─→ Login (/login)
  ├─→ Admin (/admin)
  └─→ Target Overview (/targets/[id])
        ├─→ Questions (/targets/[id]/questions)
        ├─→ Annotation (/targets/[id]/annotation)
        ├─→ Scoring (/targets/[id]/scoring)
        ├─→ Metrics (/targets/[id]/metrics)
        └─→ Report (/targets/[id]/report)
```

### State Management
- **Local component state** using React hooks (useState, useEffect)
- **No global state library** - data fetched fresh on page load
- **Polling mechanism** for async job tracking (persona, question, QA, and judge jobs)
- **Filter state** persists during session but not across page reloads
- **Snapshot selection** maintained across Annotation and Scoring pages

### Component Patterns
- **Modal dialogs** for create/generate workflows
- **Confirmation dialogs** for destructive actions
- **Loading states** with Material-UI CircularProgress and skeleton loaders
- **Empty states** with calls-to-action
- **Error boundaries** with try-catch and user feedback
- **Job status chips** for real-time status display
- **Claim highlighting** with hover tooltips for judge explanations
- **Card-based layouts** for judges and results visualization

### API Client Design
- Single Axios instance with base URL configuration
- Organized by resource (targets, jobs, personas, questions, documents, snapshots, answers, annotations, judges, QA jobs, metrics, rubrics, rubric QA jobs, rubric scores)
- Type-safe responses using TypeScript generics
- FormData support for file uploads
- Consistent error handling across all endpoints
- Polling utilities for long-running jobs

## License

[Your License Here]
