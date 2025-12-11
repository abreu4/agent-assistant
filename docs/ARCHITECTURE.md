# System Architecture

Technical architecture of the Job Application Agent.

## High-Level Overview

```
┌─────────────────────────────────────────────────────────┐
│                     User Interface                       │
│                 Interactive CLI (service.py)             │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────┐
│                  LangGraph Agent Workflow                │
│  (workflow.py: classify → route → agent → tools)        │
└──────────┬───────────────────────────────┬──────────────┘
           │                               │
┌──────────┴──────────┐        ┌──────────┴──────────────┐
│   LLM System        │        │    Agent Tools          │
│  (llm_system.py)    │        │    (tools.py)           │
│                     │        │                         │
│ • Local (Ollama)    │        │ • search_emails         │
│ • Remote (APIs)     │        │ • list_jobs             │
│ • Smart Routing     │        │ • update_job_status     │
│ • Model Locking     │        │ • search_documents      │
└─────────────────────┘        │ • web_search            │
                               │ • file operations       │
                               └───────┬─────────────────┘
                                       │
                    ┌──────────────────┴────────────────────┐
                    │                                       │
        ┌───────────┴──────────┐              ┌────────────┴─────────┐
        │  Email System        │              │  Document RAG        │
        │  (email/)            │              │  (document_rag.py)   │
        │                      │              │                      │
        │ • Gmail OAuth2       │              │ • PDF/TXT parsing    │
        │ • Multi-account      │              │ • Nomic embeddings   │
        │ • Email RAG          │              │ • Chroma vectorstore │
        │ • Job detection      │              │ • Semantic search    │
        └──────────┬───────────┘              └──────────────────────┘
                   │
        ┌──────────┴────────────┐
        │  Job Tracking         │
        │  (tracking/)          │
        │                       │
        │ • SQLite database     │
        │ • Job manager         │
        │ • Status tracking     │
        └───────────────────────┘
```

## Core Components

### 1. Agent Workflow (src/agent/workflow.py)

**LangGraph-based workflow with 4 stages:**

1. **Classify**: Determines task complexity using local 3B model
2. **Route**: Selects local vs remote model based on classification
3. **Agent**: Executes query with selected model + tools
4. **Tools**: Calls tools if needed, loops back to agent

**Key Features:**
- Multi-model retry with automatic failover
- Sticky model locking for consistency
- Context management (truncation for long conversations)
- Tool usage limiting (max 10 iterations)

### 2. LLM System (src/agent/llm_system.py)

**Hybrid architecture with intelligent routing:**

**Local Models (Ollama):**
- llama3.1:8b - Main reasoning model
- llama3.2:3b - Fast classifier
- nomic-embed-text - Embeddings

**Remote Models (Optional):**
- OpenRouter, Anthropic, Google, Groq
- Fallback chain: Native → OpenRouter → Local

**Model Locking:**
- Once a model succeeds, it becomes "locked" for that tier
- Subsequent queries use locked model (unless it fails)
- Improves consistency and performance

### 3. Email System (src/agent/email/)

#### Gmail Provider (gmail_provider.py)
- OAuth2 authentication with token auto-refresh
- Read-only Gmail scope (`gmail.readonly`)
- Supports multi-part emails (HTML → text conversion)
- Pagination for large mailboxes

#### Account Manager (account_manager.py)
- Multi-account support with JSON registry
- Per-account token storage
- Switch between accounts
- Token expiry handling

#### Email RAG (email_rag.py)
- Per-account vector databases
- Chroma vectorstore with nomic-embed-text
- Metadata: sender, subject, date, company, position
- Semantic search with filters (company, location)

#### Job Detector (job_detector.py)
- **Phase 1**: Heuristic filtering
  - Sender patterns: @linkedin.com, @indeed.com, careers@, recruiting@
  - Subject keywords: "job opening", "position", "hiring"

- **Phase 2**: LLM extraction
  - Uses local model to parse job details
  - Extracts: position, company, location, salary, job type, link
  - Returns structured JobPosting object

### 4. Job Tracking (src/agent/tracking/)

#### Database (database.py)
- SQLite with row_factory for dict returns
- Jobs table with rich metadata
- UNIQUE constraint on email_id (prevents duplicates)
- Indexes on company, status, found_date

**Schema:**
```sql
jobs (
    id, email_id UNIQUE, account_email, company, position,
    location, salary, job_type, found_date, email_date,
    status DEFAULT 'new', notes, application_link
)
```

#### Manager (manager.py)
- Orchestrates full pipeline:
  1. Fetch emails via provider
  2. Detect aggregator emails
  3. Extract job postings (LLM)
  4. Index emails in RAG
  5. Store jobs in database
- Returns sync statistics

### 5. Document RAG (src/agent/document_rag.py)

**Purpose:** Index and search CV/cover letters

**Processing Pipeline:**
1. Scan documents directory (`.pdf`, `.txt`, `.md`)
2. Extract text (pypdf for PDFs)
3. Chunk into 1000-char segments with 200-char overlap
4. Generate embeddings (nomic-embed-text)
5. Store in Chroma vectorstore

