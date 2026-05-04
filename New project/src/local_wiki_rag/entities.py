from __future__ import annotations

PEOPLE = [
    "Albert Einstein",
    "Marie Curie",
    "Leonardo da Vinci",
    "William Shakespeare",
    "Ada Lovelace",
    "Nikola Tesla",
    "Lionel Messi",
    "Cristiano Ronaldo",
    "Taylor Swift",
    "Frida Kahlo",
    "Isaac Newton",
    "Galileo Galilei",
    "Pablo Picasso",
    "Mahatma Gandhi",
    "Nelson Mandela",
    "Cleopatra",
    "Wolfgang Amadeus Mozart",
    "Ludwig van Beethoven",
    "Michael Jackson",
    "Stephen Hawking",
]

PLACES = [
    "Eiffel Tower",
    "Great Wall of China",
    "Taj Mahal",
    "Grand Canyon",
    "Machu Picchu",
    "Colosseum",
    "Hagia Sophia",
    "Statue of Liberty",
    "Pyramids of Giza",
    "Mount Everest",
    "Big Ben",
    "Sydney Opera House",
    "Golden Gate Bridge",
    "Stonehenge",
    "Niagara Falls",
    "Christ the Redeemer",
    "Petra",
    "Angkor Wat",
    "Buckingham Palace",
    "Mount Fuji",
]


def all_entities() -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    entries.extend((name, "person") for name in PEOPLE)
    entries.extend((name, "place") for name in PLACES)
    return entries
