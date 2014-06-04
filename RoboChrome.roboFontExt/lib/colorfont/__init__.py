from types import ListType
import numpy
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import Glyph
from math import ceil
from tables.C_P_A_L_ import table_C_P_A_L_, Color
from tables.C_O_L_R_ import table_C_O_L_R_, LayerRecord
from tables._s_b_i_x import table__s_b_i_x
from tables.sbixBitmapSet import BitmapSet
from tables.sbixBitmap import Bitmap
from tables.S_V_G_ import table_S_V_G_

# for png generation
from flat import document, shape, rgba
from flatPen import FlatPen

# for svg generation
from svgPen import SVGpen

from defconAppKit.windows.progressWindow import ProgressWindow


class ColorFont(object):
    def __init__(self, rfont=None):
        self.libkey = "com.fontfont.colorfont"
        self.rfont = rfont
        self._glyphs = {}
        self.palettes = [{}]
        self.color = "#000000FF"
        self.colorbg = "#FFFFFFFF"
        self.bitmap_sizes_default = [20, 32, 40, 72, 96, 128, 256, 512, 1024]
        self.bitmap_sizes = self.bitmap_sizes_default
        # FIXME hack to avoid saving after "Reset" has been pressed
        self.save_settings = True

    def __getitem__(self, key):
        return self._glyphs[key]

    def __setitem__(self, key, value):
        self._glyphs[key] = value

    def __delitem__(self, key):
        del self._glyphs[key]

    def __contains__(self, key):
        return key in self._glyphs

    def __len__(self):
        return len(self._glyphs)

    def keys(self):
        return self._glyphs.keys()

    def itervalues(self):
        for key in self._glyphs.keys():
            yield self[key]

    def import_from_otf(self, otfpath):
        font = TTFont(otfpath)
        if not (font.has_key("COLR") and font.has_key("CPAL")):
            print "ERROR: No COLR and CPAL table present in %s" % otfpath
        else:
            print "Reading palette data ..."
            cpal = table_C_P_A_L_("CPAL")
            cpal.decompile(font["CPAL"].data, font)
            for j in range(len(cpal.palettes)):
                palette = cpal.palettes[j]
                _palette = {}
                for i in range(len(palette)):
                    color = palette[i]
                    _palette[str(i)] = "#%02x%02x%02x%02x" % (color.red,
                        color.green, color.blue, color.alpha)
                self.palettes.append(_palette)
            colr = table_C_O_L_R_("COLR")
            colr.decompile(font["COLR"].data, font)
            print "Reading layer data ..."
            for glyphname in colr.ColorLayers:
                layers = colr[glyphname]
                _glyph = ColorGlyph(self)
                _glyph.basename = glyphname
                for layer in layers:
                    _glyph.layers.append(layer.name)
                    _glyph.colors.append(layer.colorID)
                self[glyphname] = _glyph
            print "Done."
        font.close()

    def __repr__(self):
        result = "<ColorFont>\n"
        result += "    Save settings: %s\n" % self.save_settings
        result += "    Palettes:\n"
        for palette in self.palettes:
            result += "        %s\n" % palette
        result += "    Glyphs: %s\n" % self.keys()
        for glyph in self.itervalues():
            result += "        %s\n" % glyph
        result += "</ColorFont>\n"
        return result
    
    def _get_fcolor(self, palette_index, color_index):
        # get a color by index, in "flat" format
        if color_index < 0xffff:
            _hexrgba = self.palettes[palette_index][str(color_index)]
        else:
            _hexrgba = self.color
        r = int(_hexrgba[1:3], 16)
        g = int(_hexrgba[3:5], 16)
        b = int(_hexrgba[5:7], 16)
        if len(_hexrgba) == 9:
            a = int(_hexrgba[7:9], 16)
        else:
            a = 255
        return rgba(r, g, b, a)
    
    def read_from_rfont(self):
        #print "DEBUG ColorFont.read_from_rfont"
        # Load color info from font lib
        
        if self.rfont is None:
            print "ERROR: rfont is None in ColorFont.read_from_rfont."
        else:
            # read palette
            if "%s.colorpalette" % self.libkey in self.rfont.lib.keys():
                self.palettes = self.rfont.lib["%s.colorpalette" % self.libkey]
                #print self.palettes
            else:
                #print "No palette found in UFO, adding empty palette."
                self.palettes = [{}]
        
            # foreground color
            if "%s.color" % self.libkey in self.rfont.lib.keys():
                self.color = self.rfont.lib["%s.color" % self.libkey]
            else:
                self.color = "#000000"
        
            # background color
            if "%s.colorbg" % self.libkey in self.rfont.lib.keys():
                self.colorbg = self.rfont.lib["%s.colorbg" % self.libkey]
            else:
                self.colorbg = "#ffffff"
        
            # bitmap sizes
            if "%s.bitmap_sizes" % self.libkey in self.rfont.lib.keys():
                self.bitmap_sizes = self.rfont.lib["%s.bitmap_sizes" % self.libkey]
            else:
                self.bitmap_sizes = self.bitmap_sizes_default
        
            # load layer info from glyph libs
            for glyph in self.rfont:
                if "%s.layers" % self.libkey in glyph.lib.keys():
                    self.add_glyph(glyph.name)

    def export_png(self, glyphname, pngpath, palette_index, size):
        image = self[glyphname].get_png(palette_index, size)
        f = open(pngpath, "wb")
        f.write(image)
        f.close()

    def rasterize(self, palette_index, sizes):
        # rasterize all glyphs in a list of sizes.
        for g in self:
            self[g].rasterize(palette_index, sizes)

    def export_to_otf(self, otfpath, write_colr=True, write_sbix=True, write_svg=True, palette_index=0, bitmap_sizes=[512], parent_window=None):
        if write_sbix:
            # export sbix first because it adds glyphs
            # (alternates for windows so it doesn't display the special outlines)
            print "Exporting sbix format ..."
            if write_colr:
                replace_outlines = False
            else:
                replace_outlines = True
            self.bitmap_sizes = bitmap_sizes
            self._export_sbix(otfpath, palette_index, "png", replace_outlines, parent_window)
            print "Done."
        if write_colr:
            print "Exporting COLR/CPAL format ..."
            self._export_colr(otfpath)
            print "Done."
        if write_svg:
            print "Exporting SVG format ...", palette_index
            self._export_svg(otfpath, palette_index, parent_window)
            print "Done."

    def _export_colr(self, otfpath):
        font = TTFont(otfpath)
        if (font.has_key("COLR") and font.has_key("CPAL")):
            print "    WARNING: Replacing existing COLR and CPAL tables in %s" % otfpath
        
        print "    Writing palette data ..."
        cpal = table_C_P_A_L_("CPAL")
        cpal.version = 0
        cpal.numPaletteEntries = len(self.palettes[0])
        cpal.palettes = []
        
        for j in range(len(self.palettes)):
            palette = self.palettes[j]
            _palette = []
            # keep a map of old to new indices (palette indices are
            # not saved in font)
            if j == 0:
                reindex = {0xffff: 0xffff}
                count = 0
            for i in sorted(palette.keys(), key=lambda k: int(k)):
                _color = Color()
                _color.red   = int(palette[i][1:3], 16)
                _color.green = int(palette[i][3:5], 16)
                _color.blue  = int(palette[i][5:7], 16)
                if len(palette[i]) >= 9:
                    _color.alpha  = int(palette[i][7:9], 16)
                else:
                    _color.alpha = 0xff
                if j == 0:
                    reindex[int(i)] = count
                    count += 1
                _palette.append(_color)
            print "        Appending palette", _palette
            #print "ReIndex:", reindex
            cpal.palettes.append(_palette)

        print "    Writing layer data ..."
        colr = table_C_O_L_R_("COLR")
        colr.version = 0
        colr.ColorLayers = {}
        
        for glyphname in self.keys():
            _layer_records = []
            for i in range(len(self[glyphname].layers)):
                glyph = self[glyphname]
                _layer_records.append(LayerRecord(glyph.layers[i],
                    reindex[glyph.colors[i]]))
            colr[glyphname] = _layer_records
        
        # save
        font["CPAL"] = cpal
        font["COLR"] = colr
        font.save(otfpath[:-4] + "_colr" + otfpath[-4:])
        font.close()
    
    def _export_svg(self, otfpath, palette=0, parent_window=None):
        font = TTFont(otfpath)
        if font.has_key("SVG"):
            print "    WARNING: Replacing existing SVG table in %s" % otfpath
        
        svg = table_S_V_G_("SVG")
        svg.version = 0
        
        if parent_window is not None:
            progress = ProgressWindow("Rendering SVG ...", tickCount=len(self.keys()), parentWindow=parent_window)
        
        _palette = self.palettes[palette]
        _svg_palette = []
        
        reindex = {0xffff: 0xffff}
        count = 0
        
        for i in sorted(_palette.keys(), key=lambda k: int(k)):
            red   = int(_palette[i][1:3], 16)
            green = int(_palette[i][3:5], 16)
            blue  = int(_palette[i][5:7], 16)
            if len(_palette[i]) >= 9:
                alpha  = int(_palette[i][7:9], 16)
            else:
                alpha = 0xff
            reindex[int(i)] = count
            count += 1
            _svg_palette.append((red, green, blue, alpha))
        print "Palette:", len(_svg_palette), _svg_palette
        
        _pen = SVGpen(self.rfont)

        for glyphname in ["A", "P"]: #self.keys():
            if parent_window is not None:
                progress.update("Rendering SVG for /%s ..." % glyphname)
            _svg_doc = ""
            for i in range(len(self[glyphname].layers)):
                _color_index = reindex[self[glyphname].colors[i]]
                print "    Layer %i, color %i" % (i, _color_index)
                rglyph = self.rfont[glyphname]
                if _color_index == 0xffff:
                    r, g, b, a = (0, 0, 0, 1)
                else:
                    r, g, b, a = _svg_palette[_color_index]
                _layer = u'<g fill="#%02x%02x%02x%02x">\n' % (r, g, b, a)
                _pen.d = u""
                rglyph.draw(_pen)
                if _pen.d:
                    _svg_doc += _layer + u'<path d="%s"/>' % _pen.d + '\n</g>'
                
            #svg[glyphname] = _svg_doc
            print "SVG glyph", glyphname
            print _svg_doc
        
        if parent_window is not None:
            progress.close()
        
        # save
        #font["SVG"] = svg
        #font.save(otfpath[:-4] + "_svg" + otfpath[-4:])
        font.close()
    
    def _format_outlines_special(self, font, replace_outlines=False):
        if font.has_key("glyf"):
            glyf = font["glyf"]
        else:
            print "ERROR: I need TTF outlines to make special glyph records for the sbix format."
            return
        if replace_outlines:
            alt_glyphname_string = "%s"
        else:
            alt_glyphname_string = "%s.mac"
            hmtx = font["hmtx"]
            cmap = font["cmap"]
        for glyphname in self.keys():
            box = self[glyphname].get_box()
            #print glyphname, box
            if glyphname in glyf.keys():
                alt_glyphname = alt_glyphname_string % glyphname
                glyph = self[glyphname].get_tt_glyph()
                if glyphname != alt_glyphname:
                    # add an alternate glyph for win
                    glyf[alt_glyphname] = glyf[glyphname]
                    glyf[alt_glyphname] = glyph
                    hmtx[alt_glyphname] = hmtx[glyphname][0], box[0]
                    # FIXME:
                    # for table in cmap.tables:
                    #    if table.plaformID == 0 and table.platEncID == 3:
                    # ...
                    cmap_mac = cmap.getcmap(0, 3).cmap
                    for k, v in cmap_mac.iteritems():
                        if v == glyphname:
                            # redirect current entry to alternate glyph
                            # FIXME: This changes the Windows cmap as well.
                            cmap_mac[k] = alt_glyphname
                    # FIXME: Reverse alternate glyph mapping for Win cmap, is this needed?
                    # FIXME: This doesn't work
                    cmap_win = cmap.getcmap(3, 1).cmap
                    for k, v in cmap_win.iteritems():
                        if v == alt_glyphname:
                            # redirect current entry to alternate glyph
                            cmap_win[k] = glyphname
                else:
                    glyf[glyphname] = glyph
    
    def _export_sbix(self, otfpath, palette=0, image_format="png", replace_outlines=False, parent_window=None):
        if image_format == "png": # FIXME: too complicated
            image_format_tag="png "
        else:
            image_format_tag="pdf "
        if replace_outlines:
            alt_glyphname_string = "%s"
        else:
            alt_glyphname_string = "%s.mac"
        font = TTFont(otfpath)
        if (font.has_key("sbix")):
            print "    WARNING: Replacing existing sbix table in %s" % otfpath
            replace_outlines = True
        # insert special nodes into glyphs
        self._format_outlines_special(font, replace_outlines)
        # build sbix table
        sbix = table__s_b_i_x("sbix")
        if parent_window is not None:
            progress = ProgressWindow("Rendering bitmaps ...", tickCount=len(self.bitmap_sizes)*len(self.keys()), parentWindow=parent_window)
        for current_size in sorted(self.bitmap_sizes):
            current_set = BitmapSet(size=current_size)
            for glyphname in self.keys():
                if parent_window is not None:
                    progress.update("Rendering /%s @ %i px ..." % (glyphname, current_size))
                alt_glyphname = alt_glyphname_string % glyphname
                if image_format == "png":
                    image_data = self[glyphname].get_png(palette, current_size)
                else:
                    image_data = self[glyphname].get_pdf(palette, current_size)
                current_set.bitmaps[alt_glyphname] = Bitmap(glyphName=glyphname,
                                                        imageFormatTag=image_format_tag,
                                                        imageData=image_data)
            sbix.bitmapSets[current_size] = current_set
        if parent_window is not None:
            progress.close()
        font["sbix"] = sbix    
        font.save(otfpath[:-4] + "_sbix" + otfpath[-4:])
        font.close()

    def save_to_rfont(self):
        values_to_save = {
            "colorpalette": self.palettes,
            "color": self.color,
            "colorbg": self.colorbg,
            "bitmap_sizes": self.bitmap_sizes,
        }
        
        for key, value in values_to_save.iteritems():
            self._save_key_to_lib(key, value)
        
        # save each glyph color layer data
        #for cglyph in self.itervalues():
        #    cglyph.save_to_rfont()

    def save_all_glyphs_to_rfont(self):
        # save each glyph color layer data
        for cglyph in self.itervalues():
            cglyph.save_to_rfont()

    def save_glyph_to_rfont(self, name):
        #print "DEBUG ColorFont.save_glyph_to_rfont(%s)" % name
        if name in self.keys():
            self[name].save_to_rfont()
        else:
            # if the glyph is not in ColorFont, but has layer info in RFont,
            # delete layer info from RFont
            #print "DEBUG Delete layer info from glyph not in ColorFont"
            if name in self.rfont.keys():
                if "%s.layers" % self.libkey in self.rfont[name].lib.keys():
                    del self.rfont[name].lib["%s.layers" % self.libkey]
                    self.rfont.update()

    def _save_key_to_lib(self, name, value):
        # save name-value-pair to font lib
        if "%s.%s" % (self.libkey, name) in self.rfont.lib.keys():
            if self.rfont.lib["%s.%s" % (self.libkey, name)] != value:
                # update only if the name exists and the value doesn't match
                self.rfont.lib["%s.%s" % (self.libkey, name)] = value
                self.rfont.update()
        else:
            self.rfont.lib["%s.%s" % (self.libkey, name)] = value
            self.rfont.update()

    def add_glyph(self, name):
        self._glyphs[name] = ColorGlyph(self, name)

    def auto_layers(self, auto_layer_regex=None, include_baseglyph=True):
        # Automatically build a color font based on glyph name suffixes
        from re import search, compile
        regex = compile(auto_layer_regex)
        _layer_base_glyphs = []
        
        # find possible base glyphs: all that don't match the regex
        for glyphname in self.rfont.glyphOrder:
            if not regex.search(glyphname):
                _layer_base_glyphs.append(glyphname)
        #print "Found layer base glyphs:", _layer_base_glyphs
        
        for baseglyph in _layer_base_glyphs:
            layer_regex = "^%s%s" % (baseglyph.replace(".", "\."), auto_layer_regex)
            regex = compile(layer_regex)
            #print "Looking for layer glyphs with regex", layer_regex
            has_layers = False
            for layername in self.rfont.glyphOrder:
                if regex.search(layername):
                    #print "  found"
                    if not baseglyph in self.keys():
                        self.add_glyph(baseglyph)
                    self[baseglyph].add_layer(layername, 0xffff)
                    has_layers = True
            if has_layers and include_baseglyph:
                self[baseglyph].add_layer(baseglyph, 0xffff)

    def auto_palette(self):
        # Automatically build a color palette with max(layers) entries
        # and assign it to all color glyphs
        # FIXME: Doesn't work for non-continuous color indices
        from random import randint
        self.palettes = [{}]
        palette = self.palettes[0]
        max_layers = 0
        for g in self.itervalues():
            if len(g.layers) > max_layers:
                max_layers = len(g.layers)
            g.colors = range(len(g.layers))
        for i in range(max_layers):
            palette[str(i)] = "#%02x%02x%02xff" % (randint(0, 255), randint(0, 255), randint(0, 255))



