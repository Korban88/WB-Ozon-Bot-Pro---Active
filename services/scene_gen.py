"""
Scene generator: gpt-image-1 /edits with product photo.

Each concept index maps to a distinct photographic/advertising creative brief.
The prompt IS the art director — generic prompts produce generic results.

Concept styles:
  1 — Luxury Dark       (Chanel / YSL advertising photography)
  2 — Editorial Bold    (Vogue / W Magazine editorial)
  3 — Lifestyle Hero    (Apple / Nike premium lifestyle)
  4 — Natural Artisan   (Kinfolk / artisan brand photography)
  5 — Minimal Pure      (Muji / Bang & Olufsen minimalism)

Text is added separately by card_renderer.overlay_text_concept().
"""

import base64
import io
import time

import aiohttp

import config
from logger_setup import log, log_ai_call

_EDITS_URL = "https://api.openai.com/v1/images/edits"
_TIMEOUT   = 120

_MP = {"wb": "Wildberries", "ozon": "Ozon"}
_CAT = {
    "clothing":    "fashion & clothing",
    "electronics": "consumer electronics",
    "home":        "home goods & interior",
    "beauty":      "beauty & personal care",
    "accessories": "accessories & lifestyle",
    "other":       "consumer goods",
}


def _brief_luxury_dark(mp, cat, colors, name, composition) -> str:
    return (
        f"Luxury dark commercial product photography. {mp} marketplace, {cat}.\n\n"

        f"CREATIVE DIRECTION: High-fashion dark luxury — the aesthetic of Chanel, YSL, or Hermès "
        f"advertising photography. Deep, atmospheric, cinematic darkness. "
        f"The product commands total attention through the power of contrast and focused light. "
        f"Concept: «{name}». {composition}\n\n"

        f"LIGHTING SETUP: Single narrow key light from upper-left at 45°, creating dramatic chiaroscuro. "
        f"Deep, rich shadows on the right side. Precise, focused light sculpts the product surface. "
        f"A very soft, minimal fill light from below-right preserves product detail without killing the drama. "
        f"Product materials — whether fabric, metal, glass, or plastic — should look luxurious and tactile.\n\n"

        f"COLOR & ATMOSPHERE: Palette reference — {colors}. "
        f"The background is very dark, almost black, but NOT a flat black — "
        f"it has atmospheric depth, subtle texture, a sense of expensive space. "
        f"Color temperature: cool to neutral. Moodboard: deep luxury, concentrated light, premium material.\n\n"

        f"COMPOSITION: Product as the absolute focal point, upper-center of the frame. "
        f"Occupying approximately 55–65% of frame height. "
        f"Elevated slightly — on an implied surface or floating in dramatic space. "
        f"Generous negative space on both sides. Fill the entire frame with the atmospheric scene.\n\n"

        f"PRODUCT REQUIREMENT: Render the product EXACTLY as it appears in the uploaded photo. "
        f"Do not alter, idealize, or redesign the product in any way. "
        f"Only the environment, lighting, and atmospheric context are created by you. "
        f"The product's shape, color, branding, and details must be preserved precisely.\n\n"

        f"ABSOLUTE RULES: No text of any kind. No letters. No numbers. No logos. "
        f"No watermarks. No borders. No frames."
    )


def _brief_editorial(mp, cat, colors, name, composition) -> str:
    return (
        f"Bold editorial product photography. {mp} marketplace, {cat}.\n\n"

        f"CREATIVE DIRECTION: High-fashion editorial photography — the aesthetic of Vogue, W Magazine, or i-D. "
        f"Bold, graphic, unexpected. The product is part of a strong visual statement. "
        f"There is a point of view here — an art director made deliberate choices. "
        f"Concept: «{name}». {composition}\n\n"

        f"LIGHTING SETUP: Strong, high-contrast directional lighting. "
        f"Bold shadows that become design elements. The lighting is a creative tool, not just illumination. "
        f"May use harsh side lighting or dramatic overhead lighting to create graphic shadow patterns. "
        f"The contrast ratio is high — this is an intentional editorial choice.\n\n"

        f"COLOR & ATMOSPHERE: Palette reference — {colors}. "
        f"Color feels deliberate and art-directed. "
        f"Consider: a dominant color field, strong color blocking, or stark color contrast. "
        f"The background should feel designed, not neutral.\n\n"

        f"COMPOSITION: Strong and asymmetric. The product is positioned with intention — "
        f"it may be off-center, may have generous negative space on one strong side. "
        f"Visual tension and resolution are present. "
        f"The composition should feel like an art director chose it. Fill the entire frame with scene.\n\n"

        f"PRODUCT REQUIREMENT: Render the product EXACTLY as it appears in the uploaded photo. "
        f"Only the environment, lighting, and staging are created by you. "
        f"Product appearance, shape, and details must be preserved precisely.\n\n"

        f"ABSOLUTE RULES: No text of any kind. No letters. No numbers. No logos. "
        f"No watermarks. No frames. No borders."
    )


