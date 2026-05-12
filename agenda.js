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
    const dateRangeMonthSelect = document.getElementById('date-range-month-select');
    const dateRangeYearSelect = document.getElementById('date-range-year-select');
    const dateRangeApply = document.getElementById('date-range-apply');
    const dateRangeClear = document.getElementById('date-range-clear');
    const dateRangeCancel = document.getElementById('date-range-cancel');
    const dateRangeClose = document.getElementById('date-range-picker-close');
    const dateRangeStartInput = document.getElementById('date-range-start-input');
    const dateRangeEndInput = document.getElementById('date-range-end-input');
    const competitionSelect = document.getElementById('filter-competition');
    const dataStatus = document.getElementById('agenda-data-status');

    const CALENDAR_CACHE_KEY = 'cfa-calendar-cache-v1';
    const CRESTS_CACHE_KEY = 'cfa-crests-cache-v1';
    const COMPETITION_CACHE_PREFIX = 'cfa-competition-cache-v1:';
    const CALENDAR_CACHE_MAX_AGE_MS = 30 * 60 * 1000;
    const COMPETITION_CACHE_MAX_AGE_MS = 2 * 60 * 60 * 1000;
    const MONTH_LABELS = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'];
    const WEEKDAY_LABELS = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];
    const LIVE_DATA_ENDPOINT = 'https://resultados.fpf.pt/Competition/GetClassificationAndMatchesByFixture?fixtureId=';
    const LIVE_DATA_SOURCES = [
        (fixtureId) => `${LIVE_DATA_ENDPOINT}${fixtureId}`,
        (fixtureId) => `https://corsproxy.io/?${LIVE_DATA_ENDPOINT}${fixtureId}`,
        (fixtureId) => `https://r.jina.ai/http://resultados.fpf.pt/Competition/GetClassificationAndMatchesByFixture?fixtureId=${fixtureId}`,
    ];
    const COMPETITION_ACCENTS = {
        agenda: '#c8a84d',
        seniores: '#0f59a7',
        juniores: '#383e42',
        juvenis: '#55738c',
        'iniciados-a': '#277e86',
        'iniciados-b': '#277e86',
        'infantis-a': '#0db3d8',
        'infantis-b': '#0db3d8',
        'infantis-c': '#0db3d8',
        'benjamins-a1': '#fb6a68',
        'benjamins-a2': '#fb6a68',
        'benjamins-b': '#fb6a68',
        'benjamins-bb': '#fb6a68',
        'feminino-sub19': '#e678b1',
        'feminino-sub17': '#e678b1',
        'feminino-sub15': '#e678b1',
    };

    let activeTab = 'proximos';
    let calendarData = null;
    let calendarDataSource = 'published';
    let crestsData = null;
    let selectedRange = { start: null, end: null };
    let draftRange = { start: null, end: null };
    let hasAppliedRange = false;
    let pickerMonth = null;
    let renderToken = 0;
    const remoteRoundCache = new Map();
    const competitionPayloadCache = new Map();
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
        if (normalized === 'casa benfica tavira') {
            return 'casa slb tavira';
        }
        if (normalized === 'clube u culatrense') {
            return 'cu culatrense';
        }
        if (normalized === 'cf os armacenenses a' || normalized === 'cf os armacenenses b') {
            return 'cf os armacenenses';
        }
        return normalized;
    };

    const displayTeamName = (teamName, competitionKey) => {
        const normalized = normalizeName(teamName);
        if (
            competitionKey === 'feminino-sub17' &&
            (normalized === 'cf os armacenenses a' || normalized === 'cf os armacenenses b')
        ) {
            return 'CF Os Armacenenses (Fem-Sub17)';
        }
        return teamName;
    };

    const isArmacenensesTeam = (teamName, competitionKey) => {
        const normalized = normalizeName(teamName);
        if (competitionKey === 'feminino-sub17') {
            return normalized === 'cf os armacenenses a' || normalized === 'cf os armacenenses b';
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

    const hexToRgba = (hex, alpha) => {
        if (!hex || typeof hex !== 'string') return `rgba(17, 24, 32, ${alpha})`;
        const normalized = hex.replace('#', '').trim();
        if (normalized.length !== 6) return `rgba(17, 24, 32, ${alpha})`;
        const r = Number.parseInt(normalized.slice(0, 2), 16);
        const g = Number.parseInt(normalized.slice(2, 4), 16);
        const b = Number.parseInt(normalized.slice(4, 6), 16);
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
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

    const cleanDisplayDate = (value = '') => {
        if (!value) return '';
        return cleanHTMLText(value)
            .replace(/\b\d{1,2}\s*[-–]\s*\d{1,2}\b/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
    };

    const textFromNode = (node) => (node ? cleanHTMLText(node.textContent || '') : '');

    const readStorageEntry = (key) => {
        try {
            const raw = window.localStorage.getItem(key);
            if (!raw) return null;
            const parsed = JSON.parse(raw);
            if (
                parsed &&
                typeof parsed === 'object' &&
                parsed.__cacheMeta &&
                Object.prototype.hasOwnProperty.call(parsed, 'payload')
            ) {
                return {
                    payload: parsed.payload,
                    savedAt: Number(parsed.__cacheMeta.savedAt) || 0,
                };
            }
            return {
                payload: parsed,
                savedAt: 0,
            };
        } catch (error) {
            return null;
        }
    };

    const readJSONFromStorage = (key, { maxAgeMs = null } = {}) => {
        const entry = readStorageEntry(key);
        if (!entry) return null;
        if (maxAgeMs !== null && entry.savedAt && (Date.now() - entry.savedAt) > maxAgeMs) {
            return null;
        }
        return entry.payload;
    };

    const writeJSONToStorage = (key, value) => {
        try {
            window.localStorage.setItem(key, JSON.stringify({
                __cacheMeta: {
                    savedAt: Date.now(),
                },
                payload: value,
            }));
        } catch (error) {
            // storage may be unavailable
        }
    };

    const getCompetitionCacheKey = (competitionKey) => `${COMPETITION_CACHE_PREFIX}${competitionKey}`;

    const isValidCompetitionPayload = (payload) => {
        return Boolean(
            payload &&
            Array.isArray(payload.rounds) &&
            payload.rounds.every((round) => round && Array.isArray(round.matches))
        );
    };

    const countFinishedMatches = (payload) => {
        if (!isValidCompetitionPayload(payload)) return -1;
        let count = 0;
        payload.rounds.forEach((round) => {
            round.matches.forEach((match) => {
                if (Number.isInteger(match?.homeScore) && Number.isInteger(match?.awayScore)) {
                    count += 1;
                }
            });
        });
        return count;
    };

    const selectPreferredCompetitionPayload = (cachedPayload, fetchedPayload, cacheSavedAt = 0) => {
        const cachedValid = isValidCompetitionPayload(cachedPayload);
        const fetchedValid = isValidCompetitionPayload(fetchedPayload);
        if (cachedValid && !fetchedValid) return cachedPayload;
        if (!cachedValid && fetchedValid) return fetchedPayload;
        if (!cachedValid && !fetchedValid) return null;

        if (cacheSavedAt && (Date.now() - cacheSavedAt) > COMPETITION_CACHE_MAX_AGE_MS) {
            return fetchedPayload;
        }

        const cachedUpdatedAt = Date.parse(cachedPayload.lastUpdatedAt || '') || 0;
        const fetchedUpdatedAt = Date.parse(fetchedPayload.lastUpdatedAt || '') || 0;
        if (cachedUpdatedAt !== fetchedUpdatedAt) {
            return cachedUpdatedAt > fetchedUpdatedAt ? cachedPayload : fetchedPayload;
        }

        const cachedFinished = countFinishedMatches(cachedPayload);
        const fetchedFinished = countFinishedMatches(fetchedPayload);
        if (cachedFinished !== fetchedFinished) {
            return cachedFinished > fetchedFinished ? cachedPayload : fetchedPayload;
        }

        return fetchedPayload;
    };

    const fetchCompetitionPayload = async (competitionMeta) => {
        if (!competitionMeta?.key) return null;
        if (competitionPayloadCache.has(competitionMeta.key)) {
            return competitionPayloadCache.get(competitionMeta.key);
        }

        const cachedEntry = readStorageEntry(getCompetitionCacheKey(competitionMeta.key));
        const cachedPayload = (
            cachedEntry &&
            (!cachedEntry.savedAt || (Date.now() - cachedEntry.savedAt) <= COMPETITION_CACHE_MAX_AGE_MS)
        ) ? cachedEntry.payload : null;
        let fetchedPayload = null;

        if (competitionMeta.outputFile) {
            try {
                const response = await fetch(competitionMeta.outputFile, { cache: 'no-cache' });
                if (response.ok) {
                    fetchedPayload = await response.json();
                }
            } catch (error) {
                console.warn(`Falha ao carregar payload da competição ${competitionMeta.key}:`, error);
            }
        }

        const preferredPayload = selectPreferredCompetitionPayload(
            cachedEntry?.payload || null,
            fetchedPayload,
            cachedEntry?.savedAt || 0
        );
        competitionPayloadCache.set(competitionMeta.key, preferredPayload);
        return preferredPayload;
    };

    const parseDateFromCalendarEntry = (entry) => {
        const parsed = parseISODate(entry.matchDateISO);
        if (parsed) return parsed;
        if (!entry.displayDate) return null;
        const match = entry.displayDate.match(/(\d{1,2})\s+([A-Za-zÀ-ÿ]{3,})/);
        if (!match) return null;
        const months = {
            jan: 0, fev: 1, mar: 2, abr: 3, mai: 4, jun: 5,
            jul: 6, ago: 7, set: 8, out: 9, nov: 10, dez: 11,
        };
        const monthKey = match[2]
            .toLowerCase()
            .normalize('NFD')
            .replace(/[\u0300-\u036f]+/g, '')
            .replace(/[^a-z]/g, '')
            .slice(0, 3);
        if (!Object.prototype.hasOwnProperty.call(months, monthKey)) return null;
        const day = Number.parseInt(match[1], 10);
        const year = new Date().getFullYear();
        return new Date(year, months[monthKey], day, 12, 0, 0, 0);
    };

    const buildCompetitionMatchLookup = (payload) => {
        const lookup = new Map();
        if (!isValidCompetitionPayload(payload)) return lookup;

        payload.rounds.forEach((round) => {
            const roundLookup = new Map();
            round.matches.forEach((match) => {
                roundLookup.set(
                    `${normalizeName(match.home)}|${normalizeName(match.away)}`,
                    match
                );
            });
            lookup.set(String(round.fixtureId || round.index || ''), roundLookup);
        });

        return lookup;
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
        hasAppliedRange = Boolean(selectedRange.start && selectedRange.end);
        updateRangeTrigger();
    };

    const updateRangeTrigger = () => {
        dateRangeTrigger.textContent = formatRangeLabel(selectedRange);
    };

    const clearSelectedRange = () => {
        selectedRange = { start: null, end: null };
        draftRange = { start: null, end: null };
        hasAppliedRange = false;
        updateRangeTrigger();
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
        const today = createDateAtMidday(new Date());
        draftRange = hasAppliedRange
            ? cloneRange(selectedRange)
            : { start: today, end: today };
        pickerMonth = new Date((draftRange.start || today).getFullYear(), (draftRange.start || today).getMonth(), 1, 12, 0, 0, 0);
        dateRangeStartInput.value = draftRange.start ? formatInputDate(draftRange.start) : '';
        dateRangeEndInput.value = draftRange.end ? formatInputDate(draftRange.end) : '';
        renderDateRangePicker();
        dateRangePicker.classList.remove('hidden');
        document.body.classList.add('agenda-picker-open');
        dateRangeTrigger.setAttribute('aria-expanded', 'true');
    };

    const closeDateRangePicker = () => {
        dateRangePicker.classList.add('hidden');
        document.body.classList.remove('agenda-picker-open');
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
            const previousMonthDate = new Date(year, month, index - startingWeekday + 1, 12, 0, 0, 0);
            cells.push(`<span class="agenda-calendar__cell agenda-calendar__cell--outside" aria-hidden="true">${previousMonthDate.getDate()}</span>`);
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

        const filledCells = startingWeekday + daysInMonth;
        const trailingCells = (7 - (filledCells % 7)) % 7;
        for (let index = 1; index <= trailingCells; index += 1) {
            cells.push(`<span class="agenda-calendar__cell agenda-calendar__cell--outside" aria-hidden="true">${index}</span>`);
        }

        return `
            <section class="agenda-calendar">
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
        dateRangeMonthSelect.innerHTML = MONTH_LABELS.map((label, index) => (
            `<option value="${index}" ${index === pickerMonth.getMonth() ? 'selected' : ''}>${label.charAt(0).toUpperCase()}${label.slice(1)}</option>`
        )).join('');

        const currentYear = new Date().getFullYear();
        const yearOptions = [];
        for (let year = currentYear - 2; year <= currentYear + 2; year += 1) {
            yearOptions.push(
                `<option value="${year}" ${year === pickerMonth.getFullYear() ? 'selected' : ''}>${year}</option>`
            );
        }
        dateRangeYearSelect.innerHTML = yearOptions.join('');
        dateRangeCalendars.innerHTML = renderSingleCalendarMonth(pickerMonth);
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
        if (!hasAppliedRange) {
            dataStatus.classList.add('hidden');
            dataStatus.innerHTML = '';
            return;
        }
        const updatedLabel = formatTimestamp(calendarData.generatedAt);
        const competitionStatus = (competition) => {
            const sourceHealth = competition?.sourceHealth || {};
            if (Number.isInteger(sourceHealth.fallbackReuseCount) && sourceHealth.fallbackReuseCount > 0) {
                return 'degraded';
            }
            return sourceHealth.status || 'ok';
        };
        const degradedCompetitions = (calendarData.competitions || []).filter(
            (competition) => competitionStatus(competition) === 'degraded'
        );
        const partialCompetitions = (calendarData.competitions || []).filter(
            (competition) => competitionStatus(competition) === 'partial'
        );

        const parts = [];
        if (updatedLabel) {
            parts.push(`<span class="data-status__item">Atualizado: ${updatedLabel}</span>`);
        }
        if (calendarDataSource === 'local-cache') {
            parts.push('<span class="data-status__item data-status__item--warning">Não foi possível obter a versão mais recente. Estás a ver dados guardados neste dispositivo.</span>');
        } else if (degradedCompetitions.length) {
            parts.push(
                `<span class="data-status__item data-status__item--warning">Atenção: há dados reaproveitados em ${degradedCompetitions.length} competição(ões).</span>`
            );
        } else if (partialCompetitions.length) {
            parts.push(
                `<span class="data-status__item data-status__item--warning">Algumas competições ainda têm resultados por publicar (${partialCompetitions.length}).</span>`
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
        history.replaceState(null, '', `#${activeTab}`);
    };

    const getDateRange = () => {
        if (!hasAppliedRange || !selectedRange.start || !selectedRange.end) {
            return { start: null, end: null };
        }
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
        if (!hasAppliedRange) return [];
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

    const hydrateMatchesFromCompetitionPayloads = async (token) => {
        const candidates = getCandidateMatches();
        if (!candidates.length || !calendarData?.competitions) return;

        const competitionsByKey = new Map(
            calendarData.competitions.map((competition) => [competition.key, competition])
        );
        const groupedEntries = new Map();
        candidates.forEach((entry) => {
            const entries = groupedEntries.get(entry.competitionKey) || [];
            entries.push(entry);
            groupedEntries.set(entry.competitionKey, entries);
        });

        let changed = false;

        for (const [competitionKey, entries] of groupedEntries.entries()) {
            const competitionMeta = competitionsByKey.get(competitionKey);
            const payload = await fetchCompetitionPayload(competitionMeta);
            if (!isValidCompetitionPayload(payload)) continue;

            const roundLookup = buildCompetitionMatchLookup(payload);

            entries.forEach((entry) => {
                const fixtureLookup = roundLookup.get(String(entry.fixtureId || ''));
                if (!fixtureLookup) return;

                const payloadMatch = fixtureLookup.get(
                    `${normalizeName(entry.home)}|${normalizeName(entry.away)}`
                );
                if (!payloadMatch) return;

                const nextHomeScore = payloadMatch.homeScore;
                const nextAwayScore = payloadMatch.awayScore;
                const nextDisplayDate = cleanDisplayDate(payloadMatch.date || entry.displayDate);
                const nextDisplayTime = (payloadMatch.time || entry.displayTime || '').trim();
                const nextStadium = payloadMatch.stadium || entry.stadium;
                const nextDate = parseDateFromCalendarEntry({
                    ...entry,
                    displayDate: nextDisplayDate,
                    displayTime: nextDisplayTime,
                });
                const nextMatchDateISO = nextDate ? nextDate.toISOString() : entry.matchDateISO;
                const nextSortTimestamp = nextDate ? Math.floor(nextDate.getTime() / 1000) : entry.sortTimestamp;

                if (
                    entry.homeScore !== nextHomeScore ||
                    entry.awayScore !== nextAwayScore ||
                    entry.displayDate !== nextDisplayDate ||
                    entry.displayTime !== nextDisplayTime ||
                    entry.stadium !== nextStadium ||
                    entry.lastUpdatedAt !== payload.lastUpdatedAt
                ) {
                    entry.homeScore = nextHomeScore;
                    entry.awayScore = nextAwayScore;
                    entry.displayDate = nextDisplayDate;
                    entry.displayTime = nextDisplayTime;
                    entry.stadium = nextStadium;
                    entry.lastUpdatedAt = payload.lastUpdatedAt;
                    entry.sourceHealth = payload.sourceHealth || entry.sourceHealth || {};
                    entry.matchDateISO = nextMatchDateISO;
                    entry.sortTimestamp = nextSortTimestamp;
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
        const accentColor = COMPETITION_ACCENTS[entry.competitionKey] || '#7d8590';
        const inlineVars = [
            `--agenda-competition-accent: ${accentColor}`,
            `--agenda-competition-accent-soft: ${accentColor}`,
            `--agenda-competition-accent-border: ${accentColor}`,
        ].join('; ');
        const score = Number.isInteger(entry.homeScore) && Number.isInteger(entry.awayScore)
            ? `${entry.homeScore} - ${entry.awayScore}`
            : (entry.displayTime || 'Agendado');
        const metaLine = [entry.displayDate, entry.displayTime].filter(Boolean).join(' · ');

        return `
            <article class="agenda-match-card" style="${inlineVars}">
                <a href="${entry.competitionUrl || '#'}" class="agenda-match-card__link" aria-label="Abrir ${entry.competitionTitle}">
                    <div class="agenda-match-card__meta">
                        <span class="agenda-chip">${entry.competitionTitle}</span>
                        <span class="agenda-match-card__subtitle">${entry.competitionSubtitle}</span>
                    </div>
                    <div class="agenda-match-card__teams">
                        <div class="agenda-team ${isArmacenensesTeam(entry.home, entry.competitionKey) ? 'agenda-team--highlight' : ''}">
                            <img src="${homeCrest}" alt="${homeDisplayName}" class="team-crest">
                            <span>${homeDisplayName}</span>
                        </div>
                        <div class="agenda-match-card__center">
                            <span class="agenda-match-card__round">Jornada ${entry.roundNumber}</span>
                            <div class="agenda-match-card__score">${score}</div>
                        </div>
                        <div class="agenda-team ${isArmacenensesTeam(entry.away, entry.competitionKey) ? 'agenda-team--highlight' : ''}">
                            <span>${awayDisplayName}</span>
                            <img src="${awayCrest}" alt="${awayDisplayName}" class="team-crest">
                        </div>
                    </div>
                    <div class="agenda-match-card__footer">
                        <span>${metaLine}</span>
                        <span>${entry.stadium || ''}</span>
                    </div>
                </a>
            </article>
        `;
    };

    const renderList = (container, summary, matches) => {
        if (!hasAppliedRange) {
            summary.textContent = '';
            container.innerHTML = '<p class="agenda-empty-state">Seleciona um período no calendário para ver jogos.</p>';
            return;
        }
        if (!matches.length) {
            summary.textContent = 'Sem jogos para os filtros selecionados.';
            container.innerHTML = '<p class="agenda-empty-state">Nenhum jogo encontrado.</p>';
            return;
        }

        const orderedMatches = [...matches].sort((left, right) => {
            const leftTs = left.sortTimestamp || 0;
            const rightTs = right.sortTimestamp || 0;
            return leftTs - rightTs;
        });

        const groups = groupMatchesByDay(orderedMatches);
        const groupEntries = Array.from(groups.entries()).sort((left, right) => {
            return left[0].localeCompare(right[0]);
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
        renderDataStatus();
        const matches = getFilteredMatches();
        if (activeTab === 'proximos') {
            renderList(listProximos, summaryProximos, matches);
        } else {
            renderList(listResultados, summaryResultados, matches);
        }
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
        calendarDataSource = 'published';
        writeJSONToStorage(CALENDAR_CACHE_KEY, calendarData);

        if (crestsResponse.ok) {
            crestsData = await crestsResponse.json();
            writeJSONToStorage(CRESTS_CACHE_KEY, crestsData);
        }
    };

    const bootstrap = async () => {
        const cachedCalendar = readJSONFromStorage(CALENDAR_CACHE_KEY, {
            maxAgeMs: CALENDAR_CACHE_MAX_AGE_MS,
        });

        const cachedCrests = readJSONFromStorage(CRESTS_CACHE_KEY);
        if (cachedCrests && typeof cachedCrests === 'object') {
            crestsData = cachedCrests;
        }

        const initialHash = (window.location.hash || '').replace('#', '').toLowerCase();
        setActiveTab(initialHash === 'resultados' ? 'resultados' : 'proximos');

        try {
            await loadFreshData();
            populateCompetitionFilter();
            renderDataStatus();
            render();
        } catch (error) {
            console.error('Erro ao carregar Agenda:', error);
            if (cachedCalendar && Array.isArray(cachedCalendar.matches)) {
                calendarData = cachedCalendar;
                calendarDataSource = 'local-cache';
                populateCompetitionFilter();
                renderDataStatus();
                render();
                return;
            }
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

    dateRangeMonthSelect.addEventListener('change', () => {
        pickerMonth = new Date(pickerMonth.getFullYear(), Number.parseInt(dateRangeMonthSelect.value, 10), 1, 12, 0, 0, 0);
        renderDateRangePicker();
    });

    dateRangeYearSelect.addEventListener('change', () => {
        pickerMonth = new Date(Number.parseInt(dateRangeYearSelect.value, 10), pickerMonth.getMonth(), 1, 12, 0, 0, 0);
        renderDateRangePicker();
    });

    dateRangeCalendars.addEventListener('click', (event) => {
        const button = event.target.closest('[data-date]');
        if (!button) return;
        event.stopPropagation();
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

    dateRangeClear.addEventListener('click', () => {
        clearSelectedRange();
        closeDateRangePicker();
        renderDataStatus();
        render();
    });

    const dismissRangePicker = () => {
        draftRange = hasAppliedRange
            ? cloneRange(selectedRange)
            : { start: null, end: null };
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
