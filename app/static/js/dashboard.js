let currentDays = 30;
let currentStartDate = null;  // For custom date range
let currentEndDate = null;    // For custom date range
let currentGroup = null;      // Track selected group
let charts = {};

async function loadGroups() {
    try {
        const response = await fetch('/api/groups');
        const data = await response.json();
        console.log('Groups data:', data);

        if (data.mode === 'multi') {
            console.log('Multi-group mode, populating selector');
            populateGroupSelector(data.groups);
            document.getElementById('groupFilter').style.display = 'inline-block';
            document.querySelector('label[for="groupFilter"]').style.display = 'inline-block';
        } else {
            // Hide group selector in single-group mode
            document.getElementById('groupFilter').style.display = 'none';
            document.querySelector('label[for="groupFilter"]').style.display = 'none';
        }
    } catch (error) {
        console.error('Error loading groups:', error);
    }
}

function populateGroupSelector(groups) {
    const selector = document.getElementById('groupFilter');
    console.log('Populating selector with groups:', groups);
    groups.forEach(group => {
        if (group.enabled) {
            console.log('Adding group:', group.name);
            const option = document.createElement('option');
            option.value = group.id;
            option.textContent = group.name;
            selector.appendChild(option);
        }
    });
    console.log('Selector now has', selector.options.length, 'options');
}

async function fetchMetrics() {
    try {
        showLoading();

        const groupParam = currentGroup ? `&group_id=${currentGroup}` : '';

        // Build date range parameters
        let dateParams = '';
        if (currentStartDate && currentEndDate) {
            // For custom dates, still send a default days parameter + custom range
            dateParams = `days=90&start_date=${currentStartDate}&end_date=${currentEndDate}`;
            console.log('Fetching metrics with custom range:', currentStartDate, 'to', currentEndDate, 'group:', currentGroup);
        } else {
            dateParams = `days=${currentDays || 30}`;  // Default to 30 if null
            console.log('Fetching metrics with days:', currentDays, 'group:', currentGroup);
        }

        const [mrData, commitData, contributorData, commentData] = await Promise.all([
            fetch(`/api/metrics/merge-requests?${dateParams}${groupParam}`).then(r => {
                if (!r.ok) throw new Error(`MR endpoint failed: ${r.status}`);
                return r.json();
            }),
            fetch(`/api/metrics/commits?${dateParams}${groupParam}`).then(r => {
                if (!r.ok) throw new Error(`Commits endpoint failed: ${r.status}`);
                return r.json();
            }),
            fetch(`/api/metrics/contributors?${dateParams}${groupParam}`).then(r => {
                if (!r.ok) throw new Error(`Contributors endpoint failed: ${r.status}`);
                return r.json();
            }),
            fetch(`/api/metrics/comments?${dateParams}${groupParam}`).then(r => {
                if (!r.ok) throw new Error(`Comments endpoint failed: ${r.status}`);
                return r.json();
            })
        ]);

        console.log('Data fetched successfully:', {mrData, commitData, contributorData, commentData});

        updateMetricCards(mrData, commitData, contributorData, commentData);
        updateCharts(mrData, contributorData);
        updateTables(mrData, contributorData);

        // Update group breakdown if viewing all groups
        if (!currentGroup && mrData.by_group) {
            updateGroupBreakdown(mrData.by_group);
            document.getElementById('groupBreakdownContainer').style.display = 'block';
        } else {
            document.getElementById('groupBreakdownContainer').style.display = 'none';
        }

        hideLoading();
    } catch (error) {
        console.error('Error fetching metrics:', error);
        showError('Failed to load metrics: ' + error.message);
        hideLoading();
    }
}

function showLoading() {
    document.querySelectorAll('.metric-card .value').forEach(el => {
        el.innerHTML = '<div class="loading">...</div>';
    });
}

function hideLoading() {
    const loadingElements = document.querySelectorAll('.loading');
    loadingElements.forEach(el => el.remove());
}

function showError(message) {
    const container = document.querySelector('.container');
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error';
    errorDiv.textContent = message;
    container.insertBefore(errorDiv, container.firstChild);
}

