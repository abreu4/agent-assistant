# Job Application Agent

An intelligent AI assistant that helps you manage job applications by automatically reading emails, detecting job postings, tracking applications, and querying your CV with semantic search.

## Features

- **Gmail Integration**: Multi-account OAuth2 with automatic job posting detection
- **Job Tracking**: SQLite database tracks positions from discovery to interview
- **Document RAG**: Semantic search through CV and cover letters (PDF/TXT support)
- **Intelligent Agent**: 10 specialized tools with local/remote LLM hybrid architecture
- **Privacy-First**: All data stored locally, read-only email access

## Quick Start

### 1. Install Dependencies

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull required models
ollama pull llama3.1:8b
ollama pull llama3.2:3b
ollama pull nomic-embed-text

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Setup Gmail OAuth2

1. Create Google Cloud Project at https://console.cloud.google.com
2. Enable Gmail API
3. Create OAuth 2.0 credentials (Desktop app)
4. Add credentials to `.env`:

```bash
GMAIL_CLIENT_ID=your-client-id.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=your-secret
GMAIL_REDIRECT_URI=http://localhost:8080/
```

See [docs/GMAIL_SETUP.md](docs/GMAIL_SETUP.md) for detailed instructions.

### 3. Run the Agent

```bash
# Start the service
python3 run_service.py

# Add Gmail account
❯ account add

# Sync emails and detect jobs
❯ sync

# List job postings
❯ jobs

# Ask about your experience
❯ What Python skills do I have?
```

## CLI Commands

**Account Management:**
- `accounts` - List configured Gmail accounts
- `account add` - Add new account (OAuth2 flow)
- `account remove <email>` - Remove account

**Job Management:**
- `sync` - Sync emails and detect job postings
- `jobs` - List tracked jobs
- `job <id>` - Show job details
- `documents` - List indexed documents

**Model Control:**
- `local` / `remote` / `auto` - Force model tier
- `models` - List available models
- `sticky` - Show model status

## Agent Tools

The AI agent has access to:
- **search_emails** - Semantic search through emails
- **list_jobs** - List jobs with filters
- **get_job_details** - Get full job info
- **update_job_status** - Update job status/notes
- **search_documents** - Search CV/cover letters
- **web_search** - Search the web
- **file operations** - Read files (read-only)

## Architecture

```
Gmail (OAuth2) → Job Detection → Email RAG + SQLite
                                      ↓
                              LangGraph Agent
                                      ↓
                          10 Specialized Tools
```

**Data Storage (Local Only):**
- Email index: `~/.job_agent/email_index/`
- Document index: `~/.job_agent/document_index/`
- Job database: `~/.job_agent/jobs.db`
- Account tokens: `~/.job_agent/accounts/`

## Configuration

Edit `config/config.yaml`:

```yaml
job_agent:
  documents_path: ~/job_applications/documents
  email:
    max_emails_per_sync: 100
    index_on_startup: false

llm:
  routing:
    force_model: local  # Use local models by default
```

## Documentation

- [GMAIL_SETUP.md](docs/GMAIL_SETUP.md) - Gmail OAuth2 setup
- [JOB_TRACKING.md](docs/JOB_TRACKING.md) - Job tracking workflow
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - System architecture
- [plans/job_agent_transformation.md](docs/plans/job_agent_transformation.md) - Transformation plan

## FAQ

**Q: Do I need API keys for remote models?**
A: No. Works entirely with local Ollama models. Remote models are optional.

**Q: Can I use Outlook/Yahoo?**
A: Not yet. Currently Gmail only.

**Q: Is my email data private?**
A: Yes. All data stays local. Gmail has read-only access. Emails never sent to remote APIs.

**Q: How do I backup my data?**
A: `cp -r ~/.job_agent ~/backup/`

## Requirements

- Python 3.11+
- Ollama
- 16GB RAM (8GB minimum)
- Gmail account + Google Cloud OAuth2 credentials

## License

[Specify your license here]

---

**Happy job hunting! 💼**
