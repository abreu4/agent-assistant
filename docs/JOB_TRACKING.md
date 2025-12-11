# Job Tracking Workflow

Guide to using the job tracking features of the Job Application Agent.

## Overview

The agent automatically:
1. Fetches emails from your Gmail account(s)
2. Detects job-related emails (LinkedIn, Indeed, etc.)
3. Extracts job posting details using LLM
4. Stores jobs in SQLite database
5. Indexes emails for semantic search

## Email Sync

### Manual Sync

```bash
❯ sync
```

This will:
- Fetch recent emails (default: last 30 days)
- Detect job aggregator emails
- Extract job postings
- Store in database
- Show summary (emails processed, jobs found)

### Automatic Sync on Startup

Edit `config/config.yaml`:

```yaml
job_agent:
  email:
    index_on_startup: true  # Sync emails when agent starts
```

### Configuration

```yaml
job_agent:
  email:
    check_interval_minutes: 30    # For future scheduled syncs
    max_emails_per_sync: 100      # How many emails to fetch
```

## Viewing Jobs

### List Jobs

```bash
# List new jobs (default)
❯ jobs

# Using the agent
❯ Show me all new job postings
❯ List jobs that I applied to
```

### View Job Details

```bash
# Direct command
❯ job 1

# Using the agent
❯ Show me details for job 1
❯ What's the salary for job 2?
```

## Job Statuses

Jobs can have these statuses:
- **new** - Just discovered, not reviewed yet
- **interested** - Reviewed, considering applying
- **applied** - Application submitted
- **interviewing** - In interview process
- **rejected** - Application rejected or not pursuing
- **archived** - Old/irrelevant

## Updating Job Status

Use the agent's natural language interface:

```bash
# Mark as interested
❯ Update job 1 to interested

# Mark as applied with notes
❯ Update job 2 status to applied with note "Submitted via company website"

# Add interview notes
❯ Update job 3 to interviewing with note "First interview scheduled for Friday"

# Archive old jobs
❯ Update job 5 to archived
```

The agent uses the `update_job_status` tool automatically.

## Searching Jobs

### Search by Agent

```bash
# Search for specific roles
❯ Show me Python developer jobs

# Search by location
❯ Are there any remote jobs?

# Search by company
❯ Do we have any jobs from Google?

# Complex queries
❯ Show me senior engineer positions with salaries over $120k
```

The agent uses `search_emails` and `list_jobs` tools.

### Direct Database Query (Advanced)

```bash
sqlite3 ~/.job_agent/jobs.db

# List all jobs
SELECT position, company, status FROM jobs ORDER BY found_date DESC;

# Filter by status
SELECT * FROM jobs WHERE status='applied';

# Search by company
SELECT * FROM jobs WHERE company LIKE '%Google%';

# Jobs with salary info
SELECT position, company, salary FROM jobs WHERE salary IS NOT NULL;
```

## Job Detection

### What Gets Detected

The agent looks for:
- **Aggregator emails**: LinkedIn, Indeed, Glassdoor, ZipRecruiter
- **Direct company emails**: careers@, recruiting@, jobs@
- **Keywords**: "job opening", "position available", "now hiring", "interview"

### What Gets Extracted

For each job, the LLM tries to extract:
- Position title
- Company name
- Location (city, state, remote/hybrid)
- Salary range
- Job type (full-time, contract, internship)
- Application link
- Email date

### False Positives/Negatives

**False Positives** (non-jobs detected):
- Mark as archived: `❯ Update job X to archived`

**Missing Jobs**:
1. Check if you're subscribed to job alert emails
2. Increase sync range: `max_emails_per_sync: 200`
3. Check logs for detection issues

## Data Storage

All job data is stored locally:

```
~/.job_agent/
├── jobs.db                    # SQLite database
├── email_index/
│   └── {account}/            # Per-account email RAG
│       └── chroma.sqlite3
└── accounts/
    └── {account}.token       # OAuth tokens
```

### Database Schema

```sql
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY,
    email_id TEXT UNIQUE,
    account_email TEXT,
    company TEXT,
    position TEXT,
    location TEXT,
    salary TEXT,
    job_type TEXT,
    found_date TEXT,
    email_date TEXT,
    status TEXT DEFAULT 'new',
    notes TEXT,
    application_link TEXT
);
```

## Backup & Export

### Backup Database

```bash
# Backup everything
cp -r ~/.job_agent ~/backup/job_agent_$(date +%Y%m%d)

# Backup just the database
cp ~/.job_agent/jobs.db ~/backup/
```

### Export to CSV

```bash
sqlite3 -header -csv ~/.job_agent/jobs.db "SELECT * FROM jobs;" > jobs_export.csv
```

### Export JSON

```bash
sqlite3 ~/.job_agent/jobs.db <<EOF
.mode json
.output jobs_export.json
SELECT * FROM jobs;
.quit
EOF
```

## Best Practices

1. **Sync Regularly**: Run `sync` daily or enable `index_on_startup`
2. **Update Status**: Keep job statuses current for accurate tracking
3. **Add Notes**: Use notes for interview details, contacts, follow-ups
4. **Archive Old Jobs**: Clean up to reduce noise
5. **Backup Weekly**: Backup `~/.job_agent/` to prevent data loss

## Tips

- **Use natural language**: The agent understands conversational queries
- **Ask for analysis**: "What types of jobs am I seeing most often?"
- **Track application progress**: Use statuses to manage your pipeline
- **Compare with your CV**: "Do I have the skills for job 3?"
- **Research companies**: "What do you know about the company for job 5?"

## Troubleshooting

### No Jobs Detected

1. Verify you're subscribed to job alerts (LinkedIn, Indeed, etc.)
2. Check emails are in the correct account: `accounts`
3. Increase emails scanned: Edit `max_emails_per_sync` in config
4. Check detection manually: Read email and look for job keywords

### Jobs Missing Information

The LLM extraction may fail for poorly formatted emails. You can:
- View the original email to get missing info
- Manually edit the database (advanced)

### Duplicate Jobs

The system prevents duplicates by `email_id`. If you see duplicates:
- They came from different emails
- You can archive one: `❯ Update job X to archived`
