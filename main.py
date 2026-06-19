#!/usr/bin/env python3
# main.py - Film-Ranker

import random
import tkinter as tk
from tkinter import messagebox, ttk

from films import FILMS_RAW

# ── Variables ─────────────────────────────────────────────────────────────────

INITIAL_ELO = 1500
ELO_K = 32
RECOMMENDED_COMPARISONS = 500

LOW_ELO_THRESHOLD = 1420
HIGH_ELO_THRESHOLD = 1565
LOW_ELO_WEIGHT = 0.05
HIGH_ELO_WEIGHT = 2.0

BG = '#f9f9f7'
WHITE = '#ffffff'
BORDER = '#e0e0e0'
CARD_WIDTH = 280
CARD_HEIGHT = 220

# ── Filmliste ─────────────────────────────────────────────────────────────────

def create_films():
    films = []
    seen  = set()
    for title, year, director in FILMS_RAW:
        key = title.lower().strip()
        if key in seen:
            continue
        seen.add(key)
        films.append(new_film(title, year, director))
    return films


def new_film(title, year='?', director='Unbekannt'):
    return {
        'title':       title,
        'year':        year,
        'director':    director,
        'elo':         INITIAL_ELO,
        'wins':        0,
        'losses':      0,
        'comparisons': 0,
        'skipped':     False,
    }

# ── Pair-Auswahl ──────────────────────────────────────────────────────────────

def film_weight(film, films):
    weight = 1.0

    # weak films appear less often
    if film['elo'] < LOW_ELO_THRESHOLD:
        weight *= LOW_ELO_WEIGHT

    # strong films appear more often
    if film['elo'] > HIGH_ELO_THRESHOLD:
        weight *= HIGH_ELO_WEIGHT

        # dynamic boost if a good film is not yet well tested
        top_films = [f for f in films if f['elo'] >= HIGH_ELO_THRESHOLD]
        max_comp = max((f['comparisons'] for f in top_films),default=1)
        weight *= (2 - film['comparisons'] / max_comp)

    return weight

def choose_film(films, exclude=None):
    active = [i for i, f in enumerate(films) if not f['skipped'] and i != exclude]
    if not active:
        return None

    # first phase: every film must appear at least once
    # so unknown movies can be sorted early out
    untested = [i for i in active if films[i]['comparisons'] == 0]
    if untested:
        return random.choice(untested)

    # weighted phase
    # lower rated movies are shown less and higher rated movies more often
    return random.choices(active, weights=[film_weight(films[i], films) for i in active], k=1)[0]

def choose_pair(films):
    first = choose_film(films)
    second = choose_film(films, exclude=first)

    if first is None or second is None:
        return None

    pair = [first, second]
    random.shuffle(pair)
    return pair

# ── ELO ──────────────────────────────────────────────────────────────────────

def update_elo(winner_elo, loser_elo):
    # using elo formula from chess
    expected = 1 / (1 + 10 ** ((loser_elo - winner_elo) / 400))
    winner_elo = round(winner_elo + ELO_K * (1 - expected))
    loser_elo  = round(loser_elo  + ELO_K * (expected - 1))
    return winner_elo, loser_elo

# ── Haupt-App ─────────────────────────────────────────────────────────────────

