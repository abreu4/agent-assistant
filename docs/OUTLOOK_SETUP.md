# Microsoft Outlook Email Integration Setup

## Overview

This guide walks you through setting up Microsoft Outlook (Outlook.com) email integration for the job tracking system using Microsoft Graph API and OAuth2 authentication.

## Prerequisites

- A Microsoft personal account (Outlook.com, Hotmail, Live, etc.)
- Python 3.8+ with `msal` package installed
- Access to Azure Portal

## Azure App Registration

### Step 1: Access Azure Portal

1. Go to [Azure Portal](https://portal.azure.com)
2. Sign in with your Microsoft account
3. Navigate to **Azure Active Directory** > **App registrations**

### Step 2: Create New App Registration

Click **"New registration"** and configure:

**Basic Information:**
- **Name**: `Job Agent - Outlook Integration` (or any descriptive name)
- **Supported account types**: Select **"Personal Microsoft accounts only"**
  - ⚠️ **Important**: Do NOT select "Accounts in any organizational directory"
  - This restricts the app to personal Outlook.com/Hotmail/Live accounts

**Redirect URI:**
- Platform: **Public client/native (mobile & desktop)**
- URI: `http://localhost`
  - ⚠️ **Important**: Use exactly `http://localhost` (no port, no trailing slash)

Click **Register**

### Step 3: Copy Application (Client) ID

1. After registration, you'll see the **Overview** page
2. Copy the **Application (client) ID** (UUID format)
3. Add it to your `.env` file:
   ```bash
   OUTLOOK_CLIENT_ID=your-client-id-here
   ```

**Note**: Personal accounts using MSAL PublicClientApplication do NOT need a Client Secret.

### Step 4: Configure API Permissions

1. Click **API permissions** in the left sidebar
2. Click **Add a permission**
3. Select **Microsoft Graph**
4. Select **Delegated permissions**
5. Add these permissions:
   - ✅ `Mail.Read` - Read user mail
   - ✅ `User.Read` - Read user profile
6. Click **Add permissions**

**Note**: You do NOT need admin consent for personal accounts with these read-only permissions.

### Step 5: Verify Configuration

Your app registration should have:
- ✅ Name: Job Agent - Outlook Integration
- ✅ Supported accounts: Personal Microsoft accounts only
- ✅ Redirect URI: http://localhost (Public client)
- ✅ API permissions: Mail.Read, User.Read (Delegated)
- ✅ Application (client) ID copied to .env

## Using the Integration

### Add an Outlook Account

1. Start the application:
   ```bash
   python -m src.cli
   ```

2. Add an account:
   ```
   account add
   ```

3. Select provider:
   ```
   Select email provider:
   1. Gmail
   2. Outlook (Outlook.com)

   Enter choice (1-2): 2
   ```

4. Browser will open for authentication
   - Sign in with your Outlook.com account
   - Grant permissions when prompted
   - Browser will show "Authentication complete" message

5. Account is now added and enabled for syncing

### Manage Accounts

**List accounts:**
```
accounts
```

**Sync all enabled accounts:**
```
sync
```

**Disable account (skip during sync):**
```
account disable user@outlook.com
```

**Re-enable account:**
```
account enable user@outlook.com
```

**Remove account completely:**
```
account remove user@outlook.com
```

## Troubleshooting

### Error: "AADSTS700016: Application not found"

**Cause**: Client ID is incorrect or app doesn't exist

**Fix**:
1. Verify the Application (client) ID from Azure Portal
2. Ensure it matches exactly in your `.env` file
3. Check that the app registration wasn't deleted

### Error: "AADSTS50011: Redirect URI mismatch"

**Cause**: Redirect URI not configured correctly in Azure

**Fix**:
1. Go to Azure Portal > App registrations > Your app
2. Click **Authentication**
3. Ensure redirect URI is exactly `http://localhost` (no port, no trailing slash)
4. Platform should be "Public client/native"

### Error: "Token acquisition failed"

**Cause**: Missing permissions or incorrect account type

**Fix**:
1. Verify API permissions (Mail.Read, User.Read) are added
2. Confirm app is configured for "Personal Microsoft accounts only"
3. Try removing and re-adding the account

### Error: "Account not supported"

**Cause**: Trying to use a work/school Microsoft 365 account

**Fix**: This integration only supports personal Outlook.com accounts. Work accounts would require:
- Different authority URL
- Potentially admin consent
- Multi-tenant app configuration

## Supported Account Types

### ✅ Supported (Personal Accounts)
- @outlook.com
- @hotmail.com
- @live.com
- @msn.com

### ❌ Not Supported (Work/School Accounts)
- @company.com (Microsoft 365)
- Organizational accounts
- Azure AD accounts

## API Rate Limits

Microsoft Graph API has these throttling limits for personal accounts:

- **Rate limit**: 10,000 requests per 10 minutes per user
- **Batch size**: Up to 20 requests per batch
- **Email fetch**: Up to 999 emails per request ($top parameter)

For typical job tracking use (100-1000 emails per sync), you won't hit these limits.

## Security Notes

- **Client ID is not secret**: Safe to commit to source control (though we keep it in .env)
- **Tokens are stored locally**: `~/.job_agent/accounts/{email}.token`
- **Read-only access**: Application can only read emails, not send or modify
- **Token refresh**: Access tokens are automatically refreshed using refresh tokens
- **Automatic expiration**: Tokens expire after inactivity (usually 90 days)

## Data Privacy

- **Local processing**: All email processing happens locally on your machine
- **No external services**: Emails are not sent to any third-party services
- **Microsoft Graph API**: Only used for fetching emails via OAuth2
- **Token storage**: Tokens stored in local pickle files (encrypted by OS permissions)

## Next Steps

After setup:
1. ✅ Add your Outlook account
2. ✅ Run `sync` to fetch recent emails
3. ✅ Use `jobs` to see detected job postings
4. ✅ Manage multiple accounts (Gmail + Outlook) simultaneously

## Advanced Configuration

### Custom Query Filters

Edit `config/config.yaml` to customize email fetching:

```yaml
job_agent:
  email:
    outlook:
      # Add custom Graph API filters here
      query_filter: "receivedDateTime ge 2025-01-01T00:00:00Z"
```

### Multiple Accounts

You can add multiple Outlook accounts:

```
account add  # Add first Outlook account
account add  # Add second Outlook account
sync        # Syncs both accounts
```

### Disable Specific Accounts

Temporarily disable accounts without removing them:

```
account disable user1@outlook.com  # Skip during sync
account disable user2@gmail.com     # Works for both providers
sync                                # Only syncs enabled accounts
```

## Support

For issues:
1. Check troubleshooting section above
2. Verify Azure app registration settings
3. Check application logs for detailed error messages
4. Ensure `msal` package is installed: `pip install msal>=1.24.0`

## References

- [Microsoft Graph API Documentation](https://docs.microsoft.com/en-us/graph/overview)
- [MSAL Python Documentation](https://msal-python.readthedocs.io/)
- [Azure App Registration Guide](https://docs.microsoft.com/en-us/azure/active-directory/develop/quickstart-register-app)
