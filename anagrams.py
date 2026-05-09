#this is the code for the anagrams game! The idea is to have this script launch when the user presses the "anagrams" button on the home page
#we wanted to have a separate script for each game that can then go back to the home page at any time to switch between games
#having the games run as separate scripts creates more ease with the code --> site is easier to then navigate
#importing necessary packages for the anagram game
import pygame
import random
import sys

#initialize Pygame modules
pygame.init

#window configurations
self.running = True
self.size = (1200, 800)
self.fps = 60
self.clock = pygame.time.Clock()

self.screen = pygame.display.set_mode(self.size, pygame.HWSURFACE | pygame.DOUBLEBUF)
self.background = pygame.Surface(self.screen.get_size()).convert()
self.background.fill((236, 201, 255))
pygame.display.set_caption("Anagrams")

#color palette for the rest of the system (easier to establish this now)
card_color = (30, 30, 46)
text_main = (255, 255, 255)
accent = (167, 117, 196)
success = (108, 255, 63)
alert = (245, 50, 50)

#game text and dimensions
font_title = pygame.font.SysFont('optima', 44, bold=True)
font_med = pygame.font.SysFont('optima', 28, bold=True)
font_game = pygame.font.SysFont('optima', 24)
font_small = pygame.font.SysFont('optima', 18)

#matrix for word solutions
anagram_solution_database = [
    {"scramble": "S I S I N T", "solutions": ["INSIST", "INTIS", "SNITS", "INTI", "NITS", "SNIT", "INTS", "SINS", "TINS", "ISIT", "SIST", "NISI", "SITS", "INS", "NIT", "TIN", "INT", "SIN", "TIS", "ITS", "SIS", "NIS", "SIT"]}
    {"scramble": "G R A N I C", "solutions": ["ARCING", "CARING", "RACING", "ACING", "AGRIN", "CAIRN", "CIGAR", "CRAIG", "GRAIN", "NARIC", "RANGI", "AGIN", "CARN", "GAIN", "GNAR", "CRAG", "GAIR", "GRAN", "RING", "CAIN", "CRAN", "GARI", "GRIN", "RAIN", "CANG", "GIRN", "NARC", "RANG", "AIN", "CAG", "NAG", "AIR", "CAN", "GAR", "RAG", "RIG", "CAR", "GIN", "RIN", "ARC", "CIG", "RAN"]}
]
