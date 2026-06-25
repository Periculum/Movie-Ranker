// ── Variables ───────────────────────────────────────────────────────────────

const INITIAL_ELO = 1500;
const ELO_K = 32;
const RECOMMENDED_COMPARISONS = 500;

const LOW_ELO_THRESHOLD = 1420;
const HIGH_ELO_THRESHOLD = 1565;
const LOW_ELO_WEIGHT = 0.05;
const HIGH_ELO_WEIGHT = 2.0;

// ── State ───────────────────────────────────────────────────────────────────

let currentListKey = "letterboxd";
let films = createFilms(FILM_LISTS[currentListKey].films);
let comparedPairs = new Set();
let comparisons = 0;
let history = [];
let pair = [];

// ── Filmliste ───────────────────────────────────────────────────────────────

function createFilms(rawFilms) {
  const films = [];
  const seen = new Set();

  for (const [title, year, director] of rawFilms) {
    const key = title.toLowerCase().trim();
    if (seen.has(key)) continue;

    seen.add(key);
    films.push(newFilm(title, year, director));
  }

  return films;
}

function newFilm(title, year = "?", director = "Unbekannt") {
  return {
    title,
    year,
    director,
    elo: INITIAL_ELO,
    wins: 0,
    losses: 0,
    comparisons: 0,
    skipped: false
  };
}

// ── Pair-Auswahl ────────────────────────────────────────────────────────────

function pairKey(a, b) {
  return [a, b].sort((x, y) => x - y).join("-");
}

function topComparisonTarget() {
  const topFilms = films.filter(
    film => !film.skipped && film.elo >= HIGH_ELO_THRESHOLD
  );

  if (topFilms.length === 0) return 1;
  return Math.max(...topFilms.map(film => film.comparisons), 1);
}

function filmWeight(film, target) {
  let weight = 1.0;

  // weak films appear less often
  if (film.elo < LOW_ELO_THRESHOLD) {
    weight *= LOW_ELO_WEIGHT;
  }

  // strong films appear more often
  if (film.elo > HIGH_ELO_THRESHOLD) {
    weight *= HIGH_ELO_WEIGHT;

    // dynamic boost if a good film is not yet well tested
    const coverage = film.comparisons / target;
    weight *= Math.max(1, 2 - coverage);
  }

  return weight;
}

function chooseFilm(exclude = null) {
  const active = films
    .map((film, index) => ({ film, index }))
    .filter(item => !item.film.skipped && item.index !== exclude)
    .map(item => item.index);

  if (active.length === 0) return null;

  // first phase: every film must appear at least once
  // so unknown movies can be sorted early out
  const untested = active.filter(index => films[index].comparisons === 0);
  if (untested.length > 0) {
    return randomItem(untested);
  }

  // weighted phase
  // lower rated movies are shown less and higher rated movies more often
  const target = topComparisonTarget();
  const weights = active.map(index => filmWeight(films[index], target));
  return weightedChoice(active, weights);
}

function choosePair() {
  for (let tries = 0; tries < 100; tries++) {
    const first = chooseFilm();
    const second = chooseFilm(first);

    if (first === null || second === null) return null;

    if (!comparedPairs.has(pairKey(first, second))) {
      const nextPair = [first, second];
      shuffle(nextPair);
      return nextPair;
    }
  }

  return null;
}

// ── ELO ─────────────────────────────────────────────────────────────────────

function updateElo(winnerElo, loserElo) {
  // using elo formula from chess
  const expected = 1 / (1 + Math.pow(10, (loserElo - winnerElo) / 400));
  winnerElo = Math.round(winnerElo + ELO_K * (1 - expected));
  loserElo = Math.round(loserElo + ELO_K * (expected - 1));
  return [winnerElo, loserElo];
}

// ── UI ──────────────────────────────────────────────────────────────────────

const startPage = document.querySelector("#startPage");
const quizPage = document.querySelector("#quizPage");
const resultsPage = document.querySelector("#resultsPage");

const newTitleInput = document.querySelector("#newTitleInput");
const addFilmButton = document.querySelector("#addFilmButton");
const addFeedback = document.querySelector("#addFeedback");
const startButton = document.querySelector("#startButton");
const listSelect = document.querySelector("#listSelect");

