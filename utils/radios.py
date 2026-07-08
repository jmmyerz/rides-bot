

# I guess this will be the source of truth for call numbers for now...
CALL_NUMBERS = {
    "Jessica Platt-Felt": "337",
    "Ty Henderson": "339",
    "Anthony Turner": "338",
    "Mallory Monroe": "349",
    "Jordan Myers": "322",
    "Kasie Wegener": "333",
    "Kyra Scott": "323",
    "Michael Windwalker": "327",
    "Owen Jensen": "340",
    "Sid Green": "331",
    "Kaylyn Kingston": "334",
    "Alex Altamirano": "316",
    "Trinity Metz": "320",
    "Samantha Forester": "361",
    "Brewer Monroe": "318",
    "Chase Oesch": "315",
    "Lindy Coy": "319",
    "Avery Black": "332",
    "Anaïs Monroe": "336",
    "David Landward": "326",
    "Sean Porter": "335",
    "Kaston Charlton": "317",
}

def insert_call_number(name: str) -> str:
    """
    name: str
        The name of the person to look up in the call number dictionary.

    Returns
    -------
    str
        `name (call_number)` unless the call number wasn't found, then returns the input unchanged.
    """

    call_number = CALL_NUMBERS.get(name)
    if call_number is not None:
        return f"{name} ({call_number})"
    return name