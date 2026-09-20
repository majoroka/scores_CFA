(function () {
    'use strict';

    const INDEX_URL = 'data/competitions/index.json';
    const COMPETITIONS_BASE_URL = 'data/competitions/';
    let indexPromise = null;
    const competitionPromises = new Map();

    const normalizeName = (value = '') => value
        .normalize('NFD')
        .replace(/[\u0300-\u036f]+/g, '')
        .toLowerCase()
        .replace(/[\-_]+/g, ' ')
        .replace(/[^a-z0-9 ]+/g, '')
        .replace(/\s+/g, ' ')
        .trim();

    const canonicalTeamName = (teamName) => {
        const normalized = normalizeName(teamName);
        if (normalized === 'casa benfica tavira') return 'casa slb tavira';
        if (normalized === 'clube u culatrense') return 'cu culatrense';
        if (normalized.startsWith('cf os armacenenses')) return 'cf os armacenenses';
        return normalized;
    };

    const displayTeamName = (teamName = '') => {
        const normalized = normalizeName(teamName);
        if (!normalized.startsWith('cf os armacenenses')) return teamName;
        if (normalized.endsWith(' a')) return 'CF Os Armacenenses - A';
        if (normalized.endsWith(' b')) return 'CF Os Armacenenses - B';
        return 'CF Os Armacenenses';
    };

    const formatDateLabel = (dateValue) => {
        if (!dateValue) return '';
        const parsed = new Date(`${dateValue}T12:00:00`);
        if (Number.isNaN(parsed.getTime())) return dateValue;
        return new Intl.DateTimeFormat('pt-PT', {
            day: 'numeric',
            month: 'short',
        }).format(parsed).replace('.', '');
    };

    const buildDate = (dateValue, timeValue = '') => {
        if (!dateValue) return null;
        const safeTime = /^\d{2}:\d{2}$/.test(timeValue || '') ? timeValue : '12:00';
        const parsed = new Date(`${dateValue}T${safeTime}:00`);
        return Number.isNaN(parsed.getTime()) ? null : parsed;
    };

    const validateIndex = (payload) => {
        if (!payload || !Array.isArray(payload.competitions)) {
            throw new Error('Catálogo de competições inválido.');
        }
        return payload;
    };

    const loadIndex = () => {
        if (!indexPromise) {
            indexPromise = fetch(INDEX_URL, { cache: 'no-cache' })
                .then((response) => {
                    if (!response.ok) throw new Error(`Falha ao carregar catálogo (${response.status}).`);
                    return response.json();
                })
                .then(validateIndex);
        }
        return indexPromise;
    };

    const getEnabledCompetitions = async () => {
        const index = await loadIndex();
        return index.competitions.filter((competition) => competition.enabled !== false);
    };

    const getCompetitionMeta = async (key) => {
        const competitions = await getEnabledCompetitions();
        return competitions.find((competition) => competition.key === key) || null;
    };

    const validateRawCompetition = (payload, meta) => {
        if (!payload || !Array.isArray(payload.rounds)) {
            throw new Error(`Ficheiro inválido para ${meta.title}.`);
        }
        if (payload.validation && payload.validation.complete === false) {
            throw new Error(`O ficheiro de ${meta.title} está incompleto.`);
        }
        return payload;
    };

    const isClubTeam = (teamName, meta) => {
        const normalized = normalizeName(teamName);
        return (meta.teamNames || []).some((candidate) => normalizeName(candidate) === normalized);
    };

    const normalizeMatch = (game) => ({
        id: game.fpf_match_id,
        order: game.order,
        home: game.home || '',
        away: game.away || '',
        date: formatDateLabel(game.date),
        dateISO: game.date || '',
        time: game.time || '',
        stadium: game.venue || '',
        homeScore: Number.isInteger(game.home_score) ? game.home_score : null,
        awayScore: Number.isInteger(game.away_score) ? game.away_score : null,
        status: game.status || 'scheduled',
    });

    const normalizeClassification = (entry) => ({
        position: entry.pos,
        team: entry.team || '',
        played: entry.played || 0,
        wins: entry.wins || 0,
        draws: entry.draws || 0,
        losses: entry.losses || 0,
        goalsFor: entry.goals_for || 0,
        goalsAgainst: entry.goals_against || 0,
        points: entry.points || 0,
    });

    const chooseDefaultRoundIndex = (rounds, meta) => {
        const now = new Date();
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const clubMatches = [];

        rounds.forEach((round, roundIndex) => {
            round.matches.forEach((match) => {
                if (!isClubTeam(match.home, meta) && !isClubTeam(match.away, meta)) return;
                const date = buildDate(match.dateISO, match.time);
                if (date) clubMatches.push({ date, roundIndex });
            });
        });

        const upcoming = clubMatches
            .filter((entry) => entry.date >= today)
            .sort((left, right) => left.date - right.date)[0];
        if (upcoming) return upcoming.roundIndex;

        const latest = clubMatches.sort((left, right) => right.date - left.date)[0];
        return latest ? latest.roundIndex : 0;
    };

    const normalizeCompetition = (raw, meta) => {
        const rounds = raw.rounds
            .map((round) => ({
                index: Number(round.round),
                fixtureId: String(round.fixtureId || ''),
                matches: (round.games || []).map(normalizeMatch),
                classification: (round.classification || []).map(normalizeClassification),
            }))
            .sort((left, right) => left.index - right.index);

        const matches = rounds.flatMap((round) => round.matches);
        const completedMatchCount = matches.filter((match) => (
            Number.isInteger(match.homeScore) && Number.isInteger(match.awayScore)
        )).length;

        return {
            key: meta.key,
            title: meta.title,
            subtitle: meta.subtitle,
            season: meta.season,
            capturedAt: raw.captured_at || null,
            validation: raw.validation || {},
            source: raw.source || {},
            rounds,
            defaultRoundIndex: chooseDefaultRoundIndex(rounds, meta),
            dataQuality: {
                matchCount: matches.length,
                completedMatchCount,
                matchesWithoutScore: matches.length - completedMatchCount,
                teamCount: Array.isArray(raw.teams) ? raw.teams.length : 0,
            },
        };
    };

    const loadCompetition = async (metaOrKey) => {
        const meta = typeof metaOrKey === 'string'
            ? await getCompetitionMeta(metaOrKey)
            : metaOrKey;
        if (!meta) throw new Error('Competição não encontrada.');

        if (!competitionPromises.has(meta.key)) {
            const request = fetch(`${COMPETITIONS_BASE_URL}${meta.file}`, { cache: 'no-cache' })
                .then((response) => {
                    if (!response.ok) throw new Error(`Falha ao carregar ${meta.title} (${response.status}).`);
                    return response.json();
                })
                .then((payload) => validateRawCompetition(payload, meta))
                .then((payload) => normalizeCompetition(payload, meta));
            competitionPromises.set(meta.key, request);
        }
        return competitionPromises.get(meta.key);
    };

    const loadAllCompetitions = async () => {
        const metadata = await getEnabledCompetitions();
        const payloads = await Promise.all(metadata.map(async (meta) => ({
            meta,
            payload: await loadCompetition(meta),
        })));
        return payloads;
    };

    const buildAgenda = async () => {
        const competitions = await loadAllCompetitions();
        const matches = [];

        competitions.forEach(({ meta, payload }) => {
            payload.rounds.forEach((round) => {
                round.matches.forEach((match) => {
                    if (!isClubTeam(match.home, meta) && !isClubTeam(match.away, meta)) return;
                    const matchDate = buildDate(match.dateISO, match.time);
                    matches.push({
                        competitionKey: meta.key,
                        competitionTitle: meta.title,
                        competitionSubtitle: meta.subtitle,
                        competitionUrl: `competition.html?key=${encodeURIComponent(meta.key)}#resultados-j${round.index}`,
                        accent: meta.accent,
                        teamNames: meta.teamNames || [],
                        roundNumber: round.index,
                        fixtureId: round.fixtureId,
                        matchDateISO: matchDate ? matchDate.toISOString() : null,
                        sortTimestamp: matchDate ? Math.floor(matchDate.getTime() / 1000) : 0,
                        status: match.status,
                        home: match.home,
                        away: match.away,
                        homeScore: match.homeScore,
                        awayScore: match.awayScore,
                        displayDate: match.date,
                        displayTime: match.time,
                        stadium: match.stadium,
                        capturedAt: payload.capturedAt,
                    });
                });
            });
        });

        return {
            generatedAt: new Date().toISOString(),
            competitions: competitions.map(({ meta, payload }) => ({
                ...meta,
                capturedAt: payload.capturedAt,
            })),
            matches,
        };
    };

    window.CFAData = {
        buildAgenda,
        canonicalTeamName,
        displayTeamName,
        getCompetitionMeta,
        getEnabledCompetitions,
        isClubTeam,
        loadAllCompetitions,
        loadCompetition,
        loadIndex,
        normalizeName,
    };
})();
