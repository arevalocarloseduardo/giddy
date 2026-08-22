import re

from core.utils.music_queries import fold_music_query


IMAGE_ACTION = re.compile(
    r"\b(?:dame|mostra(?:me)?|muestra(?:me)?|pon(?:e(?:me)?)?|"
    r"crea(?:me)?|crear|crees|genera(?:me)?|generar|generes|"
    r"disena(?:me)?|disenar|disenes|dibuja(?:me)?|dibujar|dibujes|"
    r"hace(?:me)?|hacer|hagas)\b",
    re.IGNORECASE,
)
IMAGE_NOUN = re.compile(
    r"\b(?:imagen|foto|ilustracion|dibujo|flyer|afiche|poster)\b",
    re.IGNORECASE,
)


def _image_parts(text: str):
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    folded = fold_music_query(value)
    action = IMAGE_ACTION.search(folded)
    noun = IMAGE_NOUN.search(folded)
    if not action or not noun or action.start() > noun.start():
        return None
    return value, folded, noun


def is_image_creation_request(text: str) -> bool:
    return _image_parts(text) is not None


def _aspect_ratio(folded: str) -> str:
    if re.search(r"\b(vertical|retrato|historia|story|9[: ]16)\b", folded):
        return "portrait"
    if re.search(
        r"\b(horizontal|apaisad[ao]|banner|panoramica|16[: ]9)\b", folded
    ):
        return "landscape"
    return "square"


def parse_image_description(text: str):
    value = re.sub(r"\s+", " ", str(text or "")).strip(" .,:;!?\u00bf\u00a1")
    folded = fold_music_query(value)
    aspect_ratio = _aspect_ratio(folded)
    prompt = re.sub(
        r"^(?:(?:en\s+formato\s+)?(?:vertical|horizontal|apaisad[ao]|"
        r"panoramica|cuadrad[ao]))(?:\s+(?:de|con))?\s+",
        "",
        value,
        count=1,
        flags=re.IGNORECASE,
    ).strip(" .,:;!?\u00bf\u00a1")
    if folded.startswith("que muestre "):
        prompt = prompt[len("que muestre ") :].strip()
    if len(prompt) < 2:
        return None
    return prompt, aspect_ratio


def parse_image_request(text: str):
    parts = _image_parts(text)
    if not parts:
        return None
    value, _folded, noun = parts
    prompt = value[noun.end() :].strip()
    prompt = re.sub(
        r"^(?:de|con|que\s+muestre|mostrando)\s+",
        "",
        prompt,
        count=1,
        flags=re.IGNORECASE,
    ).strip(" .,:;!?\u00bf\u00a1")
    if len(prompt) < 2:
        return None
    return parse_image_description(prompt)