def _brief_lifestyle_hero(mp, cat, colors, name, composition) -> str:
    return (
        f"Premium aspirational lifestyle product photography. {mp} marketplace, {cat}.\n\n"

        f"CREATIVE DIRECTION: Aspirational premium lifestyle — the warmth and confidence of "
        f"top consumer brand photography (Apple, Nike, premium beauty brands). "
        f"The product is perfectly at home in its ideal world. Beautiful, accessible, desirable. "
        f"Concept: «{name}». {composition}\n\n"

        f"LIGHTING SETUP: Warm, natural-feeling three-point studio lighting. "
        f"Soft main light from upper-front-left. "
        f"Product surfaces look their absolute best — materials glow with quality. "
        f"No harsh shadows, but not flat either. "
        f"Dimensionality, depth, and warmth are the qualities of the light.\n\n"

        f"COLOR & ATMOSPHERE: Palette reference — {colors}. "
        f"Warm, inviting, aspirational. "
        f"Background: a harmonious mid-tone or soft gradient that complements the product beautifully. "
        f"Environmental hints or soft bokeh lifestyle context in the background, subtle.\n\n"

        f"COMPOSITION: Product as a confident hero. "
        f"Upper-center position, large in frame — approximately 65% of frame height. "
        f"Balanced, welcoming composition with lifestyle context. "
        f"Fill the entire frame with the beautiful scene and its environment.\n\n"

        f"PRODUCT REQUIREMENT: Render the product EXACTLY as it appears in the uploaded photo. "
        f"Only the environment, lighting, and lifestyle context are created by you. "
        f"Product must be rendered with perfect fidelity.\n\n"

        f"ABSOLUTE RULES: No text of any kind. No letters. No numbers. No logos. "
        f"No watermarks. No frames. No borders."
    )


def _brief_natural_artisan(mp, cat, colors, name, composition) -> str:
    return (
        f"Artisan lifestyle product photography. {mp} marketplace, {cat}.\n\n"

        f"CREATIVE DIRECTION: Warm, natural, handcrafted aesthetic — "
        f"the visual language of Kinfolk magazine and premium artisan brand photography. "
        f"The product exists in a world of natural materials, warmth, and genuine beauty. "
        f"Not polished advertising — crafted, real, tactile. "
        f"Concept: «{name}». {composition}\n\n"

        f"LIGHTING SETUP: Natural window light. Soft, directional, warm. "
        f"Morning or golden hour quality — the kind of light that makes things look beautiful naturally. "
        f"Gentle shadows that feel authentic, not artificial. "
        f"Warm color temperature throughout the scene.\n\n"

        f"COLOR & ATMOSPHERE: Palette reference — {colors}. "
        f"Natural materials as environmental elements: linen, wood, stone, ceramic, unbleached cotton, "
        f"hand-thrown pottery, dried botanicals — use what is appropriate for the product category. "
        f"The background should feel genuinely natural and tactile.\n\n"

        f"COMPOSITION: Product nestled naturally in an artisan setting. "
        f"Supporting natural elements in soft focus around it — they add context without competing. "
        f"The product is clearly the hero but belongs to the scene. "
        f"Fill the entire frame with the warm, natural world of the scene.\n\n"

        f"PRODUCT REQUIREMENT: Render the product EXACTLY as it appears in the uploaded photo. "
        f"Only the environment and natural styling around it are created by you.\n\n"

        f"ABSOLUTE RULES: No text of any kind. No letters. No numbers. No logos. No watermarks."
    )


