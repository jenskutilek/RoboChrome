from operator import itemgetter
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import Glyph as TTGlyph
from fontTools.ttLib.tables.C_P_A_L_ import table_C_P_A_L_, Color
from fontTools.ttLib.tables.C_O_L_R_ import table_C_O_L_R_, LayerRecord
from fontTools.ttLib.tables._s_b_i_x import table__s_b_i_x
from fontTools.ttLib.tables.sbixStrike import Strike
from fontTools.ttLib.tables.sbixGlyph import Glyph as sbixGlyph
from fontTools.ttLib.tables.S_V_G_ import table_S_V_G_

import array
from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates

from math import ceil
from re import compile

# for png generation
try:
    from flat import document, shape, rgba
    have_flat = True
except ImportError:
    have_flat = False
    print("colorfont: The 'flat' Python module is missing.")
    print("Raster output formats will not be available.")
    print("Please see <https://github.com/jenskutilek/RoboChrome/blob/master/README.md>")
if have_flat:
    from colorfont.flatPen import FlatPen

# for svg generation
from colorfont.svgPen import SVGpen

# for svg storage in glyph lib
from plistlib import Data

from defconAppKit.windows.progressWindow import ProgressWindow


class ColorFont(object):
    def __init__(self, rfont=None):
        """Initialize a ColorFont and read color data from a RFont.
            rfont: The RFont object to load the color data from"""
        self.libkey = "com.fontfont.colorfont"

        # default values
        self._auto_layer_regex_default = r"\.alt[0-9]{3}$"
        self._bitmap_sizes_default = [20, 32, 40, 72, 96, 128, 256, 512, 1024]
        self._write_cbdt_default = False
        self._write_colr_default = True
        self._write_sbix_default = False
        self._write_svg_default = True

        self._rfont = rfont
        self._glyphs = {}

        self._auto_layer_include_baseglyph = False
        self._auto_layer_regex = self._auto_layer_regex_default
        self._bitmap_sizes = self._bitmap_sizes_default
        self.color = "#000000FF"
        self.colorbg = "#FFFFFFFF"
        self.palettes = [{}]
        self.reset_generate_formats()
        self._prefer_placed_images = False

        # FIXME hack to avoid saving after "Reset" has been pressed
        self._save_settings = True

        # These are loaded and saved from/to UFO lib
        self.settings = {
            # attribute, default value
            "auto_layer_include_baseglyph": False,
            "auto_layer_regex": self._auto_layer_regex_default,
            "bitmap_sizes": self._bitmap_sizes_default,
            "color": "#000000",
            "colorbg": "#ffffff",
            "colorpalette": [{}],
            "prefer_placed_images": False,
            "write_cbdt": self._write_cbdt_default,
            "write_colr": self._write_colr_default,
            "write_sbix": self._write_sbix_default,
            "write_svg": self._write_svg_default,
        }

    # properties

    def _get_rfont(self):
        """RFont the ColorFont belongs to"""
        return self._rfont

    def _set_rfont(self, rfont):
        self._rfont = rfont

    rfont = property(_get_rfont, _set_rfont)

    def _get_auto_layer_include_baseglyph(self):
        """boolean to indicate whether the auto layer function should
        include the base glyph as the last layer"""
        return self._auto_layer_include_baseglyph

    def _set_auto_layer_include_baseglyph(self, setting):
        self._auto_layer_include_baseglyph = setting

    auto_layer_include_baseglyph = property(_get_auto_layer_include_baseglyph, _set_auto_layer_include_baseglyph)

    def _get_auto_layer_regex(self):
        """string of the regular expression used to identify
        layer glyphs"""
        return self._auto_layer_regex

    def _set_auto_layer_regex(self, regex):
        self._auto_layer_regex = regex

    auto_layer_regex = property(_get_auto_layer_regex, _set_auto_layer_regex)

    def _get_bitmap_sizes(self):
        """list of (int) bitmap sizes in pixels per em that should be generated"""
        return self._bitmap_sizes

    def _set_bitmap_sizes(self, sizes):
        self._bitmap_sizes = sizes

    bitmap_sizes = property(_get_bitmap_sizes, _set_bitmap_sizes)

    def _get_palettes(self):
        """list of color palette dicts"""
        return self.colorpalette

    def _set_palettes(self, palettes):
        self.colorpalette = palettes

    palettes = property(_get_palettes, _set_palettes)

    def remove_from_palettes(self, color_index):
        # Remove color with index `color_index` from all palettes
        for p in self.palettes:
            if color_index in p:
                del p[color_index]

    def _get_prefer_placed_images(self):
        """boolean to indicate whether placed images in UFO
        should be preferred over generated bitmaps from vector
        layers"""
        return self._prefer_placed_images

    def _set_prefer_placed_images(self, setting):
        self._prefer_placed_images = setting

    prefer_placed_images = property(_get_prefer_placed_images, _set_prefer_placed_images)

    def _get_save_settings(self):
        """boolean to indicate whether settings should be saved
        (set to False to avoid saving to RFont after color data
        has been removed)"""
        return self._save_settings

    def _set_save_settings(self, setting):
        self._save_settings = setting

    save_settings = property(_get_save_settings, _set_save_settings)

    # ColorFont should behave like a dict w/ regard to its glyphs

    def __getitem__(self, glyph_name):
        """Return the ColorGlyph object with the name <glyph_name>."""
        return self._glyphs[glyph_name]

    def __setitem__(self, glyph_name, glyph_object):
        """Assign a glyph object to a glyph name of the ColorFont.
            glyph_name:   The glyph name
            glyph_object: The ColorGlyph object"""
        self._glyphs[glyph_name] = glyph_object

    def __delitem__(self, glyph_name):
        """Delete the ColorGlyph object with the name <glyph_name>."""
        del self._glyphs[glyph_name]

    def __contains__(self, glyph_name):
        """Return True if a ColorGlyph called <glyph_name> exists
        in the ColorFont, otherwise return False."""
        return glyph_name in self._glyphs

    def __len__(self):
        """Return the number of glyphs in the ColorFont."""
        return len(self._glyphs)

    def keys(self):
        """Return a list of the ColorFont's glyph names."""
        return self._glyphs.keys()

    def values(self):
        """Return a list of the ColorFont's glyph objects."""
        return self._glyphs.values()

    # normal methods

    def import_from_otf(self, otfpath):
        """Import color data (CPAL/COLR) from a font file.
            otfpath: Path of the font file"""
        font = TTFont(otfpath)
        if not ("COLR" in font and "CPAL" in font):
            print("ERROR: No COLR and CPAL table present in %s" % otfpath)
        else:
            print("Reading palette data ...")
            cpal = table_C_P_A_L_("CPAL")
            cpal.decompile(font["CPAL"].data, font)
            for j in range(len(cpal.palettes)):
                palette = cpal.palettes[j]
                _palette = {}
                for i in range(len(palette)):
                    color = palette[i]
                    _palette[str(i)] = "#%02x%02x%02x%02x" % (
                        color.red,
                        color.green,
                        color.blue,
                        color.alpha
                    )
                self.palettes.append(_palette)
            colr = table_C_O_L_R_("COLR")
            colr.decompile(font["COLR"].data, font)
            print("Reading layer data ...")
            for glyphname in colr.ColorLayers:
                layers = colr[glyphname]
                _glyph = ColorGlyph(self)
                _glyph.basename = glyphname
                for layer in layers:
                    _glyph.layers.append(layer.name)
                    _glyph.colors.append(layer.colorID)
                self[glyphname] = _glyph
            print("Done.")
        font.close()

    def __repr__(self):
        result = "<ColorFont>\n"
        result += "    Save settings: %s\n" % self.save_settings
        result += "    Auto layer regex: %s\n" % self.auto_layer_regex
        result += "    Auto layer includes base glyph: %s\n" % self.auto_layer_include_baseglyph
        result += "    Bitmap sizes: %s\n" % self.bitmap_sizes
        result += "    Palettes:\n"
        for palette in self.palettes:
            result += "        %s\n" % palette
        result += "    Glyphs: %s\n" % self.keys()
        for glyph in self.values():
            result += "%s\n" % glyph
        result += "</ColorFont>\n"
        return result

    def reset_auto_layer_regex(self):
        """Reset the regex for the Auto Layer function to its default value."""
        self.auto_layer_regex = self._auto_layer_regex_default

    def reset_bitmap_sizes(self):
        """Reset the list of bitmap sizes for the Generate function to its
        default value."""
        self.bitmap_sizes = self._bitmap_sizes_default

    def reset_generate_formats(self):
        """Reset the choices of table formats for the Generate function to
        their default states."""
        self.write_colr = self._write_colr_default
        self.write_sbix = self._write_sbix_default
        self.write_cbdt = self._write_cbdt_default
        self.write_svg = self._write_svg_default

    def _get_fcolor(self, palette_index, color_index):
        # get a color by index, in "flat" format
        if palette_index not in range(len(self.palettes)):
            print("ERROR: _get_fcolor(self, palette_index, color_index)")
            print("       Requested palette key %s (%s) not in available palette keys." % (
                palette_index, type(palette_index)
            ))
            raise KeyError(palette_index)
        if not str(color_index) in self.palettes[palette_index]:
            print("ERROR: _get_fcolor(self, palette_index, color_index)")
            print("       Requested color key %s (%s) not in available color keys." % (
                color_index, type(str(color_index))
            ))
            raise KeyError(str(color_index))
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
        """Read color data from RFont."""
        # print("DEBUG ColorFont.read_from_rfont")
        # Load color info from font lib

        if self.rfont is None:
            print("ERROR: rfont is None in ColorFont.read_from_rfont.")
        else:
            for propkey, default in self.settings.items():
                if "%s.%s" % (self.libkey, propkey) in self.rfont.lib.keys():
                    setattr(
                        self,
                        propkey,
                        self.rfont.lib["%s.%s" % (self.libkey, propkey)]
                    )
                else:
                    setattr(self, propkey, default)
            if self.palettes:
                # Convert palette keys to integer
                new_palettes = []
                for palette in self.palettes:
                    new_palettes.append({
                        int(color_index): color
                        for color_index, color in palette.items()
                    })
                self.palettes = new_palettes

            # load layer info from glyph libs
            for glyph in self.rfont:
                if "%s.layers" % self.libkey in glyph.lib.keys():
                    self.add_glyph(glyph.name)

    def export_png(self, glyph_name, png_path, palette_index, size):
        """Export a glyph as PNG image to a file.
            glyph_name:    The glyph name
            png_path:      The path of the image file
            palette_index: Use colors from this palette
            size:          Size in pixels per em"""
        image = self[glyph_name].get_png(palette_index, size)
        f = open(png_path, "wb")
        f.write(image)
        f.close()

    def rasterize(self, palette_index, sizes):
        """Rasterize all glyphs.
            palette_index: Use colors from this palette
            sizes:         A list of sizes in pixels per em"""
        if not have_flat:
            print("ColorFont.rasterize: The 'flat' Python module is missing.")
            print("Please see <https://github.com/jenskutilek/RoboChrome/blob/master/README.md>")
            return
        for g in self:
            self[g].rasterize(palette_index, sizes)

    def export_to_otf(self, otfpath, palette_index=0, parent_window=None):
        """Export all color data to an existing font file.
            otfpath:       The font file to export the color data to
            palette_index: Use colors from this palette
            parent_window: The ColorFontEditor window, needed to display progress bar."""
        if self.write_sbix:
            # export sbix first because it adds glyphs
            # (alternates for windows so it doesn't display the special outlines)
            print("Exporting sbix format ...")
            if self.write_colr:
                replace_outlines = False
            else:
                replace_outlines = True
            self._export_sbix(otfpath, palette_index, "png", replace_outlines, parent_window)
            print("Done.")
        if self.write_colr:
            print("Exporting COLR/CPAL format ...")
            self._export_colr(otfpath)
            print("Done.")
        if self.write_svg:
            print("Exporting SVG format with palette %i ..." % palette_index)
            self._export_svg(otfpath, palette_index, parent_window)
            print("Done.")

    def _export_colr(self, otfpath):
        font = TTFont(otfpath)
        if ("COLR" in font and "CPAL" in font):
            print("    WARNING: Replacing existing COLR and CPAL tables in %s" % otfpath)

        print("    Writing palette data ...")
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
                _blue, _green, _red, _alpha = 0, 0, 0, 0
                _red   = int(palette[i][1:3], 16)
                _green = int(palette[i][3:5], 16)
                _blue  = int(palette[i][5:7], 16)
                if len(palette[i]) >= 9:
                    _alpha  = int(palette[i][7:9], 16)
                else:
                    _alpha = 0xff
                _color = Color(_blue, _green, _red, _alpha)
                if j == 0:
                    reindex[int(i)] = count
                    count += 1
                _palette.append(_color)
            print("        Appending palette", _palette)
            # print("ReIndex:", reindex)
            cpal.palettes.append(_palette)

        print("    Writing layer data ...")
        colr = table_C_O_L_R_("COLR")
        colr.version = 0
        colr.ColorLayers = {}

        for glyphname in self.keys():
            _layer_records = []
            for i in range(len(self[glyphname].layers)):
                glyph = self[glyphname]
                _layer_records.append(
                    LayerRecord(glyph.layers[i], reindex[glyph.colors[i]])
                )
            colr[glyphname] = _layer_records

        # save
        font["CPAL"] = cpal
        font["COLR"] = colr
        font.save(otfpath[:-4] + "_colr" + otfpath[-4:])
        font.close()

    def _export_svg(self, otfpath, palette=0, parent_window=None):
        font = TTFont(otfpath)
        if "SVG " in font:
            print("    WARNING: Replacing existing SVG table in %s" % otfpath)
        # font.getReverseGlyphMap(rebuild=1)

        svg = table_S_V_G_("SVG ")
        svg.version = 0
        svg.docList = []
        svg.colorPalettes = None

        if parent_window is not None:
            progress = ProgressWindow(
                "Rendering SVG ...",
                tickCount=len(self.keys()),
                parentWindow=parent_window
            )

        _palette = self.palettes[palette]
        _svg_palette = []
        _docList = []

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
        # print("Palette:", len(_svg_palette), _svg_palette)

        _pen = SVGpen(self.rfont, optimize_output=True)

        for glyphname in self.keys():

            # look up glyph id
            try:
                gid = font.getGlyphID(glyphname)
            except:
                assert 0, "SVG table contains a glyph name not in font: " + str(glyphname)

            # update progress bar
            if parent_window is not None:
                progress.update("Rendering SVG for /%s ..." % glyphname)

            # build svg glyph
            _svg_transfrom_group = """<g transform="scale(1 -1)">%s</g>"""

            contents = u""
            for i in range(len(self[glyphname].layers)):
                _color_index = reindex[self[glyphname].colors[i]]
                # print("    Layer %i, color %i" % (i, _color_index))
                rglyph = self.rfont[self[glyphname].layers[i]]
                if _color_index == 0xffff:
                    r, g, b, a = (0, 0, 0, 0xff)
                else:
                    r, g, b, a = _svg_palette[_color_index]
                _pen.reset()
                rglyph.draw(_pen)
                if _pen.d:
                    contents += u'<g fill="#%02x%02x%02x"' % (r, g, b)
                    if a != 0xff:
                        contents += u' fill-opacity="%g"' % (a / 0xff)
                    contents += u'><path d="%s"/></g>' % _pen.d
            if contents:
                contents = _svg_transfrom_group % contents
            _svg_doc = (
                '<svg enable-background="new 0 0 64 64" id="glyph%i" '
                'version="1.1" xmlns="http://www.w3.org/2000/svg" '
                'xmlns:xlink="http://www.w3.org/1999/xlink">%s</svg>' % (
                    gid,
                    contents
                )
            )
            _docList.append((_svg_doc, gid, gid))

        svg.docList = sorted(_docList, key=itemgetter(1))

        if parent_window is not None:
            progress.close()

        # save
        font["SVG "] = svg
        font.save(otfpath[:-4] + "_svg" + otfpath[-4:])
        font.close()

    def _format_outlines_special(self, font, replace_outlines=False):
        if "glyf" in font:
            glyf = font["glyf"]
        else:
            print("ERROR: I need TTF outlines to make special glyph records for the sbix format.")
            return
        if replace_outlines:
            alt_glyphname_string = "%s"
        else:
            alt_glyphname_string = "%s.mac"
            hmtx = font["hmtx"]
            cmap = font["cmap"]
        for glyphname in self.keys():
            box = self[glyphname].get_box()
            # print(glyphname, box)
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
                    for k, v in cmap_mac.items():
                        if v == glyphname:
                            # redirect current entry to alternate glyph
                            # FIXME: This changes the Windows cmap as well.
                            cmap_mac[k] = alt_glyphname
                    # FIXME: Reverse alternate glyph mapping for Win cmap, is this needed?
                    # FIXME: This doesn't work
                    cmap_win = cmap.getcmap(3, 1).cmap
                    for k, v in cmap_win.items():
                        if v == alt_glyphname:
                            # redirect current entry to alternate glyph
                            cmap_win[k] = glyphname
                else:
                    glyf[glyphname] = glyph

    def _export_sbix(self, otfpath, palette=0, image_format="png",
                     replace_outlines=False, parent_window=None):
        if not have_flat:
            print("ColorFont._export_sbix: The 'flat' Python module is missing.")
            print("Please see <https://github.com/jenskutilek/RoboChrome/blob/master/README.md>")
            return
        if replace_outlines:
            alt_glyphname_string = "%s"
        else:
            alt_glyphname_string = "%s.mac"
        font = TTFont(otfpath)
        if "sbix" in font:
            print("    WARNING: Replacing existing sbix table in %s" % otfpath)
            replace_outlines = True
        # insert special nodes into glyphs
        self._format_outlines_special(font, replace_outlines)
        # build sbix table
        sbix = table__s_b_i_x("sbix")
        if parent_window is not None:
            progress = ProgressWindow(
                "Rendering bitmaps ...",
                tickCount=len(self.bitmap_sizes) * len(self.keys()),
                parentWindow=parent_window
            )
        for current_ppem in sorted(self.bitmap_sizes):
            current_set = Strike(ppem=current_ppem)
            for glyphname in self.keys():
                if parent_window is not None:
                    progress.update(
                        "Rendering /%s @ %i px ..." % (
                            glyphname,
                            current_ppem
                        )
                    )
                alt_glyphname = alt_glyphname_string % glyphname
                if image_format == "png":
                    image_data = self[glyphname].get_png(palette, current_ppem)
                elif image_format == "pdf":
                    image_data = self[glyphname].get_pdf(palette, current_ppem)
                else:
                    # TODO: handle tiff, jpg, (dupe, mask)
                    # fallback
                    image_data = self[glyphname].get_png(palette, current_ppem)
                if image_data is not None:
                    current_set.glyphs[alt_glyphname] = sbixGlyph(
                        glyphName=glyphname,
                        graphicType=image_format,
                        imageData=image_data,
                    )
            sbix.strikes[current_ppem] = current_set
        if parent_window is not None:
            progress.close()
        font["sbix"] = sbix
        font.save(otfpath[:-4] + "_sbix" + otfpath[-4:])
        font.close()

    def save_to_rfont(self):
        """Save color data to RFont."""
        if self.rfont is not None:
            for propkey in self.settings.keys():
                if propkey == "colorpalette":
                    # Convert color indices to strings
                    lib_palettes = []
                    for palette in self.colorpalette:
                        lib_palettes.append({
                            str(color_index): color
                            for color_index, color in palette.items()
                        })
                    self._save_key_to_lib(propkey, lib_palettes)
                else:
                    self._save_key_to_lib(propkey, getattr(self, propkey))

        # save each glyph color layer data
        # for cglyph in self.values():
        #     cglyph.save_to_rfont()

    def save_all_glyphs_to_rfont(self):
        """Save color data for each ColorGlyph to RFont."""
        # save each glyph color layer data
        for cglyph in self.values():
            cglyph.save_to_rfont()

    def save_glyph_to_rfont(self, glyph_name):
        """Save color data for one ColorGlyph to RFont.
            glyph_name: The glyph name"""
        # print("DEBUG ColorFont.save_glyph_to_rfont(%s)" % name)
        if glyph_name in self.keys():
            self[glyph_name].save_to_rfont()
        else:
            # if the glyph is not in ColorFont, but has layer info in RFont,
            # delete layer info from RFont
            # print("DEBUG Delete layer info from glyph not in ColorFont")
            if glyph_name in self.rfont.keys():
                if "%s.layers" % self.libkey in self.rfont[glyph_name].lib.keys():
                    del self.rfont[glyph_name].lib["%s.layers" % self.libkey]
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

    def add_glyph(self, glyph_name):
        """Add a glyph by name.
            glyph_name: The glyph name"""
        self[glyph_name] = ColorGlyph(self, glyph_name)

    def add_svg(self, glyph_name, file_name):
        """Add an SVG document from a file to a glyph.
            glyph_name: The glyph name
            file_name:  The path to the SVG file"""
        if not glyph_name in self:
            self.add_glyph(glyph_name)
        self[glyph_name].add_svg(file_name)

    def auto_layers(self):
        """Assign layers for all base glyphs in RFont based on the
        regular expression <ColorFont.auto_layer_regex>."""
        regex = compile(self.auto_layer_regex)
        _layer_base_glyphs = []

        # find possible base glyphs: all that don't match the regex
        for glyphname in self.rfont.glyphOrder:
            if not regex.search(glyphname):
                _layer_base_glyphs.append(glyphname)
        # print("Found layer base glyphs:", _layer_base_glyphs)

        for baseglyph in _layer_base_glyphs:
            layer_regex = "^%s%s" % (baseglyph.replace(".", r"\."), self.auto_layer_regex)
            regex = compile(layer_regex)
            # print("Looking for layer glyphs with regex", layer_regex)
            has_layers = False
            for layername in self.rfont.glyphOrder:
                if regex.search(layername):
                    # print("  found")
                    if baseglyph not in self.keys():
                        self.add_glyph(baseglyph)
                    self[baseglyph].add_layer(layername, 0xffff)
                    has_layers = True
            if has_layers and self.auto_layer_include_baseglyph:
                self[baseglyph].add_layer(baseglyph, 0xffff)

    def auto_palette(self):
        """Automatically build a color palette with max(layers) entries
        and assign it to all color glyphs."""
        from random import randint
        self.palettes = [{}]
        palette = self.palettes[0]
        used_color_indices = set()
        for g in self.values():
            used_color_indices |= set(g.colors)
        for i in used_color_indices:
            palette[str(i)] = "#%02x%02x%02xff" % (
                randint(0, 255),
                randint(0, 255),
                randint(0, 255)
            )


