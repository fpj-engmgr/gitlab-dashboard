# GitLab Dashboard - Feature Roadmap

This document tracks planned features and improvements for the GitLab Metrics Dashboard.

## Status Legend
- ✅ Completed
- 🚧 In Progress
- 📋 Planned
- 💡 Idea (needs discussion)

---

## Implemented Features

### Core Features ✅
- [x] Multi-group/multi-project tracking
- [x] Support for both GitLab groups and individual projects
- [x] Merge request metrics (total, merged, open, closed, avg time-to-merge)
- [x] Contributor statistics with aggregation across groups
- [x] Sortable contributors table (all columns)
- [x] MR comment/review metrics
- [x] Group filtering and breakdown
- [x] Interactive charts (Chart.js)
- [x] SQLite caching with configurable duration
- [x] Team-member-first approach (efficient for large groups)
- [x] Parallel fetching from multiple sources

### Recent Additions ✅
- [x] Top Contributors by MRs chart
- [x] Top Contributors by Comments chart
- [x] Compact group breakdown view
- [x] Helper scripts (start.sh, stop.sh)
- [x] All team members in table (including 0 contributions)

---

## Planned Improvements

## Quick Wins (Easy Implementation)

### ✅ Review Response Time Metrics
**Priority:** High | **Effort:** Low | **Category:** Metrics | **Status:** Completed

~~Add metrics showing how quickly the team responds to merge requests:~~
- ✅ Average time from MR creation to first comment/review
- ✅ Median response time (less affected by outliers)
- ✅ Response time by project/group
- ✅ Add to metrics cards section
- ✅ Review response time by group chart (bar chart visualization)

**Value:** Identifies review bottlenecks, encourages faster feedback cycles

**Note:** Requires `FETCH_COMMENT_DETAILS=True` in `.env` to populate comment timestamps.
Currently shows `0` in hybrid mode where comments table is not fully populated.

---

### ✅ Stale MR Detection
**Priority:** High | **Effort:** Low | **Category:** Metrics | **Status:** Completed

~~Highlight merge requests that need attention:~~
- ✅ Add "Stale MRs" metric card (count of MRs >7 days old)
- ✅ Color-code rows in Recent MRs table (orange highlight for stale)
- ✅ Configurable threshold via STALE_MR_DAYS (default: 7 days)
- ✅ Warning styling on metric card when stale count > 0
- 📋 Filter option to show only stale MRs (future enhancement)

**Value:** Prevents MRs from being forgotten, reduces review backlog

**Implementation:** Backend calculates stale count (open MRs older than threshold). Frontend highlights stale rows in Recent MRs table with orange background and adds warning-styled metric card.

---

### ✅ Custom Date Range Picker
**Priority:** Medium | **Effort:** Low | **Category:** UX | **Status:** Completed

~~Replace fixed date options with flexible date picker:~~
- ✅ Calendar-based custom date range selection (from/to dates)
- ✅ Quick presets (Last 7/14/30/60/90 days, This Month, Last Month, This Quarter, Last Quarter)
- ✅ Persist selection in browser localStorage
- ✅ Auto-restore last selected range on page load
- 📋 Compare to previous period option (future enhancement)

**Value:** Enables specific reporting periods (e.g., "Q2 2026"), better for executive reports

**Implementation:** Backend supports start_date/end_date parameters on all metric APIs. Frontend includes preset calculator and localStorage integration.

---

### 📋 Export to CSV
**Priority:** Medium | **Effort:** Low | **Category:** Data Export

Add download buttons for data export:
- Export contributor stats table to CSV
- Export MR list to CSV
- Export summary metrics to CSV
- Include filters/date range in filename (e.g., `contributors_2026-06-01_to_2026-06-30.csv`)

**Value:** Enables offline analysis, executive reporting, data archival

---

### 💡 Dark Mode Toggle
**Priority:** Low | **Effort:** Low | **Category:** UX

Add theme toggle for dark mode:
- Toggle button in header
- Dark color scheme for dashboard
- Persist preference in localStorage
- Adjust chart colors for dark backgrounds

**Value:** Better viewing experience in low-light environments, modern UX

---

## Medium Effort, High Value

### 📋 Trend Analysis Charts
**Priority:** High | **Effort:** Medium | **Category:** Visualization

Add time-series visualizations:
- MR velocity over time (line chart: MRs created/merged per week)
- Week-over-week comparison
- Month-over-month trends
- Rolling averages to smooth noise

