from enum import Enum, auto

class RoutineState(Enum):
    IDLE = auto()
    WORKING = auto()
    FUN = auto()
    BREAK = auto()

class AudioState(Enum):
    SILENT = auto()
    MUSIC = auto()

class UIState(Enum):
    REST = auto()
    SHOWING = auto()
    THINKING = auto()

class BuddyStateManager():
    def __init__(self):
        self.routine_state = RoutineState.IDLE
        self.audio_state = AudioState.SILENT
        self.ui_state = UIState.REST

    def get_current_state(self) -> str:

        if self.ui_state == UIState.THINKING or self.ui_state == UIState.SHOWING:
            return self.ui_state.name
        
        return f"{self.routine_state.name}_{self.audio_state.name}"
    