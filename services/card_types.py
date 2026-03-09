"""
Card type system — 5 distinct card types per product category.

Each type has a specific purpose, scene composition, and typography treatment.
Types are ordered by category — electronics gets tech-appropriate types,
clothing gets fashion-appropriate types, etc.

Types:
  hero      — product as sole subject, clean background, minimal text
  lifestyle — product in atmospheric context, large scene, minimal overlay
  features  — infographic with icons and benefits, clean product shot
  editorial — dramatic typographic treatment, art-directed scene
  detail    — material/craft focus, close-up prompt, minimal text
"""

_MP  = {"wb": "Wildberries", "ozon": "Ozon"}

_CAT_DESC = {
    "clothing":    "fashion & clothing",
    "electronics": "consumer electronics",
    "beauty":      "beauty & personal care",
    "home":        "home goods & interior",
    "accessories": "accessories & lifestyle",
    "other":       "consumer goods",
}

_CAT_CONTEXT = {
    "clothing":    "a natural interior or outdoor lifestyle setting, real environment",
    "electronics": "a modern, clean tech environment with appropriate surfaces and context",
    "beauty":      "a beauty scene with natural light, soft textures, vanity or bathroom context",
    "home":        "a cozy interior home setting with warm natural light and natural materials",
    "accessories": "a styled setting with complementary lifestyle props and surfaces",
    "other":       "an appropriate, aspirational lifestyle environment for this product",
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


def get_card_types(category: str) -> list[str]:
    return TYPES_BY_CATEGORY.get(category, TYPES_BY_CATEGORY["other"])


def build_scene_prompt(card_type: str, concept: dict,
                       marketplace: str, category: str) -> str:
    """
    Build a card-type-specific scene generation prompt.
    FEATURES type returns None — it uses a Pillow background instead.
    """
    mp_name  = _MP.get(marketplace, marketplace)
    cat_desc = _CAT_DESC.get(category, "consumer goods")
    context  = _CAT_CONTEXT.get(category, "an appropriate lifestyle environment")

    name        = concept.get("name",        "")
    colors      = concept.get("colors",      "")
    composition = concept.get("composition", "")

    if card_type == "hero":
        return (
            f"Premium clean product photography. {mp_name} marketplace, {cat_desc}.\n\n"

            f"STYLE: Pure product presentation. Style reference: Apple product photography, "
            f"Muji catalog, high-end e-commerce. The product is everything — zero distractions.\n\n"

            f"LIGHTING: Perfect soft studio lighting. Balanced, shadow-controlled. "
            f"Product surfaces, textures, and materials are rendered beautifully. "
            f"Quality and craftsmanship are visible.\n\n"

            f"BACKGROUND: Very clean — near-white, soft light grey, or a subtle tonal gradient "
            f"inspired by the concept palette ({colors}). "
            f"Atmospheric but absolutely minimal. Nothing competes with the product.\n\n"

            f"CONCEPT MOOD: «{name}». {composition}. "
            f"Translate this into lighting quality and background atmosphere only — "
            f"not into props, decorative elements, or visual clutter.\n\n"

            f"COMPOSITION: Product centered and prominent. "
            f"Takes up 60–70% of frame height. "
            f"Generous, balanced negative space on all sides. No other elements.\n\n"

            f"PRODUCT REQUIREMENT: Render the product EXACTLY as it appears in the uploaded photo. "
            f"Shape, colors, branding, details — all preserved precisely. "
            f"Only background and lighting are yours to create.\n\n"

            f"ABSOLUTE RULES: No text. No letters. No numbers. No logos. No frames. No watermarks."
        )

    elif card_type == "lifestyle":
        return (
            f"Lifestyle product photography. {mp_name} marketplace, {cat_desc}.\n\n"

            f"STYLE: Aspirational lifestyle scene. The product lives naturally in its ideal world. "
            f"Concept: «{name}». Color palette: {colors}.\n\n"

            f"SCENE: {context}. {composition}. "
            f"The environment is beautiful, warm, and real — not a studio set. "
            f"It creates emotion: warmth, desire, comfort, aspiration.\n\n"

            f"LIGHTING: Natural or natural-feeling light. Warm, directional, flattering. "
            f"Product and scene share the same light — unified and coherent.\n\n"

            f"COMPOSITION: Product naturally placed — slightly off-center or interacting with its environment. "
            f"Supporting elements in soft focus. Scene fills the entire frame richly. "
            f"No empty or dead zones.\n\n"

            f"PRODUCT REQUIREMENT: Render the product EXACTLY as in the uploaded photo. "
            f"Only the surrounding world is generated.\n\n"

            f"ABSOLUTE RULES: No text. No letters. No numbers. No logos."
        )

    elif card_type == "editorial":
        return (
            f"Editorial product photography. {mp_name} marketplace, {cat_desc}.\n\n"

            f"STYLE: High-fashion editorial — the aesthetic of Vogue, W Magazine, Dazed. "
            f"Concept: «{name}». {composition}. "
            f"Art-directed, bold, with a distinct point of view. Color palette: {colors}.\n\n"

            f"LIGHTING: Dramatic, high-contrast. Lighting is itself a design element. "
            f"Strong shadows, precise highlights, intentional light placement.\n\n"

            f"ATMOSPHERE: Bold and considered. The background feels designed and intentional — "
            f"a strong color field, graphic shadow pattern, or architectural context. "
            f"Every element in the frame has a reason to be there.\n\n"

            f"COMPOSITION: Bold and asymmetric, or dramatically centered with strong visual tension. "
            f"Fill the entire frame with the editorial scene and its energy.\n\n"

            f"PRODUCT REQUIREMENT: Render the product EXACTLY as uploaded. "
            f"Only environment and lighting are generated by you.\n\n"

            f"ABSOLUTE RULES: No text. No letters. No numbers. No logos."
        )

    else:  # detail
        return (
            f"Close-up detail product photography. {mp_name} marketplace, {cat_desc}.\n\n"

            f"STYLE: Luxury material and craft photography — show the quality intimately. "
            f"Concept: «{name}». Colors: {colors}.\n\n"

            f"LIGHTING: Dramatic raking light or precision accent lighting that reveals "
            f"texture, material quality, surface finish, craftsmanship. "
            f"The light makes the material beautiful and tactile.\n\n"

            f"FOCUS: The most compelling visual detail of this product — "
            f"fabric texture, surface finish, construction detail, material quality. "
            f"Shallow depth of field is appropriate. {composition}\n\n"

            f"COMPOSITION: Close and intimate. Fill the frame with quality and craft. "
            f"The product's material tells the story.\n\n"

            f"PRODUCT REQUIREMENT: Focus on the detail and texture of the product as uploaded.\n\n"

            f"ABSOLUTE RULES: No text. No letters. No numbers. No logos."
        )
    # Note: "features" card type uses Pillow gradient background — no AI prompt needed
