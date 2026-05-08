document.addEventListener('DOMContentLoaded', () => {
    const tabProximos = document.getElementById('tab-proximos');
    const tabResultados = document.getElementById('tab-agenda-resultados');
    const contentProximos = document.getElementById('content-proximos');
    const contentResultados = document.getElementById('content-resultados-globais');
    const summaryProximos = document.getElementById('agenda-summary-proximos');
    const summaryResultados = document.getElementById('agenda-summary-resultados');
    const listProximos = document.getElementById('agenda-list-proximos');
    const listResultados = document.getElementById('agenda-list-resultados');
    const dateRangeTrigger = document.getElementById('filter-date-range-trigger');
    const dateRangePicker = document.getElementById('date-range-picker');
    const dateRangePickerSummary = document.getElementById('date-range-picker-summary');
    const dateRangeCalendars = document.getElementById('date-range-calendars');
    const dateRangePrev = document.getElementById('date-range-prev');
    const dateRangeNext = document.getElementById('date-range-next');
    const dateRangeApply = document.getElementById('date-range-apply');
    const dateRangeCancel = document.getElementById('date-range-cancel');
    const dateRangeClose = document.getElementById('date-range-picker-close');
    const dateRangeStartInput = document.getElementById('date-range-start-input');
    const dateRangeEndInput = document.getElementById('date-range-end-input');
    const competitionSelect = document.getElementById('filter-competition');
    const dataStatus = document.getElementById('agenda-data-status');
    const presetButtons = Array.from(document.querySelectorAll('.agenda-preset-btn'));

    const CALENDAR_CACHE_KEY = 'cfa-calendar-cache-v1';
    const CRESTS_CACHE_KEY = 'cfa-crests-cache-v1';
    const MONTH_LABELS = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'];
    const WEEKDAY_LABELS = ['S', 'T', 'Q', 'Q', 'S', 'S', 'D'];
    const LIVE_DATA_ENDPOINT = 'https://resultados.fpf.pt/Competition/GetClassificationAndMatchesByFixture?fixtureId=';
    const LIVE_DATA_SOURCES = [
        (fixtureId) => `${LIVE_DATA_ENDPOINT}${fixtureId}`,
        (fixtureId) => `https://corsproxy.io/?${LIVE_DATA_ENDPOINT}${fixtureId}`,
        (fixtureId) => `https://r.jina.ai/http://resultados.fpf.pt/Competition/GetClassificationAndMatchesByFixture?fixtureId=${fixtureId}`,
    ];

    let activeTab = 'proximos';
    let calendarData = null;
    let crestsData = null;
    let selectedRange = { start: null, end: null };
    let draftRange = { start: null, end: null };
    let pickerMonth = null;
    let renderToken = 0;
    const remoteRoundCache = new Map();
    const htmlDecoder = document.createElement('textarea');

    const normalizeName = (name) => {
        if (!name) return '';
        return name
            .normalize('NFD')
            .replace(/[\u0300-\u036f]+/g, '')
            .toLowerCase()
            .replace(/[\-_]+/g, ' ')
            .replace(/[^a-z0-9 ]+/g, '')
            .replace(/\s+/g, ' ')
            .trim();
    };

    const canonicalTeamName = (teamName) => {
        const normalized = normalizeName(teamName);
        if (normalized === 'cf os armacenenses a' || normalized === 'cf os armacenenses b') {
            return 'cf os armacenenses';
        }
        return normalized;
    };

    const displayTeamName = (teamName, competitionKey) => {
        const normalized = normalizeName(teamName);
        if ((competitionKey === 'feminino-sub17' || competitionKey === 'iniciados-b') && normalized === 'cf os armacenenses b') {
            return 'CF Os Armacenenses (Fem-Sub17)';
        }
        return teamName;
    };

    const isArmacenensesTeam = (teamName, competitionKey) => {
        const normalized = normalizeName(teamName);
        if (competitionKey === 'feminino-sub17') {
            return normalized === 'cf os armacenenses b';
        }
        if (competitionKey === 'iniciados-b') {
            return normalized === 'cf os armacenenses a';
        }
        return normalized === 'cf os armacenenses' || normalized === 'cf os armacenenses a';
    };

    const getCrestUrl = (teamName) => {
        const fallback = 'img/crests/jornada.png';
        if (!crestsData) return fallback;
        return crestsData[canonicalTeamName(teamName)] || fallback;
    };

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

    const readJSONFromStorage = (key) => {
        try {
            const raw = window.localStorage.getItem(key);
            return raw ? JSON.parse(raw) : null;
        } catch (error) {
            return null;
        }
    };

    const writeJSONToStorage = (key, value) => {
        try {
            window.localStorage.setItem(key, JSON.stringify(value));
        } catch (error) {
            // storage may be unavailable
        }
    };

    const formatTimestamp = (value) => {
        if (!value) return null;
        const parsed = new Date(value);
        if (Number.isNaN(parsed.getTime())) return null;
        return new Intl.DateTimeFormat('pt-PT', {
            dateStyle: 'short',
            timeStyle: 'short',
        }).format(parsed);
    };

    const parseISODate = (value) => {
        if (!value) return null;
        const parsed = new Date(value);
        return Number.isNaN(parsed.getTime()) ? null : parsed;
    };

    const formatGroupDate = (date) => {
        return new Intl.DateTimeFormat('pt-PT', {
            weekday: 'long',
            day: 'numeric',
            month: 'long',
        }).format(date);
    };

    const formatInputDate = (date) => {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    };

    const createDateAtMidday = (date) => {
        const next = new Date(date);
        next.setHours(12, 0, 0, 0);
        return next;
    };

    const startOfDay = (date) => {
        if (!date) return null;
        const next = new Date(date);
        next.setHours(0, 0, 0, 0);
        return next;
    };

    const endOfDay = (date) => {
        if (!date) return null;
        const next = new Date(date);
        next.setHours(23, 59, 59, 999);
        return next;
    };

    const cloneRange = (range) => ({
        start: range?.start ? new Date(range.start) : null,
        end: range?.end ? new Date(range.end) : null,
    });

    const sameCalendarDay = (left, right) => {
        if (!left || !right) return false;
        return (
            left.getFullYear() === right.getFullYear() &&
            left.getMonth() === right.getMonth() &&
            left.getDate() === right.getDate()
        );
    };

    const compareDates = (left, right) => {
        return startOfDay(left).getTime() - startOfDay(right).getTime();
    };

    const addMonths = (date, amount) => {
        const next = new Date(date);
        next.setDate(1);
        next.setMonth(next.getMonth() + amount);
        return next;
    };

    const formatRangeLabel = (range) => {
        if (!range?.start || !range?.end) {
            return 'Selecionar período';
        }
        const start = range.start;
        const end = range.end;
        const startLabel = `${start.getDate()} ${MONTH_LABELS[start.getMonth()].slice(0, 3)}`;
        const endLabel = `${end.getDate()} ${MONTH_LABELS[end.getMonth()].slice(0, 3)}`;
        return `${startLabel} - ${endLabel}`;
    };

    const setSelectedRange = (start, end = start) => {
        selectedRange = {
            start: start ? createDateAtMidday(start) : null,
            end: end ? createDateAtMidday(end) : null,
        };
        updateRangeTrigger();
    };

    const updateRangeTrigger = () => {
        dateRangeTrigger.textContent = formatRangeLabel(selectedRange);
    };

    const formatPickerSummary = (range) => {
        if (!range.start) return 'Escolhe a data inicial e final.';
        if (!range.end) return `Início: ${formatInputDate(range.start)}. Escolhe a data final.`;
        return `${formatInputDate(range.start)} até ${formatInputDate(range.end)}`;
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

    const inferEntryStatus = (entry) => {
        if (Number.isInteger(entry.homeScore) && Number.isInteger(entry.awayScore)) {
            return 'finished';
        }
        const parsed = parseISODate(entry.matchDateISO);
        if (!parsed) return 'unknown';
        return parsed >= new Date() ? 'scheduled' : 'unknown';
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
                        Accept: 'text/html,application/xhtml+xml',
                    },
                    cache: 'no-store',
                    mode: 'cors',
                });

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }

                const html = await response.text();
                const matches = parseMatchesFragment(html);
                if (!matches.length) {
                    throw new Error('Resposta sem jogos utilizáveis');
                }

                remoteRoundCache.set(fixtureId, matches);
                return matches;
            } catch (error) {
                lastError = error;
            }
        }

        if (lastError) {
            console.warn(`Falha ao carregar fixture remoto ${fixtureId}:`, lastError);
        }
        remoteRoundCache.set(fixtureId, null);
        return null;
    };

    const openDateRangePicker = () => {
        draftRange = cloneRange(selectedRange);
        const today = createDateAtMidday(new Date());
        pickerMonth = new Date((draftRange.start || today).getFullYear(), (draftRange.start || today).getMonth(), 1, 12, 0, 0, 0);
        dateRangeStartInput.value = draftRange.start ? formatInputDate(draftRange.start) : '';
        dateRangeEndInput.value = draftRange.end ? formatInputDate(draftRange.end) : '';
        renderDateRangePicker();
        dateRangePicker.classList.remove('hidden');
        dateRangeTrigger.setAttribute('aria-expanded', 'true');
    };

    const closeDateRangePicker = () => {
        dateRangePicker.classList.add('hidden');
        dateRangeTrigger.setAttribute('aria-expanded', 'false');
    };

    const handleDraftDateSelection = (date) => {
        const clicked = createDateAtMidday(date);
        if (!draftRange.start || (draftRange.start && draftRange.end)) {
            draftRange = { start: clicked, end: null };
        } else if (compareDates(clicked, draftRange.start) < 0) {
            draftRange = { start: clicked, end: draftRange.start };
        } else {
            draftRange = { start: draftRange.start, end: clicked };
        }
        dateRangeStartInput.value = draftRange.start ? formatInputDate(draftRange.start) : '';
        dateRangeEndInput.value = draftRange.end ? formatInputDate(draftRange.end) : '';
        renderDateRangePicker();
    };

    const renderSingleCalendarMonth = (monthDate) => {
        const year = monthDate.getFullYear();
        const month = monthDate.getMonth();
        const firstDay = new Date(year, month, 1, 12, 0, 0, 0);
        const startingWeekday = (firstDay.getDay() + 6) % 7;
        const daysInMonth = new Date(year, month + 1, 0).getDate();
        const today = createDateAtMidday(new Date());
        const cells = [];

        for (let index = 0; index < startingWeekday; index += 1) {
            cells.push('<span class="agenda-calendar__cell agenda-calendar__cell--empty" aria-hidden="true"></span>');
        }

        for (let day = 1; day <= daysInMonth; day += 1) {
            const cellDate = new Date(year, month, day, 12, 0, 0, 0);
            const isStart = draftRange.start && sameCalendarDay(cellDate, draftRange.start);
            const effectiveEnd = draftRange.end || draftRange.start;
            const isEnd = draftRange.end && sameCalendarDay(cellDate, draftRange.end);
            const isInRange = draftRange.start && effectiveEnd
                ? compareDates(cellDate, draftRange.start) >= 0 && compareDates(cellDate, effectiveEnd) <= 0
                : false;
            const isToday = sameCalendarDay(cellDate, today);
            const classes = ['agenda-calendar__cell'];
            if (isInRange) classes.push('agenda-calendar__cell--in-range');
            if (isStart) classes.push('agenda-calendar__cell--start');
            if (isEnd) classes.push('agenda-calendar__cell--end');
            if (isToday) classes.push('agenda-calendar__cell--today');
            cells.push(
                `<button type="button" class="${classes.join(' ')}" data-date="${formatInputDate(cellDate)}">${day}</button>`
            );
        }

        return `
            <section class="agenda-calendar">
                <header class="agenda-calendar__header">${MONTH_LABELS[month]} ${year}</header>
                <div class="agenda-calendar__weekdays">
                    ${WEEKDAY_LABELS.map((label) => `<span>${label}</span>`).join('')}
                </div>
                <div class="agenda-calendar__grid">
                    ${cells.join('')}
                </div>
            </section>
        `;
    };

    const renderDateRangePicker = () => {
        dateRangePickerSummary.textContent = formatPickerSummary(draftRange);
        dateRangeCalendars.innerHTML = [
            renderSingleCalendarMonth(pickerMonth),
            renderSingleCalendarMonth(addMonths(pickerMonth, 1)),
        ].join('');
    };

    const updateDraftRangeFromInputs = () => {
        const start = dateRangeStartInput.value
            ? createDateAtMidday(new Date(`${dateRangeStartInput.value}T12:00:00`))
            : null;
        const end = dateRangeEndInput.value
            ? createDateAtMidday(new Date(`${dateRangeEndInput.value}T12:00:00`))
            : null;

        if (start && end && compareDates(end, start) < 0) {
            draftRange = { start: end, end: start };
            dateRangeStartInput.value = formatInputDate(end);
            dateRangeEndInput.value = formatInputDate(start);
        } else {
            draftRange = { start, end };
        }
        renderDateRangePicker();
    };

    const applyPreset = (preset) => {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const start = new Date(today);
        const end = new Date(today);

        switch (preset) {
            case 'today':
                break;
            case 'weekend': {
                const day = today.getDay();
                const daysUntilSaturday = day === 6 ? 0 : (6 - day + 7) % 7;
                start.setDate(today.getDate() + daysUntilSaturday);
                end.setTime(start.getTime());
                end.setDate(start.getDate() + 1);
                break;
            }
            case 'next7':
                end.setDate(today.getDate() + 6);
                break;
            case 'last7':
                start.setDate(today.getDate() - 6);
                break;
            default:
                return;
        }
        setSelectedRange(start, end);

        if (preset === 'last7') {
            setActiveTab('resultados');
        } else {
            setActiveTab('proximos');
        }
        render();
    };

    const ensureDefaultFilters = () => {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        if (!selectedRange.start || !selectedRange.end) {
            if (activeTab === 'resultados') {
                const start = new Date(today);
                start.setDate(today.getDate() - 6);
                setSelectedRange(start, today);
            } else {
                const end = new Date(today);
                end.setDate(today.getDate() + 6);
                setSelectedRange(today, end);
            }
        }
    };

    const populateCompetitionFilter = () => {
        if (!calendarData || !Array.isArray(calendarData.competitions)) return;
        const currentValue = competitionSelect.value;
        const options = ['<option value="">Todas</option>']
            .concat(
                calendarData.competitions.map((competition) => (
                    `<option value="${competition.key}">${competition.title}</option>`
                ))
            );
        competitionSelect.innerHTML = options.join('');
        competitionSelect.value = currentValue || '';
    };

    const renderDataStatus = () => {
        if (!calendarData) {
            dataStatus.classList.add('hidden');
            dataStatus.innerHTML = '';
            return;
        }
        const updatedLabel = formatTimestamp(calendarData.generatedAt);
        const degradedCompetitions = (calendarData.competitions || []).filter(
            (competition) => competition.sourceHealth && competition.sourceHealth.status === 'degraded'
        );

        const parts = [];
        if (updatedLabel) {
            parts.push(`<span class="data-status__item">Atualizado: ${updatedLabel}</span>`);
        }
        if (degradedCompetitions.length) {
            parts.push(
                `<span class="data-status__item data-status__item--warning">Origem: degradada em ${degradedCompetitions.length} competição(ões)</span>`
            );
        } else {
            parts.push('<span class="data-status__item">Origem: estável</span>');
        }
        dataStatus.innerHTML = parts.join('');
        dataStatus.classList.remove('hidden');
    };

    const updateTabsUI = () => {
        const isProximos = activeTab === 'proximos';
        tabProximos.classList.toggle('active', isProximos);
        tabResultados.classList.toggle('active', !isProximos);
        tabProximos.setAttribute('aria-selected', String(isProximos));
        tabResultados.setAttribute('aria-selected', String(!isProximos));
        tabProximos.setAttribute('tabindex', isProximos ? '0' : '-1');
        tabResultados.setAttribute('tabindex', isProximos ? '-1' : '0');
        contentProximos.classList.toggle('hidden', !isProximos);
        contentResultados.classList.toggle('hidden', isProximos);
    };

    const setActiveTab = (nextTab) => {
        activeTab = nextTab === 'resultados' ? 'resultados' : 'proximos';
        updateTabsUI();
        ensureDefaultFilters();
        history.replaceState(null, '', `#${activeTab}`);
    };

    const getDateRange = () => {
        const start = startOfDay(selectedRange.start);
        const end = endOfDay(selectedRange.end);
        return { start, end };
    };

    const matchesDateRange = (entry, start, end) => {
        const parsed = parseISODate(entry.matchDateISO);
        if (!parsed) return false;
        if (start && parsed < start) return false;
        if (end && parsed > end) return false;
        return true;
    };

    const getCandidateMatches = () => {
        if (!calendarData || !Array.isArray(calendarData.matches)) return [];
        const { start, end } = getDateRange();
        const competitionKey = competitionSelect.value;

        return calendarData.matches.filter((entry) => {
            if (competitionKey && entry.competitionKey !== competitionKey) return false;
            return matchesDateRange(entry, start, end);
        });
    };

    const getFilteredMatches = () => {
        const candidates = getCandidateMatches();
        return candidates.filter((entry) => {
            if (activeTab === 'proximos') return entry.status === 'scheduled';
            if (activeTab === 'resultados') return entry.status === 'finished';
            return true;
        });
    };

    const hydrateVisibleMatches = async (token) => {
        const candidates = getCandidateMatches();
        if (!candidates.length) return;

        const fixtureMap = new Map();
        candidates.forEach((entry) => {
            if (!entry.fixtureId) return;
            const fixtureEntries = fixtureMap.get(entry.fixtureId) || [];
            fixtureEntries.push(entry);
            fixtureMap.set(entry.fixtureId, fixtureEntries);
        });

        let changed = false;

        for (const [fixtureId, entries] of fixtureMap.entries()) {
            const liveMatches = await fetchRoundFromRemote(fixtureId);
            if (!liveMatches) continue;

            entries.forEach((entry) => {
                const liveMatch = liveMatches.find((candidate) => (
                    normalizeName(candidate.home) === normalizeName(entry.home) &&
                    normalizeName(candidate.away) === normalizeName(entry.away)
                ));
                if (!liveMatch) return;

                const nextHomeScore = liveMatch.homeScore;
                const nextAwayScore = liveMatch.awayScore;
                const nextDate = liveMatch.date || entry.displayDate;
                const nextTime = liveMatch.time || entry.displayTime;
                const nextStadium = liveMatch.stadium || entry.stadium;

                if (
                    entry.homeScore !== nextHomeScore ||
                    entry.awayScore !== nextAwayScore ||
                    entry.displayDate !== nextDate ||
                    entry.displayTime !== nextTime ||
                    entry.stadium !== nextStadium
                ) {
                    entry.homeScore = nextHomeScore;
                    entry.awayScore = nextAwayScore;
                    entry.displayDate = nextDate;
                    entry.displayTime = nextTime;
                    entry.stadium = nextStadium;
                    entry.status = inferEntryStatus(entry);
                    changed = true;
                }
            });
        }

        if (!changed) return;
        writeJSONToStorage(CALENDAR_CACHE_KEY, calendarData);
        if (token === renderToken) {
            render();
        }
    };

    const groupMatchesByDay = (matches) => {
        const groups = new Map();
        matches.forEach((entry) => {
            const parsed = parseISODate(entry.matchDateISO);
            const key = parsed ? formatInputDate(parsed) : 'sem-data';
            if (!groups.has(key)) {
                groups.set(key, []);
            }
            groups.get(key).push(entry);
        });
        return groups;
    };

    const buildMatchCard = (entry) => {
        const homeDisplayName = displayTeamName(entry.home, entry.competitionKey);
        const awayDisplayName = displayTeamName(entry.away, entry.competitionKey);
        const homeCrest = getCrestUrl(entry.home);
        const awayCrest = getCrestUrl(entry.away);
        const score = Number.isInteger(entry.homeScore) && Number.isInteger(entry.awayScore)
            ? `${entry.homeScore} - ${entry.awayScore}`
            : (entry.displayTime || 'Agendado');

        return `
            <article class="agenda-match-card">
                <a href="${entry.competitionUrl || '#'}" class="agenda-match-card__link" aria-label="Abrir ${entry.competitionTitle}">
                    <div class="agenda-match-card__meta">
                        <span class="agenda-chip">${entry.competitionTitle}</span>
                        <span class="agenda-match-card__round">Jornada ${entry.roundNumber}</span>
                    </div>
                    <div class="agenda-match-card__teams">
                        <div class="agenda-team ${isArmacenensesTeam(entry.home, entry.competitionKey) ? 'agenda-team--highlight' : ''}">
                            <img src="${homeCrest}" alt="${homeDisplayName}" class="team-crest">
                            <span>${homeDisplayName}</span>
                        </div>
                        <div class="agenda-match-card__score">${score}</div>
                        <div class="agenda-team ${isArmacenensesTeam(entry.away, entry.competitionKey) ? 'agenda-team--highlight' : ''}">
                            <span>${awayDisplayName}</span>
                            <img src="${awayCrest}" alt="${awayDisplayName}" class="team-crest">
                        </div>
                    </div>
                    <div class="agenda-match-card__footer">
                        <span>${entry.displayDate}${entry.displayTime ? ` · ${entry.displayTime}` : ''}</span>
                        <span>${entry.stadium || ''}</span>
                        <span>${entry.competitionSubtitle}</span>
                    </div>
                </a>
            </article>
        `;
    };

    const renderList = (container, summary, matches) => {
        if (!matches.length) {
            summary.textContent = 'Sem jogos para os filtros selecionados.';
            container.innerHTML = '<p class="agenda-empty-state">Nenhum jogo encontrado.</p>';
            return;
        }

        const orderedMatches = [...matches].sort((left, right) => {
            const leftTs = left.sortTimestamp || 0;
            const rightTs = right.sortTimestamp || 0;
            return activeTab === 'resultados' ? rightTs - leftTs : leftTs - rightTs;
        });

        const groups = groupMatchesByDay(orderedMatches);
        const groupEntries = Array.from(groups.entries()).sort((left, right) => {
            return activeTab === 'resultados'
                ? right[0].localeCompare(left[0])
                : left[0].localeCompare(right[0]);
        });

        summary.textContent = `${matches.length} jogo(s) encontrado(s).`;

        const html = groupEntries.map(([groupKey, groupMatches]) => {
            const groupDate = groupKey === 'sem-data'
                ? 'Data por confirmar'
                : formatGroupDate(new Date(`${groupKey}T12:00:00`));
            return `
                <section class="agenda-day-group">
                    <h2 class="agenda-day-group__title">${groupDate}</h2>
                    <div class="agenda-day-group__list">
                        ${groupMatches.map(buildMatchCard).join('')}
                    </div>
                </section>
            `;
        }).join('');

        container.innerHTML = html;
    };

    const render = () => {
        renderToken += 1;
        const currentToken = renderToken;
        ensureDefaultFilters();
        const matches = getFilteredMatches();
        if (activeTab === 'proximos') {
            renderList(listProximos, summaryProximos, matches);
        } else {
            renderList(listResultados, summaryResultados, matches);
        }
        void hydrateVisibleMatches(currentToken);
    };

    const loadFreshData = async () => {
        const [calendarResponse, crestsResponse] = await Promise.all([
            fetch('data/calendar.json', { cache: 'no-cache' }),
            fetch('data/crests.json', { cache: 'force-cache' }),
        ]);

        if (!calendarResponse.ok) {
            throw new Error(`Falha ao obter calendário (${calendarResponse.status})`);
        }

        calendarData = await calendarResponse.json();
        writeJSONToStorage(CALENDAR_CACHE_KEY, calendarData);

        if (crestsResponse.ok) {
            crestsData = await crestsResponse.json();
            writeJSONToStorage(CRESTS_CACHE_KEY, crestsData);
        }
    };

    const bootstrap = async () => {
        const cachedCalendar = readJSONFromStorage(CALENDAR_CACHE_KEY);
        if (cachedCalendar && Array.isArray(cachedCalendar.matches)) {
            calendarData = cachedCalendar;
        }

        const cachedCrests = readJSONFromStorage(CRESTS_CACHE_KEY);
        if (cachedCrests && typeof cachedCrests === 'object') {
            crestsData = cachedCrests;
        }

        const initialHash = (window.location.hash || '').replace('#', '').toLowerCase();
        setActiveTab(initialHash === 'resultados' ? 'resultados' : 'proximos');

        if (calendarData) {
            populateCompetitionFilter();
            renderDataStatus();
            render();
        }

        try {
            await loadFreshData();
            populateCompetitionFilter();
            renderDataStatus();
            render();
        } catch (error) {
            console.error('Erro ao carregar Agenda:', error);
            if (!calendarData) {
                listProximos.innerHTML = '<p class="agenda-empty-state">Não foi possível carregar a agenda.</p>';
                listResultados.innerHTML = '<p class="agenda-empty-state">Não foi possível carregar os resultados.</p>';
            }
        }
    };

    tabProximos.addEventListener('click', (event) => {
        event.preventDefault();
        setActiveTab('proximos');
        render();
    });

    tabResultados.addEventListener('click', (event) => {
        event.preventDefault();
        setActiveTab('resultados');
        render();
    });

    [tabProximos, tabResultados].forEach((tab) => {
        tab.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                if (tab === tabResultados) {
                    setActiveTab('resultados');
                } else {
                    setActiveTab('proximos');
                }
                render();
            }
        });
    });

    competitionSelect.addEventListener('change', render);

    presetButtons.forEach((button) => {
        button.addEventListener('click', () => applyPreset(button.dataset.preset));
    });

    dateRangePicker.addEventListener('click', (event) => {
        event.stopPropagation();
    });

    dateRangeTrigger.addEventListener('click', () => {
        if (dateRangePicker.classList.contains('hidden')) {
            openDateRangePicker();
        } else {
            closeDateRangePicker();
        }
    });

    dateRangePrev.addEventListener('click', () => {
        pickerMonth = addMonths(pickerMonth, -1);
        renderDateRangePicker();
    });

    dateRangeNext.addEventListener('click', () => {
        pickerMonth = addMonths(pickerMonth, 1);
        renderDateRangePicker();
    });

    dateRangeCalendars.addEventListener('click', (event) => {
        const button = event.target.closest('[data-date]');
        if (!button) return;
        const [year, month, day] = button.dataset.date.split('-').map((value) => Number.parseInt(value, 10));
        handleDraftDateSelection(new Date(year, month - 1, day, 12, 0, 0, 0));
    });

    [dateRangeStartInput, dateRangeEndInput].forEach((input) => {
        input.addEventListener('change', updateDraftRangeFromInputs);
    });

    dateRangeApply.addEventListener('click', () => {
        updateDraftRangeFromInputs();
        if (!draftRange.start) {
            closeDateRangePicker();
            return;
        }
        setSelectedRange(draftRange.start, draftRange.end || draftRange.start);
        closeDateRangePicker();
        render();
    });

    const dismissRangePicker = () => {
        draftRange = cloneRange(selectedRange);
        closeDateRangePicker();
    };

    dateRangeCancel.addEventListener('click', dismissRangePicker);
    dateRangeClose.addEventListener('click', dismissRangePicker);

    document.addEventListener('click', (event) => {
        if (dateRangePicker.classList.contains('hidden')) return;
        if (dateRangePicker.contains(event.target) || dateRangeTrigger.contains(event.target)) return;
        dismissRangePicker();
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && !dateRangePicker.classList.contains('hidden')) {
            dismissRangePicker();
        }
    });

    bootstrap();
});
