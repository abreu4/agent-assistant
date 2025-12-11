# Job Application Agent Transformation Plan

## Overview
Transform the hybrid AI assistant from a 4-mode coding agent into a single-mode job application agent that reads emails, detects job postings, and tracks applications.

## User Requirements
- ✅ Remove all coding-specific functionality (4-mode → single "default" mode)
- ✅ Keep workspace RAG, repurpose for CV/documents indexing
- ✅ Add email RAG system for Gmail (extensible to other providers)
- ✅ Read-only email access with OAuth2 (persistent credentials)
- ✅ Detect and track job postings from emails
- ✅ Configurable path for documents directory

## Architecture Changes

### Current System
```
4-Mode System: local_default, local_code, remote_default, remote_code
├── Warmup tests all 4 mode combinations
├── Mode-based model locking and routing
└── Code-specific tools (execution, file writing)
```

### Target System
```
Single-Mode System: default only
├── Gmail → OAuth2 → Email RAG → Job Detection → SQLite DB
├── Documents (CV/Cover Letters) → Document RAG
└── LLM Agent with email/job/document tools
```

## Implementation Phases

### Phase 1: Simplify to Single Mode (Foundation)
**Goal:** Remove 4-mode complexity, establish clean baseline

**Files to Modify:**

1. **`config/config.yaml`**
   - Flatten `llm.local.available_models`: Remove `default` and `code` keys, merge into single list (keep only default models)
   - Flatten `llm.remote.available_models`: Same approach
   - Remove `llm.local.mode` field
   - Update routing: `last_successful_local_model` and `last_successful_remote_model` (remove mode suffixes)
   - Add new section:
     ```yaml
     job_agent:
       documents_path: ~/job_applications/documents
       email:
         provider: gmail
         check_interval_minutes: 30
         max_emails_per_sync: 100
         index_on_startup: true
       tracking:
         database_path: ~/.job_agent/jobs.db
     ```

2. **`src/agent/llm_system.py`** (Lines 28-34, 322-474)
   - Replace `_locked_models` dict → 2 simple fields: `_locked_local_model`, `_locked_remote_model`
   - Simplify `warmup()`: Remove mode loops, just test local then remote once
   - Remove mode parameter from `get_model(tier, mode)` → `get_model(tier)`
   - Update warmup methods to not take mode parameter
   - Remove mode-based sticky model logic

3. **`src/agent/router.py`** (Lines 19, 58)
   - Remove `TaskComplexity.CODE` enum value
   - Update classification prompt: Remove code-specific language, add job-related hints
   - Update `_simple_classify()`: Replace code keywords with job keywords (job, position, hiring, application, etc.)

4. **`src/utils/config.py`** (Lines 187-270)
   - Simplify `get_last_successful_model(tier)`: Remove mode_key complexity
   - Remove `get_local_mode()` and `set_local_mode()` methods (or make them no-ops)

5. **`src/service.py`** (Lines 253-259, 467-528)
   - Remove CLI commands: `mode <type>`, `showmode`
   - Simplify `_show_sticky_status()`: Show only 2 models (local, remote)
   - Simplify `_reset_sticky_models()`: Reset only 2 keys
   - Remove `_show_local_mode()` and `_switch_local_mode()` methods

6. **`src/agent/tools.py`** (Line 41-42)
   - Disable code execution: Set `tools.code_execution.enabled: false` in config

**Success Criteria:**
- Agent starts without 4-mode errors
- Single local and remote model lock correctly
- All existing functionality works (just simplified)

---

### Phase 2: Email Infrastructure (Gmail + RAG)
**Goal:** Implement Gmail OAuth2 and email indexing system
**Status:** ✅ COMPLETE (Finished: 2025-12-11)

**New Directory Structure:**
```
src/agent/email/
├── __init__.py
├── provider.py          # Abstract email provider interface
├── gmail_provider.py    # Gmail OAuth2 implementation
├── email_rag.py         # Email RAG system (parallel to workspace_rag)
└── job_detector.py      # Job posting detection logic
```

**Files to Create:**

1. **`src/agent/email/provider.py`** (NEW - ~100 lines)
   - Abstract base class `EmailProvider`
   - Define `Email` dataclass (id, sender, subject, body, date, labels, job metadata)
   - Methods: `authenticate()`, `fetch_emails()`, `is_authenticated()`
   - Extensible for future providers (Outlook, Yahoo)

