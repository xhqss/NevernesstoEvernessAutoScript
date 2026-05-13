from enum import Enum


class Labels(str, Enum):
    """Game UI element labels for Neverness to Everness."""
    # -- Auto / idle --
    auto_play = "auto_play"

    # -- Boss level --
    boss_lv_text = "boss_lv_text"

    # -- Box / frame overlays --
    box_all_esc_options = "box_all_esc_options"
    box_char_1 = "box_char_1"
    box_char_2 = "box_char_2"
    box_char_3 = "box_char_3"
    box_char_4 = "box_char_4"
    box_f1_activity_reward = "box_f1_activity_reward"
    box_skill = "box_skill"
    box_ultimate = "box_ultimate"

    # -- Character text labels --
    char_1_text = "char_1_text"
    char_2_text = "char_2_text"
    char_3_text = "char_3_text"
    char_4_text = "char_4_text"

    # -- Claim / rewards --
    claim_icon = "claim_icon"

    # -- Dialog --
    dialog_click = "dialog_click"
    dialog_history = "dialog_history"

    # -- ESC menu --
    esc_option = "esc_option"

    # -- F1 panel --
    f1_activity_mission = "f1_activity_mission"
    f1_activity_panel = "f1_activity_panel"
    f1_panel = "f1_panel"

    # -- F2 panel --
    f2_mission_panel = "f2_mission_panel"
    f2_panel = "f2_panel"

    # -- Fishing --
    fish_bait = "fish_bait"
    fish_start = "fish_start"
    fising_sucess = "fising_sucess"

    # -- Health / combat --
    health_bar_slash = "health_bar_slash"

    # -- Interaction --
    interactable = "interactable"

    # -- Character state --
    is_current_char = "is_current_char"

    # -- Launcher --
    launcher_start_game = "launcher_start_game"

    # -- Level --
    lv = "lv"

    # -- Mail --
    mail_panel = "mail_panel"

    # -- Map --
    map_location_card = "map_location_card"

    # -- Messages --
    message = "message"
    message_dialog = "message_dialog"

    # -- Mini map --
    mini_map_arrow = "mini_map_arrow"

    # -- Monthly card --
    monthly_card = "monthly_card"

    # -- Skip UI --
    skip_dialog = "skip_dialog"
    skip_quest_confirm = "skip_quest_confirm"

    # -- Stamina --
    stamina_icon = "stamina_icon"

    # -- Targeting --
    target = "target"

    # -- Teleport --
    teleport = "teleport"

    # -- Treasure / chest --
    treasure = "treasure"
