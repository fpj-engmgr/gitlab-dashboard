let currentDays = 30;
let currentGroup = null;  // Track selected group
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

        console.log('Fetching metrics with days:', currentDays, 'group:', currentGroup);

        const [mrData, commitData, contributorData, commentData] = await Promise.all([
            fetch(`/api/metrics/merge-requests?days=${currentDays}${groupParam}`).then(r => {
                if (!r.ok) throw new Error(`MR endpoint failed: ${r.status}`);
                return r.json();
            }),
            fetch(`/api/metrics/commits?days=${currentDays}${groupParam}`).then(r => {
                if (!r.ok) throw new Error(`Commits endpoint failed: ${r.status}`);
                return r.json();
            }),
            fetch(`/api/metrics/contributors?days=${currentDays}${groupParam}`).then(r => {
                if (!r.ok) throw new Error(`Contributors endpoint failed: ${r.status}`);
                return r.json();
            }),
            fetch(`/api/metrics/comments?days=${currentDays}${groupParam}`).then(r => {
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
    document.getElementById('avg-review-response').textContent = mrData.avg_review_response_hours.toFixed(1);
    document.getElementById('total-contributors').textContent = contributorData.total_contributors;
    document.getElementById('total-comments').textContent = commentData.total;
}

function updateCharts(mrData, contributorData) {
    updateMRStateChart(mrData);
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
    // Clear all sort indicators
    document.querySelectorAll('th.sortable').forEach(th => {
        th.removeAttribute('data-sort');
    });

    // Set current sort indicator
    const currentHeader = document.querySelector(`th.sortable[data-column="${currentSort.column}"]`);
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

function changeDateRange() {
    const select = document.getElementById('dateRange');
    currentDays = parseInt(select.value);
    fetchMetrics();
}

document.addEventListener('DOMContentLoaded', () => {
    loadGroups();  // Load and populate group selector
    fetchMetrics();
    document.getElementById('refreshBtn').addEventListener('click', refreshData);
    document.getElementById('dateRange').addEventListener('change', changeDateRange);
    document.getElementById('groupFilter').addEventListener('change', changeGroup);

    // Add click handlers for sortable table headers
    document.querySelectorAll('th.sortable').forEach(th => {
        th.addEventListener('click', () => {
            const column = th.getAttribute('data-column');
            handleSort(column);
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
