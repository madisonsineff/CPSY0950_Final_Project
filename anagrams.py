# this is the code for the anagrams game! The idea is to have this script launch when the user presses the "anagrams" button on the home page
# we wanted to have a separate script for each game that can then go back to the home page at any time to switch between games
# having the games run as separate scripts creates more ease with the code --> site is easier to then navigate

import pathlib
import random
import subprocess
import sys

import pygame


NUM_TARGET_SLOTS = 3
TIME_LIMIT_MS = 120 * 1000
MAX_TYPED_LENGTH = 16

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

        # UI colors (timed mode layouts use card_bg vs card_color naming)
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

  
