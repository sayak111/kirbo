import pygame

from client.avatar_art import make_avatar_surface
from lib.avatar import AVATAR_PALETTE, AVATAR_SIZE


GRID_RECT = pygame.Rect(40, 100, 320, 320)
GRID_CELL_SIZE = GRID_RECT.width // AVATAR_SIZE
PROMPT_RECT = pygame.Rect(415, 250, 345, 74)
GENERATE_RECT = pygame.Rect(415, 350, 160, 44)
SAVE_RECT = pygame.Rect(415, 415, 160, 44)
BACK_RECT = pygame.Rect(600, 415, 160, 44)
PALETTE_RECTS = [
    pygame.Rect(415 + (index % 4) * 48, 195 + (index // 4) * 38, 30, 30)
    for index in range(len(AVATAR_PALETTE))
]

COLOR_BG = (24, 24, 27)
COLOR_CARD = (39, 39, 42)
COLOR_BORDER = (63, 63, 70)
COLOR_TEXT = (244, 244, 245)
COLOR_MUTED = (161, 161, 170)
COLOR_ACCENT = (99, 102, 241)


def grid_cell_at(pos):
    if not GRID_RECT.collidepoint(pos):
        return None
    col = (pos[0] - GRID_RECT.x) // GRID_CELL_SIZE
    row = (pos[1] - GRID_RECT.y) // GRID_CELL_SIZE
    return row, col


def draw(screen, state, fonts):
    font_title, font_body, font_sm = fonts
    screen.fill(COLOR_BG)
    screen.blit(font_title.render("Avatar Studio", True, COLOR_TEXT), (40, 30))

    canvas_rect = GRID_RECT.inflate(12, 12)
    pygame.draw.rect(screen, COLOR_CARD, canvas_rect, border_radius=4)
    for row_index, row in enumerate(state["avatar_grid"]):
        for col_index, pixel in enumerate(row):
            rect = pygame.Rect(
                GRID_RECT.x + col_index * GRID_CELL_SIZE,
                GRID_RECT.y + row_index * GRID_CELL_SIZE,
                GRID_CELL_SIZE,
                GRID_CELL_SIZE,
            )
            if pixel == "0":
                checker = (63, 63, 70) if (row_index + col_index) % 2 else (47, 47, 52)
                pygame.draw.rect(screen, checker, rect)
            else:
                pygame.draw.rect(screen, AVATAR_PALETTE[int(pixel)], rect)
            pygame.draw.rect(screen, (34, 34, 38), rect, 1)

    screen.blit(font_sm.render("Palette", True, COLOR_MUTED), (415, 165))
    for index, rect in enumerate(PALETTE_RECTS):
        color = AVATAR_PALETTE[index] or (52, 52, 58)
        pygame.draw.rect(screen, color, rect)
        pygame.draw.rect(
            screen,
            COLOR_TEXT if index == state["avatar_color"] else COLOR_BORDER,
            rect,
            2 if index == state["avatar_color"] else 1,
        )
        if index == 0:
            pygame.draw.line(screen, (190, 90, 90), rect.topleft, rect.bottomright, 2)

    preview_rect = pygame.Rect(650, 105, 48, 48)
    pygame.draw.rect(screen, COLOR_CARD, preview_rect, border_radius=4)
    preview_rows = ["".join(row) for row in state["avatar_grid"]]
    preview = make_avatar_surface(preview_rows, 2)
    screen.blit(preview, preview.get_rect(center=preview_rect.center))
    screen.blit(font_sm.render("32 x 32", True, COLOR_MUTED), (650, 160))

    screen.blit(font_sm.render("Character description", True, COLOR_MUTED), (415, 225))
    pygame.draw.rect(screen, COLOR_CARD, PROMPT_RECT, border_radius=4)
    pygame.draw.rect(
        screen,
        COLOR_ACCENT if state["active_input"] == "avatar_prompt" else COLOR_BORDER,
        PROMPT_RECT,
        1,
        border_radius=4,
    )
    prompt = state["avatar_prompt"]
    visible_prompt = prompt[-48:] if len(prompt) > 48 else prompt
    screen.blit(font_sm.render(visible_prompt, True, COLOR_TEXT if prompt else COLOR_MUTED), (425, 276))

    _draw_button(screen, font_sm, GENERATE_RECT, "GENERATE WITH AI", COLOR_ACCENT)
    _draw_button(screen, font_sm, SAVE_RECT, "SAVE AVATAR", (34, 139, 94))
    _draw_button(screen, font_sm, BACK_RECT, "BACK", COLOR_BORDER)

    status = state.get("status_msg", "")
    screen.blit(font_sm.render(status[:52], True, COLOR_MUTED), (415, 480))
    pygame.display.flip()


def _draw_button(screen, font, rect, label, color):
    pygame.draw.rect(screen, color, rect, border_radius=4)
    text = font.render(label, True, COLOR_TEXT)
    screen.blit(text, text.get_rect(center=rect.center))