# GitLab Dashboard

A web dashboard for monitoring GitLab metrics for your engineering team. Uses a **team-member-first approach** - you specify your team members, and the dashboard tracks their contributions across multiple GitLab groups and projects.

## Key Benefits

- **Multi-Group & Multi-Project Support**: Track metrics across multiple GitLab groups AND individual projects simultaneously
- **Fast & Efficient**: Parallel fetching from multiple sources with intelligent caching
- **Scales to Large Groups**: Works efficiently even with hundreds or thousands of projects
- **Team-Focused**: See exactly what your team is working on, filtered from the noise
- **Flexible Source Types**: Mix and match GitLab groups (all projects within) and individual projects

## Features

- **Multi-Source Tracking**: Monitor multiple GitLab groups and individual projects in a single dashboard
- **Group Filtering**: View metrics across all sources or filter by specific group/project
- **Merge Request Metrics**: Track total, merged, open, and closed MRs with average and median time to merge
- **Stale MR Detection** 🚨: Identify MRs needing attention with configurable threshold (default 7 days)
  - Metric card with warning styling when stale MRs detected
  - Dedicated sortable table with severity-based color coding (yellow → orange → red)
  - Sort by title, project, author, days open, or creation date
- **Review Response Time Metrics** ⚡: Track 90th percentile and median time to first review (configurable, adds ~8 min to refresh)
- **Code Review Metrics**: Monitor MR comment activity and trends with top contributors chart
- **Custom Date Range Picker**: Select specific periods (This Month, Last Quarter, etc.) or custom date ranges
- **Contributor Stats**: Sortable table showing ALL team members (even with 0 contributions) with real names
- **Interactive Sorting**: Click column headers to sort tables by any metric (ascending/descending)
- **SQLite Caching**: Fast dashboard loads with automatic cache refresh
- **Interactive Charts**: Beautiful visualizations using Chart.js
- **Per-Group Breakdown**: See metrics split by each configured source

## Tech Stack

- **Backend**: FastAPI
- **Database**: SQLite with SQLAlchemy ORM
- **Frontend**: HTML templates with Chart.js
- **GitLab Integration**: python-gitlab library

## Installation

