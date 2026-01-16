import random

ADJECTIVES = [
    "Silent", "Curious", "Hidden", "Lost", "Brave", "Witty", "Calm"
]

NOUNS = [
    "Fox", "Crow", "Leaf", "Wolf", "Tiger", "Owl", "River"
]


def generate_alias():
    return f"{random.choice(ADJECTIVES)}{random.choice(NOUNS)}{random.randint(100,999)}"
