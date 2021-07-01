class ExtraFeature:
    # __init__ need to have two arguments. The device will be passed when create an instance.
    def __init__(self, device) -> None:
        pass

    def original(self) -> None:
        # This function should assign original state to local object variable and return None.
        self.original_state = 1

    def current(self) -> None:
        # This function should assign current state to local object variable and return None.
        self.current_state = 2

    def is_changed(self) -> bool:
        # This function should compare original and current state and return True or False.

        if self.current_state != self.original_state:
            return True
        else:
            return False

    def diff(self) -> str:
        # This function should return a string that describes the differences between the original and current state.
        if self.current_state != self.original_state:
            return "\nThis is from Extended feature.\nThere is a difference between the original and current state.\n"
        else:
            return "The original and current state are same.\n"
