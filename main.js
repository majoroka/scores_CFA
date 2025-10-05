const ThemeManager = (() => {
    const STORAGE_KEY = 'cfa-theme';
    const prefersDark = typeof window !== 'undefined' && window.matchMedia
        ? window.matchMedia('(prefers-color-scheme: dark)')
        : null;

    const readStoredTheme = () => {
        try {
            const value = window.localStorage.getItem(STORAGE_KEY);
            return value === 'light' || value === 'dark' ? value : null;
        } catch (err) {
            return null;
        }
    };

    const writeStoredTheme = (value) => {
        try {
            window.localStorage.setItem(STORAGE_KEY, value);
        } catch (err) {
            // storage might be unavailable (private mode, etc)
        }
    };

    const buttons = new Map();
    const ICONS = {
        light: 'img/sun.png',
        dark: 'img/moon.png',
    };

    const storedTheme = readStoredTheme();
    let manualOverride = Boolean(storedTheme);
    let currentTheme = storedTheme || ((prefersDark && prefersDark.matches) ? 'dark' : 'light');

    const updateButtons = () => {
        buttons.forEach((button, theme) => {
            const isActive = currentTheme === theme;
            button.classList.toggle('is-active', isActive);
            button.setAttribute('aria-pressed', String(isActive));
        });
    };

    const applyTheme = (theme, persist = false) => {
        currentTheme = theme === 'light' ? 'light' : 'dark';
        document.documentElement.dataset.theme = currentTheme;
        if (persist) {
            manualOverride = true;
            writeStoredTheme(currentTheme);
        }
        updateButtons();
    };

    const handleButtonClick = (theme) => {
        if (theme === currentTheme) return;
        applyTheme(theme, true);
    };

    const createButton = (theme) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'theme-toggle__btn';
        button.dataset.theme = theme;
        button.setAttribute('aria-label', theme === 'light' ? 'Ativar tema claro' : 'Ativar tema escuro');
        const icon = document.createElement('img');
        icon.src = ICONS[theme];
        icon.alt = theme === 'light' ? 'Tema claro' : 'Tema escuro';
        icon.className = 'theme-toggle__icon';
        button.appendChild(icon);
        button.addEventListener('click', () => handleButtonClick(theme));
        buttons.set(theme, button);
        return button;
    };

    const createToggle = () => {
        const wrapper = document.createElement('div');
        wrapper.className = 'theme-toggle-wrapper';

        const container = document.createElement('div');
        container.className = 'theme-toggle';

        container.appendChild(createButton('light'));
        container.appendChild(createButton('dark'));
        wrapper.appendChild(container);

        updateButtons();
        return wrapper;
    };

    if (prefersDark) {
        const listener = (event) => {
            if (!manualOverride) {
                applyTheme(event.matches ? 'dark' : 'light');
            }
        };
        if (typeof prefersDark.addEventListener === 'function') {
            prefersDark.addEventListener('change', listener);
        } else if (typeof prefersDark.addListener === 'function') {
            prefersDark.addListener(listener);
        }
    }

    applyTheme(currentTheme);

    return {
        initToggle() {
            const header = document.querySelector('.details-header') || document.querySelector('.site-header');
            if (!header) return;
            let wrapper = header.querySelector('.theme-toggle-wrapper');
            if (!wrapper) {
                wrapper = createToggle();
                header.appendChild(wrapper);
            } else {
                buttons.clear();
                const container = wrapper.querySelector('.theme-toggle');
                if (container) {
                    container.innerHTML = '';
                    container.appendChild(createButton('light'));
                    container.appendChild(createButton('dark'));
                    updateButtons();
                }
            }
        }
    };
})();