const undoButton = document.querySelector("#undoButton");
const resultsButton = document.querySelector("#resultsButton");
const resetButton = document.querySelector("#resetButton");
const backButton = document.querySelector("#backButton");

const statusText = document.querySelector("#status");
const progressFill = document.querySelector("#progressFill");
const rankingBody = document.querySelector("#rankingBody");
const resultsInfo = document.querySelector("#resultsInfo");

const exportButton = document.querySelector("#exportButton");
const finetuneButton = document.querySelector("#finetuneButton");

const cards = [
  document.querySelector("#card0"),
  document.querySelector("#card1")
];

function showPage(page) {
  startPage.classList.add("hidden");
  quizPage.classList.add("hidden");
  resultsPage.classList.add("hidden");
  page.classList.remove("hidden");
}

function setFeedback(text, type = "") {
  addFeedback.textContent = text;
  addFeedback.className = `feedback ${type}`.trim();
}

function resetRankingForList(listKey) {
  currentListKey = listKey;
  films = createFilms(FILM_LISTS[currentListKey].films);
  comparisons = 0;
  history = [];
  pair = [];
  newTitleInput.value = "";
  setFeedback(`${FILM_LISTS[currentListKey].label}: ${films.length} Filme geladen.`, "good");
}

function normalize(text) {
  return text.toLowerCase().trim();
}

// ── Startseite ──────────────────────────────────────────────────────────────

function checkTitle() {
  // check while typing if the title is already in the list
  const raw = newTitleInput.value.trim();
  const query = normalize(raw);

  if (!raw) {
    setFeedback("");
    return;
  }

  // exact match
  const exact = films.find(film => normalize(film.title) === query);
  if (exact) {
    setFeedback(`„${exact.title}” ist bereits in der Liste.`, "good");
    return;
  }

  // safe partial match, only after 3 characters
  let partial = null;
  if (query.length >= 3) {
    partial = films.find(film => normalize(film.title).includes(query));
  }

  if (partial) {
    setFeedback(`Meinst Du „${partial.title}”? Der Film ist bereits in der Liste.`, "good");
  } else {
    setFeedback(`„${raw}” ist noch nicht in der Liste – Enter zum Hinzufügen.`, "bad");
  }
}

function addFilm() {
  const title = newTitleInput.value.trim();
  if (!title) return;

  const exists = films.some(film => normalize(film.title) === normalize(title));
  if (exists) return;

  films.push(newFilm(title));
  newTitleInput.value = "";
  setFeedback(`✓ „${title}” wurde hinzugefügt.`, "good");
}

// ── Quiz ────────────────────────────────────────────────────────────────────

function startQuiz() {
  showPage(quizPage);
  refresh();
  nextPair();
}

function nextPair() {
  const next = choosePair();

  if (next === null) {
    alert(
      "Alle möglichen Vergleiche wurden durchgeführt.\n\n" +
      "Du kannst die Ergebnisse ansehen oder weitere Filme hinzufügen."
    );
    return;
  }

  pair = next;
  updateCard(0, films[pair[0]]);
  updateCard(1, films[pair[1]]);
}

function updateCard(side, film) {
  const card = cards[side];
  card.querySelector(".year").textContent = film.year;
  card.querySelector(".title").textContent = film.title;
  card.querySelector(".director").textContent = film.director;
}

function choose(side) {
  const winnerIndex = pair[side];
  const loserIndex = pair[1 - side];

  comparedPairs.add(pairKey(winnerIndex, loserIndex));

  const winner = films[winnerIndex];
  const loser = films[loserIndex];

  history.push({
    winnerIndex,
    loserIndex,
    winnerElo: winner.elo,
    loserElo: loser.elo
  });

  [winner.elo, loser.elo] = updateElo(winner.elo, loser.elo);

  winner.wins += 1;
  winner.comparisons += 1;
  loser.losses += 1;
  loser.comparisons += 1;
  comparisons += 1;

  refresh();
  nextPair();
}

function skip(side) {
  films[pair[side]].skipped = true;

  const kept = pair[1 - side];
  const newIndex = chooseFilm(kept);

  if (newIndex === null) {
    alert("Nicht genug aktive Filme übrig.");
    refresh();
    return;
  }

  pair[side] = newIndex;
  updateCard(side, films[newIndex]);
  refresh();
}

