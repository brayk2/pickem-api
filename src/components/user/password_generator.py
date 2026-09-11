# List of 25 adjectives
import random

_adjectives = [
    "Luminous",
    "Silent",
    "Fierce",
    "Clever",
    "Bold",
    "Swift",
    "Mystic",
    "Noble",
    "Vivid",
    "Brave",
    "Gentle",
    "Daring",
    "Serene",
    "Radiant",
    "Sage",
    "Wild",
    "Mighty",
    "Fearless",
    "Ancient",
    "Graceful",
    "Humble",
    "Majestic",
    "Ethereal",
    "Vigilant",
    "Whimsical",
]

# List of 25 nouns
_nouns = [
    "Tiger",
    "River",
    "Phoenix",
    "Eagle",
    "Shadow",
    "Thunder",
    "Falcon",
    "Willow",
    "Mountain",
    "Horizon",
    "Ocean",
    "Dragon",
    "Wolf",
    "Star",
    "Blizzard",
    "Forest",
    "Lion",
    "Stream",
    "Meadow",
    "Voyage",
    "Sky",
    "Comet",
    "Canyon",
    "Tempest",
    "Echo",
]


def gen_pass():
    return f"{random.choice(_adjectives)}.{random.choice(_nouns)}{random.randint(1000, 9999)}"