**Value:** Shows team productivity trends, helps predict capacity

---

### 📋 MR Size Distribution
**Priority:** Medium | **Effort:** Medium | **Category:** Metrics

Categorize MRs by size and analyze impact:
- Define size categories (Small: <100 lines, Medium: 100-500, Large: >500)
- Size distribution chart (bar/pie chart)
- Correlation: Size vs Time-to-Merge
- Average comments per size category
- Encourage smaller, faster MRs

**Value:** Identifies if large MRs are slowing down reviews, encourages best practices

---

### 📋 Review Activity Heatmap
**Priority:** Medium | **Effort:** Medium | **Category:** Visualization

Show when team is most active:
- Heatmap: Day of week × Hour of day
- When MRs are created vs merged
- Review comment activity by time
- Helps identify optimal meeting times

**Value:** Understand team work patterns, optimize collaboration schedules

---

### 📋 Top Reviewers Chart
**Priority:** Medium | **Effort:** Medium | **Category:** Metrics

Recognize valuable code reviewers:
- Count reviews (not just comments)
- Weight by thoroughness (comments per review)
- Time invested in reviews
- Separate from Top Contributors

**Value:** Recognizes often-invisible review work, encourages quality reviews

---

### 📋 Project/Group Health Score
**Priority:** High | **Effort:** Medium | **Category:** Metrics

Composite health indicator per group:
- Combine metrics: avg merge time, stale MR %, review response time
- Red/Yellow/Green scoring
- Trend indicator (improving/declining)
- Drill-down to see which metric is affecting score

**Value:** At-a-glance project health, executive-level visibility

---

## Bigger Features

### 💡 Alerts & Notifications
**Priority:** High | **Effort:** High | **Category:** Integration

Proactive notifications for team:
- Email alerts when MRs go stale
- Slack integration for daily/weekly summaries
- Configurable thresholds per alert type
- Weekly team summary email
- Per-user notification preferences

**Value:** Keeps team engaged, reduces forgotten MRs, proactive management

**Technical Requirements:**
- Email service configuration (SMTP)
- Slack webhook integration
- Background job scheduler
- User preferences storage

---

### 💡 Team Velocity Dashboard
**Priority:** Medium | **Effort:** High | **Category:** Visualization

Sprint/iteration view for agile teams:
- Sprint selector (if using sprints)
- Burndown charts
- Planned vs actual throughput
- Velocity trends over sprints
- Story points integration (if tracked in GitLab)

**Value:** Better sprint planning, capacity forecasting

**Technical Requirements:**
- Sprint/iteration data source
- Story point extraction from MR descriptions or labels

---

### 📋 Historical Comparison
**Priority:** High | **Effort:** Medium | **Category:** Metrics

Compare current period to previous periods:
- Show percentage change for all metrics
- "This month: 45 MRs (↑ 12% from last month)"
- Arrow indicators (↑/↓/→)
- Configurable comparison periods
- Highlight significant changes

**Value:** Quickly spot trends, identify improvements or regressions

---

### 💡 Label/Tag Analysis
**Priority:** Medium | **Effort:** Medium | **Category:** Metrics

If using GitLab labels (bug, feature, enhancement):
- MR breakdown by label/tag
- Pie chart of work types
- Label-specific metrics (e.g., avg merge time for bugs vs features)
- Filter dashboard by label

**Value:** Understand team focus areas, balance feature work vs bugs

**Technical Requirements:**
- Extract labels from GitLab API
- Label-based filtering in database queries

---

### 💡 Saved Views/Bookmarks
**Priority:** Low | **Effort:** Medium | **Category:** UX

Save commonly used filter combinations:
- Save current filters + date range as named view
- Quick access buttons for saved views
- Examples: "Monthly Executive Report", "Q2 Review", "Last Sprint"
- Share saved views via URL

**Value:** Faster access to common reports, consistent reporting formats

**Technical Requirements:**
- View definition storage (localStorage or database)
- URL parameter encoding/decoding

---

### 💡 Custom Metrics Builder
**Priority:** Low | **Effort:** High | **Category:** Advanced

Allow users to define custom metrics:
- Formula builder (e.g., "Merged MRs / Total MRs * 100")
- Aggregate custom fields from MR descriptions
- Save custom metric definitions
- Add custom metrics to dashboard