class FilmRanker(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Was ist Dein Lieblingsfilm?')
        self.geometry('760x640')
        self.configure(bg=BG)

        self.films       = create_films()
        self.comparisons = 0
        self.history     = []
        self.pair        = []
        self.cards       = []

        self.setup_style()
        self.show_start()

    # ── Style ─────────────────────────────────────────────────────────────────

    def setup_style(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('TLabel',     background=BG, font=('Helvetica', 11))
        style.configure('Sub.TLabel', background=BG, foreground='#777', font=('Helvetica', 10))
        style.configure('TButton',    font=('Helvetica', 10))

    def clear(self):
        for child in self.winfo_children():
            child.destroy()

    # ── Startseite ────────────────────────────────────────────────────────────

    def show_start(self):
        self.clear()

        tk.Label(self, text='Was ist Dein wahrer Lieblingsfilm?',
                 font=('Helvetica', 28, 'bold'), bg=BG).pack(pady=(60, 10))
        tk.Label(self,
                 text='Wähle in jedem Duell den Film, den Du lieber magst.\n'
                      'Daraus entsteht Dein persönliches Ranking auf Basis der ELO-Wertung.',
                 font=('Helvetica', 12), fg='#555', bg=BG, justify='center').pack(pady=(0, 30))

        # ── Eingabebereich ──
        tk.Label(self,
                 text='Hier kannst du prüfen, ob deine Lieblingsfilme auch wirklich in der Liste sind.',
                 font=('Helvetica', 12), fg='#555', bg=BG, justify='center').pack(pady=(0, 10))

        row = tk.Frame(self, bg=BG)
        row.pack(pady=4)

        self.new_title = tk.StringVar()
        self.new_title.trace_add('write', self._on_title_type)

        entry = tk.Entry(row, textvariable=self.new_title,
                         width=34, font=('Helvetica', 12))
        entry.pack(side='left', ipady=6)
        entry.bind('<Return>', lambda e: self._confirm_add())

        # ── Live-Feedback ──
        self.add_feedback = tk.StringVar()
        self.add_feedback_color = tk.StringVar()

        self.feedback_lbl = tk.Label(self, textvariable=self.add_feedback,
                                     font=('Helvetica', 10), bg=BG)
        self.feedback_lbl.pack(pady=(6, 0))

        # ── Anzahl und Start ──
        tk.Button(self,
                  text='Abfrage starten →',
                  font=('Helvetica', 13, 'bold'),
                  bg='#222', fg='white',
                  activebackground='#444', activeforeground='white',
                  relief='flat', padx=24, pady=12,
                  command=self.show_quiz).pack()

    def _on_title_type(self, *_):
        # check while typing if the title is already in the list
        raw = self.new_title.get().strip()
        query = raw.lower()

        if not raw:
            self.add_feedback.set('')
            self.feedback_lbl.configure(fg='#777')
            return

        # exact match
        exact = next((f['title'] for f in self.films if f['title'].lower() == query),None)

        if exact:
            self.add_feedback.set(f'„{exact}" ist bereits in der Liste.')
            self.feedback_lbl.configure(fg='#2d9e5f')
            return

        # safe partial match, only after 3 characters
        partial = None
        if len(query) >= 3:
            partial = next((f['title'] for f in self.films if query in f['title'].lower()),None)

        if partial:
            self.add_feedback.set(f'Meinst Du „{partial}"? Der Film ist bereits in der Liste.')
            self.feedback_lbl.configure(fg='#2d9e5f')
        else:
            self.add_feedback.set(f'„{raw}" ist noch nicht in der Liste  –  Enter zum Hinzufügen.')
            self.feedback_lbl.configure(fg='#e07b39')

    def _confirm_add(self):
        """Film hinzufügen – nur wenn er noch nicht existiert."""
        title = self.new_title.get().strip()
        if not title:
            return

        if any(f['title'].lower() == title.lower() for f in self.films):
            # bereits vorhanden – Feedback wurde schon live gezeigt
            return

        self.films.append(new_film(title))
        self.new_title.set('')
        self.add_feedback.set(f'✓  „{title}" wurde hinzugefügt.')
        self.feedback_lbl.configure(fg='#2d9e5f')

    # ── Quiz ──────────────────────────────────────────────────────────────────

    def show_quiz(self):
        self.clear()

        tk.Label(self, text='Welchen Film magst Du mehr?',
                 font=('Helvetica', 20, 'bold'), bg=BG).pack(pady=(24, 4))

        self.status = tk.StringVar()
        ttk.Label(self, textvariable=self.status, style='Sub.TLabel').pack()

        self.progress = ttk.Progressbar(self, maximum=100)
        self.progress.pack(fill='x', padx=40, pady=(8, 20))

        area = tk.Frame(self, bg=BG)
        area.pack(expand=True)

        tk.Label(self,
                 text='Klicke auf einer der beiden Filme, um einen auszuwählen. \n'
                 'Mit einem Klick auf X kannst du unbekannte oder irrelevante Filme entfernen',
                 font=('Helvetica', 12), fg='#555', bg=BG, justify='center').pack(pady=(0, 30))

        self.cards = [self.make_card(area, 0), self.make_card(area, 1)]
        self.cards[0].grid(row=0, column=0, padx=20)
        self.cards[1].grid(row=0, column=1, padx=20)

        buttons = tk.Frame(self, bg=BG)
        buttons.pack(fill='x', padx=32, pady=24)
        ttk.Button(buttons, text='Zurück',     command=self.undo).pack(side='left')
        ttk.Button(buttons, text='Ergebnisse', command=self.show_results).pack(side='right', padx=8)

        self.refresh()
        self.next_pair()

    def make_card(self, parent, side):
        card = tk.Frame(parent, width=CARD_WIDTH, height=CARD_HEIGHT,
                        bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
        card.pack_propagate(False)

        top = tk.Frame(card, bg=WHITE)
        top.pack(fill='x')
        close = tk.Label(top, text='✕', bg=WHITE, fg='#bbb',
                         font=('Helvetica', 13), cursor='hand2')
        close.pack(side='right', padx=10, pady=6)
        close.bind('<Button-1>', lambda e: self.skip(side))
        close.bind('<Enter>',    lambda e: close.configure(fg='#888'))
        close.bind('<Leave>',    lambda e: close.configure(fg='#bbb'))

        body = tk.Frame(card, bg=WHITE)
        body.pack(fill='both', expand=True, padx=16, pady=(0, 16))

        year     = tk.Label(body, bg=WHITE, fg='#aaa', font=('Helvetica', 10), anchor='w')
        title    = tk.Label(body, bg=WHITE, fg='#111', font=('Helvetica', 14, 'bold'),
                            wraplength=240, justify='left', anchor='nw')
        director = tk.Label(body, bg=WHITE, fg='#777', font=('Helvetica', 9), anchor='w')

        year.pack(fill='x', pady=(8, 4))
        title.pack(fill='both', expand=True)
        director.pack(fill='x')

        for widget in (card, body, year, title, director):
            widget.bind('<Button-1>', lambda e, s=side: self.choose(s))
            widget.bind('<Enter>',    lambda e: card.configure(highlightbackground='#444'))
            widget.bind('<Leave>',    lambda e: card.configure(highlightbackground=BORDER))
            widget.configure(cursor='hand2')

        card.labels = (year, title, director)
        return card

    def update_card(self, side, film):
        year, title, director = self.cards[side].labels
        year.configure(text=str(film['year']))
        title.configure(text=film['title'])
        director.configure(text=film['director'])

    def next_pair(self):
        pair = choose_pair(self.films)
        if pair is None:
            messagebox.showinfo('Hinweis', 'Nicht genug aktive Filme übrig.')
            return
        self.pair = pair
        self.update_card(0, self.films[pair[0]])
        self.update_card(1, self.films[pair[1]])

    def choose(self, side):
        wi, li = self.pair[side], self.pair[1 - side]
        w, l   = self.films[wi], self.films[li]

        self.history.append((wi, li, w['elo'], l['elo']))
        w['elo'], l['elo'] = update_elo(w['elo'], l['elo'])
        w['wins']    += 1;  w['comparisons'] += 1
        l['losses']  += 1;  l['comparisons'] += 1
        self.comparisons += 1

        self.refresh()
        self.next_pair()

    def skip(self, side):
        self.films[self.pair[side]]['skipped'] = True

        kept = self.pair[1 - side]
        new_idx = choose_film(self.films, exclude=kept)

        if new_idx is None:
            messagebox.showinfo('Hinweis', 'Nicht genug aktive Filme übrig.')
            self.refresh()
            return

        self.pair[side] = new_idx
        self.update_card(side, self.films[new_idx])
        self.refresh()

    def undo(self):
        if not self.history:
            messagebox.showinfo('Zurück', 'Kein vorheriger Vergleich.')
            return

        wi, li, ew, el = self.history.pop()
        w, l = self.films[wi], self.films[li]
        w['elo'] = ew;  w['wins']   -= 1;  w['comparisons'] -= 1
        l['elo'] = el;  l['losses'] -= 1;  l['comparisons'] -= 1
        self.comparisons -= 1

        self.pair = [wi, li]
        self.update_card(0, w)
        self.update_card(1, l)
        self.refresh()

    def refresh(self):
        skipped = sum(1 for f in self.films if f['skipped'])
        remaining = max(0, RECOMMENDED_COMPARISONS - self.comparisons)
        if hasattr(self, 'status'):
            self.status.set(
                f'Vergleiche: {self.comparisons}  ·  ~{remaining} empfohlen  ·  {skipped} übersprungen'
            )
            self.progress['value'] = min(100, self.comparisons / RECOMMENDED_COMPARISONS * 100)

    # ── Ergebnisse ────────────────────────────────────────────────────────────

    def show_results(self):
        win = tk.Toplevel(self)
        win.title('Ranking')
        win.geometry('720x650')
        win.configure(bg=BG)

        tk.Label(win, text='Dein Ranking',
                 font=('Helvetica', 18, 'bold'), bg=BG).pack(anchor='w', padx=20, pady=(20, 8))

        columns = ('#', 'Titel', 'Jahr', 'Regisseur', 'ELO')
        widths  = {'#': 40, 'Titel': 300, 'Jahr': 60, 'Regisseur': 220, 'ELO': 60}

        tree = ttk.Treeview(win, columns=columns, show='headings')
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=widths[col],
                        anchor='e' if col in ('#', 'ELO') else 'w')

        sb = ttk.Scrollbar(win, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side='left', fill='both', expand=True, padx=(20, 0), pady=(0, 12))
        sb.pack(side='left', fill='y', pady=(0, 12))

        ranked = sorted(
            [f for f in self.films if not f['skipped']],
            key=lambda f: f['elo'], reverse=True
        )
        for rank, film in enumerate(ranked, 1):
            tree.insert('', 'end',
                        values=(rank, film['title'], film['year'], film['director'], film['elo']))


# ── Start ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    FilmRanker().mainloop()
