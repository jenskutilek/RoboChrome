# SVG pen implementation (C) 2012 by Andreas Eigendorf

from fontTools.pens.basePen import BasePen

class SVGpen(BasePen):
	def __init__(self, glyphSet):
		BasePen.__init__(self, glyphSet)
		self.d = u''

	def _moveTo(self, (x,y)):
		self.d += u'm%s %s' % (x,y)

	def _lineTo(self, (x,y)):
		self.d += u'l%s %s' % (x,y)

	def _curveToOne(self, (x1,y1), (x2,y2), (x3,y3)):
		self.d += u'c%d %d %d %d %d %d' % (int(round(x1)), int(round(y1)),
		                                   int(round(x2)), int(round(y2)),
		                                   int(round(x3)), int(round(y3)))

	def _closePath(self):
		self.d += u'z'

