#Script for the GamePython home screen hub where all of the scripts will live; the hope is to have this constantly running so that users can return back to this before, between, and after games to select new ones; will only be quit if user hits the red x button in the top left corner of the window
import pathlib
import subprocess
import sys

import pygame


class App:
    def __init__(self):
        pygame.init()
        #these lines are responsible for configuring the main window and background color/size of the home hub
        self.running = True
        self.size = (1200, 800)
        self.fps = 60
        self.clock = pygame.time.Clock()

        self.screen = pygame.display.set_mode(self.size, pygame.HWSURFACE | pygame.DOUBLEBUF)
        self.background = pygame.Surface(self.screen.get_size()).convert()
        self.background.fill((153, 204, 255))
        pygame.display.set_caption("GamePython Hub!")

        #adjusting font size and colors for different titles within the home hub
        self.title_font = pygame.font.SysFont("chalkboard", 52, bold=True)
        self.button_font = pygame.font.SysFont("optima", 30, bold=True)
        self.message_font = pygame.font.SysFont("optima", 24)
        self.message = "Choose any game to launch!"

        #this enales the main folder of GamePython_MAINHUB.py to be accessed so that future scripts (like scripts specific to the games) can be accessed and built relative to the home hub
        base_dir = pathlib.Path(__file__).parent
        # specific game scripts are located here as an access point from the home screen
        #make all updates to game scripts here 
        self.games = [
            {"title": "Anagrams", "script": base_dir / "anagrams.py", "image": base_dir / "wordhuntbackground.png", "image_zoom": 0.05},
            {"title": "Four in a Row", "script": base_dir / "mini_golf.py", "image": base_dir / "connect4background.jpg"},
            {"title": "Cup Pong", "script": base_dir / "cup_pong.py", "image": base_dir / "cuppongbackground.webp"},
        ]

        #makes the buttons for game scripts into a clickable rectangle 
        self.buttons = self.build_buttons()
        self.load_button_images()

    def load_button_images(self):
        for button in self.buttons:
            rect = button["rect"]
            image_path = button["game"].get("image")
            image_zoom = button["game"].get("image_zoom", 1.0)
            button["image"] = None
            if not image_path:
                continue

            try:
                loaded_image = pygame.image.load(str(image_path)).convert_alpha()
                button["image"] = self.prepare_button_image(loaded_image, rect.size, image_zoom)
            except (pygame.error, FileNotFoundError):
                #if an image file is missing or unreadable, fallback drawing will be used
                button["image"] = None

    def prepare_button_image(self, image_surface, target_size, image_zoom=1.0):
        target_w, target_h = target_size
        source_w, source_h = image_surface.get_size()

        #zoom < 1 means show more of the source image while still filling the whole button
        crop_w = min(source_w, max(1, int(round(target_w / zoom))))
        crop_h = min(source_h, max(1, int(round(target_h / zoom))))

        #keep crop aspect ratio aligned with the button to avoid distortion
        target_ratio = target_w / target_h
        crop_ratio = crop_w / crop_h
        if crop_ratio > target_ratio:
            crop_w = max(1, int(crop_h * target_ratio))
        elif crop_ratio < target_ratio:
            crop_h = max(1, int(crop_w / target_ratio))

        crop_x = max(0, (source_w - crop_w) // 2)
        crop_y = max(0, (source_h - crop_h) // 2)
        cropped = image_surface.subsurface((crop_x, crop_y, crop_w, crop_h)).copy()

        button_image = pygame.transform.smoothscale(cropped, (target_w, target_h))

        #apply rounded corners so the image matches the button shape
        mask_surface = pygame.Surface((target_w, target_h), pygame.SRCALPHA)
        pygame.draw.rect(mask_surface, (255, 255, 255, 255), mask_surface.get_rect(), border_radius=14)
        button_image.blit(mask_surface, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        return button_image

    #specific dimensions of the build buttons 
    def build_buttons(self):
        buttons = []
        button_w, button_h = 320, 90
        spacing = 30
        start_x = (self.size[0] - button_w) // 2
        start_y = 220

        for i, game in enumerate(self.games): #enables creation of multiple buttons for each game script
            rect = pygame.Rect(start_x, start_y + i * (button_h + spacing), button_w, button_h)
            buttons.append({"rect": rect, "game": game})
        return buttons

    def launch_game(self, script_path):
        if not script_path.exists():
            #checks if the game script exists (if not it will say missing file)
            self.message = f"Missing file: {script_path.name}"
            return

        # Launch using the same Python interpreter as this hub and lets user know that the game script has been launched
        subprocess.Popen([sys.executable, str(script_path)])
        self.message = f"Launched {script_path.name}"

    def draw(self):
        self.screen.blit(self.background, (0, 0))

        title_surface = self.title_font.render("GamePython Hub", True, (20, 20, 60))
        self.screen.blit(title_surface, (self.size[0] // 2 - title_surface.get_width() // 2, 80))

        #for tracking mouse coordinates so that the buttons can react to hovering
        mouse_pos = pygame.mouse.get_pos()
        #loops through each of the previously created buttons
        for button in self.buttons:
            rect = button["rect"]
            game = button["game"]
            is_hover = rect.collidepoint(mouse_pos) #checks whether the mouse is currently within the boundaries of a given button
            image = button.get("image")

            if image is not None:
                self.screen.blit(image, rect.topleft)
                if is_hover:
                    hover_overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
                    hover_overlay.fill((255, 255, 255, 35))
                    self.screen.blit(hover_overlay, rect.topleft)
                pygame.draw.rect(self.screen, (15, 38, 100), rect, width=2, border_radius=14)
            else:
                color = (68, 121, 255) if is_hover else (45, 92, 210) #changes the color of the button to lighter blue when hovered over, and dark blue otherwise
                pygame.draw.rect(self.screen, color, rect, border_radius=14) #draws a border around the button when hovered over for asthetic effect
                pygame.draw.rect(self.screen, (15, 38, 100), rect, width=2, border_radius=14)

            text_surface = self.button_font.render(game["title"], True, (255, 255, 255)) #renders game titles in white
            text_x = rect.centerx - text_surface.get_width() // 2
            text_y = rect.centery - text_surface.get_height() // 2
            outline_surface = self.button_font.render(game["title"], True, (0, 0, 0))
            for dx, dy in [
                (-2, 0), (2, 0), (0, -2), (0, 2),
                (-1, -1), (1, -1), (-1, 1), (1, 1),
            ]:
                self.screen.blit(outline_surface, (text_x + dx, text_y + dy))
            #draws label centered inside the button
            self.screen.blit(text_surface, (text_x, text_y))

        #renders the status message of launching
        message_surface = self.message_font.render(self.message, True, (20, 20, 60))
        self.screen.blit(message_surface, (40, self.size[1] - 60))

        pygame.display.flip()

    #keeping the hub running and quits the window when the x button is pressed
    def run(self):
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for button in self.buttons:
                        if button["rect"].collidepoint(event.pos):
                            self.launch_game(button["game"]["script"])
                            break

            self.draw()
            self.clock.tick(self.fps)

        pygame.quit()


if __name__ == "__main__":
    app = App() #creates the app object and starts the main loop
    app.run()