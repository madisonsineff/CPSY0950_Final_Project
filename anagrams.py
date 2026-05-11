# this is the code for the anagrams game! The idea is to have this script launch when the user presses the "anagrams" button on the home page
# we wanted to have a separate script for each game that can then go back to the home page at any time to switch between games
# having the games run as separate scripts creates more ease with the code --> site is easier to then navigate

import pathlib
import random
import subprocess
import sys

import pygame


# gameplay constants 
TIME_LIMIT_MS = 80 * 1000  # length of each round after PLAY (80 seconds)
MIN_WORD_LENGTH = 3 #minimum word length (guesses under 3 letters are rejected)
MAX_TYPED_LENGTH = 20 #point values for 3-6 letter words that are accepted

# points by word length (cannot have 6+ letter words since each given letter can only be used once!)
SCORE_LEN_3 = 300
SCORE_LEN_4 = 400
SCORE_LEN_5 = 500
SCORE_LEN_6_PLUS = 600


# function to calculate points for a word based on its length
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


# different possible puzzles and their solutions to be used in the game; this is in matrix form to make it easier to add new puzzles and solutions
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

# creates the entire anagrams game as a class object; essentially the control center for display, game state, and gameplay
class AnagramsGame:
    def __init__(self):
        # initialize pygame and set up the display
        pygame.init()

        self.running = True # flag to indicate if the game is running
        self.size = (1200, 800)
        self.fps = 60 # frames per second
        self.clock = pygame.time.Clock()

        self.screen = pygame.display.set_mode(self.size, pygame.HWSURFACE | pygame.DOUBLEBUF)
        self.background = pygame.Surface(self.screen.get_size()).convert() # background surface to fill the screen
        self.background.fill((236, 201, 255))
        pygame.display.set_caption("Anagrams")

        self.card_color = (30, 30, 46) # color of the card border
        self.card_bg = (245, 240, 255)
        self.text_main = (0, 0, 0) # color of the main text
        self.accent = (0, 0, 0) # color of the accent text
        self.success = (51, 0, 102) # color of the success text
        self.alert = (245, 50, 50) # color of the alert text

        self.font_title = pygame.font.SysFont("optima", 44, bold=True) # font for the title
        self.font_med = pygame.font.SysFont("optima", 28, bold=True) # font for the medium text
        self.font_game = pygame.font.SysFont("optima", 24) # font for the game text
        self.font_small = pygame.font.SysFont("optima", 18) # font for the small text

        self.database = ANAGRAM_SOLUTION_DATABASE # the database of puzzles and solutions

        cx = self.size[0] // 2 # center of the screen
        self.start_btn_rect = pygame.Rect(cx - 100, 480, 200, 55) # rectangle for the start button
        self.play_again_btn_rect = pygame.Rect(cx - 220, 400, 200, 52) # rectangle for the play again button
        self.home_btn_rect = pygame.Rect(cx + 20, 400, 200, 52) # rectangle for the home button
        self.hub_script = pathlib.Path(__file__).resolve().parent / "GamePython_MAINHUB.py" # path to the main hub script

        self.game_state = "INSTRUCTIONS" # initial game state
        self.start_ticks = 0 # time when the game started
        self.time_limit_ms = TIME_LIMIT_MS # time limit for the game
        self.score = 0 # initial score
        self.guess_buffer = "" # initial guess buffer
        self.feedback = "" # initial feedback

        self.puzzle_index = 0 # initial puzzle index
        self.scramble = "" # initial scramble
        self.valid_words = frozenset() # initial valid words
        self.guessed_words = set() # initial guessed words
        self.found_words_display = [] # initial found words display
        self.word_bank_scroll = 0 # initial word bank scroll
        self.word_bank_scroll_to_bottom = False # initial word bank scroll to bottom
        self.word_bank_panel_rect = self._word_bank_panel_rect() # initial word bank panel rectangle

    def _word_bank_panel_rect(self):
        w = self.size[0] # width of the screen
        return pygame.Rect(80, 280, w - 160, 200) # rectangle for the word bank panel

    def _word_bank_inner_rect(self, panel):
        """Area below the title, reserved for wrapped words (scrollbar uses right strip).""" # area below the title, reserved for wrapped words (scrollbar uses right strip)
        return pygame.Rect(panel.x + 10, panel.y + 38, panel.width - 20, panel.height - 46) # rectangle for the word bank inner rectangle       

    def _layout_word_bank_rows(self, inner_w):
        """Wrap words left-to-right; each row is a list of rendered surfaces.""" # wrap words left-to-right; each row is a list of rendered surfaces
        font = self.font_small
        color = self.card_color
        gap_x = 8 # gap between words
        line_gap = 4 # gap between lines
        rows = [] # list of rows
        row = [] # list of words in a row
        row_w = 0 # width of the row
        for word in self.found_words_display:
            surf = font.render(word, True, color) # render the word as a surface
            ww = surf.get_width() # width of the surface
            if not row:
                row.append(surf)
                row_w = ww # width of the row       
            elif row_w + gap_x + ww <= inner_w:
                row.append(surf)
                row_w += gap_x + ww # width of the row       
            else:
                rows.append(row)
                row = [surf]
                row_w = ww # width of the row       
        if row:
            rows.append(row)
        row_heights = [] # list of heights of the rows
        for r in rows:
            rh = max(s.get_height() for s in r) + line_gap # height of the row
            row_heights.append(rh) # add the height of the row to the list
        total_h = sum(row_heights) # total height of the rows
        return rows, row_heights, total_h

    def _candidate_words(self, entry):
        return sorted( # sort the words
            {
                w.strip().upper()
                for w in entry["solutions"] # solutions for the puzzle      
                if isinstance(w, str) and w.strip() # if the word is a string and is not empty
            }
        )

    def _pick_random_scramble_round(self):
        """One random scramble; player may submit any valid words from that puzzle until time ends."""
        self.puzzle_index = random.randrange(len(self.database)) # select a random puzzle from the database
        entry = self.database[self.puzzle_index]
        self.scramble = entry["scramble"]
        self.valid_words = frozenset(self._candidate_words(entry)) # valid words for the puzzle
        self.guessed_words = set() # guessed words
        self.found_words_display = [] # found words display
        self.guess_buffer = "" # guess buffer
        self.feedback = "Type a word (3+ letters), then press Enter. Words must be in the puzzle list." # feedback
        self.word_bank_scroll = 0
        self.word_bank_scroll_to_bottom = False # word bank scroll to bottom

    def _remaining_ms_playing(self):
        elapsed = pygame.time.get_ticks() - self.start_ticks # time elapsed since the game started
        return max(0, self.time_limit_ms - elapsed)

    def _submit_guess(self):
        raw = self.guess_buffer.strip().upper() # strip the guess buffer and convert to uppercase
        if not raw:
            self.feedback = "Enter a word, then press Enter." # feedback            
            return

        if len(raw) < MIN_WORD_LENGTH:
            self.feedback = f"Words must be at least {MIN_WORD_LENGTH} letters." # feedback
            self.guess_buffer = "" # clear the guess buffer     
            return

        if raw not in self.valid_words:
            self.feedback = f'"{raw}" is not a valid word for this scramble.'
            self.guess_buffer = "" # clear the guess buffer     
            return

        if raw in self.guessed_words:
            self.feedback = f'You already scored "{raw}".'
            self.guess_buffer = "" # clear the guess buffer     
            return

        pts = points_for_word(raw) # points for the word
        self.guessed_words.add(raw)
        self.score += pts # add the points to the score
        self.found_words_display.append(raw) # add the word to the found words display
        self.word_bank_scroll_to_bottom = True # word bank scroll to bottom
        self.feedback = f'"{raw}" counted — keep going!'
        self.guess_buffer = ""

    def _begin_timed_round(self):
        self.score = 0 # reset the score
        self._pick_random_scramble_round() # pick a random scramble round
        self.start_ticks = pygame.time.get_ticks() # time when the game started
        self.game_state = "PLAYING" # game state is playing

    def _return_to_hub(self):
        if self.hub_script.exists(): # if the hub script exists
            subprocess.Popen([sys.executable, str(self.hub_script)])
        pygame.quit() # quit pygame
        sys.exit(0)

    def _draw_instructions(self):
        self.screen.blit(self.background, (0, 0)) # draw the background
        w = self.size[0] # width of the screen

        title_surf = self.font_title.render("HOW TO PLAY", True, self.accent)
        self.screen.blit(title_surf, (w // 2 - title_surf.get_width() // 2, 60)) # draw the title

        rules = [ # rules for the game
            "Welcome to Anagrams! Try to make as many words as possible from the given scrambled letters.",
            "Words must be at least 3 letters long and must be a valid word from the puzzle's word list.",
            "Longer words earn more points, and repeated words will not be counted.",
            "Type your guess and press Enter. Good luck!",
        ]
        y = 150 # y position for the rules
        for rule in rules:
            surf = self.font_game.render(rule, True, self.text_main) # render the rule as a surface
            self.screen.blit(surf, (w // 2 - surf.get_width() // 2, y)) # draw the rule
            y += 38

        mouse_pos = pygame.mouse.get_pos() # position of the mouse
        hover = self.start_btn_rect.collidepoint(mouse_pos) # if the mouse is hovering over the start button
        btn_fill = self.success if hover else self.accent # color of the button fill
        lbl_on_fill = tuple(self.screen.get_at((0, 0))[:3]) # color of the label on the button fill
        pygame.draw.rect(self.screen, btn_fill, self.start_btn_rect, border_radius=10) # draw the start button
        btn_text = self.font_med.render("PLAY", True, lbl_on_fill if hover else self.card_bg) # render the button text as a surface
        self.screen.blit(btn_text, (self.start_btn_rect.centerx - btn_text.get_width() // 2, self.start_btn_rect.centery - btn_text.get_height() // 2)) # draw the button text

        hint = self.font_small.render('Click "PLAY" to begin. Press Esc anytime to quit.', True, self.accent) # render the hint as a surface
        self.screen.blit(hint, (w // 2 - hint.get_width() // 2, self.size[1] - 70)) # draw the hint
        pygame.display.flip()

    def _draw_playing(self):
        remaining_ms = self._remaining_ms_playing() # remaining time in milliseconds
        seconds_total = remaining_ms // 1000 # remaining time in seconds

        self.screen.blit(self.background, (0, 0)) # draw the background
        w, h = self.size # width and height of the screen

        header = self.font_title.render("ANAGRAM SOLVER", True, self.accent) # render the header as a surface   
        self.screen.blit(header, (w // 2 - header.get_width() // 2, 36)) # draw the header

        minutes = seconds_total // 60 # minutes
        seconds = seconds_total % 60 # seconds
        time_str = f"TIME LEFT: {minutes:02d}:{seconds:02d}" # time string
        tc = self.alert if seconds_total <= 15 else self.text_main # color of the time text
        self.screen.blit(self.font_med.render(time_str, True, tc), (40, 100)) # draw the time text

        words_ct = len(self.guessed_words) # number of words found
        meta = self.font_med.render(f"WORDS FOUND: {words_ct}", True, self.success)
        self.screen.blit(meta, (w - meta.get_width() - 40, 100)) # draw the meta text

        pool_lbl = self.font_game.render("SCRAMBLED LETTERS:", True, self.text_main) # render the pool label as a surface
        self.screen.blit(pool_lbl, (w // 2 - pool_lbl.get_width() // 2, 168)) # draw the pool label

        scramble_surf = self.font_title.render(self.scramble, True, self.accent) # render the scramble as a surface
        self.screen.blit(scramble_surf, (w // 2 - scramble_surf.get_width() // 2, 208)) # draw the scramble

        panel = self._word_bank_panel_rect() # word bank panel rectangle
        self.word_bank_panel_rect = panel # word bank panel rectangle
        pygame.draw.rect(self.screen, self.card_bg, panel, border_radius=12) # draw the word bank panel background
        pygame.draw.rect(self.screen, self.accent, panel, width=2, border_radius=12) # draw the word bank panel border
        hist_title = self.font_game.render(
            "Words you scored (wraps across; wheel to scroll if list is long)", True, self.text_main
        ) # render the history title as a surface
        self.screen.blit(hist_title, (panel.x + 16, panel.y + 10)) # draw the history title

        inner = self._word_bank_inner_rect(panel)
        scroll_gutter = 12 # scroll gutter
        content = pygame.Rect(inner.x, inner.y, max(40, inner.width - scroll_gutter), inner.height) # content rectangle
        rows, row_heights, total_h = self._layout_word_bank_rows(content.width) # layout the word bank rows
        max_scroll = max(0, total_h - content.height) # maximum scroll
        if self.word_bank_scroll_to_bottom:
            self.word_bank_scroll = max_scroll # maximum scroll
            self.word_bank_scroll_to_bottom = False # word bank scroll to bottom
        else:
            self.word_bank_scroll = max(0, min(self.word_bank_scroll, max_scroll)) # word bank scroll

        gap_x = 8 # gap between words
        prev_clip = self.screen.get_clip() # previous clip  to set the clip to the content
        self.screen.set_clip(content) # set the clip to the content to draw the word bank           
        y = content.y - self.word_bank_scroll # y position for the word bank
        for row, rh in zip(rows, row_heights): # zip the rows and row heights
            row_max_h = max(s.get_height() for s in row) # maximum height of the row
            x = content.x # x position for the word bank
            for surf in row:
                self.screen.blit(surf, (x, y + row_max_h - surf.get_height())) # draw the word bank
                x += surf.get_width() + gap_x
            y += rh
        self.screen.set_clip(prev_clip) # set the clip to the previous clip

        if max_scroll > 0:
            track = pygame.Rect(inner.right - 10, inner.y, 8, inner.height) # track rectangle
            pygame.draw.rect(self.screen, (220, 215, 235), track, border_radius=4) # draw the track
            thumb_h = max(18, int(inner.height * inner.height / (total_h + 0.001))) # height of the thumb
            t_top = inner.y + int((self.word_bank_scroll / max_scroll) * (inner.height - thumb_h)) # top position of the thumb
            thumb = pygame.Rect(track.x, t_top, track.width, thumb_h) # thumb rectangle
            pygame.draw.rect(self.screen, self.accent, thumb, border_radius=4) # draw the thumb

        in_lbl = self.font_game.render("TYPE A WORD, THEN PRESS ENTER:", True, self.text_main) # render the input label as a surface    
        self.screen.blit(in_lbl, (w // 2 - in_lbl.get_width() // 2, 500)) # draw the input label
        inp = self.font_title.render(self.guess_buffer + "_", True, self.success) # render the input as a surface to display the input
        self.screen.blit(inp, (w // 2 - inp.get_width() // 2, 536)) # draw the input

        fb_surf = self.font_small.render(self.feedback[:95], True, self.accent) # render the feedback as a surface to display the feedback
        self.screen.blit(fb_surf, (w // 2 - fb_surf.get_width() // 2, 590)) # draw the feedback to display the feedback

        help_line = self.font_small.render(
            "Enter: submit  |  Backspace: delete  |  Wheel/PgUp/PgDn: scroll word bank  |  Esc: quit",
            True,
            self.card_color,
        ) # render the help line as a surface to display the help line
        self.screen.blit(help_line, (w // 2 - help_line.get_width() // 2, h - 56)) # draw the help line to display the help line
        pygame.display.flip()

    def _draw_game_over(self):
        self.screen.blit(self.background, (0, 0)) # draw the background
        w = self.size[0]

        over = self.font_title.render("TIME'S UP", True, self.alert) # render the over as a surface
        final = self.font_med.render(f"Final Score: {self.score}", True, self.text_main) # render the final score as a surface
        words_line = self.font_game.render(f"Unique words scored: {len(self.guessed_words)}", True, self.text_main) # render the words line as a surface

        self.screen.blit(over, (w // 2 - over.get_width() // 2, 210)) # draw the over
        self.screen.blit(final, (w // 2 - final.get_width() // 2, 278)) # draw the final score
        self.screen.blit(words_line, (w // 2 - words_line.get_width() // 2, 322)) # draw the words line

        sub = self.font_game.render("Play again (new scramble) or return to the hub?", True, self.text_main) # render the sub as a surface
        self.screen.blit(sub, (w // 2 - sub.get_width() // 2, 368)) # draw the sub

        mouse_pos = pygame.mouse.get_pos()
        lbl_on_play = tuple(self.screen.get_at((0, 0))[:3]) # color of the label on the play button fill
        pa_hover = self.play_again_btn_rect.collidepoint(mouse_pos) # if the mouse is hovering over the play again button
        home_hover = self.home_btn_rect.collidepoint(mouse_pos) # if the mouse is hovering over the home button

        pygame.draw.rect(
            self.screen, self.success if pa_hover else self.accent, self.play_again_btn_rect, border_radius=10 # draw the play again button
        )
        pygame.draw.rect(
            self.screen, (72, 195, 88) if home_hover else self.success,
            self.home_btn_rect, # draw the home button
            border_radius=10, # border radius of the home button
        )

        pa_text = self.font_med.render("PLAY AGAIN", True, lbl_on_play if pa_hover else self.card_bg) # render the play again text as a surface
        home_text = self.font_med.render("HOME", True, lbl_on_play if home_hover else self.card_bg) # render the home text as a surface
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

        hint = self.font_small.render("Enter: play again  |  H: home  |  Esc: quit", True, self.accent) # render the hint as a surface to display the hint
        self.screen.blit(hint, (w // 2 - hint.get_width() // 2, self.size[1] - 80)) # draw the hint to display the hint
        pygame.display.flip()

    def draw(self):
        if self.game_state == "INSTRUCTIONS": # if the game state is instructions
            self._draw_instructions()
        elif self.game_state == "PLAYING": # if the game state is playing
            self._draw_playing()
        else:
            self._draw_game_over() # if the game state is game over

    def run(self):
        while self.running: # while the game is running
            if self.game_state == "PLAYING":
                if self._remaining_ms_playing() <= 0: # if the remaining time is 0
                    self.game_state = "GAME_OVER" # set the game state to game over

            for event in pygame.event.get():
                if event.type == pygame.QUIT: # if the event type is quit
                    self.running = False
                    continue # continue to the next event

                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.running = False # set the running to False to stop the game
                    continue # continue to the next event

                if self.game_state == "INSTRUCTIONS": # if the game state is instructions
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1: # if the mouse button is down
                        if self.start_btn_rect.collidepoint(event.pos): # if the mouse is hovering over the start button
                            self._begin_timed_round() # begin a timed round

                elif self.game_state == "GAME_OVER": # if the game state is game over
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if self.play_again_btn_rect.collidepoint(event.pos): # if the mouse is hovering over the play again button
                            self._begin_timed_round() # begin a timed round
                        elif self.home_btn_rect.collidepoint(event.pos): # if the mouse is hovering over the home button
                            self._return_to_hub() # return to the hub
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_RETURN:
                            self._begin_timed_round() # begin a timed round
                        elif event.key == pygame.K_h:
                            self._return_to_hub() # return to the hub

                elif self.game_state == "PLAYING": # if the game state is playing   
                    if event.type == pygame.MOUSEWHEEL: # if the mouse wheel is moved
                        if self.word_bank_panel_rect.collidepoint(pygame.mouse.get_pos()): # if the mouse is hovering over the word bank panel
                            dy = float(getattr(event, "precise_y", event.y)) # get the precise y position of the mouse
                            self.word_bank_scroll -= dy * 32 # scroll the word bank

                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_RETURN:
                            self._submit_guess() # submit a guess
                        elif event.key == pygame.K_BACKSPACE:
                            self.guess_buffer = self.guess_buffer[:-1] # delete the last character in the guess buffer
                        elif event.key in (pygame.K_PAGEUP,):
                            self.word_bank_scroll -= 80 # scroll the word bank up
                        elif event.key in (pygame.K_PAGEDOWN,):
                            self.word_bank_scroll += 80 # scroll the word bank down
                        elif hasattr(event, "unicode") and event.unicode and event.unicode.isalpha(): # if the unicode is a letter
                            if len(self.guess_buffer) < MAX_TYPED_LENGTH: # if the length of the guess buffer is less than the maximum typed length
                                self.guess_buffer += event.unicode.upper() # add the unicode to the guess buffer

            self.draw()
            self.clock.tick(self.fps) # tick the clock to update the game

        pygame.quit() # quit pygame


if __name__ == "__main__":
    AnagramsGame().run() # run the game
