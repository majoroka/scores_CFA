document.addEventListener('DOMContentLoaded', () => {
    const elements = {
        tabUpcoming: document.getElementById('tab-proximos'),
        tabResults: document.getElementById('tab-agenda-resultados'),
        upcomingContent: document.getElementById('content-proximos'),
        resultsContent: document.getElementById('content-resultados-globais'),
        upcomingSummary: document.getElementById('agenda-summary-proximos'),
        resultsSummary: document.getElementById('agenda-summary-resultados'),
        upcomingList: document.getElementById('agenda-list-proximos'),
        resultsList: document.getElementById('agenda-list-resultados'),
        competition: document.getElementById('filter-competition'),
        status: document.getElementById('agenda-data-status'),
        rangeTrigger: document.getElementById('filter-date-range-trigger'),
        picker: document.getElementById('date-range-picker'),
        pickerSummary: document.getElementById('date-range-picker-summary'),
        calendar: document.getElementById('date-range-calendars'),
        previousMonth: document.getElementById('date-range-prev'),
        nextMonth: document.getElementById('date-range-next'),
        month: document.getElementById('date-range-month-select'),
        year: document.getElementById('date-range-year-select'),
        apply: document.getElementById('date-range-apply'),
        clear: document.getElementById('date-range-clear'),
        cancel: document.getElementById('date-range-cancel'),
        close: document.getElementById('date-range-picker-close'),
        startInput: document.getElementById('date-range-start-input'),
        endInput: document.getElementById('date-range-end-input'),
    };

    const MONTHS = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];
    const WEEKDAYS = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];
    let activeTab = 'upcoming';
    let agenda = { matches: [], competitions: [] };
    let crests = {};
    let selectedRange = { start: null, end: null };
    let draftRange = { start: null, end: null };
    let pickerMonth = new Date(new Date().getFullYear(), new Date().getMonth(), 1);

    const escapeHTML = (value = '') => String(value)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#039;');

    const atMidday = (date) => date
        ? new Date(date.getFullYear(), date.getMonth(), date.getDate(), 12, 0, 0, 0)
        : null;

    const parseDate = (value) => {
        if (!value) return null;
        const parsed = new Date(value);
        return Number.isNaN(parsed.getTime()) ? null : atMidday(parsed);
    };

    const parseInputDate = (value) => {
        if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) return null;
        const [year, month, day] = value.split('-').map(Number);
        return new Date(year, month - 1, day, 12, 0, 0, 0);
    };

    const inputDate = (date) => date
        ? `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
        : '';

    const longDate = (date) => new Intl.DateTimeFormat('pt-PT', {
        weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
    }).format(date);

    const shortDate = (date) => new Intl.DateTimeFormat('pt-PT', {
        day: '2-digit', month: '2-digit', year: 'numeric',
    }).format(date);

    const crest = (teamName) => {
        const canonical = window.CFAData.canonicalTeamName(teamName);
        return crests[canonical] || crests[window.CFAData.normalizeName(teamName)] || 'img/crests/jornada.png';
    };

    const isClubTeam = (teamName, match) => (match.teamNames || [])
        .some((candidate) => window.CFAData.normalizeName(candidate) === window.CFAData.normalizeName(teamName));

    const scored = (match) => Number.isInteger(match.homeScore) && Number.isInteger(match.awayScore);

    const filteredMatches = (results) => agenda.matches.filter((match) => {
        if (scored(match) !== results) return false;
        if (elements.competition.value && match.competitionKey !== elements.competition.value) return false;
        const date = parseDate(match.matchDateISO);
        if (selectedRange.start && (!date || date < selectedRange.start)) return false;
        if (selectedRange.end && (!date || date > selectedRange.end)) return false;
        return true;
    }).sort((left, right) => results
        ? right.sortTimestamp - left.sortTimestamp
        : left.sortTimestamp - right.sortTimestamp);

    const renderCard = (match) => {
        const homeName = window.CFAData.displayTeamName(match.home);
        const awayName = window.CFAData.displayTeamName(match.away);
        const result = scored(match) ? `${match.homeScore} - ${match.awayScore}` : (match.displayTime || 'A definir');
        const dateTime = [match.displayDate, match.displayTime].filter(Boolean).join(' · ');
        return `
            <article class="agenda-match-card">
                <a class="agenda-match-card__link" href="${escapeHTML(match.competitionUrl)}">
                    <div class="agenda-match-card__meta">
                        <span class="agenda-chip" style="background: ${escapeHTML(match.accent)}; border-color: ${escapeHTML(match.accent)}; color: #fff;">${escapeHTML(match.competitionTitle)}</span>
                        <span class="agenda-match-card__subtitle">${escapeHTML(match.competitionSubtitle)}</span>
                    </div>
                    <div class="agenda-match-card__teams">
                        <div class="agenda-team ${isClubTeam(match.home, match) ? 'agenda-team--highlight' : ''}">
                            <img src="${escapeHTML(crest(match.home))}" alt="" class="team-crest">
                            <span>${escapeHTML(homeName)}</span>
                        </div>
                        <div class="agenda-match-card__center">
                            <span class="agenda-match-card__round">Jornada ${match.roundNumber}</span>
                            <strong class="agenda-match-card__score">${escapeHTML(result)}</strong>
                        </div>
                        <div class="agenda-team ${isClubTeam(match.away, match) ? 'agenda-team--highlight' : ''}">
                            <span>${escapeHTML(awayName)}</span>
                            <img src="${escapeHTML(crest(match.away))}" alt="" class="team-crest">
                        </div>
                    </div>
                    <div class="agenda-match-card__footer">
                        <span>${escapeHTML(dateTime)}</span>
                        <span>${escapeHTML(match.stadium)}</span>
                    </div>
                </a>
            </article>
        `;
    };

    const renderList = (target, summary, matches, noun) => {
        summary.textContent = `${matches.length} ${matches.length === 1 ? noun : `${noun}s`}`;
        if (!matches.length) {
            target.innerHTML = '<p class="agenda-empty-state">Sem jogos para os filtros selecionados.</p>';
            return;
        }

        const groups = new Map();
        matches.forEach((match) => {
            const date = parseDate(match.matchDateISO);
            const key = date ? inputDate(date) : 'sem-data';
            if (!groups.has(key)) groups.set(key, { date, matches: [] });
            groups.get(key).matches.push(match);
        });

        target.innerHTML = Array.from(groups.values()).map((group) => `
            <section class="agenda-day-group">
                <h2 class="agenda-day-group__title">${group.date ? escapeHTML(longDate(group.date)) : 'Data por definir'}</h2>
                <div class="agenda-day-group__list">${group.matches.map(renderCard).join('')}</div>
            </section>
        `).join('');
    };

    const renderAgenda = () => {
        renderList(elements.upcomingList, elements.upcomingSummary, filteredMatches(false), 'jogo');
        renderList(elements.resultsList, elements.resultsSummary, filteredMatches(true), 'resultado');
    };

    const setActiveTab = (tab) => {
        activeTab = tab;
        const showUpcoming = activeTab === 'upcoming';
        elements.upcomingContent.classList.toggle('hidden', !showUpcoming);
        elements.resultsContent.classList.toggle('hidden', showUpcoming);
        elements.tabUpcoming.classList.toggle('active', showUpcoming);
        elements.tabResults.classList.toggle('active', !showUpcoming);
        elements.tabUpcoming.setAttribute('aria-selected', String(showUpcoming));
        elements.tabResults.setAttribute('aria-selected', String(!showUpcoming));
        elements.tabUpcoming.tabIndex = showUpcoming ? 0 : -1;
        elements.tabResults.tabIndex = showUpcoming ? -1 : 0;
    };

    const updateRangeText = () => {
        elements.rangeTrigger.textContent = selectedRange.start && selectedRange.end
            ? `${shortDate(selectedRange.start)} até ${shortDate(selectedRange.end)}`
            : 'Selecionar período';
    };

    const updateDraftInputs = () => {
        elements.startInput.value = inputDate(draftRange.start);
        elements.endInput.value = inputDate(draftRange.end);
        elements.pickerSummary.textContent = draftRange.start
            ? `${shortDate(draftRange.start)}${draftRange.end ? ` até ${shortDate(draftRange.end)}` : ' · selecionar fim'}`
            : 'Escolhe a data inicial e final.';
    };

    const sameDay = (left, right) => Boolean(left && right && inputDate(left) === inputDate(right));

    const renderCalendar = () => {
        elements.month.value = String(pickerMonth.getMonth());
        elements.year.value = String(pickerMonth.getFullYear());
        const first = new Date(pickerMonth.getFullYear(), pickerMonth.getMonth(), 1, 12);
        const gridStart = new Date(first);
        gridStart.setDate(first.getDate() - ((first.getDay() + 6) % 7));
        const today = atMidday(new Date());
        const cells = [];

        for (let offset = 0; offset < 42; offset += 1) {
            const date = new Date(gridStart);
            date.setDate(gridStart.getDate() + offset);
            const classes = ['agenda-calendar__cell'];
            if (date.getMonth() !== pickerMonth.getMonth()) classes.push('agenda-calendar__cell--outside');
            if (sameDay(date, today)) classes.push('agenda-calendar__cell--today');
            if (draftRange.start && draftRange.end && date >= draftRange.start && date <= draftRange.end) classes.push('agenda-calendar__cell--in-range');
            if (sameDay(date, draftRange.start)) classes.push('agenda-calendar__cell--start');
            if (sameDay(date, draftRange.end)) classes.push('agenda-calendar__cell--end');
            cells.push(`<button type="button" class="${classes.join(' ')}" data-date="${inputDate(date)}">${date.getDate()}</button>`);
        }

        elements.calendar.innerHTML = `
            <div class="agenda-calendar">
                <div class="agenda-calendar__weekdays">${WEEKDAYS.map((day) => `<span>${day}</span>`).join('')}</div>
                <div class="agenda-calendar__grid">${cells.join('')}</div>
            </div>
        `;
        elements.calendar.querySelectorAll('[data-date]').forEach((button) => {
            button.addEventListener('click', () => {
                const date = parseInputDate(button.dataset.date);
                if (!draftRange.start || draftRange.end || date < draftRange.start) {
                    draftRange = { start: date, end: null };
                } else {
                    draftRange.end = date;
                }
                updateDraftInputs();
                renderCalendar();
            });
        });
    };

    const openPicker = () => {
        draftRange = { ...selectedRange };
        const reference = draftRange.start || new Date();
        pickerMonth = new Date(reference.getFullYear(), reference.getMonth(), 1);
        updateDraftInputs();
        renderCalendar();
        elements.picker.classList.remove('hidden');
        elements.rangeTrigger.setAttribute('aria-expanded', 'true');
    };

    const closePicker = () => {
        elements.picker.classList.add('hidden');
        elements.rangeTrigger.setAttribute('aria-expanded', 'false');
    };

    MONTHS.forEach((month, index) => elements.month.add(new Option(month, String(index))));
    const baseYear = new Date().getFullYear();
    for (let year = baseYear - 2; year <= baseYear + 3; year += 1) {
        elements.year.add(new Option(String(year), String(year)));
    }

    elements.tabUpcoming.addEventListener('click', (event) => { event.preventDefault(); setActiveTab('upcoming'); });
    elements.tabResults.addEventListener('click', (event) => { event.preventDefault(); setActiveTab('results'); });
    elements.competition.addEventListener('change', renderAgenda);
    elements.rangeTrigger.addEventListener('click', () => elements.picker.classList.contains('hidden') ? openPicker() : closePicker());
    elements.close.addEventListener('click', closePicker);
    elements.cancel.addEventListener('click', closePicker);
    elements.previousMonth.addEventListener('click', () => { pickerMonth.setMonth(pickerMonth.getMonth() - 1); renderCalendar(); });
    elements.nextMonth.addEventListener('click', () => { pickerMonth.setMonth(pickerMonth.getMonth() + 1); renderCalendar(); });
    elements.month.addEventListener('change', () => { pickerMonth.setMonth(Number(elements.month.value)); renderCalendar(); });
    elements.year.addEventListener('change', () => { pickerMonth.setFullYear(Number(elements.year.value)); renderCalendar(); });
    elements.startInput.addEventListener('change', () => { draftRange.start = parseInputDate(elements.startInput.value); updateDraftInputs(); renderCalendar(); });
    elements.endInput.addEventListener('change', () => { draftRange.end = parseInputDate(elements.endInput.value); updateDraftInputs(); renderCalendar(); });
    elements.apply.addEventListener('click', () => {
        if (draftRange.start && !draftRange.end) draftRange.end = draftRange.start;
        if (draftRange.start && draftRange.end && draftRange.end < draftRange.start) {
            [draftRange.start, draftRange.end] = [draftRange.end, draftRange.start];
        }
        selectedRange = { ...draftRange };
        updateRangeText();
        renderAgenda();
        closePicker();
    });
    elements.clear.addEventListener('click', () => {
        draftRange = { start: null, end: null };
        selectedRange = { start: null, end: null };
        updateDraftInputs();
        updateRangeText();
        renderCalendar();
        renderAgenda();
        closePicker();
    });
    document.addEventListener('click', (event) => {
        if (!elements.picker.classList.contains('hidden') && !elements.picker.contains(event.target) && event.target !== elements.rangeTrigger) closePicker();
    });

    const bootstrap = async () => {
        try {
            const [agendaPayload, crestResponse] = await Promise.all([
                window.CFAData.buildAgenda(),
                fetch('data/crests.json', { cache: 'no-cache' }),
            ]);
            agenda = agendaPayload;
            if (crestResponse.ok) crests = await crestResponse.json();
            agenda.competitions.forEach((competition) => {
                elements.competition.add(new Option(competition.title, competition.key));
            });

            const latestCapture = agenda.competitions
                .map((competition) => Date.parse(competition.capturedAt || ''))
                .filter(Number.isFinite)
                .sort((left, right) => right - left)[0];
            elements.status.innerHTML = latestCapture
                ? `<span class="data-status__item">Ficheiros mais recentes: ${escapeHTML(new Intl.DateTimeFormat('pt-PT', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(latestCapture)))}</span>`
                : '<span class="data-status__item">Agenda gerada a partir dos ficheiros das competições</span>';
            elements.status.classList.remove('hidden');
            renderAgenda();
        } catch (error) {
            console.error('Erro ao carregar a agenda:', error);
            elements.status.innerHTML = `<span class="data-status__item data-status__item--warning">Não foi possível carregar a agenda: ${escapeHTML(error.message)}</span>`;
            elements.status.classList.remove('hidden');
            elements.upcomingList.innerHTML = '<p class="agenda-empty-state">Dados indisponíveis.</p>';
            elements.resultsList.innerHTML = '<p class="agenda-empty-state">Dados indisponíveis.</p>';
        }
    };

    setActiveTab('upcoming');
    updateRangeText();
    bootstrap();
});