function updateMetricCards(mrData, commitData, contributorData, commentData) {
    document.getElementById('total-mrs').textContent = mrData.total;
    document.getElementById('merged-mrs').textContent = mrData.merged;
    document.getElementById('open-mrs').textContent = mrData.open;
    document.getElementById('avg-merge-time').textContent = mrData.avg_time_to_merge_hours.toFixed(1);
    document.getElementById('median-merge-time').textContent = mrData.median_time_to_merge_hours.toFixed(1);

    // Update stale MRs
    const staleMrs = mrData.stale || 0;
    const staleThreshold = mrData.stale_threshold_days || 7;
    document.getElementById('stale-mrs').textContent = staleMrs;
    document.getElementById('stale-label').textContent = `Open >${staleThreshold}d`;

    // Color-code stale count (yellow warning if any stale MRs)
    const staleCard = document.querySelector('.stale-card');
    if (staleMrs > 0) {
        staleCard.classList.add('warning');
    } else {
        staleCard.classList.remove('warning');
    }

    // Show/hide review metrics based on backend config
    const reviewMetricsEnabled = mrData.review_metrics_enabled !== false;
    const avgReviewCard = document.getElementById('avg-review-response')?.closest('.metric-card');
    const medianReviewCard = document.getElementById('median-review-response')?.closest('.metric-card');

    if (reviewMetricsEnabled) {
        document.getElementById('avg-review-response').textContent = mrData.avg_review_response_hours.toFixed(1);
        document.getElementById('median-review-response').textContent = mrData.median_review_response_hours.toFixed(1);
        if (avgReviewCard) avgReviewCard.style.display = '';
        if (medianReviewCard) medianReviewCard.style.display = '';
    } else {
        if (avgReviewCard) avgReviewCard.style.display = 'none';
        if (medianReviewCard) medianReviewCard.style.display = 'none';
    }

    document.getElementById('total-contributors').textContent = contributorData.total_contributors;
    document.getElementById('total-comments').textContent = commentData.total;
}

function updateCharts(mrData, contributorData) {
    updateMRStateChart(mrData);

    // Only update review response chart if metrics are enabled
    const reviewMetricsEnabled = mrData.review_metrics_enabled !== false;
    const reviewChartCard = document.getElementById('reviewResponseByGroupChart')?.closest('.chart-card');

    if (reviewMetricsEnabled) {
        updateReviewResponseByGroupChart(mrData);
        if (reviewChartCard) reviewChartCard.style.display = '';
    } else {
        if (reviewChartCard) reviewChartCard.style.display = 'none';
    }

    updateTopContributorsMRChart(contributorData);
    updateTopContributorsCommentsChart(contributorData);
}

function updateMRStateChart(mrData) {
    const ctx = document.getElementById('mrStateChart').getContext('2d');

    if (charts.mrState) {
        charts.mrState.destroy();
    }

    charts.mrState = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Merged', 'Open', 'Closed'],
            datasets: [{
                data: [mrData.merged, mrData.open, mrData.closed],
                backgroundColor: ['#28a745', '#17a2b8', '#dc3545']
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

function updateReviewResponseByGroupChart(mrData) {
    const ctx = document.getElementById('reviewResponseByGroupChart').getContext('2d');

    if (charts.reviewResponseByGroup) {
        charts.reviewResponseByGroup.destroy();
    }

    const byGroup = mrData.review_response_by_group || {};
    const groupIds = Object.keys(byGroup);
    const hours = groupIds.map(gid => byGroup[gid]);

    if (groupIds.length === 0) {
        // No data - show placeholder
        ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
        return;
    }

    charts.reviewResponseByGroup = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: groupIds,
            datasets: [{
                label: 'Avg Hours to First Review',
                data: hours,
                backgroundColor: '#17a2b8'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Hours'
                    }
                }
            }
        }
    });
}