class ColorGlyph(object):
    def __init__(self, parent, basename=""):
        self.font = parent
        self.basename = basename
        self.layers = []
        self.colors = []
        self.bitmaps = {}
        if basename != "":
            self.read_from_rfont()

    def __repr__(self):
        result = "<ColorGlyph>\n"
        result += "    Base glyph: %s\n" % self.basename
        result += "    Layers: %s\n" % self.layers
        result += "    Colors: %s\n" % self.colors
        result += "</ColorGlyph>\n"
        return result

    def add_layer(self, layername, colorindex):
        self.layers.append(layername)
        self.colors.append(colorindex)

    def read_from_rfont(self):
        self.layers = []
        self.colors = []
        if "%s.layers" % self.font.libkey in self.font.rfont[self.basename].lib.keys():
            entry = self.font.rfont[self.basename].lib["%s.layers" % self.font.libkey]
            if len(entry) == 2:
                layers = entry[0]
                colors = entry[1]
                if type(layers) == ListType and type(colors) == ListType:
                    self.layers = layers
                    self.colors = colors
                else:
                    print "\nERROR: %s: Failed reading layer or color information from glyph lib. Glyph will have no layers." % self.basename
                    print "       Received data for layer and color, but one or both of them weren't a list."
                    print "       Layers:", layers, type(layers)
                    print "       Colors:", colors, type(colors)
            else:
                print "\nERROR: %s: Failed reading layer and color information from glyph lib. Glyph will have no layers." % self.basename
                print "       Expected a list with 2 elements, but got %i elements." % len(entry)

    def save_to_rfont(self):
        # outlines may have changed, clear the rasterized image
        self.bitmaps = {}
        if self.font is not None:
            rfont = self.font.rfont
            if self.basename in rfont:
                if "%s.layers" % self.font.libkey in rfont[self.basename].lib.keys():
                    if self.layers == [] and self.colors == []:
                        del rfont[self.basename].lib["%s.layers" % self.font.libkey]
                    else:
                        if rfont[self.basename].lib["%s.layers" % self.font.libkey] != (self.layers, self.colors):
                            rfont[self.basename].lib["%s.layers" % self.font.libkey] = self.layers, self.colors
                    rfont[self.basename].update()
                else:
                    if self.layers != [] or self.colors != []:
                        if self.font.save_settings:
                            rfont[self.basename].lib["%s.layers" % self.font.libkey] = self.layers, self.colors
                            rfont[self.basename].update()
            else:
                print "ERROR: Glyph %s does not exist in font %s (ColorGlyph.save_to_rfont)" % (self.basename, rfont)

    # sbix export stuff

    def rasterize(self, palette_index, sizes=[]):
        if not 0 in self.bitmaps.keys():
            _page = self._get_drawing(palette_index)
            self.bitmaps[0] = _page.image(ppi=72, kind="rgba", samples=32).flip(False, True)
        for size in sizes:
            scale = float(size)/self.font.rfont.info.unitsPerEm
            _width = int(ceil(self.bitmaps[0].width*scale))
            _height = int(ceil(self.bitmaps[0].height*scale))
            scale = min(float(_width)/(self.bitmaps[0].width+2), (float(_height)/(self.bitmaps[0].height+2)))
            self.bitmaps[size] = self.bitmaps[0].resized(
                int(round(self.bitmaps[0].width * scale)),
                int(round(self.bitmaps[0].height * scale)),
                ).png(optimized=True)

    def _get_drawing(self, palette_index=0):
        box = self.get_box() # FIXME rasterizing fails if the box is too small, i.e. when the layers are bigger than the base glyph.
        width = box[2] - box[0]
        height = box[3] - box[1]
        d = document(width+2, height+2, "pt")
        p = d.addpage()
        _path = shape.path(shape())
        for i in range(len(self.layers)):
            layer = self.font.rfont[self.layers[i]]
            colorindex = self.colors[i]
            layer_color = self.font._get_fcolor(palette_index, colorindex)
            pen = FlatPen(self.font.rfont)
            layer.draw(pen)
            g = p.place(shape().nostroke().fill(layer_color).path(*pen.path))
            g.position(1 - box[0], 1 - box[1])
        return p

    def get_tt_glyph(self):
        # make dummy contours
        box = self.get_box()
        contours = [
            [(box[0], box[1], 1)],
            [(box[2], box[3], 1)],
        ]
        glyph = Glyph()
        glyph.program = NoProgram()
        glyph.numberOfContours = 0
        for contour in contours:
            coordinates = []
            flags = []
            for x, y, flag in contour:
                if not hasattr(glyph, "xMin"):
                    glyph.xMin = x
                    glyph.yMin = y
                    glyph.xMax = x
                    glyph.yMax = y
                else:
                    glyph.xMin = min(glyph.xMin, x)
                    glyph.yMin = min(glyph.yMin, y)
                    glyph.xMax = max(glyph.xMax, x)
                    glyph.yMax = max(glyph.yMax, y)
                coordinates.append([x, y])
                flags.append(flag)
            coordinates = numpy.array(coordinates, numpy.int16)
            flags = numpy.array(flags, numpy.int8)
            if not hasattr(glyph, "coordinates"):
                glyph.coordinates = coordinates
                glyph.flags = flags
                glyph.endPtsOfContours = [len(coordinates)-1]
            else:
                glyph.coordinates = numpy.concatenate((glyph.coordinates, coordinates))
                glyph.flags = numpy.concatenate((glyph.flags, flags))
                glyph.endPtsOfContours.append(len(glyph.coordinates)-1)
            glyph.numberOfContours += 1
        return glyph

    def get_png(self, palette_index, size):
        if size not in self.bitmaps.keys():
            self.rasterize(palette_index, [size])
        return self.bitmaps[size]

    def get_box(self):
        # FIXME: bbox of base glyph is not always the biggest one
        box = self.font.rfont[self.basename].box
        return box



class NoProgram(object):
    def toXML(self, writer, ttFont):
        pass
        
    def getBytecode(self):
        return ''

# ----------

def test():
    # make PDF for color glyph
    _font = ColorFont(CurrentFont())
    _font.read_from_rfont()
    #_font._export_sbix(r"/Users/jenskutilek/Documents/Color Fonts MS/Dingbats2SamplerOT.ttf", 0, [20, 40, 72, 96, 128, 160, 256, 512], "png")
    #_font.rasterize(0, [16])
    #_font.export_png("six", "/Users/jenskutilek/Desktop/six.png", 0, 1000)
    _font._export_sbix(r"/Users/jenskutilek/Documents/Color Fonts MS/Dingbats2SamplerOT.ttf", 0, [128], "png", replace_outlines=True)
    
    
if __name__ == "__main__":
    test()