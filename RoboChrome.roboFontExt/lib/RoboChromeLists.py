from vanilla import List
from AppKit import NSBackspaceCharacter, NSDeleteCharacter, NSDeleteFunctionKey

# After <https://github.com/robotools/vanilla/issues/50>


class DeletableList(List):

    def __init__(self, *args, **kwargs):
        self._deleteCallback = None
        if "deleteCallback" in kwargs:
            self._deleteCallback = kwargs["deleteCallback"]
            del kwargs["deleteCallback"]
        super(DeletableList, self).__init__(*args, **kwargs)

    def _keyDown(self, event):
        if self._deleteCallback is not None:
            characters = event.characters()
            deleteCharacters = [
                NSBackspaceCharacter,
                NSDeleteFunctionKey,
                NSDeleteCharacter,
                chr(0x7F),
            ]
            if characters in deleteCharacters:
                self._deleteCallback(self)
                return True
        super(DeletableList, self)._keyDown(event)
