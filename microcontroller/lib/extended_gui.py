from gui.widgets.label import Label
from gui.widgets.label import ALIGN_CENTER
from gui.widgets.label import ALIGN_LEFT
from gui.widgets.label import ALIGN_RIGHT

class PicoLabel(Label):
    def __init__(self, writer, text, x, y, width = -1, align = ALIGN_CENTER):
        text_width = writer.stringlen(text)
        if width <= 0 or width < text_width:
            width = text_width
        if align == ALIGN_CENTER:
            x = x + (width - text_width) // 2
        elif align == ALIGN_RIGHT:
            x = x + (width - text_width)
        super().__init__(writer, y, x, text)