function updateTopContributorsMRChart(contributorData) {
    const ctx = document.getElementById('topContributorsMRChart').getContext('2d');

    if (charts.topContributorsMR) {
        charts.topContributorsMR.destroy();
    }

    const topContribs = contributorData.top_contributors.slice(0, 10);
    const names = topContribs.map(c => c.name);
    const mrs = topContribs.map(c => c.mr_count);

    charts.topContributorsMR = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: names,
            datasets: [{
                label: 'Merge Requests',
                data: mrs,
                backgroundColor: '#667eea'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                x: {
                    beginAtZero: true
                }
            }
        }
    });
}

function updateTopContributorsCommentsChart(contributorData) {
    const ctx = document.getElementById('topContributorsCommentsChart').getContext('2d');

    if (charts.topContributorsComments) {
        charts.topContributorsComments.destroy();
    }

    // Sort by comment count and get top 10
    const allContribs = contributorData.all_contributors || contributorData.top_contributors;
    const sortedByComments = allContribs
        .filter(c => c.comment_count > 0)
        .sort((a, b) => b.comment_count - a.comment_count)
        .slice(0, 10);

    const names = sortedByComments.map(c => c.name);
    const comments = sortedByComments.map(c => c.comment_count);

    charts.topContributorsComments = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: names,
            datasets: [{
                label: 'Comments',
                data: comments,
                backgroundColor: '#764ba2'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                x: {
                    beginAtZero: true
                }
            }
        }
    });
}

function updateTables(mrData, contributorData) {
    updateMRTable(mrData.merge_requests);
    updateStaleMRsTable(mrData.merge_requests, mrData.stale_threshold_days || 7);
    updateContributorTable(contributorData.all_contributors || contributorData.top_contributors);
}

function updateMRTable(mergeRequests) {
    const tbody = document.getElementById('mrTableBody');
    tbody.innerHTML = '';

    const recentMRs = mergeRequests
        .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
        .slice(0, 20);

    recentMRs.forEach(mr => {
        const row = document.createElement('tr');
        const stateBadge = `<span class="badge ${mr.state}">${mr.state}</span>`;
        const timeToMerge = mr.time_to_merge_hours ? `${mr.time_to_merge_hours.toFixed(1)}h` : 'N/A';

        // Calculate age and mark stale MRs
        const createdDate = new Date(mr.created_at);
        const ageInDays = (new Date() - createdDate) / (1000 * 60 * 60 * 24);
        const isStale = mr.state === 'opened' && ageInDays > 7; // matches backend threshold

        if (isStale) {
            row.classList.add('stale-mr');
        }

        row.innerHTML = `
            <td><a href="${mr.web_url}" target="_blank">${mr.title}</a></td>
            <td>${mr.project_name}</td>
            <td>${mr.author}</td>
            <td>${stateBadge}</td>
            <td>${timeToMerge}</td>
            <td>${new Date(mr.created_at).toLocaleDateString()}</td>
        `;
        tbody.appendChild(row);
    });
}

let allStaleMRs = [];
let currentStaleMRSort = { column: 'days_open', direction: 'desc' };

function updateStaleMRsTable(mergeRequests, staleThreshold = 7) {
    const tbody = document.getElementById('staleMRsTableBody');
    const tableCard = document.getElementById('staleMRsTableCard');
    tbody.innerHTML = '';

    // Filter for stale MRs (open and older than threshold)
    allStaleMRs = mergeRequests
        .filter(mr => {
            const createdDate = new Date(mr.created_at);
            const ageInDays = (new Date() - createdDate) / (1000 * 60 * 60 * 24);
            return mr.state === 'opened' && ageInDays > staleThreshold;
        })
        .map(mr => {
            const createdDate = new Date(mr.created_at);
            const daysOpen = Math.floor((new Date() - createdDate) / (1000 * 60 * 60 * 24));
            return {
                ...mr,
                daysOpen: daysOpen,
                createdDate: createdDate
            };
        });

    // Show/hide table based on whether there are stale MRs
    if (allStaleMRs.length === 0) {
        tableCard.style.display = 'none';
        return;
    }
    tableCard.style.display = 'block';

    // Sort by current sort settings
    sortStaleMRs();
}

