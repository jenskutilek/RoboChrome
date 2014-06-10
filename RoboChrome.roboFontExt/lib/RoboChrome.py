import vanilla

from os.path import basename, exists

from AppKit import NSColor
from defconAppKit.windows.baseWindow import BaseWindowController
from fontTools.misc.transform import Offset
from mojo.events import addObserver, removeObserver
from mojo.drawingTools import *
from mojo.canvas import Canvas
from mojo.UI import UpdateCurrentGlyphView, CurrentGlyphWindow, setGlyphViewDisplaySettings, getGlyphViewDisplaySettings
from robofab.interface.all.dialogs import GetFile
import colorfont
reload(colorfont)
from colorfont import ColorFont



class ColorFontEditor(BaseWindowController):

    def __init__(self):
        self.libkey = "com.fontfont.colorfont"
        
        self.font = CurrentFont()
        self.cfont = ColorFont(self.font)
        self.glyph = None
        self.glyphPreview = None
        self.width = 0
        self.palette_index = 0 # currently active palette
        
        self.currentPaletteChanged = False
        self.currentGlyphChanged = False
        
        self.layer_glyphs = []
        self.layer_colors = []
        self.layer_glyphs_glyph_window = []
        self.layer_colors_glyph_window = []
        
        self.show_only_glyphs_with_layers = True
        
        self.color = "#000000"
        self.colorbg = "#ffffff"
        
        self.write_colr = True
        self.write_sbix = True
        self._sbix_sizes = self.cfont.bitmap_sizes
        self.write_cbdt = False
        self.write_svg = False
        self.prefer_placed_images = False
        self._auto_layer_regex_default = r"\.alt[0-9]{3}$"
        self._auto_layer_regex = self._auto_layer_regex_default
        self._auto_layer_regex_ok = True
        
        self.oldDisplaySettings = getGlyphViewDisplaySettings()
        setGlyphViewDisplaySettings({"On Curve Points": False, "Off Curve Points": False})
        
        self.save_settings = True
        
        if self.font is not None:
            self.metrics = (
                self.font.info.descender,
                self.font.info.xHeight,
                self.font.info.capHeight,
                self.font.info.ascender,
                self.font.info.unitsPerEm,
            )
        else:
            self.metrics = (-200, 500, 700, 800, 1000)
            #print "Hey, I work better when there's an open font!"
        self.scale = 180.0 / (self.metrics[3] - self.metrics[0])
        
        palette_columns = [
            {"title": "Index",
            #"cell": IntType, #TODO
            "width": 45},
            {"title": "Color",
            "typingSensitive": True,
            "editable": True},
        ]
        
        column_descriptions = [
            {"title": "Layers",
            "cell": vanilla.CheckBoxListCell(),
            #"cell": "X",
            "width": 35,
            "editable": False},
            {"title": "Name",
            "typingSensitive": True,
            "editable": False},
        ]
        
        layer_columns = [
            {"title": "Index",
            #"cell": vanilla.CheckBoxListCell(),
            "width": 45,
            "editable": True},
            {"title": "Color",
            #"cell": vanilla.CheckBoxListCell(),
            "width": 45,
            "editable": True},
            {"title": "Layer Glyph",
            "typingSensitive": True,
            "editable": True},
        ]
        
        
        width = 500
        col2 = int(round(width/2))
        y = 10
        if self.font:
            title = basename(self.font.fileName)
        else:
            title = "None"
        self.w = vanilla.Window((width, 496), "%s - RoboChrome" % title)
        self.w.preview = Canvas((10, y, 320, 200), canvasSize=(318, 200),
                                hasHorizontalScroller=False,
                                hasVerticalScroller=False,
                                delegate=self)
        self.w.paletteswitch = vanilla.PopUpButton((340, y, -10, 20),
                                                   [],
                                                   callback=self._paletteSwitchCallback)
        self.w.colorpalette  = vanilla.List((340, y+30, -10, 170),
                                            [],
                                            columnDescriptions=palette_columns,
                                            drawFocusRing=True,
                                            editCallback=self.paletteEdit,
                                            selectionCallback=self._callback_color_select_in_palette,
                                            allowsMultipleSelection=False,
                                            # enableDelete=True, # TODO
            )
        self.w.addPalette = vanilla.GradientButton((340, 215, 24, 24),
            imagePath="iconColorFontPalette.pdf",
            callback=self.paletteDuplicate,
        )
        self.w.deletePalette = vanilla.GradientButton((363, 215, 24, 24),
            imagePath="iconColorFontPaletteMinus.pdf",
            callback=self.paletteDelete,
        )
        self.w.addColorToPalette = vanilla.GradientButton((410, 215, 24, 24),
            imagePath="iconColorFontPlus.pdf",
            callback=self.addColorToPalette,
        )
        y += 210
        self.w.glyph_list_label = vanilla.TextBox((10, y, 120, 20), "Glyphs with layers:", sizeStyle="small")
        self.w.glyph_list_search_box = vanilla.SearchBox((118, y-3, 114, 20),
            placeholder="Filter glyphs",
            callback=self._callback_update_ui_glyph_list,
            sizeStyle="small",
        )
        self.w.colorChooser = vanilla.ColorWell((240, y-4, 40, 22), 
            callback=self._callback_color_changed_foreground,
            color=self.getNSColor(self.color),
        )
        self.w.colorbgChooser = vanilla.ColorWell((290, y-4, 40, 22), 
            color=self.getNSColor(self.colorbg),
            callback=self._callback_color_changed_background
        )
        self.w.colorPaletteColorChooser = vanilla.ColorWell((450, y-4, 40, 22), 
            callback=self._callback_color_changed_layer,
            color=self.getNSColor(self.color),
        )
        y += 25
        self.w.glyph_list = vanilla.List((10, y, col2-10, 150),
            [],
            columnDescriptions=column_descriptions,
            drawFocusRing=True,
            #editCallback=None,
            doubleClickCallback=self._callback_goto_glyph,
            selectionCallback=self._callback_ui_glyph_list_selection,
            allowsMultipleSelection=False,
            )
        self.w.layer_list = vanilla.List((col2+10, y, -10, 150),
            [],
            columnDescriptions=layer_columns,
            drawFocusRing=True,
            editCallback=self._callback_layer_edit,
            enableDelete=True,
            selectionCallback=self._callback_layer_select,
            allowsMultipleSelection=False,
            )
        y += 160
        self.w.show_only_glyphs_with_layers = vanilla.CheckBox((10, y, 176, -10), "Show only glyphs with layers",
            callback=self._callback_set_show_only_glyphs_with_layers,
            value=self.show_only_glyphs_with_layers,
            sizeStyle="small"
        )
        self.w.add_layer_button = vanilla.GradientButton((col2+10, y-10, 24, 24),
            imagePath="iconColorFontPlus.pdf",
            callback=self._callback_layer_add,
        )
        y += 28
        self.w.selectButton = vanilla.Button((10, y, col2-10, 20), "Select glyphs with layers",
            callback = self._callback_select_glyphs_in_font_window,
        )
        self.w.auto_palette_button = vanilla.Button((col2+10, y, 110, 20), "Mix palette",
            callback = self._callback_auto_palette,
        )
        self.w.png_button = vanilla.Button((380, y, 110, 20), "Export PNG",
            callback = self._save_png,
        )
        y +=31
        self.w.toggleSettingsButton = vanilla.Button((10, y, 115, 20), "Settings...",
            callback = self._callback_toggle_settings,
        )
        self.w.auto_layer_button = vanilla.Button((135, y, 115, 20), "Auto layers",
            callback = self._callback_auto_layers,
        )
        self.w.import_button = vanilla.Button((col2+10, y, 110, 20), "Import font",
            callback = self._import_from_font,
        )
        self.w.export_button = vanilla.Button((380, y, 110, 20), "Export to font",
            callback = self._export_to_font,
        )
        
        
        # Settings drawer
        self.d = vanilla.Drawer((width, 204), self.w, preferredEdge='bottom', forceEdge=True)
        
        y = 22
        self.d.generate_formats_label = vanilla.TextBox((10, y+2, 160, 20), "Generate formats:", sizeStyle="small")
        y += 20
        self.d.generateMSFormat = vanilla.CheckBox((10, y, 200, -10), "COLR/CPAL (Windows)",
            callback=None,
            value=self.write_colr,
            sizeStyle="small"
        )
        self.d.generateAppleFormat = vanilla.CheckBox((235, y, 200, -10), "sbix (Mac OS/iOS)",
            callback=None,
            value=self.write_sbix,
            sizeStyle="small"
        )
        y += 20
        self.d.generateSVGFormat = vanilla.CheckBox((10, y, 200, -10), "SVG (Mozilla/Adobe)",
            callback=None,
            value=self.write_svg,
            sizeStyle="small",
        )
        self.d.generateGoogleFormat = vanilla.CheckBox((235, y, 200, -10), "CBDT/CBLC (Google)",
            callback=None,
            value=self.write_cbdt,
            sizeStyle="small",
        )
        y += 32
        self.d.generate_sizes_label = vanilla.TextBox((10, y, 160, 20), "Generate bitmap sizes:", sizeStyle="small")
        self.d.auto_layer_suffix_label = vanilla.TextBox((235, y, 160, 20), "Auto layer suffix regex:", sizeStyle="small")
        y += 25
        self.d.generate_sbix_sizes = vanilla.EditText((10, y, 200, 36),
            callback=self._callback_set_sbix_sizes,
            text=self._ui_get_sbix_sizes(),
            sizeStyle="small"
        )
        self.d.auto_layer_regex_box = vanilla.EditText((235, y, 178, 20),
            callback=self._callback_check_regex,
            text=self._auto_layer_regex,
            sizeStyle="small"
        )
        self.d.auto_layer_regex_ok = vanilla.CheckBox((-22, y, 20, 20), "",
            callback=None,
            value=self._auto_layer_regex_ok,
            sizeStyle="small",
        )
        y += 26
        self.d._add_base_layer = vanilla.CheckBox((235, y, -10, 20), "Auto layers include base glyph",
            callback=None,
            value=True,
            sizeStyle="small",
        )
        self.d.preferPlacedImages = vanilla.CheckBox((10, y+16, 280, -10), "Prefer placed images over outlines",
            callback=None,
            value=self.prefer_placed_images,
            sizeStyle="small",
        )
        self.d.infoButton = vanilla.Button((-150, -30, -80, -10), "Debug",
            callback = self._show_svg, # self._show_font_info,
        )
        self.d.resetButton = vanilla.Button((-70, -30, -10, -10), "Reset",
            callback = self._reset_color_data,
        )
        
        
        
        self.setUpBaseWindowBehavior()
        
        self.cfont.read_from_rfont()
        
        self._ui_update_palette_chooser()
        self._ui_update_palette(self.palette_index)
        self._callback_update_ui_glyph_list()
        
        if len(self.cfont) > 0:
            self.w.glyph_list.setSelection([0])
        #self._callback_ui_glyph_list_selection()

        addObserver(self, "_observer_glyph_changed", "currentGlyphChanged")
        addObserver(self, "_observer_draw_glyph_window", "drawBackground")
        addObserver(self, "_observer_draw_glyph_window", "drawInactive")
        #addObserver(self, "removeFontFromList", "fontWillClose")
        #addObserver(self, "updateFontList", "fontDidOpen")
        
        if CurrentGlyph() is not None:
            self.glyphPreview = CurrentGlyph().name
            if self.glyphPreview in self.cfont.keys():
                self.layer_glyphs_glyph_window = self.cfont[self.glyphPreview].layers
                self._cache_color_info_glyph_window()
            UpdateCurrentGlyphView()
        
        # grey out controls that are not implemented yet
        self.d.generateGoogleFormat.enable(False)
        self.d.preferPlacedImages.enable(False)
        
        # disable regex check box, because it is read only
        self.d.auto_layer_regex_ok.enable(False)
        
        if len(self.cfont.keys()) > 0:
            self.w.auto_layer_button.enable(False)
        
        self.w.open()

    def _show_font_info(self, sender=None):
        print self.cfont

    def _import_from_font(self, sender=None):
        _font = -1
        _font = GetFile("Select a font file to import layer and color information from.")
        if _font > -1:
            _cf = ColorFont(CurrentFont())
            _cf.import_from_otf(_font)
            _cf.save_to_rfont()
            _cf.save_all_glyphs_to_rfont()
            self.cfont = _cf
            self._ui_update_palette_chooser()
            self._ui_update_palette(self.palette_index)
            self._callback_update_ui_glyph_list()
            if len(self.cfont) > 0:
                self.w.glyph_list.setSelection([0])

    def _export_to_font(self, sender=None):
        pathkey = "com.typemytype.robofont.compileSettings.path"
        _font = -1
        if pathkey in self.font.lib:
            _font = self.font.lib.get(pathkey)
            if not exists(_font):
                _font = -1
        if _font == -1:
            from robofab.interface.all.dialogs import GetFile
            _font = GetFile("Select a font file to export layer and color information to.")
        
        if _font > -1:
            print "Exporting to", _font
            if _font[-4:].lower() in [".ttf", ".otf"]:
                self.cfont.export_to_otf(_font,
                    write_colr=self.d.generateMSFormat.get(),
                    write_sbix=self.d.generateAppleFormat.get(),
                    write_svg=self.d.generateSVGFormat.get(),
                    palette_index=self.palette_index,
                    bitmap_sizes=self._sbix_sizes,
                    parent_window=self.w,
                )
            else:
                print "ERROR: Can only export color information to TTFs and OTFs."
    
    def _show_svg(self, sender=None):
        pathkey = "com.typemytype.robofont.compileSettings.path"
        _font = -1
        if pathkey in self.font.lib:
            _font = self.font.lib.get(pathkey)
            if not exists(_font):
                _font = -1
        if _font == -1:
            from robofab.interface.all.dialogs import GetFile
            _font = GetFile("Select a font file to export layer and color information to.")
        
        if _font > -1:
            print "Exporting to", _font
            if _font[-4:].lower() in [".ttf", ".otf"]:
                self.cfont.export_to_otf(_font,
                    write_colr=False,
                    write_sbix=False,
                    write_svg=True,
                    palette_index=self.palette_index,
                    bitmap_sizes=self._sbix_sizes,
                    parent_window=self.w,
                )
            else:
                print "ERROR: Can only export color information to TTFs and OTFs."

    def _save_png(self, sender=None):
        # save current glyph as PNG
        from robofab.interface.all.dialogs import PutFile
        _file = -1
        _file = PutFile("Save current glyph as PNG", "%s.png" % self.glyph)
        if _file > -1:
            png_str = self.cfont[self.glyph].get_png(self.palette_index, 1000)
            png = open(_file, "wb")
            png.write(png_str)
            png.close()
        
    
    def _ui_update_layer_list(self):
        # set layer UI for current glyph
        _ui_list = []
        if self.glyph in self.cfont.keys():
            for i in range(len(self.cfont[self.glyph].layers)):
                g = self.cfont[self.glyph].layers[i]
                if g in self.font.keys():
                    _ui_list.append({"Index": str(i), "Color": self.cfont[self.glyph].colors[i], "Layer Glyph": g})
                else:
                    print "Warning: Missing layer glyph '%s' referenced in glyph '%s'." % (g, self.glyph)
        ##print "DEBUG: self.w.layer_list.set(_ui_list)"
        self.w.layer_list.set(_ui_list)
        # cache for faster drawing
        self._cache_layer_info()
        self._cache_color_info()
        
    def _ui_layer_list_save_to_cfont(self):
        ##print "DEBUG ColorFontEditor._ui_layer_list_save_to_cfont"
        if self.glyph is not None:
            if self.glyph in self.cfont.keys():
                layerGlyphs = []
                _layer_colors = []
                for layerDict in sorted(self.w.layer_list.get(), key=lambda k: int(k["Index"])):
                    layerGlyphs.append(layerDict["Layer Glyph"])
                    _layer_colors.append(int(layerDict["Color"]))
                if len(layerGlyphs) > 0 or len(_layer_colors) > 0:
                    _modified = False
                    if self.cfont[self.glyph].layers != layerGlyphs:
                        self.cfont[self.glyph].layers = layerGlyphs
                        _modified = True
                    if self.cfont[self.glyph].colors != _layer_colors:
                        self.cfont[self.glyph].colors = _layer_colors
                        _modified = True
                    if _modified:
                        self.cfont.save_glyph_to_rfont(self.glyph)
                else:
                    # empty layers, delete from lib
                    #print "DEBUG Delete info for glyph", self.glyph
                    del self.cfont[self.glyph]
                    self.cfont.save_glyph_to_rfont(self.glyph)
            #else:
            #    print "  Glyph is not in ColorFont, not saving:", self.glyph
        #else:
        #    print "  Glyph is None."

    def _ui_get_sbix_sizes(self):
        return str(self._sbix_sizes).strip("[]")

    def _reset_color_data(self, sender=None):
        #completely remove color info from UFO
        if self.font is not None:
            # font lib
            if "%s.colorpalette" % self.libkey in self.font.lib.keys():
                del self.font.lib["%s.colorpalette" % self.libkey]
            if "%s.color" % self.libkey in self.font.lib.keys():
                del self.font.lib["%s.color" % self.libkey]
            if "%s.colorbg" % self.libkey in self.font.lib.keys():
                del self.font.lib["%s.colorbg" % self.libkey]
            # glyph lib
            for g in self.font:
                if "%s.layers" % self.libkey in g.lib.keys():
                    del g.lib["%s.layers" % self.libkey]
                    self.layer_glyphs = []
                    self.layer_colors = []
            self.font.update()
        
        # Reset UI
        self.w.colorpalette.set([{"Index": str(0xffff), "Color": "(foreground)"}])
        self.color = "#000000"
        self.colorbg = "#ffffff"
        
        self.cfont.save_settings = False
        self.cfont.palettes = []
        self.cfont = ColorFont(self.font)
        self._callback_update_ui_glyph_list()
        self._callback_ui_glyph_list_selection()
        
        self._sbix_sizes = self.cfont.bitmap_sizes_default
        self._auto_layer_regex = self._auto_layer_regex_default
        self.w.auto_layer_button.enable(True)

    def addColorToPalette(self, sender=None):
        # find a new palette index
        paletteIndices = sorted(self.cfont.palettes[0].keys(), key=lambda k: int(k))
        if len(paletteIndices) > 0:
            newIndex = int(paletteIndices[-1])+1
        else:
            newIndex = 0
        
        if newIndex < 0xffff:
            # add new color to current palette
            self.w.colorpalette.append({"Index": str(newIndex), "Color": "#ffde00"})
            # add new color to all other palettes
            for p in self.cfont.palettes:
                p[newIndex] = "#ffde00"
            self.cfont.save_settings = True
            self.currentPaletteChanged = True
        else:
            print "ERROR: Color Index 0xffff is reserved."
    
    def _get_color_for_layer_color_index(self, index):
        # TODO: unused?
        for c in self.w.colorpalette.get():
            if int(c["Index"]) == index:
                return c["Color"]
        return self.color
    
    def _get_list_index_for_layer_color_index(self, index):
        _palette = self.w.colorpalette.get()
        for i in range(len(_palette)):
            if int(_palette[i]["Index"]) == index:
                return i
        return None
    
    def _cache_layer_info(self):
        # self.layer_glyphs is used for drawing
        _layers = sorted(self.w.layer_list.get(), key=lambda k: int(k["Index"]))
        if _layers == []:
            self.layer_glyphs = [{"Color": 0xffff, "Index": 0, "Layer Glyph": self.glyph}]
        else:
            self.layer_glyphs = _layers
    
    def _cache_color_info(self):
        ##print "DEBUG _cache_color_info"
        # write colors for current glyph to self.layer_colors for faster drawing
        colorDict = self.getColorDict()
        _layer_colors = []
        for g in self.layer_glyphs:
            colorIndex = int(g["Color"])
            if colorIndex == 0xffff:
                _layer_colors.append(self.color)
            else:
                if colorIndex in colorDict.keys():
                    _layer_colors.append(colorDict[colorIndex])
                else:
                    print "Missing color in palette %i: %i" % (self.palette_index, colorIndex)
        self.layer_colors = _layer_colors
    
    def _cache_color_info_glyph_window(self):
        ##print "DEBUG _cache_color_info_glyph_window"
        # write colors for current glyph to self.layer_colors_glyph_window for faster drawing
        _layer_colors = []
        if self.glyphPreview is not None and self.glyphPreview in self.cfont.keys():
            colorDict = self.getColorDict()
            for colorIndex in self.cfont[self.glyphPreview].colors:
                if colorIndex == 0xffff:
                    _layer_colors.append(self.color)
                else:
                    if colorIndex in colorDict.keys():
                        _layer_colors.append(colorDict[colorIndex])
                    else:
                        print "Missing color in palette %i: %i" % (self.palette_index, colorIndex)
        self.layer_colors_glyph_window = _layer_colors
    
    
    # layer callbacks
    
    def _callback_layer_add(self, sender):
        if self.glyph is not None:
            self.save_settings = True
            if CurrentGlyph() is not None:
                newlayer = CurrentGlyph().name
            else:
                newlayer = self.glyph
            _color = self.getSelectedColorIndex()
            if _color is None:
                _color = str(0xffff)
            self.w.layer_list.append({"Index": str(len(self.w.layer_list)+1), "Color": _color, "Layer Glyph": newlayer})
            #self._ui_layer_list_save_to_cfont()
            if not self.glyph in self.cfont.keys():
                #print "DEBUG: Add new layer glyph to cfont"
                self.cfont.add_glyph(self.glyph)
            #self._ui_layer_list_save_to_cfont()
            sel = self.w.glyph_list.getSelection()
            self._callback_update_ui_glyph_list()
            self.w.glyph_list.setSelection(sel)
                
    def _callback_layer_edit(self, sender=None):
        # editing a layer (= change color index or glyph name or z-index)
        ##print "DEBUG: _callback_layer_edit"
        #print "  Sender:", sender.get()
        self._cache_layer_info()
        self._cache_color_info()
        self.w.preview.update()
    
    def _callback_layer_select(self, sender):
        # a layer has been selected in the layers list. Select corresponding color in the palette.
        sel = sender.getSelection()
        layers = sender.get()
        if sel == []:
            self.w.colorpalette.setSelection([])
        else:
            i = layers[sel[0]]["Color"]
            colorIndex = self._get_list_index_for_layer_color_index(int(i))
            if colorIndex is None:
                self.w.colorpalette.setSelection([])
            else:
                self.w.colorpalette.setSelection([colorIndex])
    
    def getNSColor(self, hexrgba):
        # return NSColor for r, g, b, a tuple
        r, g, b, a = self.getTupleColor(hexrgba)
        return NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, a)
    
    def getHexColor(self, nscolor):
        r = int(round(255 * float(nscolor.redComponent())))
        g = int(round(255 * float(nscolor.greenComponent())))
        b = int(round(255 * float(nscolor.blueComponent())))
        a = int(round(255 * float(nscolor.alphaComponent())))
        if a == 1:
            return "#%02x%02x%02x" % (r, g, b)            
        else:
            return "#%02x%02x%02x%02x" % (r, g, b, a)
    
    def getTupleColor(self, hexrgba):
        r = float(int(hexrgba[1:3], 16)) / 255
        g = float(int(hexrgba[3:5], 16)) / 255
        b = float(int(hexrgba[5:7], 16)) / 255
        if len(hexrgba) == 9:
            a = float(int(hexrgba[7:9], 16)) / 255
        else:
            a = 1
        return (r, g, b, a)
    
    def _callback_set_show_only_glyphs_with_layers(self, sender):
        self.show_only_glyphs_with_layers = sender.get()
        self._callback_update_ui_glyph_list()
    
    def _callback_toggle_settings(self, sender):
        self.d.toggle()
    
    def _callback_set_write_sbix(self, sender):
        self.d.generate_sbix_sizes.enable(sender.get())
    
    def _callback_set_sbix_sizes(self, sender):
        sizes_str = sender.get().split(",")
        sizes = []
        for entry in sizes_str:
            entry = entry.strip("[], ")
            if entry != "":
                sizes.append(int(entry))
        print sizes
        self._sbix_sizes = sizes
        self.cfont.bitmap_sizes = sizes
    
    def _callback_color_changed_foreground(self, sender):
        if sender is not None:
            self.color = self.getHexColor(sender.get())
            self._cache_color_info()
            self.w.preview.update()
    
    def _callback_color_changed_background(self, sender):
        if sender is not None:
            self.colorbg = self.getHexColor(sender.get())
            self._cache_color_info()
            self.w.preview.update()
    
    def _callback_color_select_in_palette(self, sender):
        # a color has been selected in the current palette
        i = sender.getSelection()
        if i == []:
            # empty selection
            self.w.colorPaletteColorChooser.enable(False)
        else:
            sel = sender.get()
            selIndex = int(sel[i[0]]["Index"])
            if selIndex == 0xffff:
                # use foreground color
                self.w.colorPaletteColorChooser.set(self.w.colorChooser.get())
                self.w.colorPaletteColorChooser.enable(False)
            else:
                _color = sel[i[0]]["Color"]
                self.w.colorPaletteColorChooser.set(self.getNSColor(_color))
                self.w.colorPaletteColorChooser.enable(True)
    
    def _ui_update_palette_chooser(self):
        pl = []
        for i in range(len(self.cfont.palettes)):
            pl.append("Palette %s" % i)
        self.w.paletteswitch.setItems(pl)
    
    def paletteEdit(self, sender):
        ##print "DEBUG ColorFontEditor.paletteEdit"
        sel = sender.getSelection()
        if sel != []:
            i = sel[0]
            if i < len(self.w.colorpalette):
                if self.w.colorpalette[i] != sender.get()[i]:
                    self.w.colorpalette[i] = sender.get()[i]
                    self.currentPaletteChanged = True
                    print "  Palette changed"
            else:
                print "Ignored edit of foreground color"
        self.w.preview.update()
    
    def _paletteWriteToColorFont(self):
        #print "DEBUG _paletteWriteToColorFont"
        # make a dict for active palette and write it to self.cfont.palettes
        _dict = {}
        for _color in sorted(self.w.colorpalette.get(), key=lambda _key: _key["Index"]):
            if int(_color["Index"]) != 0xffff:
                _dict[str(_color["Index"])] = _color["Color"]
        self.cfont.palettes[self.palette_index] = _dict
        self.cfont.save_to_rfont()
    
    def _paletteSwitchCallback(self, sender):
        # activate a different palette
        # save current palette
        if self.currentPaletteChanged:
            self._paletteWriteToColorFont()
        self._ui_update_palette(sender.get())
        ##print "DEBUG Active Palette is now #%i" % self.palette_index
    
    def paletteDuplicate(self, sender):
        if self.currentPaletteChanged:
            self._paletteWriteToColorFont()
        sp = self.w.paletteswitch.get()
        if sp < len(self.cfont.palettes) and sp >= 0:
            print "Duplicate palette %i ..." % sp
            colorpalette = self.cfont.palettes[sp].copy()
        else:
            colorpalette = {}
        self.cfont.palettes.append(colorpalette)
        self._ui_update_palette_chooser()
        # new palette should be active
        self._ui_update_palette(len(self.cfont.palettes)-1)
    
    def _ui_update_palette(self, palette_index):
        # load a different palette from the color font and show it in UI
        # save the currently selected color index
        selectedColorIndex = self.w.colorpalette.getSelection()
        self.palette_index = palette_index
        if self.palette_index < len(self.cfont.palettes):
            colorpalette = self.cfont.palettes[self.palette_index]
        else:
            colorpalette = {}
        newColorpalette = []
        for k in sorted(colorpalette.keys()):
            newColorpalette.append({"Index": str(k), "Color": colorpalette[k]})
        newColorpalette.append({"Index": str(0xffff), "Color": "(foreground)"})
        
        self.w.colorpalette.set(newColorpalette)
        self.w.colorpalette.setSelection(selectedColorIndex)
        self.w.paletteswitch.set(self.palette_index)
        
        self._cache_color_info()
        self._cache_color_info_glyph_window()
        self.currentPaletteChanged = False
        self.w.preview.update()
        UpdateCurrentGlyphView()
    
    def paletteDelete(self, sender):
        pass
    
    def getSelectedColorIndex(self):
        i = self.w.colorpalette.getSelection()
        if i == []:
            return None
        else:
            return self.w.colorpalette.get()[i[0]]["Index"]
    
    def _callback_color_changed_layer(self, sender):
        if sender is not None:
            #print "Set color in palette"
            _selected_color = self.w.colorpalette.getSelection()
            if _selected_color != []:
                _colors = self.w.colorpalette.get()
                #print "Colors:", _colors
                #print "Selected:", _selected_color[0]
                _colors[_selected_color[0]]["Color"] = self.getHexColor(sender.get())
                self.w.colorpalette.set(_colors)
            self.currentPaletteChanged = True
            self._cache_color_info()
            self.w.preview.update()
    
    def windowCloseCallback(self, sender):
        #print "DEBUG windowCloseCallback"
        #removeObserver(self, "fontDidOpen")
        #removeObserver(self, "fontWillClose")
        removeObserver(self, "currentGlyphChanged")
        removeObserver(self, "drawBackground")
        removeObserver(self, "drawInactive")
        setGlyphViewDisplaySettings(self.oldDisplaySettings)
        self._ui_layer_list_save_to_cfont()
        if self.cfont.save_settings and self.currentPaletteChanged:
            self._paletteWriteToColorFont()
        super(ColorFontEditor, self).windowCloseCallback(sender)
    
    def _callback_ui_glyph_list_selection(self, sender=None):
        # selection changed in the ui glyph list
        if self.glyph is not None:
            # save current glyph layers
            self._ui_layer_list_save_to_cfont()
        sel = self.w.glyph_list.getSelection()
        if sel == []:
            self.w.layer_list.set([])
            self.glyph = None
            self.width = 0
            self.w.add_layer_button.enable(False)
        else:
            self.glyph = self.w.glyph_list[sel[0]]["Name"]
            self.width = self.font[self.glyph].width
            self._ui_update_layer_list()
            self.w.add_layer_button.enable(True)
        self.w.preview.update()
    
    def _callback_update_ui_glyph_list(self, sender=None):
        _match = self.w.glyph_list_search_box.get()
        #print "DEBUG: _callback_update_ui_glyph_list"
        glyphlist = []
        if self.font is not None:
            cfglyphs = self.cfont.keys()
            for n in self.font.glyphOrder:
                if n in cfglyphs:
                    _glyph_has_layers = True
                else:
                    _glyph_has_layers = False
                if not self.show_only_glyphs_with_layers or _glyph_has_layers:
                    if _match == "":
                        glyphlist.append({"Layers": _glyph_has_layers, "Name": n})
                    else:
                        if _match in n:
                            glyphlist.append({"Layers": _glyph_has_layers, "Name": n})
        self.w.glyph_list.set(glyphlist)
        if glyphlist != []:
            self.w.glyph_list.setSelection([0])
    
    def setFill(self, rgba):
        red, green, blue, alpha = rgba
        fill(red, green, blue, alpha)
    
    def getColorDict(self):
        # returns the current UI color palette as dictionary
        _dict = {}
        for _color in self.w.colorpalette.get():
            _dict[int(_color["Index"])] = _color["Color"]
        return _dict
    
    def draw(self):
        if self.font is not None:
            save()
            self.setFill(self.getTupleColor(self.colorbg))
            rect(0, 0, 310, 200)
            self.setFill(self.getTupleColor(self.color))
            #rect(50, 100, 20, 20)
            scale(self.scale)
            translate(50.5, -self.metrics[0]+20.5)
            self._canvas_draw_metrics()
            g = RGlyph()
            for i in range(len(self.layer_glyphs)):
                layerGlyph = self.layer_glyphs[i]["Layer Glyph"]
                if layerGlyph in self.font:
                    if i < len(self.layer_colors):
                        _color = self.layer_colors[i]
                        self.setFill(self.getTupleColor(_color))
                        #mPen = MojoDrawingToolsPen(g, self.font)
                        #mPen.addComponent(layerGlyph, Offset(0, 0))
                        #g.draw(mPen)
                        #mPen.draw()
                        drawGlyph(self.font[layerGlyph])
            restore()

    def _canvas_draw_metrics(self):
        save()
        strokeWidth(1.0/self.scale)
        stroke(0.8, 0.8, 0.8)
        line(0, 0, self.width, 0)
        line(0, self.metrics[0], self.width, self.metrics[0])
        line(0, self.metrics[1], self.width, self.metrics[1])
        line(0, self.metrics[2], self.width, self.metrics[2])
        line(0, self.metrics[3], self.width, self.metrics[3])
        line(0, self.metrics[3], 0, self.metrics[0])
        line(self.width, self.metrics[3], self.width, self.metrics[0])
        restore()

    def _observer_glyph_changed(self, info=None):
        # Current Glyph has changed
        if info is not None:
            if info["glyph"] is not None:
                self.glyphPreview = CurrentGlyph().name
                if self.glyphPreview in self.cfont.keys():
                    self.layer_glyphs_glyph_window = self.cfont[self.glyphPreview].layers
                    self._cache_color_info_glyph_window()
        UpdateCurrentGlyphView()

    def _callback_goto_glyph(self, sender=None):
        newGlyphName = sender.get()[sender.getSelection()[0]]["Name"]
        if CurrentGlyphWindow():
            CurrentGlyphWindow().setGlyphByName(newGlyphName)
        else:
            # TODO: open glyph window?
            pass

    def _callback_select_glyphs_in_font_window(self, sender=None):
        # select all glyphs which have layers.
        self.font.selection = self.cfont.keys()

    def _observer_draw_glyph_window(self, info):
        ##print "DEBUG: _observer_draw_glyph_window"
        if self.glyphPreview in self.cfont.keys():
            ##print "DEBUG: draw glyph"
            save()
            #self.setFill(self.getTupleColor(self.colorbg))
            #rect(0, 0, self.width, 200)
            self.setFill(self.getTupleColor(self.color))
            g = RGlyph()
            for i in range(len(self.layer_glyphs_glyph_window)):
                layerGlyph = self.layer_glyphs_glyph_window[i]
                if layerGlyph in self.font:
                    if i < len(self.layer_colors_glyph_window):
                        _color = self.layer_colors_glyph_window[i]
                        self.setFill(self.getTupleColor(_color))
                        drawGlyph(self.font[layerGlyph])
            restore()

    def _callback_auto_layers(self, sender=None):
        print "Auto layers: %s" % self._auto_layer_regex
        if self._auto_layer_regex is not None:
            self.cfont.auto_layers(self._auto_layer_regex, self.d._add_base_layer.get())
            self.cfont.auto_palette()
            self.cfont.save_to_rfont()
            self.cfont.save_all_glyphs_to_rfont()
            self._ui_update_palette_chooser()
            self._ui_update_palette(self.palette_index)
            self._callback_update_ui_glyph_list()
            if len(self.cfont) > 0:
                self.w.glyph_list.setSelection([0])
            self.w.auto_layer_button.enable(False)
        else:
            print "ERROR: Invalid auto layer regex"
    
    def _callback_auto_palette(self, sender=None):
        self.cfont.auto_palette()
        self.cfont.save_to_rfont()
        self._ui_update_palette_chooser()
        self._ui_update_palette(self.palette_index)

    def _callback_check_regex(self, sender=None):
        # check if the entered regex does compile
        from re import compile
        test_re = sender.get()
        try:
            compile(test_re)
            self.d.auto_layer_regex_ok.set(True)
            self.w.auto_layer_button.enable(True)
            self._auto_layer_regex = test_re
        except:
            self.d.auto_layer_regex_ok.set(False)
            self.w.auto_layer_button.enable(False)
            self._auto_layer_regex = None


OpenWindow(ColorFontEditor)
