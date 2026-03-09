from aiogram.fsm.state import State, StatesGroup


class Dialog(StatesGroup):
    """
    FSM states for the product card creation dialog.
    Each state = one step where the bot is waiting for user input.
    """
    choose_marketplace = State()   # Step 1: WB or Ozon
    choose_category    = State()   # Step 2: product category
    enter_title        = State()   # Step 3: product name
    enter_benefits     = State()   # Step 4: product description & advantages
    upload_photo       = State()   # Step 5: product photo
    generating         = State()   # Step 6: AI is working (intermediate)
    show_card          = State()   # Step 7: card ready, user sees result
    design_concepts    = State()   # Step 8: showing 5 text design concepts
    visual_concepts    = State()   # Step 9: generating & showing 5 images
