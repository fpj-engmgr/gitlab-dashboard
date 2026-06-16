# GitLab Dashboard

A web dashboard for monitoring GitLab metrics for your engineering team. Uses a **team-member-first approach** - you specify your team members, and the dashboard tracks their contributions across all projects in a GitLab group.

## Key Benefits

- **Fast & Efficient**: Queries only your team members' contributions instead of scanning all projects
- **Scales to Large Groups**: Works efficiently even with hundreds or thousands of projects
- **Team-Focused**: See exactly what your team is working on, filtered from the noise

## Features

- **Merge Request Metrics**: Track total, merged, open, and closed MRs with average time to merge
- **Code Review Metrics**: Monitor MR review activity and trends  
- **Commit Activity**: Visualize commits over time by project and contributor
- **Contributor Stats**: See top contributors and their activity levels
- **SQLite Caching**: Fast dashboard loads with automatic cache refresh
- **Interactive Charts**: Beautiful visualizations using Chart.js
- **Time Range Selection**: View metrics for 7, 14, 30, 60, or 90 days

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
   GITLAB_GROUP=redhat/rhel-ai
   DATABASE_URL=sqlite:///./gitlab_metrics.db
   CACHE_DURATION_HOURS=1
   TEAM_MEMBERS_FILE=team_members.json
   ```

6. **Configure team members (REQUIRED)**:
   ```bash
   cp team_members.json.example team_members.json
   ```
   
   Edit `team_members.json` and add your team's GitLab usernames:
   ```json
   {
     "team_members": [
       "jdoe",
       "asmith",
       "bwilliams"
     ]
   }
   ```
   
   **Important**: This file is required. The dashboard uses a team-member-first approach, querying GitLab for each person's contributions. This is much more efficient than scanning all projects, especially for large groups with hundreds of projects.

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

The dashboard will automatically fetch and cache data from GitLab on first load.

## API Endpoints

- `GET /` - Main dashboard page
- `GET /api/metrics/merge-requests?days=30` - Get MR metrics
- `GET /api/metrics/commits?days=30` - Get commit metrics
- `GET /api/metrics/contributors?days=30` - Get contributor stats
- `POST /api/refresh?days=30` - Force refresh all metrics from GitLab
- `GET /health` - Health check endpoint

## Configuration

Edit `.env` to customize:

- `GITLAB_URL`: Your GitLab instance URL (default: https://gitlab.com)
- `GITLAB_TOKEN`: Your personal access token
- `GITLAB_GROUP`: The group/subgroup path to monitor
- `DATABASE_URL`: SQLite database location
- `CACHE_DURATION_HOURS`: How long to cache data before refreshing (default: 1 hour)
- `TEAM_MEMBERS_FILE`: Path to JSON file with team member usernames (default: team_members.json)

### Team Member Configuration (Required)

The dashboard uses a **team-member-first approach**. You must create a `team_members.json` file listing your team's GitLab usernames:

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

**Benefits:**
- Much faster than scanning all projects (especially for groups with 100+ projects)
- Only tracks your team's work, excluding external contributors and bots
- Scales efficiently to large GitLab groups

## Project Structure

```
gitlab-dashboard/
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py          # API endpoints
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py        # Database setup
│   │   └── schemas.py         # SQLAlchemy models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── gitlab_client.py   # GitLab API client
│   │   └── metrics_service.py # Metrics calculation
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css      # Dashboard styles
│   │   └── js/
│   │       └── dashboard.js   # Frontend logic
│   ├── templates/
│   │   └── dashboard.html     # Main dashboard template
│   ├── config.py              # Configuration management
│   └── main.py                # FastAPI application
├── .env.example
├── .gitignore
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
