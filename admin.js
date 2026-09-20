document.addEventListener('DOMContentLoaded', () => {
    const summaryGrid = document.getElementById('admin-summary-grid');
    const statusBody = document.getElementById('admin-status-body');
    const dataStatus = document.getElementById('admin-data-status');

    const escapeHTML = (value = '') => String(value)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#039;');

    const formatTimestamp = (value) => {
        if (!value) return '-';
        const parsed = new Date(value);
        if (Number.isNaN(parsed.getTime())) return '-';
        return new Intl.DateTimeFormat('pt-PT', {
            dateStyle: 'short',
            timeStyle: 'short',
        }).format(parsed);
    };

    const renderSummary = (entries) => {
        const complete = entries.filter(({ payload }) => payload.validation.complete !== false).length;
        const incomplete = entries.length - complete;
        const matches = entries.reduce((total, { payload }) => total + payload.dataQuality.matchCount, 0);
        const results = entries.reduce((total, { payload }) => total + payload.dataQuality.completedMatchCount, 0);
        summaryGrid.innerHTML = `
            <article class="admin-summary-card"><span class="admin-summary-card__label">Competições</span><strong class="admin-summary-card__value">${entries.length}</strong></article>
            <article class="admin-summary-card admin-summary-card--ok"><span class="admin-summary-card__label">Ficheiros completos</span><strong class="admin-summary-card__value">${complete}</strong></article>
            <article class="admin-summary-card ${incomplete ? 'admin-summary-card--degraded' : ''}"><span class="admin-summary-card__label">Incompletos</span><strong class="admin-summary-card__value">${incomplete}</strong></article>
            <article class="admin-summary-card"><span class="admin-summary-card__label">Resultados / jogos</span><strong class="admin-summary-card__value">${results}/${matches}</strong></article>
        `;
    };

    const renderTable = (entries) => {
        statusBody.innerHTML = entries.map(({ meta, payload }) => {
            const complete = payload.validation.complete !== false;
            return `
                <tr>
                    <td>
                        <a href="competition.html?key=${encodeURIComponent(meta.key)}" class="admin-status-table__link">${escapeHTML(meta.title)}</a>
                        <div class="admin-status-table__subtitle">${escapeHTML(meta.subtitle)}</div>
                    </td>
                    <td><span class="admin-badge admin-badge--${complete ? 'ok' : 'degraded'}">${complete ? 'completo' : 'incompleto'}</span></td>
                    <td>${escapeHTML(formatTimestamp(payload.capturedAt))}</td>
                    <td>${payload.rounds.length}</td>
                    <td>${payload.dataQuality.completedMatchCount}/${payload.dataQuality.matchCount}</td>
                    <td>${payload.dataQuality.matchesWithoutScore}</td>
                    <td>${payload.dataQuality.teamCount}</td>
                </tr>
            `;
        }).join('');
    };

    const bootstrap = async () => {
        try {
            const entries = await window.CFAData.loadAllCompetitions();
            renderSummary(entries);
            renderTable(entries);
            dataStatus.innerHTML = '<span class="data-status__item">Diagnóstico calculado diretamente a partir dos ficheiros JSON ativos.</span>';
            dataStatus.classList.remove('hidden');
        } catch (error) {
            console.error('Erro ao carregar o diagnóstico:', error);
            statusBody.innerHTML = `<tr><td colspan="7">Não foi possível carregar os ficheiros: ${escapeHTML(error.message)}</td></tr>`;
        }
    };

    bootstrap();
});