def _brief_minimal_pure(mp, cat, colors, name, composition) -> str:
    return (
        f"Minimalist pure product photography. {mp} marketplace, {cat}.\n\n"

        f"CREATIVE DIRECTION: Pure Japanese minimalism — the visual discipline of Muji, "
        f"Dieter Rams industrial design photography, or Bang & Olufsen product imagery. "
        f"Almost nothing. The product is everything. White space is the most expensive element. "
        f"Concept: «{name}». {composition}\n\n"

        f"LIGHTING SETUP: Perfect, even, very clean studio lighting. "
        f"Either completely shadowless or with a single very soft shadow. "
        f"The product is beautifully illuminated with absolute clarity. "
        f"Cool to neutral light temperature. No warmth, no drama — just precision.\n\n"

        f"COLOR & ATMOSPHERE: Palette reference — {colors}. Extremely restrained. "
        f"Background: near-white, very light grey, or the very lightest possible tone. "
        f"Nothing in the frame competes with the product. Silence is the statement.\n\n"

        f"COMPOSITION: Product perfectly centered, large, with extreme breathing room on all sides. "
        f"Absolutely nothing else in the frame — no props, no context, no environmental elements. "
        f"The product floats in pure, silent space. "
        f"Fill the entire frame with this perfect emptiness and the product within it.\n\n"

        f"PRODUCT REQUIREMENT: Render the product EXACTLY as it appears in the uploaded photo. "
        f"Absolutely nothing else is added. The product floats in pure space.\n\n"

        f"ABSOLUTE RULES: No text. No letters. No numbers. No logos. No watermarks. "
        f"No props whatsoever. No frames. No borders. Pure simplicity only."
    )


_BRIEFS = {
    1: _brief_luxury_dark,
    2: _brief_editorial,
    3: _brief_lifestyle_hero,
    4: _brief_natural_artisan,
    5: _brief_minimal_pure,
}


def _build_scene_prompt(concept: dict, marketplace: str, category: str,
                        concept_index: int = 1) -> str:
    mp  = _MP.get(marketplace, marketplace)
    cat = _CAT.get(category, category)

    name        = concept.get("name",        "")
    colors      = concept.get("colors",      "")
    composition = concept.get("composition", "")

    # Cycle through briefs 1-5, map concept index to style
    style_idx = (concept_index - 1) % 5 + 1
    brief_fn  = _BRIEFS.get(style_idx, _brief_lifestyle_hero)

    return brief_fn(mp, cat, colors, name, composition)


async def generate_scene(
    concept:       dict,
    product_bytes: bytes,
    marketplace:   str,
    category:      str,
    user_id:       int,
    username:      str | None,
    concept_index: int = 1,
) -> bytes | None:
    """
    Generate a complete product card scene via gpt-image-1 /edits.
    Product photo is passed as input — integrated naturally into a concept-specific scene.
    Returns PNG bytes or None on failure/unavailable.
    """
    if not config.OPENAI_API_KEY:
        return None

    prompt  = _build_scene_prompt(concept, marketplace, category, concept_index)
    service = f"openai_scene/concept_{concept_index}"
    start   = time.monotonic()

    try:
        form = aiohttp.FormData()
        form.add_field("model",  config.OPENAI_IMAGE_MODEL)
        form.add_field("prompt", prompt)
        form.add_field("n",      "1")
        form.add_field("size",   "1024x1024")
        form.add_field(
            "image",
            io.BytesIO(product_bytes),
            filename     = "product.png",
            content_type = "image/png",
        )

        headers = {"Authorization": f"Bearer {config.OPENAI_API_KEY}"}
        timeout = aiohttp.ClientTimeout(total=_TIMEOUT)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(_EDITS_URL, headers=headers, data=form) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise RuntimeError(f"OpenAI HTTP {resp.status}: {body[:300]}")
                data = await resp.json()

        item = data["data"][0]
        if "b64_json" in item:
            image_bytes = base64.b64decode(item["b64_json"])
        elif "url" in item:
            async with aiohttp.ClientSession() as session:
                async with session.get(item["url"]) as r:
                    image_bytes = await r.read()
        else:
            raise RuntimeError(f"Unexpected OpenAI response keys: {list(item.keys())}")

        elapsed = int((time.monotonic() - start) * 1000)
        log_ai_call(user_id, username, service, success=True, duration_ms=elapsed)
        log.info("Scene generated — concept %d style %d (%dms)",
                 concept_index, (concept_index - 1) % 5 + 1, elapsed)
        return image_bytes

    except Exception as exc:
        elapsed = int((time.monotonic() - start) * 1000)
        log_ai_call(user_id, username, service, success=False,
                    duration_ms=elapsed, error=str(exc))
        log.warning("Scene generation failed for concept %d: %s", concept_index, exc)
        return None
