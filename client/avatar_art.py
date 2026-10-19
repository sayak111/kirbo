import pygame

from lib.avatar import AVATAR_PALETTE, AVATAR_SIZE, validate_avatar


def make_avatar_surface(rows, scale=2):
    rows = validate_avatar(rows)
    sprite = pygame.Surface((AVATAR_SIZE, AVATAR_SIZE), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, pixel in enumerate(row):
            color = AVATAR_PALETTE[int(pixel)]
            if color is not None:
                sprite.set_at((x, y), color)
    return pygame.transform.scale(sprite, (AVATAR_SIZE * scale, AVATAR_SIZE * scale))