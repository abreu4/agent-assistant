# Gmail OAuth2 Setup Guide

This guide walks you through setting up Gmail OAuth2 credentials for the Job Application Agent.

## Prerequisites

- Gmail account
- Google Cloud account (free)

## Step 1: Create Google Cloud Project

1. Go to https://console.cloud.google.com
2. Click "Select a project" → "New Project"
3. Enter project name: "Job Application Agent"
4. Click "Create"

## Step 2: Enable Gmail API

1. In the project dashboard, go to "APIs & Services" → "Library"
2. Search for "Gmail API"
3. Click on "Gmail API"
4. Click "Enable"

## Step 3: Configure OAuth Consent Screen

1. Go to "APIs & Services" → "OAuth consent screen"
2. Select "External" user type
3. Click "Create"
4. Fill in required fields:
   - App name: "Job Application Agent"
   - User support email: your email
   - Developer contact: your email
5. Click "Save and Continue"
6. Click "Add or Remove Scopes"
7. Filter for Gmail, select: `https://www.googleapis.com/auth/gmail.readonly`
8. Click "Update" then "Save and Continue"
9. Add test users (your Gmail address)
10. Click "Save and Continue"

## Step 4: Create OAuth 2.0 Credentials

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. Application type: "Desktop app"
4. Name: "Job Application Agent"
5. Click "Create"
6. Download the JSON file (click the download icon)

## Step 5: Add Credentials to .env

The downloaded JSON contains your credentials. Extract these values:

```json
{
  "installed": {
    "client_id": "123456789-abc.apps.googleusercontent.com",
    "client_secret": "GOCSPX-your_secret_here",
    ...
  }
}
```

Add to your `.env` file (all on one line, no line breaks):

```bash
GMAIL_CLIENT_ID=123456789-abc.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=GOCSPX-your_secret_here
GMAIL_REDIRECT_URI=http://localhost:8080/
```

**Important:** The credentials must be on single lines with no line breaks!

## Step 6: Add Account in Agent

```bash
# Start the agent
python3 run_service.py

# Add account
❯ account add

# Browser will open automatically
# Sign in with your Gmail account
# Grant "Read-only" permission
# Browser will show "Authentication successful"
```

The agent will save your token to `~/.job_agent/accounts/{your_email}.token`

## Troubleshooting

### Error: "redirect_uri_mismatch"

**Cause:** Redirect URI doesn't match

**Solution:**
1. Ensure `.env` has exactly: `GMAIL_REDIRECT_URI=http://localhost:8080/`
2. If using a different URI, add it in Google Cloud Console:
   - Go to Credentials → Edit OAuth client
   - Add URI to "Authorized redirect URIs"

### Error: "invalid_grant"

**Cause:** Token expired or revoked

**Solution:**
```bash
# Remove and re-add account
❯ account remove your@email.com
❯ account add
```

### Error: "Access blocked: This app's request is invalid"

**Cause:** OAuth consent screen not configured properly

**Solution:**
1. Go to OAuth consent screen
2. Ensure status is "Testing" (not "In production")
3. Add your email to "Test users"

### Browser doesn't open

**Cause:** No DISPLAY environment variable (headless server)

**Solution:**
The agent will print the OAuth URL. Copy and paste into a browser on any machine.

## Security Notes

- **Scope**: Agent only has `gmail.readonly` permission (cannot send/delete emails)
- **Token Storage**: Tokens stored in `~/.job_agent/accounts/` with restrictive permissions
- **Auto-Refresh**: Tokens automatically refresh, no repeated logins needed
- **Revoke Access**: Go to https://myaccount.google.com/permissions to revoke

## Multi-Account Setup

You can add multiple Gmail accounts:

```bash
❯ account add
# Add first account

❯ account add
# Add second account

❯ accounts
# List all accounts

❯ account switch other@gmail.com
# Switch active account
```

Each account stores its own token and email index separately.
