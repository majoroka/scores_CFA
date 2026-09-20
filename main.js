const ThemeManager = (() => {
    const STORAGE_KEY = 'cfa-theme';
    const media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

    const readTheme = () => {
        try {
            const value = window.localStorage.getItem(STORAGE_KEY);
            return value === 'light' || value === 'dark' ? value : null;
        } catch (error) {
            return null;
        }
    };

    const storedTheme = readTheme();
    let hasManualTheme = Boolean(storedTheme);
    let currentTheme = storedTheme || (media?.matches ? 'dark' : 'light');
    const buttons = new Map();

    const updateButtons = () => {
        buttons.forEach((button, theme) => {
            const active = theme === currentTheme;
            button.classList.toggle('is-active', active);
            button.setAttribute('aria-pressed', String(active));
        });
    };

    const applyTheme = (theme, persist = false) => {
        currentTheme = theme === 'light' ? 'light' : 'dark';
        document.documentElement.dataset.theme = currentTheme;
        if (persist) {
            hasManualTheme = true;
            try {
                window.localStorage.setItem(STORAGE_KEY, currentTheme);
            } catch (error) {
                // localStorage can be unavailable in private browsing.
            }
        }
        updateButtons();
    };

    const createButton = (theme) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'theme-toggle__btn';
        button.setAttribute('aria-label', theme === 'light' ? 'Ativar tema claro' : 'Ativar tema escuro');
        button.innerHTML = `<img src="img/${theme === 'light' ? 'sun' : 'moon'}.png" alt="" aria-hidden="true">`;
        button.addEventListener('click', () => applyTheme(theme, true));
        buttons.set(theme, button);
        return button;
    };

    const initToggle = () => {
        const header = document.querySelector('.details-header, .site-header');
        if (!header || header.querySelector('.theme-toggle-wrapper')) return;

        const wrapper = document.createElement('div');
        wrapper.className = 'theme-toggle-wrapper';
        const toggle = document.createElement('div');
        toggle.className = 'theme-toggle';
        toggle.append(createButton('light'), createButton('dark'));
        wrapper.appendChild(toggle);
        header.appendChild(wrapper);
        updateButtons();
    };

    if (media) {
        media.addEventListener?.('change', (event) => {
            if (!hasManualTheme) applyTheme(event.matches ? 'dark' : 'light');
        });
    }
    applyTheme(currentTheme);
    return { initToggle };
})();

const escapeHTML = (value = '') => String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');

const loadCrests = async () => {
    try {
        const response = await fetch('data/crests.json', { cache: 'no-cache' });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.warn('Não foi possível carregar os emblemas:', error);
        return {};
    }
};

const getCrestUrl = (teamName, crests) => {
    const fallback = 'img/crests/jornada.png';
    const normalized = window.CFAData.canonicalTeamName(teamName);
    return crests[normalized] || crests[window.CFAData.normalizeName(teamName)] || fallback;
};

const formatCapturedAt = (value) => {
    if (!value) return null;
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return null;
    return new Intl.DateTimeFormat('pt-PT', {
        dateStyle: 'short',
        timeStyle: 'short',
    }).format(parsed);
};

const bootstrapHome = async () => {
    const list = document.getElementById('competitions-list');
    if (!list) return;

    const loading = document.getElementById('competitions-loading');
    try {
        const index = await window.CFAData.loadIndex();
        const competitions = index.competitions.filter((competition) => competition.enabled !== false);
        const seasonTitle = document.getElementById('active-season-title');
        if (seasonTitle) seasonTitle.textContent = `Competições ${index.activeSeason}`;

        const cards = competitions.map((competition) => `
            <a class="competition-card" href="competition.html?key=${encodeURIComponent(competition.key)}" style="--card-accent: ${escapeHTML(competition.accent)};">
                <div class="competition-info">
                    <h3>${escapeHTML(competition.title)}</h3>
                    <p>${escapeHTML(competition.subtitle)}</p>
                </div>
                <img alt="Aceder" class="arrow-icon" src="img/seta.png">
            </a>
        `).join('');
        loading?.remove();
        list.insertAdjacentHTML('beforeend', cards);
    } catch (error) {
        console.error('Erro ao carregar o catálogo:', error);
        if (loading) loading.textContent = 'Não foi possível carregar as competições.';
    }
};