1. **Clone or navigate to the project directory**:
   ```bash
   cd gitlab-dashboard
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   ```bash
   cp .env.example .env
   ```

5. **Edit `.env` and add your GitLab personal access token**:
   ```
   GITLAB_URL=https://gitlab.com
   GITLAB_TOKEN=your_gitlab_personal_access_token_here
   GITLAB_GROUP=yourorg/yourgroup  # Default group (used for single-group mode)
   DATABASE_URL=sqlite:///./gitlab_metrics.db
   CACHE_DURATION_HOURS=6
   TEAM_MEMBERS_FILE=team_members.json
   ```

6. **Configure multi-group/multi-project tracking (OPTIONAL)**:
   ```bash
   cp groups.json.example groups.json
   ```
   
   Edit `groups.json` to track multiple groups and/or individual projects:
   ```json
   {
     "groups": [
       {
         "id": "base-images",
         "name": "Base Images",
         "path": "yourorg/yourgroup/base-images",
         "type": "group",
         "description": "Base container images",
         "enabled": true
       },
       {
         "id": "team-docs",
         "name": "Team Documentation",
         "path": "yourorg/yourgroup/team-docs",
         "type": "project",
         "description": "Documentation project",
         "enabled": true
       }
     ]
   }
   ```
   
   **Source Types:**
   - `"type": "group"` - Fetches MRs from ALL projects within the group
   - `"type": "project"` - Fetches MRs from a single specific project
   
   **Note:** If `groups.json` doesn't exist, the dashboard uses single-group mode with `GITLAB_GROUP` from `.env`.

7. **Configure team members (REQUIRED)**:
   ```bash
   cp team_members.json.example team_members.json
   ```
   
   Edit `team_members.json` and add your team's GitLab usernames and display names.
   
   **New format (recommended)** - with display names:
   ```json
   {
     "team_members": [
       {
         "username": "jdoe",
         "name": "John Doe"
       },
       {
         "username": "asmith",
         "name": "Alice Smith"
       },
       {
         "username": "bwilliams",
         "name": "Bob Williams"
       }
     ]
   }
   ```
   
   **Legacy format (still supported)** - usernames only:
   ```json
   {
     "team_members": [
       "jdoe",
       "asmith",
       "bwilliams"
     ]
   }
   ```
   
   **Important**: This file is required. The dashboard uses a team-member-first approach, querying GitLab for each person's contributions. This is much more efficient than scanning all projects, especially for large groups with hundreds of projects. The new format allows you to display real names in the contributor table instead of just usernames.

## Getting a GitLab Personal Access Token

1. Go to GitLab.com and log in
2. Click your avatar → **Settings** → **Access Tokens**
3. Create a new token with these scopes:
   - `read_api`
   - `read_repository`
4. Copy the token and paste it into your `.env` file

## Running the Dashboard

1. **Start the development server**:
   ```bash
   uvicorn app.main:app --reload
   ```

2. **Open your browser** and navigate to:
   ```
   http://localhost:8000
   ```
   
   **Note:** The port is configurable via the `PORT` environment variable in `.env` (default: 8000).

The dashboard will automatically fetch and cache data from GitLab on first load.

## Using Custom Date Ranges

The dashboard supports flexible date range selection including presets (This Month, Last Quarter, etc.) and custom date ranges.

### ⚠️ Important: Historical Date Ranges Require Manual Refresh

**The dashboard caches data for performance**. By default, it fetches the last 30-60 days of data. When selecting a date range further back in history, you must manually refresh to fetch that data.

**When to click "Refresh Data":**
- ✅ Selecting **"Last Quarter"** (if more than ~60 days ago)
- ✅ Selecting **"Last Month"** (if more than ~60 days ago)  
- ✅ Using **Custom Range** for any period outside the last 60 days
- ✅ First time viewing a historical period

**You do NOT need to refresh for:**
- ❌ Last 7, 14, 30 days (already cached)
- ❌ This Month, This Quarter (if current period)
- ❌ Switching between groups/projects (uses same cache)

### How It Works:

1. **Select your date range** (e.g., "Last Quarter" for Q1 2026)
2. **Click "Refresh Data" button** (if the period is older than cached data)
3. **Wait for Phase 1** to complete (~30 seconds - fetches MRs, commits, basic counts)
4. **Button returns to "Refresh Data"** - Phase 1 is done, metrics are now visible
5. **Phase 2 continues in background** (fetches detailed comment data, takes 5-10+ minutes depending on data volume)
6. **Comment counts update automatically** when Phase 2 completes

**⚠️ Important:** When the "Refresh Data" button resets, **Phase 1 is complete** but **Phase 2 is still running**. You'll see:
- ✅ Total MRs, Merged, Open counts (available immediately)
- ✅ Contributor MR counts (available immediately)  
- ⏳ Comment counts may be 0 or outdated until Phase 2 completes
- ⏳ "Top Contributors by Comments" chart updates when Phase 2 finishes

**You can continue using the dashboard** while Phase 2 runs in the background. The comment-related metrics will automatically refresh when Phase 2 completes.

**Example:**
- Today is June 25, 2026
- You select "Last Quarter" (Jan 1 - Mar 31, 2026)
- That's ~175 days ago
- Click "Refresh Data" to fetch Q1 2026 MRs from GitLab
- Dashboard will show metrics for that quarter

**Performance Tip:** The cache duration is controlled by `CACHE_DURATION_HOURS` (default: 6 hours). Increase this to 12 or 24 hours if you don't need frequent updates.

## API Endpoints

- `GET /` - Main dashboard page
- `GET /api/groups` - Get list of configured groups/projects
- `GET /api/metrics/merge-requests?days=30&group_id=<id>` - Get MR metrics (optionally filtered by group)
- `GET /api/metrics/contributors?days=30&group_id=<id>` - Get contributor stats (all team members, sortable)
- `GET /api/metrics/comments?days=30&group_id=<id>` - Get MR comment metrics
- `POST /api/refresh?days=30` - Force refresh all metrics from GitLab
- `GET /health` - Health check endpoint

## Configuration

Edit `.env` to customize:

- `GITLAB_URL`: Your GitLab instance URL (default: https://gitlab.com)
- `GITLAB_TOKEN`: Your personal access token
- `GITLAB_GROUP`: The group/subgroup path to monitor
- `DATABASE_URL`: SQLite database location
- `CACHE_DURATION_HOURS`: How long to cache data before refreshing (default: 6 hours)
- `TEAM_MEMBERS_FILE`: Path to JSON file with team member usernames (default: team_members.json)
- `FETCH_COMMENT_DETAILS`: Set to `True` to fetch MR comments (required for review metrics, slower)
- `ENABLE_REVIEW_METRICS`: Set to `True` to enable review response time metrics (default: `True`)
- `STALE_MR_DAYS`: MRs open longer than this many days are highlighted as stale (default: 7)
- `PORT`: Port to run the server on (default: 8000)

### ⚠️ Review Response Time Metrics - Performance Impact

The dashboard includes review response time metrics (average and median time from MR creation to first comment). However, **enabling these metrics significantly increases data refresh time**:

- **With `ENABLE_REVIEW_METRICS=True`**: ~8 minutes refresh time (fetches detailed comment data)
- **With `ENABLE_REVIEW_METRICS=False`**: ~34 seconds refresh time (skips comment fetching)

**Performance difference: ~14x faster when disabled!**

To disable review metrics in your `.env` file:
```bash
FETCH_COMMENT_DETAILS=True
ENABLE_REVIEW_METRICS=False  # Disable for faster refresh
```

To enable review metrics (default):
```bash
FETCH_COMMENT_DETAILS=True
ENABLE_REVIEW_METRICS=True   # Enable review response metrics
```

**When to disable:**
- You don't need review response time insights
- You want faster dashboard refresh times
- You're working with very large groups (100+ MRs)

**When to enable:**
- You want to track team review responsiveness
- You can tolerate longer refresh times for the insights
- You're analyzing team code review practices

**Note**: When review metrics are disabled, the avg/median review time cards and review response chart will be automatically hidden from the dashboard.

**Performance Tip**: Increase `CACHE_DURATION_HOURS` to 12 or 24 for even better performance if you don't need real-time data.

### 🚨 Stale MR Detection

The dashboard highlights merge requests that have been open longer than a configurable threshold to help prevent MRs from being forgotten.

**Configuration:**
```bash
STALE_MR_DAYS=7  # MRs older than this are highlighted (default: 7 days)
```

**Features:**
- **Metric Card**: Shows count of stale MRs with warning styling (orange gradient)
- **Visual Highlighting**: Stale MRs in Recent MRs table have orange background
- **Dedicated Table**: "Stale Merge Requests - Need Attention" table with:
  - Severity-based color coding:
    - 🟡 **7-14 days**: Yellow (moderate - needs attention soon)
    - 🟠 **15-30 days**: Orange (high priority - overdue for review)
    - 🔴 **>30 days**: Red (critical - urgent action required)
  - Sortable by any column (title, project, author, days open, created date)
  - Direct links to each MR for quick action
  - Only appears when stale MRs exist

**When to adjust threshold:**
- **Increase (10-14 days)**: For teams with longer review cycles or larger backlogs
- **Decrease (3-5 days)**: For fast-moving teams that need quick turnaround

### Team Member Configuration (Required)

The dashboard uses a **team-member-first approach**. You must create a `team_members.json` file listing your team's GitLab usernames.

**Recommended format** (with display names):
```json
{
  "team_members": [
    {
      "username": "jdoe",
      "name": "John Doe"
    },
    {
      "username": "asmith",
      "name": "Alice Smith"
    }
  ]
}
```

**Legacy format** (still supported):
```json
{
  "team_members": [
    "username1",
    "username2",
    "username3"
  ]
}
```

**How it works:**
1. Dashboard loads the list of team members from this file
2. For each team member, queries GitLab for their MRs and commits across the entire group
3. Aggregates and displays metrics only for your team
4. With the new format, displays real names in the contributor table instead of just usernames

**Benefits:**
- Much faster than scanning all projects (especially for groups with 100+ projects)
- Only tracks your team's work, excluding external contributors and bots
- Scales efficiently to large GitLab groups
- Display friendly names in the dashboard while using GitLab usernames for API queries

## Performance Optimizations

The dashboard is highly optimized for large GitLab groups:

**Parallel Multi-Source Fetching**:
- Multiple groups/projects fetched in parallel (up to 5 concurrent workers)
- MRs: 1 API call per source to fetch all MRs, then filter to team members
- Comments: Derived from MR data (no separate API calls)
- Commits: Derived from contributor stats (hybrid approach)

**Intelligent Caching**:
- Project cache: Projects fetched once and reused across API calls
- User cache: User objects cached to avoid repeated lookups
- Database cache: All data cached in SQLite for `CACHE_DURATION_HOURS`
- Per-group storage: Contributors tracked with composite key (group_id + username)

**Result**: 
- First load with 4 sources: ~10-15 seconds (parallel fetching)
- Subsequent loads (within cache window): <1 second (served from database)
- For multiple groups with 100+ projects total + 25 team members: efficient parallel processing

## Project Structure

```
gitlab-dashboard/
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py              # API endpoints
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py            # Database setup
│   │   └── schemas.py             # SQLAlchemy models (with multi-group support)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── gitlab_client.py       # GitLab API client (group & project support)
│   │   ├── multi_group_client.py  # Parallel multi-source orchestrator
│   │   └── metrics_service.py     # Metrics calculation with group filtering
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css          # Dashboard styles (sortable table styles)
│   │   └── js/
│   │       └── dashboard.js       # Frontend logic (sorting, filtering)
│   ├── templates/
│   │   └── dashboard.html         # Main dashboard template
│   ├── config.py                  # Configuration management
│   └── main.py                    # FastAPI application
├── scripts/
│   └── migrate_add_groups.py     # Database migration for multi-group support
├── .env.example
├── .gitignore
├── groups.json.example            # Multi-group configuration example
├── team_members.json.example
├── requirements.txt
└── README.md
```

## Development

The application uses:
- **FastAPI** for the backend API with automatic OpenAPI docs at `/docs`
- **SQLAlchemy** for database ORM
- **python-gitlab** for GitLab API integration
- **Jinja2** for HTML templating
- **Chart.js** for interactive visualizations

## Caching

The dashboard caches GitLab data in SQLite to improve performance. Cache is automatically refreshed when:
- Data is older than `CACHE_DURATION_HOURS`
- You click the "Refresh Data" button
- You call the `/api/refresh` endpoint

## Troubleshooting

**"Failed to load metrics"**: Check that your GitLab token is valid and has the correct permissions.

**Empty dashboard**: Ensure the `GITLAB_GROUP` path is correct and you have access to the projects.

**Slow initial load**: First-time data fetch can take a while depending on the number of projects and MRs. Subsequent loads use the cache.

## License

MIT
