let currentDays = 30;
let charts = {};

async function fetchMetrics() {
    try {
        showLoading();

        const [mrData, commitData, contributorData, commentData] = await Promise.all([
            fetch(`/api/metrics/merge-requests?days=${currentDays}`).then(r => r.json()),
            fetch(`/api/metrics/commits?days=${currentDays}`).then(r => r.json()),
            fetch(`/api/metrics/contributors?days=${currentDays}`).then(r => r.json()),
            fetch(`/api/metrics/comments?days=${currentDays}`).then(r => r.json())
        ]);

        updateMetricCards(mrData, commitData, contributorData, commentData);
        updateCharts(mrData, commitData, contributorData);
        updateTables(mrData, contributorData);

        hideLoading();
    } catch (error) {
        console.error('Error fetching metrics:', error);
        showError('Failed to load metrics. Please check your GitLab token and configuration.');
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
    document.getElementById('total-commits').textContent = commitData.total;
    document.getElementById('total-contributors').textContent = contributorData.total_contributors;
    document.getElementById('total-comments').textContent = commentData.total;
}

function updateCharts(mrData, commitData, contributorData) {
    updateMRStateChart(mrData);
    updateCommitsByDayChart(commitData);
    updateTopContributorsChart(contributorData);
    updateCommitsByProjectChart(commitData);
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

function updateCommitsByDayChart(commitData) {
    const ctx = document.getElementById('commitsByDayChart').getContext('2d');

    if (charts.commitsByDay) {
        charts.commitsByDay.destroy();
    }

    const sortedDays = Object.keys(commitData.by_day).sort();
    const commitCounts = sortedDays.map(day => commitData.by_day[day]);

    charts.commitsByDay = new Chart(ctx, {
        type: 'line',
        data: {
            labels: sortedDays,
            datasets: [{
                label: 'Commits per Day',
                data: commitCounts,
                borderColor: '#667eea',
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                tension: 0.4,
                fill: true
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
                    beginAtZero: true
                }
            }
        }
    });
}

function updateTopContributorsChart(contributorData) {
    const ctx = document.getElementById('topContributorsChart').getContext('2d');

    if (charts.topContributors) {
        charts.topContributors.destroy();
    }

    const topContribs = contributorData.top_contributors.slice(0, 10);
    const names = topContribs.map(c => c.name);
    const commits = topContribs.map(c => c.commit_count);

    charts.topContributors = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: names,
            datasets: [{
                label: 'Commits',
                data: commits,
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

function updateCommitsByProjectChart(commitData) {
    const ctx = document.getElementById('commitsByProjectChart').getContext('2d');

    if (charts.commitsByProject) {
        charts.commitsByProject.destroy();
    }

    const projects = Object.keys(commitData.by_project);
    const counts = Object.values(commitData.by_project);

    charts.commitsByProject = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: projects,
            datasets: [{
                label: 'Commits',
                data: counts,
                backgroundColor: '#667eea'
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
                    beginAtZero: true
                }
            }
        }
    });
}

function updateTables(mrData, contributorData) {
    updateMRTable(mrData.merge_requests);
    updateContributorTable(contributorData.top_contributors);
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

function updateContributorTable(contributors) {
    const tbody = document.getElementById('contributorTableBody');
    tbody.innerHTML = '';

    contributors.forEach(contrib => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${contrib.name}</td>
            <td>${contrib.username}</td>
            <td>${contrib.commit_count}</td>
            <td>${contrib.mr_count}</td>
            <td>${contrib.comment_count}</td>
            <td>${contrib.last_activity ? new Date(contrib.last_activity).toLocaleDateString() : 'N/A'}</td>
        `;
        tbody.appendChild(row);
    });
}

async function refreshData() {
    const button = document.getElementById('refreshBtn');
    button.disabled = true;
    button.textContent = 'Refreshing...';

    try {
        await fetch(`/api/refresh?days=${currentDays}`, { method: 'POST' });
        await fetchMetrics();
    } catch (error) {
        showError('Failed to refresh data');
    } finally {
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
    fetchMetrics();
    document.getElementById('refreshBtn').addEventListener('click', refreshData);
    document.getElementById('dateRange').addEventListener('change', changeDateRange);
});
