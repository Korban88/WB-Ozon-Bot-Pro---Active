from aiogram.fsm.state import State, StatesGroup


class Menu(StatesGroup):
    main = State()


class Analysis(StatesGroup):
    wait_url           = State()
    analyzing          = State()
    wait_manual_title  = State()   # ручной ввод когда парсер не смог
    wait_manual_desc   = State()   # ручной ввод описания/характеристик


class Visuals(StatesGroup):
    wait_category = State()
    wait_title    = State()
    wait_benefits = State()
    wait_photo    = State()
    generating    = State()


class Copy(StatesGroup):
    wait_title    = State()
    wait_benefits = State()
    generating    = State()


class Infographic(StatesGroup):
    wait_title    = State()
    wait_benefits = State()
    generating    = State()


class UGC(StatesGroup):
    wait_title    = State()
    wait_benefits = State()
    generating    = State()