2. **`src/agent/email/gmail_provider.py`** (NEW - ~200 lines)
   - Implement `GmailProvider(EmailProvider)`
   - OAuth2 flow using `google-auth-oauthlib`
   - Token storage: `~/.job_agent/gmail_token.pickle`
   - Credentials file: `~/.job_agent/gmail_credentials.json`
   - Read-only scope: `gmail.readonly`
   - Auto token refresh logic
   - Email parsing: handle multipart, HTML → text, metadata extraction

3. **`src/agent/email/email_rag.py`** (NEW - ~250 lines)
   - Based on `workspace_rag.py` structure
   - Class `EmailRAG` with similar interface
   - Use `DirectOllamaEmbeddings` (reuse existing)
   - Chroma collection: "emails" in `~/.job_agent/email_index`
   - Metadata: email_id, sender, subject, date, is_job_related, company, position
   - Methods: `index_emails()`, `search()`, `_email_to_document()`
   - Change detection: hash email ID + subject + body

4. **`src/agent/email/job_detector.py`** (NEW - ~200 lines)
   - Class `JobDetector`
   - Method `is_job_related(email)`: Keyword + pattern matching
   - Job keywords: job, position, opening, hiring, interview, application, etc.
   - Sender patterns: `@linkedin.com`, `@indeed.com`, `careers@`, `recruiting@`
   - Subject patterns: "job opening", "position available", "hiring"
   - Method `extract_metadata(email)`: Extract company, position, location, salary, job type
   - Regex patterns for metadata extraction

5. **`src/agent/email/__init__.py`** (NEW)
   - Exports for easy imports

**Dependencies to Add** (`requirements.txt`):
```
google-auth-oauthlib>=1.0.0
google-auth-httplib2>=0.1.0
google-api-python-client>=2.100.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
```

**Success Criteria:**
- Gmail OAuth2 flow completes successfully
- Token persists and refreshes automatically
- Emails fetch and parse correctly
- Email RAG indexes and searches work
- Job detection achieves >80% accuracy on test emails

---

### Phase 3: Job Tracking System
**Goal:** SQLite database for tracking job postings
**Status:** ✅ COMPLETE (Finished: 2025-12-11)

**Progress:**
- ✅ Directory created: `src/agent/tracking/`
- ✅ `database.py` - Complete & tested (381 lines)
- ✅ `manager.py` - Complete & tested (295 lines)
- ✅ `__init__.py` - Complete (11 lines)
- ✅ End-to-end testing - All tests passed

**New Directory Structure:**
```
src/agent/tracking/
├── __init__.py
├── database.py    # SQLite schema and queries
└── manager.py     # Orchestration: email sync + detection + tracking
```

**Files to Create:**

1. **`src/agent/tracking/database.py`** (NEW - ~150 lines)
   - Class `JobDatabase`
   - SQLite schema:
     ```sql
     jobs (
       id, email_id UNIQUE, company, position, location, salary,
       job_type, found_date, email_date, status, notes, application_link
     )
     ```
   - Methods: `add_job()`, `get_jobs(status, company, limit)`, `update_job_status()`
   - Default statuses: new, interested, applied, interviewing, rejected, archived
   - Indexes on company, status, found_date

2. **`src/agent/tracking/manager.py`** (NEW - ~150 lines)
   - Class `JobManager` - orchestrates full pipeline
   - Constructor: takes `EmailProvider`, `EmailRAG`, `JobDatabase`
   - Method `sync_emails()`: Fetch → Detect → Index → Track
   - Method `get_jobs()`: Query database
   - Method `update_job_status()`: Update tracking
   - Singleton pattern: `get_job_manager()`

3. **`src/agent/tracking/__init__.py`** (NEW)
   - Exports

**Success Criteria:**
- Jobs stored in SQLite correctly
- Metadata extracted and saved
- Duplicate detection works (email_id unique constraint)
- Status updates work
- Query filtering works (by status, company)

---

### Phase 4: Document RAG (Repurpose Workspace)
**Goal:** Index CV, cover letters, and application documents
**Status:** ✅ COMPLETE (Finished: 2025-12-11)

**Progress:**
- ✅ `document_rag.py` - Complete & tested (379 lines)
- ✅ PDF parsing support (pypdf)
- ✅ TXT/MD file support
- ✅ Semantic search tested and working
- ✅ Dependencies added to requirements.txt

**Files to Modify:**