function sortStaleMRs() {
    const { column, direction } = currentStaleMRSort;

    allStaleMRs.sort((a, b) => {
        let valA, valB;

        switch(column) {
            case 'title':
                valA = a.title.toLowerCase();
                valB = b.title.toLowerCase();
                break;
            case 'project':
                valA = a.project_name.toLowerCase();
                valB = b.project_name.toLowerCase();
                break;
            case 'author':
                valA = a.author.toLowerCase();
                valB = b.author.toLowerCase();
                break;
            case 'days_open':
                valA = a.daysOpen;
                valB = b.daysOpen;
                break;
            case 'created':
                valA = a.createdDate;
                valB = b.createdDate;
                break;
            default:
                return 0;
        }

        if (valA < valB) return direction === 'asc' ? -1 : 1;
        if (valA > valB) return direction === 'asc' ? 1 : -1;
        return 0;
    });

    renderStaleMRsTable();
    updateStaleMRSortIndicators();
}

function renderStaleMRsTable() {
    const tbody = document.getElementById('staleMRsTableBody');
    tbody.innerHTML = '';

    allStaleMRs.forEach(mr => {
        const row = document.createElement('tr');

        // Severity-based styling
        // 7-14 days = moderate (yellow)
        // 15-30 days = high (orange)
        // >30 days = critical (red)
        let severityClass = 'stale-moderate';
        if (mr.daysOpen > 30) {
            severityClass = 'stale-critical';
        } else if (mr.daysOpen > 14) {
            severityClass = 'stale-high';
        }

        row.classList.add(severityClass);

        row.innerHTML = `
            <td><a href="${mr.web_url}" target="_blank">${mr.title}</a></td>
            <td>${mr.project_name}</td>
            <td>${mr.author}</td>
            <td><strong>${mr.daysOpen} days</strong></td>
            <td>${mr.createdDate.toLocaleDateString()}</td>
            <td><a href="${mr.web_url}" target="_blank" class="btn-link">View MR →</a></td>
        `;
        tbody.appendChild(row);
    });
}

let allContributors = [];
let currentSort = { column: 'mr_count', direction: 'desc' };

