"""
Card type system — 5 distinct premium visual card types.

CORE RULE: NO text overlay on any card. Images are clean premium visuals only.
Text (copy, headlines, features) is delivered separately as Ad Copy Pack.

Product integrity:
  - Product pixels are NEVER modified.
  - Only scale, position, and shadow are applied.

Types:
  hero      — clean studio product shot, full-canvas
  lifestyle — atmospheric interior scene, full-canvas
  social    — outdoor / real-world context, social media feel
  editorial — dramatic contrast, luxury editorial
  detail    — material / craft focus, macro atmosphere
"""

_MP = {"wb": "Wildberries", "ozon": "Ozon"}

_CAT_CONTEXT = {
    "clothing":    "fashion editorial, soft textile atmosphere, Scandinavian interior",
    "electronics": "clean minimal dark tech surface, modern geometry, blue-tinted ambient light",
    "beauty":      "soft marble or glass surface, spa atmosphere, warm golden natural light",
    "home":        "warm interior, natural wood and linen textures, cozy afternoon light",
    "accessories": "luxury display surface, velvet or leather hint, jewellery store lighting",
    "other":       "clean commercial studio environment, neutral professional light",
}

# Category → ordered list of 5 card types
TYPES_BY_CATEGORY = {
    "clothing":    ["hero", "lifestyle", "social",    "editorial", "detail"],
    "electronics": ["hero", "editorial", "lifestyle", "social",    "detail"],
    "beauty":      ["hero", "lifestyle", "detail",    "editorial", "social"],
    "home":        ["hero", "lifestyle", "social",    "detail",    "editorial"],
    "accessories": ["hero", "editorial", "lifestyle", "detail",    "social"],
    "other":       ["hero", "lifestyle", "social",    "editorial", "detail"],
}

TYPE_LABELS_RU = {
    "hero":      "Главный кадр",
    "lifestyle": "Лайфстайл",
    "social":    "Соцсети",
    "editorial": "Редакция",
    "detail":    "Детали",
}

# Full-height canvas — no text panel, product fills the scene
# (canvas_w, canvas_h, scene_h, blend_px)
CANVAS_LAYOUT = {
    "hero":      (800, 1000, 1000, 0),
    "lifestyle": (800, 1000, 1000, 0),
    "social":    (800, 1000, 1000, 0),
    "editorial": (800, 1000, 1000, 0),
    "detail":    (800, 1000, 1000, 0),
}

# Scene prompts: EMPTY BACKGROUNDS only, no product ever
_SCENE_PROMPTS = {
    "hero": (
        "Professional commercial product photography studio backdrop. "
        "{color_mood} color palette. "
        "Seamless gradient surface sweep, soft directional key light from upper-left, "
        "subtle fill light from right, gentle floor reflection, smooth vignette at edges. "
        "Premium retail photography background, 4:5 portrait format, high-end quality. "
        "EMPTY SCENE — absolutely no product, no objects, no people, no text, no logos, no props."
    ),
    "lifestyle": (
        "Modern minimal lifestyle interior scene. {color_mood} palette. "
        "Natural soft daylight through floor-to-ceiling window, "
        "clean Scandinavian-Nordic room, editorial magazine atmosphere, "
        "warm and inviting ambient. Neutral empty surface in foreground. "
        "4:5 portrait format, commercial product photography quality. "
        "EMPTY SCENE — no product, no clothing, no people, no mannequin, no objects."
    ),
    "social": (
        "Fresh outdoor lifestyle background for social media product photography. "
        "{color_mood} palette. "
        "Soft natural light, urban or garden context, Instagram-worthy aesthetic, "
        "clean depth of field with soft bokeh background. "
        "Empty foreground surface for product placement. "
        "4:5 portrait format, contemporary social media visual style. "
        "EMPTY SCENE — no product, no people, no text, no props."
    ),
    "editorial": (
        "High-end editorial photography backdrop. {color_mood} dramatic cinematic lighting. "
        "Luxury magazine aesthetic, deep textured gradient, "
        "artistic geometric shadow play, premium brand visual identity background. "
        "Strong directional light creating mood and depth. "
        "4:5 portrait format, fashion week editorial quality. "
        "EMPTY SCENE — no product, no text, no logos, no people."
    ),
    "detail": (
        "Premium macro product photography background. "
        "Shallow depth of field, {color_mood} neutral tones. "
        "Artisan material surface texture — marble, velvet, linen, or glass. "
        "Soft bokeh, craftsmanship and quality aesthetic, "
        "close-up atmospheric scene. 4:5 portrait format. "
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
    return f"{base} Style reference: {hint}."
