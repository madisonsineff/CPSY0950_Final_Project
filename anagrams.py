# this is the code for the anagrams game! The idea is to have this script launch when the user presses the "anagrams" button on the home page
# we wanted to have a separate script for each game that can then go back to the home page at any time to switch between games
# having the games run as separate scripts creates more ease with the code --> site is easier to then navigate

import pathlib
import random
import subprocess
import sys

import pygame


# gameplay constants 
TIME_LIMIT_MS = 120 * 1000 #length of each round after player hits the play button (2 minute cap)
MIN_WORD_LENGTH = 3 #minimum word length (guesses under 3 letters are rejected)
MAX_TYPED_LENGTH = 20 #point values for 3-6 letter words that are accepted

# points by word length (cannot have 6+ letter words since each given letter can only be used once!)
SCORE_LEN_3 = 300
SCORE_LEN_4 = 400
SCORE_LEN_5 = 500
SCORE_LEN_6_PLUS = 600


def points_for_word(word: str) -> int:
    n = len(word.strip())
    if n <= 2:
        return 0
    if n == 3:
        return SCORE_LEN_3
    if n == 4:
        return SCORE_LEN_4
    if n == 5:
        return SCORE_LEN_5
    return SCORE_LEN_6_PLUS


# matrix for word solutions (module-level constants do not need `self`)
ANAGRAM_SOLUTION_DATABASE = [
    {
        "scramble": "S I S I N T",
        "solutions": [
            "INSIST",
            "INTIS",
            "SNITS",
            "INTI",
            "NITS",
            "SNIT",
            "INTS",
            "SINS",
            "TINS",
            "ISIT",
            "SIST",
            "NISI",
            "SITS",
            "INS",
            "NIT",
            "TIN",
            "INT",
            "SIN",
            "TIS",
            "ITS",
            "SIS",
            "NIS",
            "SIT",
        ],
    },
    {
        "scramble": "G R A N I C",
        "solutions": [
            "ARCING",
            "CARING",
            "RACING",
            "ACING",
            "AGRIN",
            "CAIRN",
            "CIGAR",
            "CRAIG",
            "GRAIN",
            "NARIC",
            "RANGI",
            "AGIN",
            "CARN",
            "GAIN",
            "GNAR",
            "CRAG",
            "GAIR",
            "GRAN",
            "RING",
            "CAIN",
            "CRAN",
            "GARI",
            "GRIN",
            "RAIN",
            "CANG",
            "GIRN",
            "NARC",
            "RANG",
            "AIN",
            "CAG",
            "NAG",
            "AIR",
            "CAN",
            "GAR",
            "RAG",
            "RIG",
            "CAR",
            "GIN",
            "RIN",
            "ARC",
            "CIG",
            "RAN",
        ],
    },
    {
        "scramble": "T N Y O S T",
        "solutions": [
            "SNOTTY",
            "STONY",
            "NOSY",
            "SNOT",
            "TOST",
            "NOTT",
            "STOT",
            "TOTS",
            "NOYS",
            "TONS",
            "TOYS",
            "ONST",
            "TONY",
            "YONT",
            "NOS",
            "ONS",
            "SON",
            "SYN",
            "YON",
            "NOT",
            "ONY",
            "SOT",
            "TON",
            "NOY",
            "OYS",
            "SOY",
            "TOT",
            "NYS",
            "SNY",
            "STY",
            "TOY",
        ],
    },
    {
        "scramble": "I U J E C R",
        "solutions": [
            "JUICER",
            "CURIE",
            "JUICE",
            "UREIC",
            "CIRE",
            "ERIC",
            "RICE",
            "CRUE",
            "ICER",
            "URIC",
            "CURE",
            "IURE",
            "ECRU",
            "JURE",
            "CRU",
            "ICE",
            "REI",
            "CUE",
            "IRE",
            "RUC",
            "CUR",
            "JEU",
            "RUE",
            "ECU",
            "REC",
            "URE",
        ],
    },
    {
        "scramble": "E E C I P S",
        "solutions": [
            "PIECES",
            "SPECIE",
            "CEPES",
            "SEPIC",
            "EPICS",
            "SPICE",
            "PEISE",
            "PIECE",
            "CEES",
            "ICES",
            "PICS",
            "SICE",
            "CEPE",
            "PECS",
            "PIES",
            "SIPE",
            "CEPS",
            "PEES",
            "PISE",
            "SPEC",
            "EPIC",
            "PICE",
            "SEEP",
            "SPIE",
            "CEE",
            "PEC",
            "PIE",
            "SEE",
            "CEP",
            "PEE",
            "PIS",
            "SEI",
            "CIS",
            "PES",
            "PSI",
            "SIC",
            "ICE",
            "PIC",
            "SEC",
            "SIP",
        ],
    },
]