1. **Create `src/agent/document_rag.py`** (Copy from `workspace_rag.py`)
   - Rename class: `WorkspaceRAG` → `DocumentRAG`
   - Change `workspace_dir` → `documents_dir` (from `config.job_agent.documents_path`)
   - Change `index_dir` → `~/.job_agent/document_index`
   - Change collection name: "workspace" → "documents"
   - Update file extensions: Focus on `.pdf`, `.docx`, `.txt`, `.md`
   - Remove code-specific extensions (`.py`, `.js`, `.ts`)
   - Add PDF parsing: Use `pypdf2`
   - Add DOCX parsing: Use `python-docx`
   - Singleton: `get_document_rag()`

**Dependencies to Add:**
```
pypdf2>=3.0.0
python-docx>=0.8.11
```

**Success Criteria:**
- CV and cover letters indexed
- PDF and DOCX files parsed correctly
- Semantic search returns relevant document chunks

---

### Phase 5: Tools Integration
**Goal:** Add email/job tools, remove code tools
**Status:** ✅ COMPLETE (Finished: 2025-12-11)

**Progress:**
- ✅ Modified `tools.py` - Updated tool loading (lines 29-45)
- ✅ Implemented `_get_document_rag_tools()` - 2 tools (search_documents, list_documents)
- ✅ Implemented `_get_email_job_tools()` - 4 tools (search_emails, list_jobs, get_job_details, update_job_status)
- ✅ Removed `WriteFileTool` - Read-only file operations
- ✅ All 10 tools tested and working

**Files to Modify:**

1. **`src/agent/tools.py`**

   **Remove:**
   - Code execution tool (already disabled via config)
   - `WriteFileTool` (too risky for email agent)

   **Update:**
   - `search_workspace` → `search_documents`
   - Update descriptions for job agent context
   - Keep: `ReadFileTool`, `ListDirectoryTool`, `web_search`

   **Add New Tools:**
   ```python
   @tool
   def search_emails(query: str, job_related_only: bool = False) -> str:
       """Search through emails semantically."""
       # Use EmailRAG.search()

   @tool
   def list_jobs(status: str = "new", limit: int = 20) -> str:
       """List tracked job postings."""
       # Use JobManager.get_jobs()

   @tool
   def get_job_details(job_id: int) -> str:
       """Get details of a specific job posting."""
       # Query database by ID

   @tool
   def update_job_status(job_id: int, status: str, notes: str = None) -> str:
       """Update job application status."""
       # Use JobManager.update_job_status()

   @tool
   def search_documents(query: str) -> str:
       """Search CV and cover letters."""
       # Use DocumentRAG.search()
   ```

2. **`config/config.yaml`** - Update tools section:
   ```yaml
   tools:
     file_operations:
       enabled: true  # Keep read-only operations
     workspace_rag:
       enabled: true
       auto_index_on_startup: true
     web_search:
       enabled: true
     code_execution:
       enabled: false  # Disable
   ```

**Success Criteria:**
- All 5 new email/job tools work correctly
- Document search returns CV content
- Code execution is disabled
- File writing is disabled or removed

---

### Phase 6: Workflow Integration
**Goal:** Connect all systems in main workflow
**Status:** ✅ COMPLETE (Finished: 2025-12-11)

**Progress:**
- ✅ Updated `workflow.py` initialize() - Document indexing on startup
- ✅ Added email sync to workflow startup (optional via config)
- ✅ Added 4 CLI commands: sync, jobs, job <id>, documents
- ✅ Implemented helper methods: _sync_emails, _list_jobs, _show_job_details, _list_documents
- ✅ Updated help message with new commands
- ✅ All commands tested and working

**Files to Modify:**

1. **`src/agent/workflow.py`** (initialize() method)

   Update initialization sequence:
   ```python
   async def initialize(self):
       # Warmup models (now simplified to 2 modes)
       await self.llm_system.warmup()

       # Build graph
       self.graph = self._build_graph()

       # Index documents (CV, cover letters)
       if config.get('job_agent.documents_enabled', True):
           from .document_rag import get_document_rag
           rag = get_document_rag()
           await self._index_documents_async(rag)

       # Sync emails on startup
       if config.get('job_agent.email.index_on_startup', True):
           from .tracking.manager import get_job_manager
           manager = get_job_manager()
           stats = await manager.sync_emails()
           logger.info(f"Email sync: {stats}")
   ```