function updateContributorTable(contributors) {
    // Store all contributors for sorting
    allContributors = contributors;

    // Sort by current sort settings
    sortContributors();

    const tbody = document.getElementById('contributorTableBody');
    tbody.innerHTML = '';

    allContributors.forEach(contrib => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${contrib.name}</td>
            <td>${contrib.username}</td>
            <td>${contrib.mr_count}</td>
            <td>${contrib.comment_count}</td>
            <td>${contrib.last_activity ? new Date(contrib.last_activity).toLocaleDateString() : 'N/A'}</td>
        `;
        tbody.appendChild(row);
    });

    // Update sort indicators
    updateSortIndicators();
}

function sortContributors() {
    const column = currentSort.column;
    const direction = currentSort.direction;

    allContributors.sort((a, b) => {
        let aVal = a[column];
        let bVal = b[column];

        // Handle date comparison
        if (column === 'last_activity') {
            aVal = aVal ? new Date(aVal) : new Date(0);
            bVal = bVal ? new Date(bVal) : new Date(0);
        }

        // Handle string comparison
        if (typeof aVal === 'string') {
            aVal = aVal.toLowerCase();
            bVal = bVal.toLowerCase();
        }

        if (direction === 'asc') {
            return aVal > bVal ? 1 : aVal < bVal ? -1 : 0;
        } else {
            return aVal < bVal ? 1 : aVal > bVal ? -1 : 0;
        }
    });
}

function updateSortIndicators() {
    // Clear all sort indicators for contributor table
    document.querySelectorAll('#contributorTableBody').closest('table').querySelectorAll('th.sortable').forEach(th => {
        th.removeAttribute('data-sort');
    });

    // Set current sort indicator
    const currentHeader = document.querySelector(`#contributorTableBody`).closest('table').querySelector(`th.sortable[data-column="${currentSort.column}"]`);
    if (currentHeader) {
        currentHeader.setAttribute('data-sort', currentSort.direction);
    }
}

function handleSort(column) {
    if (currentSort.column === column) {
        // Toggle direction
        currentSort.direction = currentSort.direction === 'asc' ? 'desc' : 'asc';
    } else {
        // New column, default to descending
        currentSort.column = column;
        currentSort.direction = 'desc';
    }

    updateContributorTable(allContributors);
}

function updateStaleMRSortIndicators() {
    // Clear all sort indicators for stale MRs table
    document.querySelectorAll('#staleMRsTableBody').closest('table').querySelectorAll('th.sortable').forEach(th => {
        th.removeAttribute('data-sort');
    });

    // Set current sort indicator
    const currentHeader = document.querySelector(`#staleMRsTableBody`).closest('table').querySelector(`th.sortable[data-column="${currentStaleMRSort.column}"]`);
    if (currentHeader) {
        currentHeader.setAttribute('data-sort', currentStaleMRSort.direction);
    }
}

function handleStaleMRSort(column) {
    if (currentStaleMRSort.column === column) {
        // Toggle direction
        currentStaleMRSort.direction = currentStaleMRSort.direction === 'asc' ? 'desc' : 'asc';
    } else {
        // New column, default to descending (or ascending for text columns)
        currentStaleMRSort.column = column;
        currentStaleMRSort.direction = (column === 'title' || column === 'project' || column === 'author') ? 'asc' : 'desc';
    }

    sortStaleMRs();
    updateStaleMRSortIndicators();
}

async function refreshData() {
    const button = document.getElementById('refreshBtn');
    button.disabled = true;
    button.textContent = 'Phase 1: Fetching MRs...';

    try {
        // Phase 1: Fast refresh (MRs only)
        await fetch(`/api/refresh?days=${currentDays}`, { method: 'POST' });
        await fetchMetrics();

        button.textContent = 'Phase 2: Background fetch...';

        // Phase 2: Trigger background fetch of detailed counts
        fetch(`/api/refresh-detailed?days=${currentDays}`, { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                console.log('Phase 2 started:', data.message);

                // Poll for updates every 30 seconds
                const pollInterval = setInterval(async () => {
                    const result = await fetch(`/api/metrics/contributors?days=${currentDays}`).then(r => r.json());

                    // Check if we have commit/comment counts (phase 2 complete)
                    if (result.total_commits > 0 || result.total_comments > 0) {
                        console.log('Phase 2 complete - refreshing display');
                        clearInterval(pollInterval);
                        await fetchMetrics();
                        button.textContent = 'Refresh Data';
                        button.disabled = false;
                    }
                }, 30000);  // Poll every 30 seconds

                // Also update button after 5 minutes regardless
                setTimeout(() => {
                    clearInterval(pollInterval);
                    button.textContent = 'Refresh Data';
                    button.disabled = false;
                }, 300000);  // 5 minutes
            });

    } catch (error) {
        showError('Failed to refresh data');
        button.disabled = false;
        button.textContent = 'Refresh Data';
    }
}

function getDateRangeFromPreset(preset) {
    const now = new Date();
    let start, end;

    switch(preset) {
        case 'this-month':
            start = new Date(now.getFullYear(), now.getMonth(), 1);
            end = now;
            break;
        case 'last-month':
            start = new Date(now.getFullYear(), now.getMonth() - 1, 1);
            end = new Date(now.getFullYear(), now.getMonth(), 0);
            break;
        case 'this-quarter':
            const currentQuarter = Math.floor(now.getMonth() / 3);
            start = new Date(now.getFullYear(), currentQuarter * 3, 1);
            end = now;
            break;
        case 'last-quarter':
            const lastQuarter = Math.floor(now.getMonth() / 3) - 1;
            const year = lastQuarter < 0 ? now.getFullYear() - 1 : now.getFullYear();
            const quarter = lastQuarter < 0 ? 3 : lastQuarter;
            start = new Date(year, quarter * 3, 1);
            end = new Date(year, quarter * 3 + 3, 0);
            break;
        default:
            return null;
    }

    return {
        start: start.toISOString().split('T')[0],
        end: end.toISOString().split('T')[0]
    };
}

function changeDateRange() {
    const select = document.getElementById('dateRangePreset');
    const customDiv = document.getElementById('customDateRange');
    const value = select.value;

    if (value === 'custom') {
        // Show custom date inputs
        customDiv.style.display = 'inline-block';

        // Load saved custom dates from localStorage if available
        const savedStart = localStorage.getItem('customStartDate');
        const savedEnd = localStorage.getItem('customEndDate');
        if (savedStart) document.getElementById('startDate').value = savedStart;
        if (savedEnd) document.getElementById('endDate').value = savedEnd;
    } else {
        customDiv.style.display = 'none';

        if (['this-month', 'last-month', 'this-quarter', 'last-quarter'].includes(value)) {
            // Use preset date range
            const range = getDateRangeFromPreset(value);
            currentStartDate = range.start;
            currentEndDate = range.end;
            currentDays = null;  // Clear days when using custom range

            // Save to localStorage
            localStorage.setItem('dateRangePreset', value);
        } else {
            // Use days-based range
            currentDays = parseInt(value);
            currentStartDate = null;
            currentEndDate = null;

            // Save to localStorage
            localStorage.setItem('dateRangePreset', value);
        }

        fetchMetrics();
    }
}

function applyCustomDateRange() {
    const startDate = document.getElementById('startDate').value;
    const endDate = document.getElementById('endDate').value;

    if (!startDate || !endDate) {
        alert('Please select both start and end dates');
        return;
    }

    if (new Date(startDate) > new Date(endDate)) {
        alert('Start date must be before end date');
        return;
    }

    currentStartDate = startDate;
    currentEndDate = endDate;
    currentDays = null;

    // Save to localStorage
    localStorage.setItem('customStartDate', startDate);
    localStorage.setItem('customEndDate', endDate);
    localStorage.setItem('dateRangePreset', 'custom');

    fetchMetrics();
}

function loadSavedDateRange() {
    const savedPreset = localStorage.getItem('dateRangePreset');
    if (savedPreset) {
        const select = document.getElementById('dateRangePreset');
        select.value = savedPreset;
        changeDateRange();  // Apply the saved preset
    }
}

document.addEventListener('DOMContentLoaded', () => {
    loadGroups();  // Load and populate group selector
    loadSavedDateRange();  // Load saved date range preference
    fetchMetrics();
    document.getElementById('refreshBtn').addEventListener('click', refreshData);
    document.getElementById('dateRangePreset').addEventListener('change', changeDateRange);
    document.getElementById('applyCustomRange').addEventListener('click', applyCustomDateRange);
    document.getElementById('groupFilter').addEventListener('change', changeGroup);

    // Add click handlers for contributor table sortable headers
    const contributorTable = document.querySelector('#contributorTableBody').closest('table');
    contributorTable.querySelectorAll('th.sortable').forEach(th => {
        th.addEventListener('click', () => {
            const column = th.getAttribute('data-column');
            handleSort(column);
        });
    });

    // Add click handlers for stale MRs table sortable headers
    const staleMRsTable = document.querySelector('#staleMRsTableBody').closest('table');
    staleMRsTable.querySelectorAll('th.sortable').forEach(th => {
        th.addEventListener('click', () => {
            const column = th.getAttribute('data-column');
            handleStaleMRSort(column);
        });
    });
});

function updateGroupBreakdown(groupData) {
    const container = document.getElementById('groupBreakdown');
    container.innerHTML = '';

    Object.keys(groupData).forEach(groupId => {
        const metrics = groupData[groupId];
        const card = document.createElement('div');
        card.className = 'group-breakdown-item';
        card.innerHTML = `
            <h3>${groupId}</h3>
            <div class="mini-metrics">
                <span>Total MRs: ${metrics.total}</span>
                <span>Merged: ${metrics.merged}</span>
                <span>Open: ${metrics.open}</span>
                <span>Closed: ${metrics.closed || 0}</span>
            </div>
        `;
        container.appendChild(card);
    });
}

function changeGroup() {
    const selector = document.getElementById('groupFilter');
    currentGroup = selector.value || null;
    fetchMetrics();
}