document.addEventListener('DOMContentLoaded', () => {
    ThemeManager.initToggle();
    // Verifica se estamos na página de detalhes
    if (!document.getElementById('content-resultados')) {
        return;
    }

    // --- ESTADO DA APLICAÇÃO ---
    const competitionKey = document.body.dataset.competition || 'seniores';
    let competitionData = null;
    let crestsData = null;
    let currentRoundIndex = 0;
    let activeTab = 'resultados'; // 'resultados' ou 'classificacao'
    let userHasManualRoundSelection = false;

    // --- ELEMENTOS DO DOM ---
    const tabResultados = document.getElementById('tab-resultados');
    const tabClassificacao = document.getElementById('tab-classificacao');
    const contentResultados = document.getElementById('content-resultados');
    const contentClassificacao = document.getElementById('content-classificacao');
    const prevRoundBtn = document.getElementById('prev-round');
    const nextRoundBtn = document.getElementById('next-round');
    const prevRoundBtnClass = document.getElementById('prev-round-class');
    const nextRoundBtnClass = document.getElementById('next-round-class');
    const roundTitle = document.getElementById('round-title');
    const classificationRoundTitle = document.getElementById('classification-round-title');
    const matchesContainer = document.getElementById('matches-container');
    const classificationContainer = document.getElementById('classification-container');

    // Utilitário simples para decodificar HTML vindo da FPF
    const htmlDecoder = document.createElement('textarea');
    const decodeHTML = (value = '') => {
        htmlDecoder.innerHTML = value;
        return htmlDecoder.value;
    };

    const cleanHTMLText = (value = '') => {
        if (!value) return '';
        return decodeHTML(
            value
                .replace(/<br\s*\/?>/gi, ' ')
                .replace(/<[^>]*>/g, ' ')
        ).replace(/\s+/g, ' ').trim();
    };

    const textFromNode = (node) => (node ? cleanHTMLText(node.textContent || '') : '');

    const LIVE_DATA_ENDPOINT = 'https://resultados.fpf.pt/Competition/GetClassificationAndMatchesByFixture?fixtureId=';
    const LIVE_DATA_SOURCES = [
        (fixtureId) => `${LIVE_DATA_ENDPOINT}${fixtureId}`,
        (fixtureId) => `https://corsproxy.io/?${LIVE_DATA_ENDPOINT}${fixtureId}`,
        (fixtureId) => `https://r.jina.ai/https://resultados.fpf.pt/Competition/GetClassificationAndMatchesByFixture?fixtureId=${fixtureId}`,
    ];
    const remoteRoundCache = new Map();

const MONTH_MAP = {
    jan: 0, fev: 1, mar: 2, abr: 3, mai: 4, jun: 5,
    jul: 6, ago: 7, set: 8, out: 9, nov: 10, dez: 11,
};

const normalizeMonthToken = (value = '') => {
    if (!value) return null;
    const normalized = value
        .toLowerCase()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .replace(/[^a-z]/g, '');
    if (!normalized) return null;
    return normalized.slice(0, 3);
};

const parseMatchDate = (value = '') => {
    const trimmed = (value || '').trim();
    if (!trimmed) return null;
    const match = trimmed.match(/(\d{1,2})/);
    if (!match) return null;
    const day = Number.parseInt(match[1], 10);
    if (!Number.isInteger(day)) return null;
    const tokens = trimmed.split(/\s+/).slice(1);
    let monthKey = null;
    for (const token of tokens) {
        const normalized = normalizeMonthToken(token);
        if (normalized && Object.prototype.hasOwnProperty.call(MONTH_MAP, normalized)) {
            monthKey = normalized;
            break;
        }
    }
    if (!monthKey) return null;
    const month = MONTH_MAP[monthKey];
    const today = new Date();
    const currentMonth = today.getMonth();
    let year = today.getFullYear();
    const diff = month - currentMonth;
    if (diff <= -6) {
        year += 1;
    } else if (diff >= 6) {
        year -= 1;
    }
    const result = new Date(year, month, day, 12, 0, 0, 0);
    return Number.isNaN(result.getTime()) ? null : result;
};

const getRoundReferenceDate = (round) => {
    if (!round || !Array.isArray(round.matches)) return null;
    let latest = null;
    for (const match of round.matches) {
        const parsed = parseMatchDate(match?.date);
        if (!parsed) continue;
        if (!latest || parsed > latest) {
            latest = parsed;
        }
    }
    return latest;
};

const findBestRoundIndexByDate = () => {
    if (!competitionData || !Array.isArray(competitionData.rounds)) return 0;
    const rounds = competitionData.rounds;
    if (!rounds.length) return 0;
    const today = new Date();
    today.setHours(12, 0, 0, 0);
    let previousOrCurrent = null;
    let firstFuture = null;
    rounds.forEach((round, idx) => {
        const reference = getRoundReferenceDate(round);
        if (!reference) return;
        if (reference <= today) {
            previousOrCurrent = idx;
        } else if (firstFuture === null) {
            firstFuture = idx;
        }
    });
    if (previousOrCurrent !== null) return previousOrCurrent;
    if (firstFuture !== null) return firstFuture;
    return 0;
};

const initializeRoundBasedOnDate = () => {
    if (!competitionData || !Array.isArray(competitionData.rounds) || !competitionData.rounds.length) return;
    const hash = (window.location.hash || '').toLowerCase();
    let targetTab = 'resultados';
    let shouldOverride = false;
    if (!hash || hash === '#') {
        shouldOverride = true;
    } else if (/^#resultados(?:-j1)?$/.test(hash)) {
        shouldOverride = true;
        targetTab = 'resultados';
    } else if (/^#classificacao(?:-j1)?$/.test(hash)) {
        shouldOverride = true;
        targetTab = 'classificacao';
    }
    if (!shouldOverride) return;
    const suggestedIndex = findBestRoundIndexByDate();
    const safeIndex = Math.max(0, Math.min(competitionData.rounds.length - 1, suggestedIndex));

    // Atualiza hash apenas se estivermos em resultado/classificação padrão sem seleção manual
    if (safeIndex === currentRoundIndex && (!hash || hash === '#' || /^#(?:resultados|classificacao)(?:-j1)?$/.test(hash))) {
        userHasManualRoundSelection = false;
        const currentRoundNumber = competitionData.rounds[currentRoundIndex]?.index || (currentRoundIndex + 1);
        if (/^#classificacao/.test(hash)) {
            history.replaceState(null, '', `#classificacao-j${currentRoundNumber}`);
        } else {
            history.replaceState(null, '', `#resultados-j${currentRoundNumber}`);
        }
        return;
    }

    currentRoundIndex = safeIndex;
    userHasManualRoundSelection = false;
    const roundNumber = competitionData.rounds[currentRoundIndex]?.index || (currentRoundIndex + 1);
    const nextHash = `#${targetTab}-j${roundNumber}`;
    history.replaceState(null, '', nextHash);
};

    const parseMatchesFragment = (htmlFragment = '') => {
        if (!htmlFragment) return [];
        const wrapper = document.createElement('div');
        wrapper.innerHTML = htmlFragment;
        const matchesSection = wrapper.querySelector('#matches');
        if (!matchesSection) return [];

        const matches = [];
        matchesSection.querySelectorAll('.game').forEach((game) => {
            const home = textFromNode(game.querySelector('.home-team'));
            const away = textFromNode(game.querySelector('.away-team'));

            const scoreBlock = game.querySelector('.score, .text-center');
            let scheduleText = '';
            let centralText = '';

            if (scoreBlock) {
                scheduleText = textFromNode(scoreBlock.querySelector('.game-schedule'));
                centralText = cleanHTMLText(scoreBlock.innerHTML || scoreBlock.textContent || '');
                if (scheduleText) {
                    centralText = centralText.replace(scheduleText, '').trim();
                }
            }

            let time = '';
            let date = '';
            if (scheduleText) {
                const timeMatch = scheduleText.match(/\b\d{1,2}:\d{2}\b/);
                if (timeMatch) {
                    time = timeMatch[0];
                    scheduleText = scheduleText.replace(timeMatch[0], '').trim();
                }
                date = scheduleText.trim();
            }

            if (!time && centralText) {
                const timeMatch = centralText.match(/\b\d{1,2}:\d{2}\b/);
                if (timeMatch) {
                    time = timeMatch[0];
                    centralText = centralText.replace(timeMatch[0], '').trim();
                }
            }

            let homeScore = null;
            let awayScore = null;
            if (centralText) {
                const scoreMatch = centralText.match(/(\d{1,2})\s*[-–]\s*(\d{1,2})/);
                if (scoreMatch) {
                    homeScore = Number.parseInt(scoreMatch[1], 10);
                    awayScore = Number.parseInt(scoreMatch[2], 10);
                    centralText = centralText.replace(scoreMatch[0], '').trim();
                }
            }

            if (!date) {
                date = centralText.trim();
            }

            const stadiumNode = game.nextElementSibling && game.nextElementSibling.classList.contains('game-list-stadium')
                ? game.nextElementSibling
                : null;
            const stadium = stadiumNode ? textFromNode(stadiumNode.querySelector('small')) : '';

            matches.push({
                home,
                away,
                date,
                time,
                stadium,
                homeScore,
                awayScore,
            });
        });

        return matches;
    };

    const parseClassificationFragment = (htmlFragment = '') => {
        if (!htmlFragment) return [];
        const wrapper = document.createElement('div');
        wrapper.innerHTML = htmlFragment;
        const classificationSection = wrapper.querySelector('#classification');
        if (!classificationSection) return [];

        const entries = [];
        classificationSection.querySelectorAll('.game.classification').forEach((row) => {
            const columns = Array.from(row.children).filter((child) =>
                child.className && child.className.includes('col-')
            );
            if (columns.length < 9) return;

            const toNumber = (value) => {
                const parsed = Number.parseInt(cleanHTMLText(value), 10);
                return Number.isNaN(parsed) ? 0 : parsed;
            };

            entries.push({
                position: toNumber(columns[0].textContent),
                team: cleanHTMLText(columns[1].textContent),
                played: toNumber(columns[2].textContent),
                wins: toNumber(columns[3].textContent),
                draws: toNumber(columns[4].textContent),
                losses: toNumber(columns[5].textContent),
                goalsFor: toNumber(columns[6].textContent),
                goalsAgainst: toNumber(columns[7].textContent),
                points: toNumber(columns[8].textContent),
            });
        });

        return entries;
    };

    const mergeMatches = (existing = [], incoming = []) => {
        if (!existing.length) return incoming;
        if (!incoming.length) return existing;
        const incomingMap = new Map(
            incoming.map((match) => [
                `${normalizeName(match.home)}|${normalizeName(match.away)}`,
                match,
            ])
        );
        return existing.map((match) => {
            const key = `${normalizeName(match.home)}|${normalizeName(match.away)}`;
            const updated = incomingMap.get(key);
            if (!updated) return match;
            return {
                ...match,
                ...updated,
            };
        });
    };

    const fetchRoundFromRemote = async (fixtureId) => {
        if (!fixtureId) return null;
        if (remoteRoundCache.has(fixtureId)) {
            return remoteRoundCache.get(fixtureId);
        }

        let lastError = null;

        for (const buildUrl of LIVE_DATA_SOURCES) {
            const targetUrl = buildUrl(fixtureId);
            try {
                const response = await fetch(targetUrl, {
                    headers: {
                        'Accept': 'text/html,application/xhtml+xml',
                    },
                    cache: 'no-store',
                    mode: 'cors',
                });

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }

                const html = await response.text();
                const matches = parseMatchesFragment(html);
                const classification = parseClassificationFragment(html);

                if (!matches.length && !classification.length) {
                    throw new Error('Resposta sem dados utilizáveis');
                }

                const result = { matches, classification };
                console.info(`Resultados atualizados (fixture ${fixtureId}) via ${targetUrl}`);
                remoteRoundCache.set(fixtureId, result);
                return result;
            } catch (err) {
                lastError = err;
                continue;
            }
        }

        if (lastError) {
            console.warn(`Falha ao carregar dados remotos para fixture ${fixtureId}:`, lastError);
        }
        remoteRoundCache.set(fixtureId, null);
        return null;
    };

    const hydrateRoundsWithLiveData = async () => {
        if (!competitionData || !Array.isArray(competitionData.rounds)) return;

        for (const round of competitionData.rounds) {
            if (!round || !round.fixtureId) continue;

            const liveData = await fetchRoundFromRemote(round.fixtureId);
            if (!liveData) continue;

            if (Array.isArray(liveData.matches) && liveData.matches.length) {
                round.matches = mergeMatches(round.matches, liveData.matches);
            }
            if (Array.isArray(liveData.classification) && liveData.classification.length) {
                round.classification = liveData.classification;
            }
        }
    };

    // --- FUNÇÕES DE RENDERIZAÇÃO ---

    const normalizeName = (name) => {
        if (!name) return '';
        // Remove diacríticos, normaliza espaços e remove pontuação
        const noDiacritics = name.normalize('NFD').replace(/[\u0300-\u036f]+/g, '');
        return noDiacritics
            .toLowerCase()
            .replace(/[\-_]+/g, ' ')
            .replace(/[^a-z0-9 ]+/g, '')
            .replace(/\s+/g, ' ')
            .trim();
    };

    const getCrestUrl = (teamName) => {
        const fallback = 'img/crests/jornada.png';
        if (!crestsData) return fallback;
        const normalizedName = normalizeName(teamName);
        return crestsData[normalizedName] || fallback;
    };

    const renderResults = (round) => {
        matchesContainer.innerHTML = '';
        if (!round || !round.matches) return;

        const isMobile = window.innerWidth <= 480;

        const parts = [];
        const HIGHLIGHT = normalizeName('CF Os Armacenenses');
        round.matches.forEach(match => {
            const homeCrest = getCrestUrl(match.home);
            const awayCrest = getCrestUrl(match.away);
            const hasScore = (match.homeScore !== null && match.awayScore !== null);
            const scoreDesktop = hasScore
                ? `${match.homeScore} - ${match.awayScore}`
                : (match.time || '-');
            const scoreMobileContent = hasScore
                ? `
                    <div class="score-line"><span class="score-number">${match.homeScore}</span></div>
                    <div class="score-line"><span class="score-number">${match.awayScore}</span></div>
                `
                : (match.time || '-');
            const homeHighlighted = normalizeName(match.home) === HIGHLIGHT;
            const awayHighlighted = normalizeName(match.away) === HIGHLIGHT;

            let matchHTML;
            if (isMobile) {
                matchHTML = `
                    <div class="match-item">
                        <div class="match-datetime">
                            <span>${match.time || ''}</span>
                            <span>${match.date || ''}</span>
                        </div>
                        <div class="match-teams-mobile">
                            <div class="team-line">
                                <img src="${homeCrest}" alt="${match.home}" class="team-crest">
                                <span class="team-name ${homeHighlighted ? 'highlight' : ''}">${match.home}</span>
                            </div>
                            <div class="team-line">
                                <img src="${awayCrest}" alt="${match.away}" class="team-crest">
                                <span class="team-name ${awayHighlighted ? 'highlight' : ''}">${match.away}</span>
                            </div>
                        </div>
                        <div class="match-score ${hasScore ? 'match-score-mobile' : ''}">${scoreMobileContent}</div>
                        <div class="match-meta"><span class="meta-stadium">${match.stadium || ''}</span></div>
                    </div>
                `;
            } else {
                matchHTML = `
                    <div class="match-item">
                        <div class="team-home">
                            <span class="team-block">
                                <span class="team-name ${homeHighlighted ? 'highlight' : ''}">${match.home}</span>
                                <img src="${homeCrest}" alt="${match.home}" class="team-crest">
                            </span>
                        </div>
                        <div class="match-score">${scoreDesktop}</div>
                        <div class="team-away">
                            <span class="team-block">
                                <img src="${awayCrest}" alt="${match.away}" class="team-crest">
                                <span class="team-name ${awayHighlighted ? 'highlight' : ''}">${match.away}</span>
                            </span>
                        </div>
                        <div class="match-meta">
                            <span class="meta-date">${(match.date || '')}${match.time ? ' ' + match.time : ''}</span>
                            <span class="meta-stadium">${match.stadium || ''}</span>
                        </div>
                    </div>
                `;
            }
            parts.push(matchHTML);
        });
        matchesContainer.innerHTML = parts.join('');
    };

    const renderClassification = (round) => {
        classificationContainer.innerHTML = '';
        if (!round || !round.classification) return;

        let tableHTML = `
            <table class="classification-table">
                <thead>
                    <tr>
                        <th class="pos">#</th>
                        <th class="team-name-col">Equipa</th>
                        <th>J</th>
                        <th>V</th>
                        <th>E</th>
                        <th>D</th>
                        <th>GM:GS</th>
                        <th class="pts">Pts</th>
                    </tr>
                </thead>
                <tbody>
        `;
        round.classification.forEach(entry => {
            const crestUrl = getCrestUrl(entry.team);
            tableHTML += `
                <tr>
                    <td class="pos">${entry.position}</td>
                    <td class="team-name-col">
                        <img src="${crestUrl}" alt="${entry.team}" class="team-crest-mini">
                        ${entry.team}
                    </td>
                    <td>${entry.played}</td>
                    <td>${entry.wins}</td>
                    <td>${entry.draws}</td>
                    <td>${entry.losses}</td>
                    <td>${entry.goalsFor}:${entry.goalsAgainst}</td>
                    <td class="pts">${entry.points}</td>
                </tr>
            `;
        });
        tableHTML += `</tbody></table>`;
        classificationContainer.innerHTML = tableHTML;
    };

    const updateUI = () => {
        if (!competitionData) return;

        // Atualiza estado dos tabs
        if (activeTab === 'resultados') {
            tabResultados.classList.add('active');
            tabClassificacao.classList.remove('active');
            tabResultados.setAttribute('aria-selected', 'true');
            tabClassificacao.setAttribute('aria-selected', 'false');
            tabResultados.setAttribute('tabindex', '0');
            tabClassificacao.setAttribute('tabindex', '-1');
            contentResultados.classList.remove('hidden');
            contentClassificacao.classList.add('hidden');
        } else {
            tabResultados.classList.remove('active');
            tabClassificacao.classList.add('active');
            tabResultados.setAttribute('aria-selected', 'false');
            tabClassificacao.setAttribute('aria-selected', 'true');
            tabResultados.setAttribute('tabindex', '-1');
            tabClassificacao.setAttribute('tabindex', '0');
            contentResultados.classList.add('hidden');
            contentClassificacao.classList.remove('hidden');
        }

        // Atualiza conteúdo da jornada
        const currentRound = competitionData.rounds[currentRoundIndex];
        const roundNumber = currentRound.index;
        
        roundTitle.textContent = `Jornada ${roundNumber}`;
        classificationRoundTitle.textContent = `Classificação à Jornada ${roundNumber}`;

        renderResults(currentRound);
        renderClassification(currentRound);

        // Atualiza estado dos botões de navegação
        const atStart = currentRoundIndex === 0;
        const atEnd = currentRoundIndex === competitionData.rounds.length - 1;
        if (prevRoundBtn) prevRoundBtn.disabled = atStart;
        if (nextRoundBtn) nextRoundBtn.disabled = atEnd;
        if (prevRoundBtnClass) prevRoundBtnClass.disabled = atStart;
        if (nextRoundBtnClass) nextRoundBtnClass.disabled = atEnd;
    };

    const navigate = (newRoundIndex, newTab, markManual = true) => {
        const boundedIndex = Math.max(0, Math.min(competitionData.rounds.length - 1, newRoundIndex));
        const previousIndex = currentRoundIndex;
        currentRoundIndex = boundedIndex;
        if (markManual && boundedIndex !== previousIndex) {
            userHasManualRoundSelection = true;
        }
        activeTab = newTab || activeTab;

        const roundNumber = competitionData.rounds[currentRoundIndex].index;

        // Atualiza o hash sem disparar o evento hashchange
        let newHash = `#${activeTab}`;
        newHash += `-j${roundNumber}`;
        history.replaceState(null, '', newHash);

        updateUI();
    };

    const handleHashChange = () => {
        const hash = window.location.hash || '#resultados-j1';
        const parts = hash.substring(1).split('-j');
        
        const newTab = parts[0] || 'resultados';
        const roundNumber = parts[1] ? parseInt(parts[1], 10) : 1;

        const newRoundIndex = competitionData.rounds.findIndex(r => r.index === roundNumber);

        currentRoundIndex = newRoundIndex !== -1 ? newRoundIndex : 0;
        activeTab = (newTab === 'classificacao') ? 'classificacao' : 'resultados';

        updateUI();
    };

    // --- BUSCA DE DADOS ---
    const fetchData = async () => {
        try {
            // Cache buster para garantir dados frescos
            const cacheBuster = `?v=${new Date().getTime()}`;
            
            const [competitionResponse, crestsResponse] = await Promise.all([
                fetch(`data/${competitionKey}.json${cacheBuster}`),
                fetch(`data/crests.json${cacheBuster}`)
            ]);

            if (!competitionResponse.ok) {
                throw new Error(`Falha ao obter dados da competição (${competitionResponse.status})`);
            }
            if (!crestsResponse.ok) {
                throw new Error(`Falha ao obter dados de emblemas (${crestsResponse.status})`);
            }

            competitionData = await competitionResponse.json();
            crestsData = await crestsResponse.json();

            initializeRoundBasedOnDate();

            // Renderização inicial com dados locais
            handleHashChange();

            // Atualização com dados em tempo real (quando disponíveis)
            await hydrateRoundsWithLiveData();
            updateUI();

        } catch (error) {
            console.error('Erro ao carregar os dados da competição:', error);
            matchesContainer.innerHTML = '<p>Não foi possível carregar os dados. Tente novamente mais tarde.</p>';
        }
    };

    // --- EVENT LISTENERS ---
    if (prevRoundBtn) prevRoundBtn.addEventListener('click', () => navigate(currentRoundIndex - 1));
    if (nextRoundBtn) nextRoundBtn.addEventListener('click', () => navigate(currentRoundIndex + 1));
    if (prevRoundBtnClass) prevRoundBtnClass.addEventListener('click', () => navigate(currentRoundIndex - 1, 'classificacao'));
    if (nextRoundBtnClass) nextRoundBtnClass.addEventListener('click', () => navigate(currentRoundIndex + 1, 'classificacao'));
    tabResultados.addEventListener('click', (event) => {
        if (event) event.preventDefault();
        const targetIndex = userHasManualRoundSelection ? currentRoundIndex : findBestRoundIndexByDate();
        navigate(targetIndex, 'resultados', userHasManualRoundSelection);
    });
    tabClassificacao.addEventListener('click', (event) => {
        if (event) event.preventDefault();
        const targetIndex = userHasManualRoundSelection ? currentRoundIndex : findBestRoundIndexByDate();
        navigate(targetIndex, 'classificacao', userHasManualRoundSelection);
    });
    // acessibilidade via teclado
    [tabResultados, tabClassificacao].forEach(tab => {
        tab.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                navigate(currentRoundIndex, tab.id === 'tab-resultados' ? 'resultados' : 'classificacao');
            }
        });
    });
    
    // A navegação por tabs é feita via hashchange
    window.addEventListener('hashchange', handleHashChange);
    // re-render quando muda entre mobile/desktop
    let lastIsMobile = window.innerWidth <= 480;
    window.addEventListener('resize', () => {
        const isMobile = window.innerWidth <= 480;
        if (isMobile !== lastIsMobile) {
            lastIsMobile = isMobile;
            updateUI();
        }
    });

    // Inicia a aplicação
    fetchData();
});