2. **`src/service.py`** - Add new CLI commands:
   ```python
   # In run_cli_mode()

   if prompt == 'check-emails':
       await self._sync_emails()

   if prompt == 'jobs':
       self._list_jobs()

   if prompt == 'documents':
       self._list_documents()

   if prompt.startswith('job '):
       job_id = int(prompt.split()[1])
       self._show_job_details(job_id)
   ```

   Implement helper methods:
   - `_sync_emails()`: Trigger email sync manually
   - `_list_jobs()`: Show tracked jobs table
   - `_list_documents()`: Show indexed documents
   - `_show_job_details()`: Display full job info

**Success Criteria:**
- Agent initializes: models → documents → emails
- All CLI commands work
- Full pipeline works end-to-end
- Error handling is robust

---

## Critical Files Summary

### Files to Modify (11)
1. `config/config.yaml` - Flatten models, add job_agent config
2. `src/agent/llm_system.py` - Remove 4-mode system
3. `src/agent/router.py` - Remove CODE complexity
4. `src/utils/config.py` - Simplify mode management
5. `src/service.py` - Remove mode commands, add email/job commands
6. `src/agent/tools.py` - Add email/job tools, remove code tools
7. `src/agent/workflow.py` - Update initialize() for email/docs
8. `requirements.txt` - Add Gmail, PDF, DOCX dependencies
9. `README.md` - Complete rewrite for job agent
10. `.gitignore` - Add `.job_agent/` directory
11. `pyproject.toml` - Update description

### Files to Create (13)
1. `src/agent/email/__init__.py`
2. `src/agent/email/provider.py` - Abstract interface
3. `src/agent/email/gmail_provider.py` - Gmail OAuth2
4. `src/agent/email/email_rag.py` - Email indexing
5. `src/agent/email/job_detector.py` - Job detection
6. `src/agent/tracking/__init__.py`
7. `src/agent/tracking/database.py` - SQLite schema
8. `src/agent/tracking/manager.py` - Orchestration
9. `src/agent/document_rag.py` - CV/documents RAG
10. `docs/GMAIL_SETUP.md` - OAuth2 setup guide
11. `docs/JOB_TRACKING.md` - Usage guide
12. `docs/ARCHITECTURE.md` - System design doc
13. `migrate_config.py` - Config migration script (optional)

## Implementation Order

### Week 1: Foundation
1. **Phase 1** - Simplify to single mode
2. Test thoroughly - ensure no regressions

### Week 2: Email Core
3. **Phase 2** - Gmail provider + Email RAG
4. Test OAuth2 flow and email indexing

### Week 3: Job Tracking
5. **Phase 3** - SQLite database + Job manager
6. **Phase 4** - Document RAG
7. Test detection accuracy

### Week 4: Integration
8. **Phase 5** - Tools integration
9. **Phase 6** - Workflow integration
10. End-to-end testing
11. Documentation

## Key Design Decisions

1. **Single Mode Over 4-Mode**: Simplifies system, job tasks don't need code/default distinction
2. **OAuth2 with Persistence**: Store tokens in `~/.job_agent/`, auto-refresh
3. **Read-Only Email**: Safety first, can't accidentally send/delete emails
4. **SQLite for Tracking**: Simple, file-based, no external dependencies
5. **Extensible Providers**: Abstract `EmailProvider` allows adding Outlook/Yahoo later
6. **Parallel RAG Systems**: Email RAG and Document RAG are independent
7. **Keyword + Pattern Detection**: Balance between accuracy and simplicity for job detection

## Security & Privacy

- Gmail scope: `gmail.readonly` only
- Token storage: `~/.job_agent/` with 600 permissions
- Email data: Stored locally in Chroma (not sent to remote)
- No email sending capability
- Credentials file: User must provide from Google Cloud Console

## Testing Strategy

- **Unit Tests**: Each new module (email_rag, job_detector, database)
- **Integration Tests**: Full pipeline (fetch → detect → index → track)
- **Manual Testing**: OAuth flow, email sync, job listing, document search
- **Accuracy Testing**: Job detection on sample emails (target >80%)

## Rollback Plan

- Keep current implementation in git branch
- Test Phase 1 thoroughly before proceeding
- Each phase is independently testable
- Can deploy incrementally (simplification first, email later)

## Success Metrics

- ✅ Agent starts without errors
- ✅ Gmail OAuth completes and persists
- ✅ Emails sync and index correctly
- ✅ Job detection >80% accuracy
- ✅ Documents (CV) indexed and searchable
- ✅ All CLI commands functional
- ✅ End-to-end query: "Show me software engineer jobs from last week" works