class AnagramsGame:
    def __init__(self):
        pygame.init()

        self.running = True
        self.size = (1200, 800)
        self.fps = 60
        self.clock = pygame.time.Clock()

        self.screen = pygame.display.set_mode(self.size, pygame.HWSURFACE | pygame.DOUBLEBUF)
        self.background = pygame.Surface(self.screen.get_size()).convert()
        self.background.fill((236, 201, 255))
        pygame.display.set_caption("Anagrams")

        self.card_color = (30, 30, 46)
        self.card_bg = (245, 240, 255)
        self.text_main = (30, 30, 46)
        self.accent = (167, 117, 196)
        self.success = (108, 255, 63)
        self.alert = (245, 50, 50)

        self.font_title = pygame.font.SysFont("optima", 44, bold=True)
        self.font_med = pygame.font.SysFont("optima", 28, bold=True)
        self.font_game = pygame.font.SysFont("optima", 24)
        self.font_small = pygame.font.SysFont("optima", 18)

        self.database = ANAGRAM_SOLUTION_DATABASE

        cx = self.size[0] // 2
        self.start_btn_rect = pygame.Rect(cx - 100, 480, 200, 55)
        self.play_again_btn_rect = pygame.Rect(cx - 220, 400, 200, 52)
        self.home_btn_rect = pygame.Rect(cx + 20, 400, 200, 52)
        self.hub_script = pathlib.Path(__file__).resolve().parent / "GamePython_MAINHUB.py"

        self.game_state = "INSTRUCTIONS"
        self.start_ticks = 0
        self.time_limit_ms = TIME_LIMIT_MS
        self.score = 0
        self.guess_buffer = ""
        self.feedback = ""

        self.puzzle_index = 0
        self.scramble = ""
        self.valid_words = frozenset()
        self.guessed_words = set()
        self.found_words_display = []

    def _candidate_words(self, entry):
        return sorted(
            {
                w.strip().upper()
                for w in entry["solutions"]
                if isinstance(w, str) and w.strip()
            }
        )

    def _pick_random_scramble_round(self):
        """One random scramble; player may submit any valid words from that puzzle until time ends."""
        self.puzzle_index = random.randrange(len(self.database))
        entry = self.database[self.puzzle_index]
        self.scramble = entry["scramble"]
        self.valid_words = frozenset(self._candidate_words(entry))
        self.guessed_words = set()
        self.found_words_display = []
        self.guess_buffer = ""
        self.feedback = "Type a word (3+ letters), then press Enter. Words must be in the puzzle list."

    def _remaining_ms_playing(self):
        elapsed = pygame.time.get_ticks() - self.start_ticks
        return max(0, self.time_limit_ms - elapsed)

    def _submit_guess(self):
        raw = self.guess_buffer.strip().upper()
        if not raw:
            self.feedback = "Enter a word, then press Enter."
            return

        if len(raw) < MIN_WORD_LENGTH:
            self.feedback = f"Words must be at least {MIN_WORD_LENGTH} letters."
            self.guess_buffer = ""
            return

        if raw not in self.valid_words:
            self.feedback = f'"{raw}" is not a valid word for this scramble.'
            self.guess_buffer = ""
            return

        if raw in self.guessed_words:
            self.feedback = f'You already scored "{raw}".'
            self.guess_buffer = ""
            return

        pts = points_for_word(raw)
        self.guessed_words.add(raw)
        self.score += pts
        self.found_words_display.append(raw)
        if len(self.found_words_display) > 14:
            self.found_words_display = self.found_words_display[-14:]
        self.feedback = f'"{raw}" counted — keep going!'
        self.guess_buffer = ""

    def _begin_timed_round(self):
        self.score = 0
        self._pick_random_scramble_round()
        self.start_ticks = pygame.time.get_ticks()
        self.game_state = "PLAYING"

    def _return_to_hub(self):
        if self.hub_script.exists():
            subprocess.Popen([sys.executable, str(self.hub_script)])
        pygame.quit()
        sys.exit(0)

    def _draw_instructions(self):
        self.screen.blit(self.background, (0, 0))
        w = self.size[0]

        title_surf = self.font_title.render("HOW TO PLAY", True, self.accent)
        self.screen.blit(title_surf, (w // 2 - title_surf.get_width() // 2, 60))

        rules = [
            "You get one random letter scramble from five puzzles.",
            "Within 2 minutes, submit as many different valid words as you can (from the puzzle’s word list).",
            "Type your guess and press Enter. Words under 3 letters are not accepted.",
            "Scoring: 6+ letters = 600, 5 = 500, 4 = 400, 3 = 300. Each word counts once.",
            "Your total score is shown when time runs out. Then choose Play Again or Home.",
        ]
        y = 150
        for rule in rules:
            surf = self.font_game.render(rule, True, self.text_main)
            self.screen.blit(surf, (w // 2 - surf.get_width() // 2, y))
            y += 38

        mouse_pos = pygame.mouse.get_pos()
        hover = self.start_btn_rect.collidepoint(mouse_pos)
        btn_fill = self.success if hover else self.accent
        lbl_on_fill = tuple(self.screen.get_at((0, 0))[:3])
        pygame.draw.rect(self.screen, btn_fill, self.start_btn_rect, border_radius=10)
        btn_text = self.font_med.render("PLAY", True, lbl_on_fill if hover else self.card_bg)
        self.screen.blit(
            btn_text,
            (
                self.start_btn_rect.centerx - btn_text.get_width() // 2,
                self.start_btn_rect.centery - btn_text.get_height() // 2,
            ),
        )

        hint = self.font_small.render('Click "PLAY" to begin. Press Esc anytime to quit.', True, self.accent)
        self.screen.blit(hint, (w // 2 - hint.get_width() // 2, self.size[1] - 70))
        pygame.display.flip()

    def _draw_playing(self):
        remaining_ms = self._remaining_ms_playing()
        seconds_total = remaining_ms // 1000

        self.screen.blit(self.background, (0, 0))
        w, h = self.size

        header = self.font_title.render("ANAGRAM SOLVER", True, self.accent)
        self.screen.blit(header, (w // 2 - header.get_width() // 2, 36))

        minutes = seconds_total // 60
        seconds = seconds_total % 60
        time_str = f"TIME LEFT: {minutes:02d}:{seconds:02d}"
        tc = self.alert if seconds_total <= 15 else self.text_main
        self.screen.blit(self.font_med.render(time_str, True, tc), (40, 100))

        words_ct = len(self.guessed_words)
        meta = self.font_med.render(f"WORDS FOUND: {words_ct}", True, self.success)
        self.screen.blit(meta, (w - meta.get_width() - 40, 100))

        pool_lbl = self.font_game.render("SCRAMBLED LETTERS:", True, self.text_main)
        self.screen.blit(pool_lbl, (w // 2 - pool_lbl.get_width() // 2, 168))

        scramble_surf = self.font_title.render(self.scramble, True, self.accent)
        self.screen.blit(scramble_surf, (w // 2 - scramble_surf.get_width() // 2, 208))

        panel = pygame.Rect(80, 280, w - 160, 200)
        pygame.draw.rect(self.screen, self.card_bg, panel, border_radius=12)
        pygame.draw.rect(self.screen, self.accent, panel, width=2, border_radius=12)
        hist_title = self.font_game.render("Words you have scored this round (points tallied when time ends)", True, self.text_main)
        self.screen.blit(hist_title, (panel.x + 16, panel.y + 10))

        y = panel.y + 44
        for word in reversed(self.found_words_display[-10:]):
            line = self.font_small.render(word, True, self.card_color)
            self.screen.blit(line, (panel.x + 20, y))
            y += 20

        in_lbl = self.font_game.render("TYPE A WORD, THEN PRESS ENTER:", True, self.text_main)
        self.screen.blit(in_lbl, (w // 2 - in_lbl.get_width() // 2, 500))
        inp = self.font_title.render(self.guess_buffer + "_", True, self.success)
        self.screen.blit(inp, (w // 2 - inp.get_width() // 2, 536))

        fb_surf = self.font_small.render(self.feedback[:95], True, self.accent)
        self.screen.blit(fb_surf, (w // 2 - fb_surf.get_width() // 2, 590))

        help_line = self.font_small.render(
            "Enter: submit  |  Backspace: delete  |  Esc: quit  |  Total score after time’s up",
            True,
            self.card_color,
        )
        self.screen.blit(help_line, (w // 2 - help_line.get_width() // 2, h - 56))
        pygame.display.flip()

    def _draw_game_over(self):
        self.screen.blit(self.background, (0, 0))
        w = self.size[0]

        over = self.font_title.render("TIME'S UP", True, self.alert)
        final = self.font_med.render(f"Final Score: {self.score}", True, self.text_main)
        words_line = self.font_game.render(f"Unique words scored: {len(self.guessed_words)}", True, self.text_main)

        self.screen.blit(over, (w // 2 - over.get_width() // 2, 210))
        self.screen.blit(final, (w // 2 - final.get_width() // 2, 278))
        self.screen.blit(words_line, (w // 2 - words_line.get_width() // 2, 322))

        sub = self.font_game.render("Play again (new scramble) or return to the hub?", True, self.text_main)
        self.screen.blit(sub, (w // 2 - sub.get_width() // 2, 368))

        mouse_pos = pygame.mouse.get_pos()
        lbl_on_play = tuple(self.screen.get_at((0, 0))[:3])
        pa_hover = self.play_again_btn_rect.collidepoint(mouse_pos)
        home_hover = self.home_btn_rect.collidepoint(mouse_pos)

        pygame.draw.rect(
            self.screen, self.success if pa_hover else self.accent, self.play_again_btn_rect, border_radius=10
        )
        pygame.draw.rect(
            self.screen, (72, 195, 88) if home_hover else self.success,
            self.home_btn_rect,
            border_radius=10,
        )

        pa_text = self.font_med.render("PLAY AGAIN", True, lbl_on_play if pa_hover else self.card_bg)
        home_text = self.font_med.render("HOME", True, lbl_on_play if home_hover else self.card_bg)
        self.screen.blit(
            pa_text,
            (
                self.play_again_btn_rect.centerx - pa_text.get_width() // 2,
                self.play_again_btn_rect.centery - pa_text.get_height() // 2,
            ),
        )
        self.screen.blit(
            home_text,
            (
                self.home_btn_rect.centerx - home_text.get_width() // 2,
                self.home_btn_rect.centery - home_text.get_height() // 2,
            ),
        )

        hint = self.font_small.render("Enter: play again  |  H: home  |  Esc: quit", True, self.accent)
        self.screen.blit(hint, (w // 2 - hint.get_width() // 2, self.size[1] - 80))
        pygame.display.flip()

    def draw(self):
        if self.game_state == "INSTRUCTIONS":
            self._draw_instructions()
        elif self.game_state == "PLAYING":
            self._draw_playing()
        else:
            self._draw_game_over()

    def run(self):
        while self.running:
            if self.game_state == "PLAYING":
                if self._remaining_ms_playing() <= 0:
                    self.game_state = "GAME_OVER"

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    continue

                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.running = False
                    continue

                if self.game_state == "INSTRUCTIONS":
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if self.start_btn_rect.collidepoint(event.pos):
                            self._begin_timed_round()

                elif self.game_state == "GAME_OVER":
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if self.play_again_btn_rect.collidepoint(event.pos):
                            self._begin_timed_round()
                        elif self.home_btn_rect.collidepoint(event.pos):
                            self._return_to_hub()
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_RETURN:
                            self._begin_timed_round()
                        elif event.key == pygame.K_h:
                            self._return_to_hub()

                elif self.game_state == "PLAYING":
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_RETURN:
                            self._submit_guess()
                        elif event.key == pygame.K_BACKSPACE:
                            self.guess_buffer = self.guess_buffer[:-1]
                        elif hasattr(event, "unicode") and event.unicode and event.unicode.isalpha():
                            if len(self.guess_buffer) < MAX_TYPED_LENGTH:
                                self.guess_buffer += event.unicode.upper()

            self.draw()
            self.clock.tick(self.fps)

        pygame.quit()


if __name__ == "__main__":
    AnagramsGame().run()