**Features:**
- Change detection (MD5 hashing)
- Incremental indexing
- Semantic similarity search
- File type filtering

### 6. Agent Tools (src/agent/tools.py)

**Tool Categories:**

**Email/Job Tools:**
- `search_emails(query, account, company, location)` - Semantic email search
- `list_jobs(status, company, limit)` - Query database
- `get_job_details(job_id)` - Retrieve full job info
- `update_job_status(job_id, status, notes)` - Update tracking

**Document Tools:**
- `search_documents(query, file_type)` - Search CV/cover letters
- `list_documents()` - Show indexed documents

**Utility Tools:**
- `read_file(path)` - Read files (read-only)
- `list_directory(path)` - Browse directories
- `search_files(pattern)` - Find files by glob
- `web_search(query)` - DuckDuckGo search

**Disabled for Safety:**
- `write_file` - Removed (read-only agent)
- `execute_code` - Disabled in config

## Data Flow

### Email Sync Flow

```
1. User: ❯ sync
2. CLI → _sync_emails()
3. JobManager.sync_emails()
4. GmailProvider.fetch_emails() → [Email objects]
5. JobDetector.is_aggregator_email() → filter
6. JobDetector.parse_jobs() → [JobPosting objects]
7. EmailRAG.index_email() → Chroma vectorstore
8. JobDatabase.add_job() → SQLite
9. Return stats to user
```

### Agent Query Flow

```
1. User: ❯ What Python jobs do I have?
2. CLI → AgentService.process_prompt()
3. HybridAgent.run(query)
4. Workflow:
   a. Classify (local 3B model) → complexity=SIMPLE
   b. Route → tier=local
   c. Agent (llama3.1:8b) → decides to use list_jobs tool
   d. Tools → list_jobs(status="new") → database query
   e. Agent → formats results
5. Return response to user
```

## Configuration System (src/utils/config.py)

**Hierarchical YAML configuration:**

```yaml
llm:
  local:
    base_url: http://localhost:11434
    available_models: [...]
  remote:
    available_models: [...]
  routing:
    prefer_local: true
    force_model: local
    user_force_model: local  # Persisted user preference

job_agent:
  documents_path: ~/job_applications/documents
  email:
    max_emails_per_sync: 100
    index_on_startup: false

tools:
  file_operations:
    enabled: true
  code_execution:
    enabled: false
```

**Features:**
- Nested config access: `config.get('job_agent.email.max_emails_per_sync')`
- Environment variable overrides
- Persistent model preferences
- Type-safe getters

## Storage Locations

All data stored in `~/.job_agent/`:

```
~/.job_agent/
├── jobs.db                           # SQLite database
├── email_index/
│   └── {account_email}/
│       ├── chroma.sqlite3           # Email vectorstore
│       └── {uuid}/                   # Embedding data
├── document_index/
│   ├── chroma.sqlite3               # Document vectorstore
│   └── {uuid}/                       # Embedding data
└── accounts/
    ├── registry.json                 # Account metadata
    └── {account_email}.token         # OAuth2 tokens
```

## Security & Privacy

**Email Access:**
- Read-only scope: `gmail.readonly`
- OAuth2 with refresh tokens
- Tokens stored with 600 permissions
- No passwords stored

**Data Privacy:**
- All processing happens locally
- Emails never sent to remote APIs
- LLM job extraction uses local models
- User queries may use remote models (if configured)

**Safety Features:**
- File writing disabled
- Code execution disabled
- Read-only file operations
- Sandboxed workspace directory

## Performance Characteristics

**Model Inference:**
- Local (llama3.1:8b): ~2-5 seconds/response
- Local (llama3.2:3b): ~1-2 seconds/classification
- Remote (API): ~1-3 seconds/response

**RAG Operations:**
- Document indexing: ~1-2 seconds per document
- Email indexing: ~0.5 seconds per email
- Semantic search: ~100-300ms

**Database:**
- Job queries: <10ms (indexed)
- Job insertion: <5ms

**Email Sync:**
- OAuth2 token refresh: <1 second
- Fetch 100 emails: ~5-10 seconds
- LLM extraction per email: ~2-3 seconds
- Total sync (100 emails, 5 jobs): ~30-60 seconds

## Extension Points

**Adding New Email Providers:**
1. Implement `EmailProvider` interface
2. Add to `account_manager.py`
3. Configure OAuth2 flow

**Adding New Tools:**
1. Define `@tool` function in `tools.py`
2. Add to `get_agent_tools()` return list
3. Agent automatically discovers and uses

**Custom LLM Providers:**
1. Add to `llm.remote.available_models` in config
2. Add API key to `.env`
3. System handles fallback automatically

## Dependencies

**Core:**
- langchain==0.3.13
- langgraph==0.2.58
- pydantic==2.10.3

**LLM:**
- langchain-ollama==0.2.0
- langchain-openai==0.2.14

**Email:**
- google-auth-oauthlib>=1.2.0
- google-api-python-client>=2.100.0
- beautifulsoup4>=4.12.0

**RAG:**
- chromadb (via langchain-community)
- pypdf>=5.1.0

**Utilities:**
- pyyaml==6.0.2
- python-dotenv==1.0.1
