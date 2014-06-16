import colorfont
reload(colorfont)
from colorfont import ColorFont, ColorGlyph

import pydoc
from mojo.UI import HelpWindow

doc = pydoc.HTMLDoc()
html = doc.document(ColorFont)
HelpWindow(htmlString=html)

#html = doc.document(ColorGlyph)
#HelpWindow(htmlString=html)