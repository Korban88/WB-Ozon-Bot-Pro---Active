from aiogram.fsm.state import State, StatesGroup


class Dialog(StatesGroup):
    """
    FSM states for the product content creation dialog.

    Flow:
      1. choose_marketplace  — WB or Ozon
      2. choose_category     — product category
      3. enter_title         — product name
      4. enter_benefits      — description & advantages
      5. upload_photo        — product photo → triggers AI text generation
      6. show_card           — text card ready, offer Visual Pack / Ad Copy Pack
      7. premium_visuals     — generating & showing 5 premium visual concepts
      8. ad_copy             — generating & showing ad copy pack
    """
    choose_marketplace = State()   # Step 1
    choose_category    = State()   # Step 2
    enter_title        = State()   # Step 3
    enter_benefits     = State()   # Step 4
    upload_photo       = State()   # Step 5
    generating         = State()   # Step 6: AI is working (intermediate)
    show_card          = State()   # Step 7: card ready
    premium_visuals    = State()   # Step 8: generating 5 premium visual concepts
    ad_copy            = State()   # Step 9: generating ad copy pack