**Value:** Flexibility for team-specific KPIs

**Technical Requirements:**
- Expression parser/evaluator
- Safe execution environment
- Custom metric storage

---

### 💡 API Rate Limiting Visualization
**Priority:** Low | **Effort:** Low | **Category:** Ops

Show GitLab API usage:
- Current rate limit status
- Requests per hour chart
- Time until reset
- Warning when approaching limits

**Value:** Helps understand API consumption, troubleshoot rate limit issues

---

### 💡 Multi-Language Support (i18n)
**Priority:** Low | **Effort:** High | **Category:** UX

Internationalization support:
- Language selector
- Translation files for common languages
- Date/time formatting per locale
- Number formatting per locale

**Value:** Broader team adoption for international teams

---

## Performance & Infrastructure

### 📋 Database Indexing Optimization
**Priority:** Medium | **Effort:** Low | **Category:** Performance

Optimize query performance:
- Add composite indexes for common queries
- Query performance monitoring
- Slow query logging
- Database size monitoring

---

### 💡 Incremental Cache Updates
**Priority:** Medium | **Effort:** High | **Category:** Performance

Instead of full refresh, update only new data:
- Track last sync timestamp
- Fetch only MRs updated since last sync
- Merge new data with existing cache
- Reduces API calls and refresh time

**Value:** Faster refresh cycles, lower API usage

---

### 💡 Real-time Updates (WebSocket)
**Priority:** Low | **Effort:** High | **Category:** Performance

Live dashboard updates:
- WebSocket connection to backend
- Push updates when new MRs are created/merged
- Live refresh without page reload
- Show "New data available" indicator

**Value:** Always up-to-date view without manual refresh

---

## Documentation & Developer Experience

### 📋 API Documentation
**Priority:** Medium | **Effort:** Low | **Category:** Docs

Comprehensive API docs:
- OpenAPI/Swagger UI (FastAPI built-in)
- Example requests/responses
- Authentication guide
- Rate limiting documentation

---

### 📋 Contribution Guide
**Priority:** Low | **Effort:** Low | **Category:** Docs

Guide for external contributors:
- CONTRIBUTING.md with development setup
- Code style guide
- PR checklist
- Testing requirements

---

### 💡 Docker Compose Setup
**Priority:** Medium | **Effort:** Low | **Category:** DevEx

Containerized deployment:
- Dockerfile for application
- docker-compose.yml for easy setup
- Environment variable documentation
- Production deployment guide

**Value:** Easier deployment, consistent environments

---

## Ideas for Discussion

### 💡 GitLab CI/CD Integration
Show pipeline metrics alongside MR metrics:
- Build success rate
- Test coverage trends
- Deployment frequency
- MTTR (Mean Time To Recovery)

### 💡 Jira Integration
Link MRs to Jira tickets:
- Show story points from Jira
- Track work-in-progress limits
- Cycle time from ticket creation to MR merge

### 💡 Cost/Time Analysis
Estimate engineering cost:
- Time invested per MR (creation + reviews)
- Cost per feature (if salary data available)
- ROI analysis for different project types

### 💡 Team Mood/Sentiment Tracking
Optional check-ins:
- Daily team mood indicator
- Correlation with productivity metrics
- Help identify burnout early

### 💡 Gamification
Encourage good practices:
- Badges for milestones (100 MRs, 500 comments)
- Streaks (consecutive days with reviews)
- Leaderboards (opt-in only)

---

## How to Contribute

To propose a new feature:
1. Check if it's already in this roadmap
2. Open a GitHub issue with the `enhancement` label
3. Describe the problem it solves and expected value
4. Discuss implementation approach if you have ideas

To implement a feature:
1. Comment on the feature in this file or related issue
2. Create a branch with naming: `feature/short-description`
3. Update this roadmap to mark it as 🚧 In Progress
4. Submit a PR and update to ✅ Completed when merged

---

## Versioning

Features will be grouped into releases:

**v1.0** (Current)
- Core multi-group dashboard with contributor tracking

**v1.1** (Next)
- Stale MR detection
- Review response time metrics
- Historical comparison
- Export to CSV

**v1.2** (Future)
- Trend analysis charts
- MR size distribution
- Health score per group

**v2.0** (Future)
- Alerts & notifications
- Label/tag analysis
- Advanced filtering

---

*Last Updated: 2026-06-25*
