"""
Card type system — 5 distinct card types per product category.

Scene prompts generate EMPTY BACKGROUNDS only.
Product is NEVER mentioned in scene prompts.
Colors come from product image analysis (color_extractor.py).

Types:
  hero      — product as sole subject, clean background, minimal text
  lifestyle — product in atmospheric context, large scene, minimal overlay
  features  — infographic with icons and benefits, Pillow gradient (no AI)
  editorial — dramatic typographic treatment, art-directed scene
  detail    — material/craft focus, close-up prompt, minimal text
"""

_MP = {"wb": "Wildberries", "ozon": "Ozon"}

_CAT_CONTEXT = {
    "clothing":    "fashion editorial, soft textile atmosphere, Scandinavian interior",
    "electronics": "clean minimal dark tech surface, modern geometry",
    "beauty":      "soft marble or glass surface, spa atmosphere, natural light",
    "home":        "warm interior, natural wood and linen textures, cozy light",
    "accessories": "luxury display surface, velvet or leather hint",
    "other":       "clean commercial studio environment",
}

# Category → ordered list of 5 card types
TYPES_BY_CATEGORY = {
    "clothing":    ["hero", "lifestyle", "features", "editorial", "detail"],
    "electronics": ["hero", "features", "lifestyle", "editorial", "detail"],
    "beauty":      ["hero", "lifestyle", "features", "detail",    "editorial"],
    "home":        ["hero", "lifestyle", "features", "detail",    "editorial"],
    "accessories": ["hero", "editorial", "lifestyle", "features", "detail"],
    "other":       ["hero", "lifestyle", "features", "editorial", "detail"],
}

TYPE_LABELS_RU = {
    "hero":      "Главный кадр",
    "lifestyle": "Лайфстайл",
    "features":  "Преимущества",
    "editorial": "Редакция",
    "detail":    "Детали",
}

# (canvas_w, canvas_h, scene_h, blend_px)
CANVAS_LAYOUT = {
    "hero":      (800, 1000, 740, 55),
    "lifestyle": (800, 1000, 850, 40),
    "features":  (800, 1000, 380, 25),
    "editorial": (800, 1000, 650, 60),
    "detail":    (800, 1000, 800, 50),
}

# Scene prompts: EMPTY BACKGROUNDS only, no product
_SCENE_PROMPTS = {
    "hero": (
        "Professional product photography studio backdrop. "
        "{color_mood} color palette, clean gradient surface, "
        "soft directional lighting from upper-left, subtle floor reflection, smooth vignette. "
        "Commercial photography background, 4:5 portrait format. "
        "EMPTY SCENE — absolutely no product, no objects, no people, no text, no logos."
    ),
    "lifestyle": (
        "Modern minimal lifestyle interior, {color_mood} palette. "
        "Natural soft light through window, clean Scandinavian-style room, "
        "editorial fashion atmosphere, warm and inviting. "
        "4:5 portrait format. "
        "EMPTY SCENE — no product, no clothing, no people, no mannequin, no objects."
    ),
    "features": None,  # Pillow gradient only — no AI generation
    "editorial": (
        "High-end editorial photography backdrop, {color_mood} dramatic lighting. "
        "Luxury magazine aesthetic, textured gradient, artistic geometric shadow play. "
        "Premium brand visual identity background, 4:5 portrait format. "
        "EMPTY SCENE — no product, no text, no logos, no people."
    ),
    "detail": (
        "Macro photography background, shallow depth of field, {color_mood} neutral tones. "
        "Premium material surface texture, soft bokeh, artisan craftsmanship aesthetic. "
        "Close-up atmospheric scene, 4:5 portrait format. "
        "EMPTY SCENE — no product, no text, no people."
    ),
}


def get_card_types(category: str) -> list[str]:
    return TYPES_BY_CATEGORY.get(category, TYPES_BY_CATEGORY["other"])


def build_scene_prompt(
    card_type:   str,
    color_mood:  str,
    marketplace: str = "wb",
    category:    str = "other",
) -> str:
    """
    Build scene-only prompt. Product is NOT referenced.
    color_mood comes from product image analysis, not AI concept.
    """
    template = _SCENE_PROMPTS.get(card_type)
    if not template:
        return ""

    hint = _CAT_CONTEXT.get(category, _CAT_CONTEXT["other"])
    base = template.format(color_mood=color_mood)
    return f"{base} Style: {hint}."
