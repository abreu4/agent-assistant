# Changelog

## v2.0.0 - Job Application Agent (2025-12-11)

**Major transformation from coding assistant to job application management system.**

### 🎉 New Features

#### Email Integration
- **Gmail OAuth2**: Multi-account support with persistent authentication
- **Auto Job Detection**: LLM-powered parsing of job postings from emails
- **Email RAG**: Semantic search through email history
- **Smart Aggregator Detection**: Identifies LinkedIn, Indeed, Glassdoor emails

#### Job Tracking
- **SQLite Database**: Local job tracking with rich metadata
- **Status Management**: Track jobs from discovery through interview (6 statuses)
- **Notes System**: Add personal notes and follow-up reminders
- **Metadata Extraction**: Position, company, location, salary, job type, links

#### Document Management
- **Document RAG**: Semantic search through CV and cover letters
- **PDF Support**: Index and search PDF documents
- **TXT/Markdown**: Support for plain text and markdown documents
- **Experience Matching**: Query your own skills and experience

#### Agent Tools
- Added 6 new job-specific tools:
  - `search_emails` - Semantic email search
  - `list_jobs` - List tracked jobs with filters
  - `get_job_details` - Get full job information
  - `update_job_status` - Update job status and notes
  - `search_documents` - Search CV/cover letters
  - `list_documents` - Show indexed documents

#### CLI Commands
- `accounts` - List Gmail accounts
- `account add` - Add account (OAuth2)
- `account remove` - Remove account
- `account switch` - Switch active account
- `sync` - Manually sync emails
- `jobs` - List job postings
- `job <id>` - Show job details
- `documents` - List indexed documents

### 🔧 Changes

#### Removed Features
- GUI/hotkey system (CLI-only now)
- File writing capability (read-only for safety)
- Code execution (disabled for job agent)
- 4-mode system (simplified to single mode)
- Workspace RAG (replaced with Document RAG)

#### Modified Features
- **LLM Routing**: Simplified, removed code-specific classification
- **Tool System**: Refactored for job-specific use cases
- **Configuration**: New `job_agent` section in config.yaml

### 📚 Documentation

#### New Documentation
- `docs/GMAIL_SETUP.md` - Gmail OAuth2 setup guide
- `docs/JOB_TRACKING.md` - Job tracking workflow
- `docs/ARCHITECTURE.md` - System architecture
- `docs/plans/job_agent_transformation.md` - Complete transformation plan

#### Removed Documentation
- DOCKER.md, DOCKER_SETUP.md
- KEYBOARD_SHORTCUTS.md
- LOCAL_MODELS.md
- MODEL_SELECTION_GUIDE.md
- QUICK_REFERENCE.md
- RETRY_STRATEGY.md
- SETUP_GUIDE.md
- STATUS.md

### 🏗️ Architecture

**New Components:**
- `src/agent/email/` - Email integration (4 files)
  - `gmail_provider.py` - Gmail OAuth2 (342 lines)
  - `account_manager.py` - Multi-account (353 lines)
  - `email_rag.py` - Email indexing (467 lines)
  - `job_detector.py` - Job extraction (220 lines)

- `src/agent/tracking/` - Job tracking (2 files)
  - `database.py` - SQLite operations (381 lines)
  - `manager.py` - Orchestration (295 lines)

- `src/agent/document_rag.py` - Document RAG (379 lines)

**Modified Components:**
- `src/agent/tools.py` - Refactored for job tools
- `src/agent/workflow.py` - Added document/email indexing
- `src/service.py` - Added job CLI commands
- `README.md` - Complete rewrite for job agent

### 📦 Dependencies

#### Added
- `google-auth-oauthlib>=1.2.0` - Gmail OAuth2
- `google-auth-httplib2>=0.2.0` - Gmail HTTP
- `google-api-python-client>=2.100.0` - Gmail API
- `beautifulsoup4>=4.12.0` - HTML parsing
- `lxml>=5.0.0` - XML parsing
- `pypdf>=5.1.0` - PDF parsing

### 🗄️ Data Storage

All data now stored in `~/.job_agent/`:
- `jobs.db` - SQLite database
- `email_index/{account}/` - Per-account email RAG
- `document_index/` - CV/document RAG
- `accounts/` - OAuth2 tokens and registry

### 🔒 Security

- Read-only Gmail access (`gmail.readonly` scope)
- OAuth2 with automatic token refresh
- Local data storage only
- No email content sent to remote APIs
- File writing disabled
- Code execution disabled

### ⚡ Performance

- Email sync (100 emails): ~30-60 seconds
- Job extraction: ~2-3 seconds per email
- Document indexing: ~1-2 seconds per document
- Database queries: <10ms
- Semantic search: ~100-300ms

---

## v1.0.0 - Hybrid AI Assistant (2025-12-04)

Original coding assistant with GUI, hotkeys, and code execution capabilities.

**Note**: This version is now deprecated in favor of the job application agent.