class ColorGlyph(object):
    def __init__(self, parent, basename=""):
        """Each ColorGlyph consists of a base glyph and some layer glyphs
        which are assigned to colors via palette indices.
            parent:   the ColorFont instance
            basename: name of the base glyph"""
        self.font = parent
        self.basename = basename
        self.layers = []
        self.colors = []
        self.bitmaps = {}
        self.svg = ""
        if basename != "":
            self.read_from_rfont()

    def __repr__(self):
        result = "<ColorGlyph>\n"
        result += "    Base glyph: %s\n" % self.basename
        result += "    Layers: %s\n" % self.layers
        result += "    Colors: %s\n" % self.colors
        result += "    SVG:    %s\n" % self.svg
        result += "</ColorGlyph>\n"
        return result

    def add_layer(self, layer_name, color_index):
        """Add a layer glyph and assign a color to it.
            layer_name:  The name of the layer glyph to add
            color_index: Index of the color to assign to the layer"""
        self.layers.append(layer_name)
        self.colors.append(color_index)

    def add_svg(self, file_name):
        """Add an SVG document from a file.
            file_name: The path of the SVG file"""
        f = open(file_name, "rb")
        self.svg = f.read()
        f.close()
        self.save_to_rfont()

    def read_from_rfont(self):
        """Load the ColorGlyph data from the ColorFont's RFont/RGlyph."""
        self.layers = []
        self.colors = []
        self.svg = ""
        if "%s.layers" % self.font.libkey in self.font.rfont[self.basename].lib.keys():
            entry = self.font.rfont[self.basename].lib["%s.layers" % self.font.libkey]
            if len(entry) == 2:
                layers = entry[0]
                colors = entry[1]
                if type(layers) == list and type(colors) == list:
                    self.layers = layers
                    self.colors = colors
                else:
                    print("\nERROR: %s: Failed reading layer or color information from glyph lib. Glyph will have no layers." % self.basename)
                    print("       Received data for layer and color, but one or both of them weren't a list.")
                    print("       Layers:", layers, type(layers))
                    print("       Colors:", colors, type(colors))
            else:
                print("\nERROR: %s: Failed reading layer and color information from glyph lib. Glyph will have no layers." % self.basename)
                print("       Expected a list with 2 elements, but got %i elements." % len(entry))

        # read SVG from base64-encoded data
        _svg_data = self.font.rfont[self.basename].lib.get("%s.svg" % self.font.libkey, "")
        if _svg_data != "":
            self.svg = _svg_data.data

    def save_to_rfont(self):
        """Save the ColorGlyph data to the ColorFont's RFont/RGlyph."""
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

                # save SVG as base64-encoded data
                if self.svg != "":
                    _svg_data = Data(self.svg)
                else:
                    _svg_data = ""
                self._save_key_to_lib("svg", _svg_data, "")
            else:
                print("ERROR: Glyph %s does not exist in font %s (ColorGlyph.save_to_rfont)" % (self.basename, rfont))

    def _save_key_to_lib(self, name, value, empty_value):
        # save name-value-pair to glyph lib
        _glyph = self.font.rfont[self.basename]
        _glyph_lib = _glyph.lib
        _lib_key = "%s.%s" % (self.font.libkey, name)
        if _lib_key in _glyph_lib:
            if value == empty_value:
                del _glyph_lib[_lib_key]
                _glyph.update()
            else:
                if _glyph_lib[_lib_key] != value:
                    # update only if the name exists and the value doesn't match
                    _glyph_lib[_lib_key] = value
                    _glyph.update()
        else:
            _glyph_lib[_lib_key] = value
            _glyph.update()

    # sbix export stuff

    def rasterize(self, palette_index, sizes=[]):
        """Rasterize the ColorGlyph with the colors of a palette
        in a range of sizes.
            palette_index: Use colors from this palette
            sizes:         A list of sizes in pixels per em"""
        if 0 not in self.bitmaps.keys():
            _page = self._get_drawing(palette_index)
            if _page is not None:
                self.bitmaps[0] = _page.image(ppi=72, kind="rgba").flip(False, True)
            else:
                self.bitmaps[0] = None
        if 0 in self.bitmaps.keys():
            if self.bitmaps[0] is None:
                for size in sizes:
                    self.bitmaps[size] = None
            else:
                for size in sizes:
                    scale = float(size)/self.font.rfont.info.unitsPerEm
                    _width = int(ceil(self.bitmaps[0].width*scale))
                    _height = int(ceil(self.bitmaps[0].height*scale))
                    scale = min(float(_width)/(self.bitmaps[0].width+2), (float(_height)/(self.bitmaps[0].height+2)))
                    self.bitmaps[size] = self.bitmaps[0].resize(
                        int(round(self.bitmaps[0].width * scale)),
                        int(round(self.bitmaps[0].height * scale)),
                        ).png(optimized=False)

    def _get_drawing(self, palette_index=0):
        box = self.get_box()
        if box is None:
            return None
        else:
            width = box[2] - box[0]
            height = box[3] - box[1]
            d = document(width+2, height+2, "pt")
            p = d.addpage()
            # _path = shape.path(shape(), [])
            for i in range(len(self.layers)):
                layer = self.font.rfont[self.layers[i]]
                colorindex = self.colors[i]
                layer_color = self.font._get_fcolor(palette_index, colorindex)
                pen = FlatPen(self.font.rfont)
                layer.draw(pen)
                g = p.place(shape().nostroke().fill(layer_color).path(pen.path))
                g.position(1 - box[0], 1 - box[1])
        return p

    def get_tt_glyph(self):
        """Return a special TT Glyph record for the sbix format. It contains
        two dummy contours with one point (bottom left and top right) each."""
        # make dummy contours
        glyph = TTGlyph()
        glyph.program = NoProgram()
        glyph.numberOfContours = 0
        box = self.get_box()
        if box is not None:
            contours = [
                [(box[0], box[1], 1)],
                [(box[2], box[3], 1)],
            ]
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
                coordinates = GlyphCoordinates(coordinates)
                flags = array.array("B", flags)
                if not hasattr(glyph, "coordinates"):
                    glyph.coordinates = coordinates
                    glyph.flags = flags
                    glyph.endPtsOfContours = [len(coordinates)-1]
                else:
                    glyph.coordinates.extend(coordinates)
                    glyph.flags.extend(flags)
                    glyph.endPtsOfContours.append(len(glyph.coordinates)-1)
                glyph.numberOfContours += 1
        return glyph

    def get_png(self, palette_index, size):
        """Return the ColorGlyph as a PNG image.
            palette_index: Use colors from this palette
            size:          The size in pixels per em"""
        if size not in self.bitmaps.keys():
            self.rasterize(palette_index, [size])
        if self.bitmaps[size] is None:
            return None
        return self.bitmaps[size]

    def get_box(self):
        """Return the total bounding box of all layer glyphs."""
        # Get the bounding box of the composite glyph.
        # Check all layers because they can be bigger than the base glyph.
        box = self.font.rfont[self.basename].box
        for layername in self.layers:
            lbox = self.font.rfont[layername].box
            if lbox is not None:
                box = (min(box[0], lbox[0]), min(box[1], lbox[1]), max(box[2], lbox[2]), max(box[3], lbox[3]))
        return box


class NoProgram(object):
    def toXML(self, writer, ttFont):
        pass

    def getBytecode(self):
        return ''


def test():
    # make PDF for color glyph
    _font = ColorFont(CurrentFont())
    _font.read_from_rfont()
    # _font._export_sbix(r"/Users/jenskutilek/Documents/Color Fonts MS/Dingbats2SamplerOT.ttf", 0, [20, 40, 72, 96, 128, 160, 256, 512], "png")
    # _font.rasterize(0, [16])
    # _font.export_png("six", "/Users/jenskutilek/Desktop/six.png", 0, 1000)
    _font._export_sbix(
        otfpath=r"/Users/jenskutilek/Documents/Color Fonts MS/Dingbats2SamplerOT.ttf",
        palette=0,
        image_format="png",
        replace_outlines=True,
        parent_window=None
    )


if __name__ == "__main__":
    test()