const bootstrapCompetition = async () => {
    if (document.body.dataset.page !== 'competition') return;

    const params = new URLSearchParams(window.location.search);
    const competitionKey = params.get('key');
    const status = document.getElementById('competition-data-status');
    const matchesContainer = document.getElementById('matches-container');
    const classificationContainer = document.getElementById('classification-container');

    try {
        const meta = await window.CFAData.getCompetitionMeta(competitionKey);
        if (!meta) throw new Error('A competição pedida não existe no catálogo ativo.');

        const [competition, crests] = await Promise.all([
            window.CFAData.loadCompetition(meta),
            loadCrests(),
        ]);
        if (!competition.rounds.length) throw new Error('A competição não contém jornadas.');

        document.title = `${meta.title} - CF Os Armacenenses`;
        document.documentElement.style.setProperty('--accent-blue', meta.accent || '#00aaff');
        document.getElementById('competition-heading').childNodes[0].nodeValue = `${meta.title} `;
        document.getElementById('competition-subtitle').textContent = `${meta.subtitle} · ${meta.season}`;

        const capturedAt = formatCapturedAt(competition.capturedAt);
        status.innerHTML = capturedAt
            ? `<span class="data-status__item">Ficheiro atualizado: ${escapeHTML(capturedAt)}</span>`
            : '<span class="data-status__item">Dados carregados do ficheiro da competição</span>';
        status.classList.remove('hidden');

        let currentRoundIndex = Math.min(
            Math.max(competition.defaultRoundIndex || 0, 0),
            competition.rounds.length - 1
        );

        const scoreMarkup = (match) => {
            if (Number.isInteger(match.homeScore) && Number.isInteger(match.awayScore)) {
                return {
                    desktop: `${match.homeScore} - ${match.awayScore}`,
                    mobile: `<span class="score-line"><span class="score-number">${match.homeScore}</span></span><span class="score-line"><span class="score-number">${match.awayScore}</span></span>`,
                };
            }
            const time = match.time || '-';
            return { desktop: escapeHTML(time), mobile: escapeHTML(time) };
        };

        const renderMatches = (round) => {
            document.getElementById('round-title').textContent = `Jornada ${round.index}`;
            if (!round.matches.length) {
                matchesContainer.innerHTML = '<p class="agenda-empty-state">Sem jogos nesta jornada.</p>';
                return;
            }

            matchesContainer.innerHTML = round.matches.map((match) => {
                const homeName = window.CFAData.displayTeamName(match.home);
                const awayName = window.CFAData.displayTeamName(match.away);
                const homeHighlighted = window.CFAData.isClubTeam(match.home, meta);
                const awayHighlighted = window.CFAData.isClubTeam(match.away, meta);
                const homeCrest = getCrestUrl(match.home, crests);
                const awayCrest = getCrestUrl(match.away, crests);
                const score = scoreMarkup(match);
                const dateAndTime = [match.date, match.time].filter(Boolean).join(' · ');

                return `
                    <article class="match-item">
                        <div class="match-datetime"><span>${escapeHTML(match.time || '')}</span><span>${escapeHTML(match.date)}</span></div>
                        <div class="team-home">
                            <span class="team-block">
                                <span class="team-name ${homeHighlighted ? 'highlight' : ''}">${escapeHTML(homeName)}</span>
                                <img src="${escapeHTML(homeCrest)}" alt="" class="team-crest">
                            </span>
                        </div>
                        <div class="match-score match-score-desktop">${score.desktop}</div>
                        <div class="team-away">
                            <span class="team-block">
                                <img src="${escapeHTML(awayCrest)}" alt="" class="team-crest">
                                <span class="team-name ${awayHighlighted ? 'highlight' : ''}">${escapeHTML(awayName)}</span>
                            </span>
                        </div>
                        <div class="match-teams-mobile">
                            <div class="team-line"><img src="${escapeHTML(homeCrest)}" alt="" class="team-crest"><span class="team-name ${homeHighlighted ? 'highlight' : ''}">${escapeHTML(homeName)}</span></div>
                            <div class="team-line"><img src="${escapeHTML(awayCrest)}" alt="" class="team-crest"><span class="team-name ${awayHighlighted ? 'highlight' : ''}">${escapeHTML(awayName)}</span></div>
                        </div>
                        <div class="match-score match-score-mobile">${score.mobile}</div>
                        <div class="match-meta"><span class="meta-date">${escapeHTML(dateAndTime)}</span><span>${escapeHTML(match.stadium)}</span></div>
                    </article>
                `;
            }).join('');
        };

        const renderClassification = (round) => {
            document.getElementById('classification-round-title').textContent = `Classificação · Jornada ${round.index}`;
            if (!round.classification.length) {
                classificationContainer.innerHTML = '<p class="agenda-empty-state">Classificação ainda indisponível.</p>';
                return;
            }

            const rows = round.classification.map((entry) => {
                const highlighted = window.CFAData.isClubTeam(entry.team, meta);
                return `
                    <tr>
                        <td class="pos">${entry.position}</td>
                        <td class="team-name-col ${highlighted ? 'highlight' : ''}"><img src="${escapeHTML(getCrestUrl(entry.team, crests))}" alt="" class="team-crest-mini">${escapeHTML(window.CFAData.displayTeamName(entry.team))}</td>
                        <td>${entry.played}</td><td>${entry.wins}</td><td>${entry.draws}</td><td>${entry.losses}</td>
                        <td>${entry.goalsFor}-${entry.goalsAgainst}</td><td class="pts">${entry.points}</td>
                    </tr>
                `;
            }).join('');

            classificationContainer.innerHTML = `
                <table class="classification-table">
                    <thead><tr><th>#</th><th>Equipa</th><th>J</th><th>V</th><th>E</th><th>D</th><th>G</th><th>Pts</th></tr></thead>
                    <tbody>${rows}</tbody>
                </table>
            `;
        };

        const renderRound = () => {
            const round = competition.rounds[currentRoundIndex];
            renderMatches(round);
            renderClassification(round);
            ['prev-round', 'prev-round-class'].forEach((id) => {
                document.getElementById(id).disabled = currentRoundIndex === 0;
            });
            ['next-round', 'next-round-class'].forEach((id) => {
                document.getElementById(id).disabled = currentRoundIndex === competition.rounds.length - 1;
            });
        };

        const changeRound = (offset) => {
            currentRoundIndex = Math.min(
                Math.max(currentRoundIndex + offset, 0),
                competition.rounds.length - 1
            );
            renderRound();
        };

        document.getElementById('prev-round').addEventListener('click', () => changeRound(-1));
        document.getElementById('next-round').addEventListener('click', () => changeRound(1));
        document.getElementById('prev-round-class').addEventListener('click', () => changeRound(-1));
        document.getElementById('next-round-class').addEventListener('click', () => changeRound(1));

        const setActiveTab = (tab) => {
            const showResults = tab === 'resultados';
            document.getElementById('content-resultados').classList.toggle('hidden', !showResults);
            document.getElementById('content-classificacao').classList.toggle('hidden', showResults);
            document.getElementById('tab-resultados').classList.toggle('active', showResults);
            document.getElementById('tab-classificacao').classList.toggle('active', !showResults);
            document.getElementById('tab-resultados').setAttribute('aria-selected', String(showResults));
            document.getElementById('tab-classificacao').setAttribute('aria-selected', String(!showResults));
        };

        document.getElementById('tab-resultados').addEventListener('click', (event) => {
            event.preventDefault();
            setActiveTab('resultados');
        });
        document.getElementById('tab-classificacao').addEventListener('click', (event) => {
            event.preventDefault();
            setActiveTab('classificacao');
        });

        const hashMatch = window.location.hash.match(/resultados-j(\d+)/);
        if (hashMatch) {
            const requestedRound = competition.rounds.findIndex((round) => round.index === Number(hashMatch[1]));
            if (requestedRound >= 0) currentRoundIndex = requestedRound;
        }
        setActiveTab(window.location.hash === '#classificacao' ? 'classificacao' : 'resultados');
        renderRound();
    } catch (error) {
        console.error('Erro ao carregar competição:', error);
        status.innerHTML = `<span class="data-status__item data-status__item--warning">${escapeHTML(error.message)}</span>`;
        status.classList.remove('hidden');
        matchesContainer.innerHTML = '<p class="agenda-empty-state">Não foi possível carregar esta competição.</p>';
        classificationContainer.innerHTML = '';
    }
};

document.addEventListener('DOMContentLoaded', () => {
    ThemeManager.initToggle();
    bootstrapHome();
    bootstrapCompetition();
});
