import pytest

from pitwall.replay.colours import ink_on


@pytest.mark.parametrize(
    ("colour", "ink"),
    [
        ("FFFFFF", "black"),
        ("000000", "white"),
        ("E80020", "white"),  # Ferrari red
        ("FF8000", "black"),  # McLaren papaya
        ("FF87BC", "black"),  # Alpine pink: a luma rule picked white here
        ("229971", "black"),  # Aston Martin green: so did it here
        ("6692FF", "black"),  # RB blue: and here
        ("3671C6", "white"),  # Red Bull blue
        ("abcdef", "black"),  # lower case is fine
    ],
)
def test_ink_has_the_better_contrast(colour: str, ink: str) -> None:
    assert ink_on(colour) == ink


@pytest.mark.parametrize("colour", ["#FFFFFF", "FFF", "GGGGGG", "", "FFFFFF0"])
def test_ink_rejects_anything_but_six_hex_digits(colour: str) -> None:
    with pytest.raises(ValueError, match="expected 6 hex digits"):
        ink_on(colour)
