"""
Card type system — 5 distinct premium visual card types.

CORE RULE: NO text overlay on any card. Images are clean premium visuals only.
Product integrity: pixels NEVER modified. Only scale, position, shadow applied.

Types:
  hero      — clean studio product shot, full-canvas
  lifestyle — atmospheric interior scene, full-canvas
  social    — outdoor / real-world context, social media feel
  editorial — dramatic contrast, luxury editorial
  detail    — material / craft focus, macro atmosphere

Scene prompts v2:
  Explicitly describe the foreground surface where product will be placed.
  This makes compositing more natural — product looks placed, not pasted.
"""

_CAT_CONTEXT = {
    "clothing":    "fashion editorial, soft textile atmosphere, Scandinavian interior",
    "electronics": "clean minimal dark tech surface, modern geometry, cool blue-white ambient",
    "beauty":      "soft marble or glass surface, spa aesthetic, warm golden natural light",
    "home":        "warm interior, natural wood and linen textures, cozy afternoon light",
    "accessories": "luxury display surface, velvet or leather hint, jewellery store lighting",
    "other":       "clean commercial studio environment, neutral professional light",
}

# Category-specific foreground surface descriptions for realistic product placement
_CAT_SURFACE = {
    "clothing":    "flat light wooden surface or clean fabric fold in foreground",
    "electronics": "dark matte tech surface, subtle grid texture, in foreground center",
    "beauty":      "white marble or glass shelf surface in foreground, smooth and clean",
    "home":        "warm wood tabletop or linen surface in foreground",
    "accessories": "velvet display tray or leather surface in foreground center",
    "other":       "clean neutral matte surface in foreground center",
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

# Full-height canvas — no text panel
CANVAS_LAYOUT = {
    "hero":      (800, 1000, 1000, 0),
    "lifestyle": (800, 1000, 1000, 0),
    "social":    (800, 1000, 1000, 0),
    "editorial": (800, 1000, 1000, 0),
    "detail":    (800, 1000, 1000, 0),
}

# Scene prompts v2: include explicit foreground surface for product placement
# This is critical for realistic compositing — background must accommodate the product
_SCENE_PROMPTS = {
    "hero": (
        "Professional commercial product photography studio backdrop. "
        "{color_mood} color palette. "
        "Seamless gradient surface sweep, soft directional key light from upper-left, "
        "subtle fill light from right. "
        "{surface} with gentle contact shadow zone. "
        "Smooth vignette at edges. Empty center for product. "
        "Premium retail photography background, 4:5 portrait format. "
        "EMPTY SCENE — no product, no objects, no people, no text, no logos."
    ),
    "lifestyle": (
        "Atmospheric lifestyle interior scene. {color_mood} palette. "
        "Natural soft daylight through window, "
        "Scandinavian-Nordic room, editorial magazine aesthetic. "
        "{surface} in foreground with natural ambient light falling on it. "
        "Background: blurred interior elements, plants, textures. "
        "Clear empty space in center-foreground for product placement. "
        "4:5 portrait format, commercial quality. "
        "EMPTY SCENE — no product, no people, no mannequin."
    ),
    "social": (
        "Fresh lifestyle background for social media product photography. "
        "{color_mood} palette. "
        "Soft natural light, urban or garden context, Instagram aesthetic. "
        "{surface} in foreground, clean and well-lit. "
        "Bokeh background, contemporary social media visual style. "
        "Clear empty foreground zone for product. "
        "4:5 portrait format. "
        "EMPTY SCENE — no product, no people, no text."
    ),
    "editorial": (
        "High-end editorial photography backdrop. {color_mood} dramatic cinematic lighting. "
        "Luxury magazine aesthetic, deep textured gradient. "
        "Strong directional light with dramatic shadows. "
        "{surface} as base surface in foreground, catching the dramatic light. "
        "Dark moody atmosphere in background, premium brand aesthetic. "
        "Clear empty center for product placement. "
        "4:5 portrait format, fashion editorial quality. "
        "EMPTY SCENE — no product, no people, no logos."
    ),
    "detail": (
        "Premium macro product photography background. "
        "Shallow depth of field, {color_mood} neutral tones. "
        "{surface} as primary surface — texture visible up close. "
        "Artisan quality aesthetic, craftsmanship atmosphere. "
        "Soft bokeh background, gentle ambient light on surface. "
        "Product placement zone clearly lit in center. "
        "4:5 portrait format. "
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
    Build scene-only prompt with explicit surface description.
    Product is NOT referenced — composited separately.
    color_mood comes from product image analysis.
    """
    template = _SCENE_PROMPTS.get(card_type)
    if not template:
        return ""

    cat_hint = _CAT_CONTEXT.get(category, _CAT_CONTEXT["other"])
    surface   = _CAT_SURFACE.get(category, _CAT_SURFACE["other"])
    base      = template.format(color_mood=color_mood, surface=surface)
    return f"{base} Style: {cat_hint}."
