document.addEventListener('DOMContentLoaded', () => {
    const summaryGrid = document.getElementById('admin-summary-grid');
    const statusBody = document.getElementById('admin-status-body');
    const dataStatus = document.getElementById('admin-data-status');

    const formatTimestamp = (value) => {
        if (!value) return '-';
        const parsed = new Date(value);
        if (Number.isNaN(parsed.getTime())) return '-';
        return new Intl.DateTimeFormat('pt-PT', {
            dateStyle: 'short',
            timeStyle: 'short',
        }).format(parsed);
    };

    const renderSummary = (payload) => {
        const counts = payload.statusCounts || {};
        summaryGrid.innerHTML = `
            <article class="admin-summary-card">
                <span class="admin-summary-card__label">Competições</span>
                <strong class="admin-summary-card__value">${payload.competitionCount || 0}</strong>
            </article>
            <article class="admin-summary-card admin-summary-card--ok">
                <span class="admin-summary-card__label">OK</span>
                <strong class="admin-summary-card__value">${counts.ok || 0}</strong>
            </article>
            <article class="admin-summary-card admin-summary-card--partial">
                <span class="admin-summary-card__label">Partial</span>
                <strong class="admin-summary-card__value">${counts.partial || 0}</strong>
            </article>
            <article class="admin-summary-card admin-summary-card--degraded">
                <span class="admin-summary-card__label">Degraded</span>
                <strong class="admin-summary-card__value">${counts.degraded || 0}</strong>
            </article>
        `;
    };

    const renderDataStatus = (payload) => {
        const generatedAt = formatTimestamp(payload.generatedAt);
        dataStatus.innerHTML = `<span class="data-status__item">Estado global gerado: ${generatedAt}</span>`;
        dataStatus.classList.remove('hidden');
    };

    const renderTable = (payload) => {
        const competitions = Object.entries(payload.competitions || {});
        if (!competitions.length) {
            statusBody.innerHTML = '<tr><td colspan="7">Sem dados de estado disponíveis.</td></tr>';
            return;
        }

        competitions.sort((left, right) => {
            const leftEntry = left[1] || {};
            const rightEntry = right[1] || {};
            const statusOrder = { degraded: 0, partial: 1, missing: 2, ok: 3 };
            const leftStatus = statusOrder[leftEntry.status] ?? 99;
            const rightStatus = statusOrder[rightEntry.status] ?? 99;
            if (leftStatus !== rightStatus) return leftStatus - rightStatus;
            return (leftEntry.title || left[0]).localeCompare(rightEntry.title || right[0], 'pt');
        });

        statusBody.innerHTML = competitions.map(([key, entry]) => {
            const issues = Array.isArray(entry.issues) && entry.issues.length
                ? `<div class="admin-status-table__issues">${entry.issues.join(' · ')}</div>`
                : '';
            const pagePath = entry.pagePath || '#';
            return `
                <tr>
                    <td>
                        <a href="${pagePath}" class="admin-status-table__link">${entry.title || key}</a>
                        <div class="admin-status-table__subtitle">${entry.subtitle || ''}</div>
                        ${issues}
                    </td>
                    <td><span class="admin-badge admin-badge--${entry.status || 'missing'}">${entry.status || 'missing'}</span></td>
                    <td>${formatTimestamp(entry.lastUpdatedAt)}</td>
                    <td>${entry.fallbackReuseCount || 0}</td>
                    <td>${entry.pastMatchesWithoutScore || 0}</td>
                    <td>${entry.completedMatchCount || 0}/${entry.matchCount || 0}</td>
                    <td>${entry.teamCount || 0}</td>
                </tr>
            `;
        }).join('');
    };

    const bootstrap = async () => {
        try {
            const response = await fetch('data/status.json', { cache: 'no-cache' });
            if (!response.ok) {
                throw new Error(`Falha ao obter status.json (${response.status})`);
            }
            const payload = await response.json();
            renderDataStatus(payload);
            renderSummary(payload);
            renderTable(payload);
        } catch (error) {
            console.error('Erro ao carregar estado global:', error);
            statusBody.innerHTML = '<tr><td colspan="7">Não foi possível carregar o estado das competições.</td></tr>';
        }
    };

    bootstrap();
});
