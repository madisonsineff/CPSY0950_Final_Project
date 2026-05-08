# This is the main script of GamePython (the "home page" if you will). This is where all of the different games can be located but our hope is that you will be able to click on a given game and activte a separte script, with this always running as a constant "hub" to return to in between games.
import pygame
from pygame.locals import *
class App:
    def __init__(self):
        pygame.init()
        self._running = True
        self._display_surf = None
        self.size = self.weight, self.height = 1000, 1000
        self.FPS = 60
        self.clock = pygame.time.Clock()
        
        self.screen = pygame.display.set_mode(self.size, pygame.HWSURFACE | pygame.DOUBLEBUF)
        self.background = pygame.Surface(self.screen.get_size()).convert()
        self.background.fill((250, 250, 250))
        pygame.display.set_caption("Welcome to GamePython!")
        
    def draw(self):
        self.screen.blit(self.background, (0, 0))
        pygame.display.flip()
        
    def run(self):
        while self._running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False
            self.draw()
            self.clock.tick(self.FPS)
        pygame.quit()
        
if __name__ == "__main__":
    theApp = App()
    theApp.run()