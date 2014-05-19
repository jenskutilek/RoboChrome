from flat.command import *
from fontTools.pens.basePen import BasePen

class FlatPen(BasePen):
    def __init__(self, f):
        BasePen.__init__(self, None)
        self.glyphSet = f
        self.path = []
        self.__currentPoint = None
    
    def _moveTo(self, pt):
        self.path.append(moveto(pt[0], pt[1]))
    
    def _lineTo(self, pt):
        self.path.append(lineto(pt[0], pt[1]))
    
    def _curveToOne(self, pt1, pt2, pt3):
        self.path.append(curveto(pt1[0], pt1[1],
            pt2[0], pt2[1],
            pt3[0], pt3[1]))
    
    def _closePath(self):
        self.path.append(closepath())
    
    def _endPath(self):
        self.path.append(closepath())
    
    def addComponent(self, baseName, transformation):
        glyph = self.glyphSet[baseName]
        tPen = TransformPen(self, transformation)
        glyph.draw(tPen)