function undo() {
  if (history.length === 0) {
    alert("Kein vorheriger Vergleich.");
    return;
  }

  const last = history.pop();
  const winner = films[last.winnerIndex];
  const loser = films[last.loserIndex];

  winner.elo = last.winnerElo;
  loser.elo = last.loserElo;
  winner.wins -= 1;
  winner.comparisons -= 1;
  loser.losses -= 1;
  loser.comparisons -= 1;
  comparisons -= 1;

  pair = [last.winnerIndex, last.loserIndex];
  updateCard(0, winner);
  updateCard(1, loser);
  refresh();
}

function refresh() {
  const skipped = films.filter(film => film.skipped).length;
  const remaining = Math.max(0, RECOMMENDED_COMPARISONS - comparisons);

  statusText.textContent =
    `Vergleiche: ${comparisons} · ~${remaining} empfohlen · ${skipped} übersprungen`;

  progressFill.style.width =
    `${Math.min(100, comparisons / RECOMMENDED_COMPARISONS * 100)}%`;
}

// ── Ergebnisse und Export ──────────────────────────────────────────────────────────────

function showResults() {
  const ranked = films
    .filter(film => !film.skipped)
    .slice()
    .sort((a, b) => b.elo - a.elo);

  rankingBody.innerHTML = "";
  resultsInfo.textContent = `${comparisons} Vergleiche · ${ranked.length} aktive Filme`;

  ranked.forEach((film, index) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${index + 1}</td>
      <td>${escapeHtml(film.title)}</td>
      <td>${escapeHtml(String(film.year))}</td>
      <td>${escapeHtml(film.director)}</td>
      <td>${film.elo}</td>
    `;
    rankingBody.appendChild(row);
  });

  showPage(resultsPage);
}

function exportTxt() {
  const ranked = films
    .filter(film => !film.skipped)
    .slice()
    .sort((a, b) => b.elo - a.elo);

  const lines = [
    "MEIN PERSÖNLICHES FILM-RANKING",
    `${comparisons} Vergleiche · ${ranked.length} aktive Filme`,
    "",
    ...ranked.map((film, i) =>
      `${String(i + 1).padStart(3, " ")}. ${film.title} (${film.year}) – ${film.director}  [ELO ${film.elo}]`
    )
  ];

  const blob = new Blob([lines.join("\n")], { type: "text/plain" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href     = url;
  a.download = "film_ranking.txt";
  a.click();
  URL.revokeObjectURL(url);
}

function startFinetuning() {
  const ranked = films
    .filter(film => !film.skipped)
    .slice()
    .sort((a, b) => b.elo - a.elo);

  const top20 = ranked.slice(0, Math.ceil(ranked.length * 0.2));

  films = top20.map(film => newFilm(film.title, film.year, film.director));
  comparisons = 0;
  history = [];
  pair = [];
  comparedPairs = new Set();

  startQuiz();
}

// ── Utils ───────────────────────────────────────────────────────────────────

function weightedChoice(items, weights) {
  const total = weights.reduce((sum, value) => sum + value, 0);
  let randomValue = Math.random() * total;

  for (let i = 0; i < items.length; i += 1) {
    randomValue -= weights[i];
    if (randomValue <= 0) return items[i];
  }

  return items[items.length - 1];
}

function randomItem(items) {
  return items[Math.floor(Math.random() * items.length)];
}

function shuffle(items) {
  for (let i = items.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [items[i], items[j]] = [items[j], items[i]];
  }
}

function escapeHtml(text) {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

// ── Events ──────────────────────────────────────────────────────────────────

newTitleInput.addEventListener("input", checkTitle);
newTitleInput.addEventListener("keydown", event => {
  if (event.key === "Enter") addFilm();
});

addFilmButton.addEventListener("click", addFilm);
listSelect.addEventListener("change", () => resetRankingForList(listSelect.value));
startButton.addEventListener("click", startQuiz);
undoButton.addEventListener("click", undo);
resultsButton.addEventListener("click", showResults);
resetButton.addEventListener("click", () => window.location.reload());
backButton.addEventListener("click", () => showPage(quizPage));
exportButton.addEventListener("click", exportTxt);
finetuneButton.addEventListener("click", startFinetuning);

cards.forEach((card, side) => {
  card.addEventListener("click", () => choose(side));
  card.querySelector(".skip").addEventListener("click", event => {
    event.stopPropagation();
    skip(side);
  });
});

resetRankingForList(currentListKey);
