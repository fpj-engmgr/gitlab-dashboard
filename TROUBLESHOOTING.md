# Troubleshooting Guide

## 403 Errors on Subprojects

If you're seeing many 403 errors when fetching data from GitLab, here are the steps to resolve them:

### 1. Check Your GitLab Token Permissions

Your personal access token needs the correct scopes:

1. Go to https://gitlab.com/-/user_settings/personal_access_tokens
2. Find your token or create a new one
3. Ensure these scopes are selected:
   - ✅ `read_api` - Required to read project data
   - ✅ `read_repository` - Required to read commits

### 2. Verify Group/Project Access

The 403 errors occur when your GitLab account doesn't have access to certain projects within the group tree.

**Check your access:**
1. Go to https://gitlab.com/redhat/rhel-ai
2. Browse the subgroups and projects
3. Verify you can see all the projects listed
4. If you can't see a project, you don't have access to it

**Request access:**
- Ask your GitLab group administrator to grant you at least **Reporter** role on the projects
- Reporter role gives read-only access which is all you need for the dashboard

### 3. Understanding the Error Messages

The dashboard now logs detailed information about skipped projects:

```
WARNING - No access to project <project-name> (ID: 12345) - skipping
INFO - Skipped 5 projects due to access restrictions
```

**This is normal behavior** - the dashboard will:
- ✅ Skip projects you don't have access to
- ✅ Continue fetching data from accessible projects  
- ✅ Display metrics only for the projects you can access

### 4. Filter to Accessible Projects Only

If you want to reduce noise, you can configure the dashboard to only query specific projects:

**Option A: Use a different group path**
If all your team's projects are in a specific subgroup:
```bash
# In .env
GITLAB_GROUP=redhat/rhel-ai/your-subgroup
```

**Option B: Accept the 403s**
- The dashboard handles these gracefully
- You'll only see metrics for projects you have access to
- This is the simplest approach if you don't need all projects

### 5. Check Token Expiration

Personal access tokens can expire:

1. Go to https://gitlab.com/-/user_settings/personal_access_tokens
2. Check the "Expires at" date for your token
3. If expired, create a new token and update your `.env` file

### 6. Verify Your Configuration

Check that your settings are correct:

```bash
# View your current .env settings
cat .env
```

Verify:
- `GITLAB_URL=https://gitlab.com` (or your self-hosted instance)
- `GITLAB_TOKEN` is set to a valid token
- `GITLAB_GROUP=redhat/rhel-ai` (or your specific group)

### 7. Test Your Token

You can test your GitLab token manually:

```bash
# Replace YOUR_TOKEN with your actual token
curl --header "PRIVATE-TOKEN: YOUR_TOKEN" "https://gitlab.com/api/v4/groups/redhat%2Frhel-ai"
```

Expected responses:
- ✅ **200 OK** - Token is valid and you have access
- ❌ **401 Unauthorized** - Token is invalid or expired
- ❌ **404 Not Found** - Group path is wrong or you don't have access

### 8. Viewing Detailed Logs

The dashboard now logs which projects are being skipped. To see detailed logs:

```bash
# Run with verbose logging
uvicorn app.main:app --reload --log-level debug
```

This will show you exactly which projects are causing 403 errors.

## Other Common Issues

### "Failed to load metrics" in Dashboard

**Cause**: GitLab API connection issue or invalid token

**Solution**:
1. Check your `.env` file has the correct `GITLAB_TOKEN`
2. Verify your token hasn't expired
3. Check the terminal logs for specific error messages

### Empty Dashboard / No Data

**Possible causes**:
- All projects return 403 (no access to any projects)
- Team member filter is excluding everyone
- No activity in the selected time range

**Solutions**:
1. Remove `team_members.json` temporarily to see all contributors
2. Increase the time range (try 90 days)
3. Check terminal logs for access errors

### Slow Dashboard Load

**Cause**: Many projects in the group or large history

**Solutions**:
1. Increase `CACHE_DURATION_HOURS` in `.env` (e.g., to 6 or 12)
2. Use a shorter time range (7 or 14 days instead of 90)
3. Filter to a specific subgroup with fewer projects

## Getting Help

If you're still experiencing issues:

1. Check the terminal output for specific error messages
2. Look for patterns in which projects are failing
3. Verify your GitLab role/permissions with your admin
4. Test with a smaller group or subgroup first

The dashboard is designed to be resilient - it will work with whatever projects you have access to and skip the rest.
