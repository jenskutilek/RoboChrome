from AppKit import NSColor, NSCalibratedRGBColorSpace
#from AppKit import NSAttributedString, NSForegroundColorAttributeName # for popup listbox cells
from defconAppKit.windows.baseWindow import BaseWindowController
from fontTools.misc.transform import Offset
from mojo.events import addObserver, removeObserver
from mojo.drawingTools import drawGlyph, fill, line, rect, restore, save, scale, stroke, strokeWidth, translate
from mojo.UI import UpdateCurrentGlyphView, CurrentGlyphWindow
#from mojo.UI import setGlyphViewDisplaySettings, getGlyphViewDisplaySettings
from os.path import basename, exists
from re import search, compile
from RoboChromeUI import get_ui, get_drawer

# Fix import for flat module
import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), "external", "flat", "flat"))
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
        
        self.color = NSColor.blackColor()
        self.colorbg = NSColor.whiteColor()
        self._selected_color_index = None
        
        # live update the canvas when glyphs are edited
        self._debug_enable_live_editing = True
        
        self._auto_layer_regex_ok = True
        
        #self.oldDisplaySettings = getGlyphViewDisplaySettings()
        #setGlyphViewDisplaySettings({"On Curve Points": False, "Off Curve Points": False})
        
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
        
        if self.font:
            title = basename(self.font.fileName)
        else:
            title = "None"

        self.w = get_ui(self, title)
        self.d = get_drawer(self)
        self.setUpBaseWindowBehavior()
        
        # load color data from rfont
        self.cfont.read_from_rfont()
        
        # update ui
        self._callback_update_ui_formats()
        self.d.generate_sbix_sizes.set(self._ui_get_sbix_sizes())
        self.d.auto_layer_regex_box.set(self.cfont.auto_layer_regex)
        self.d._add_base_layer.set(self.cfont.auto_layer_include_baseglyph)
        self.d.preferPlacedImages.set(self.cfont.prefer_placed_images)
        
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
        
        if len(self.cfont) > 0:
            self.w.auto_layer_button.enable(False)
        
        # If sbix or cbdt is inactive, disable bitmap sizes box
        self._check_bitmap_ui_active()
        
        self.w.open()

    #def  _getColorPopupList(self):
    #    # build a list of current palette's colors that can be assigned
    #    # to the color popup in the layer list
    #    # FIXME: It seems the cell's popup list can't be changed easily after
    #    # the list has been built.
    #    return [NSAttributedString.alloc().initWithString_attributes_(str(entry["layer_index"]), {NSForegroundColorAttributeName: entry["Color"]}) for entry in self.w.colorpalette]

    def _show_font_info(self, sender=None):
        print self.cfont

    def _choose_file_to_import(self, sender=None):
        self.showGetFile(["public.opentype-font", "public.truetype-ttf-font"], self._import_from_font)
        
    def _import_from_font(self, file_paths=None):
        if file_paths is not None:
            self.cfont = ColorFont(CurrentFont())
            self.cfont.import_from_otf(file_paths[0])
            self.cfont.save_to_rfont()
            self.cfont.save_all_glyphs_to_rfont()
        
            self._ui_update_palette_chooser()
            self._ui_update_palette(self.palette_index)
            self._callback_update_ui_glyph_list()
        
            if len(self.cfont) > 0:
                self.w.glyph_list.setSelection([0])
    
    def _choose_file_to_export(self, sender=None):
        pathkey = "com.typemytype.robofont.compileSettings.path"
        _font = -1
        if pathkey in self.font.lib:
            _font = self.font.lib.get(pathkey)
            if not exists(_font):
                _font = -1
        if _font == -1:
            self.showPutFile(["public.opentype-font", "public.truetype-ttf-font"], self._export_to_font)
        else:
            self._export_to_font(_font)
    
    def _export_to_font(self, file_path=None):
        print "_export_to_font", file_path
        if file_path is not None:
            if len(self.cfont.palettes[0]) > 0:
                print "Exporting to", file_path
                self.cfont.export_to_otf(file_path,
                    palette_index=self.palette_index,
                    parent_window=self.w,
                )
            else:
                print "ERROR: No color data in UFO."
    
    def _choose_png_to_export(self, sender=None):
        self.showPutFile(["public.png"], self._save_png, "%s.png" % self.glyph)
    
    def _save_png(self, png_path=None):
        # save current glyph as PNG
        if png_path is not None:
            self.cfont.export_png(self.glyph, png_path, self.palette_index, self.font.info.unitsPerEm)
    
    def _ui_update_layer_list(self):
        # set layer UI for current glyph
        _ui_list = []
        if self.glyph in self.cfont.keys():
            for i in range(len(self.cfont[self.glyph].layers)):
                g = self.cfont[self.glyph].layers[i]
                if g in self.font.keys():
                    _ui_list.append({
                            "layer_index": str(i),
                            "layer_color_index": self.cfont[self.glyph].colors[i],
                            #"Color": self._getColorPopupList(),
                            "Layer Glyph": g,
                        })
                else:
                    print "Warning: Missing layer glyph '%s' referenced in glyph '%s'." % (g, self.glyph)
        ##print "DEBUG: self.w.layer_list.set(_ui_list)"
        self.w.layer_list.set(_ui_list)
        # cache for faster drawing
        self._cache_layer_info()
        self._cache_color_info()
        
    def _ui_layer_list_save_to_cfont(self):
        # save the ui layer list to colorfont
        ##print "DEBUG ColorFontEditor._ui_layer_list_save_to_cfont"
        if self.glyph is not None:
            if self.glyph in self.cfont.keys():
                layerGlyphs = []
                _layer_colors = []
                for layerDict in sorted(self.w.layer_list.get(), key=lambda k: int(k["layer_index"])):
                    layerGlyphs.append(layerDict["Layer Glyph"])
                    _layer_colors.append(int(layerDict["layer_color_index"]))
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
        # get the display string for a python list
        return str(self.cfont.bitmap_sizes).strip("[]")

    def _reset_color_data(self, sender=None):
        # completely remove color info from UFO
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
        
        self.cfont = ColorFont(self.font) 
        self.color = self.getNSColor(self.cfont.color)
        self.colorbg = self.getNSColor(self.cfont.colorbg)
        
        # Reset UI
        self.w.colorpalette.set([{"Index": 0xffff, "Color": self.color}])
        self._callback_update_ui_glyph_list()
        self._callback_ui_glyph_list_selection()
        
        self.d.generate_sbix_sizes.set(self._ui_get_sbix_sizes())
        self.d.auto_layer_regex_box.set(self.cfont.auto_layer_regex)
        self.w.auto_layer_button.enable(True)
        self._callback_update_ui_formats()

    def addColorToPalette(self, sender=None):
        # add a new color to the current palette
        
        # find a new palette index
        paletteIndices = sorted(self.cfont.palettes[0].keys(), key=lambda k: int(k))
        if len(paletteIndices) > 0:
            newIndex = int(paletteIndices[-1])+1
        else:
            newIndex = 0
        
        if newIndex < 0xffff:
            # add new color to current palette
            self.w.colorpalette.append({"Index": str(newIndex), "Color": NSColor.yellowColor()})
            # add new color to all other palettes
            for p in self.cfont.palettes:
                p[newIndex] = NSColor.yellowColor()
            self.cfont.save_settings = True
            self.currentPaletteChanged = True
        else:
            print "ERROR: Color Index 0xffff is reserved."
    
    def _get_palette_color_ui_index_for_layer_color_index(self, index):
        # find the index of a color in the palette (= ui list index, not layer_color_index)
        _palette = self.w.colorpalette.get()
        for i in range(len(_palette)):
            if int(_palette[i]["Index"]) == index:
                return i
        return None
    
    def _cache_layer_info(self):
        # self.layer_glyphs is used for drawing
        _layers = sorted(self.w.layer_list.get(), key=lambda k: int(k["layer_index"]))
        if _layers == []:
            self.layer_glyphs = [{
                "layer_color_index": 0xffff,
                #"Color": self._getColorPopupList(),
                "layer_index": 0,
                "Layer Glyph": self.glyph
            }]
        else:
            self.layer_glyphs = _layers
    
    def _cache_color_info(self):
        ##print "DEBUG _cache_color_info"
        # write colors for current glyph to self.layer_colors for faster drawing
        colorDict = self.getColorDict()
        _layer_colors = []
        for g in self.layer_glyphs:
            colorIndex = int(g["layer_color_index"])
            if colorIndex == 0xffff:
                _layer_colors.append(self.color)
            else:
                if colorIndex in colorDict.keys():
                    _layer_colors.append(colorDict[colorIndex])
                else:
                    print "Missing color in palette %i: %i" % (self.palette_index, colorIndex)
        self.layer_colors = _layer_colors
        
        # update color list in layer list popup
        #self.w.layer_list["Color"].set(self._getColorPopupList())
    
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
            self.cfont.save_settings = True
            if CurrentGlyph() is not None:
                newlayer = CurrentGlyph().name
            else:
                newlayer = self.glyph
            _color = self.getSelectedColorIndex()
            if _color is None:
                _color = 0xffff
            self.w.layer_list.append({
                "layer_index": str(len(self.w.layer_list)+1),
                # "Color": self._getColorPopupList(),
                "layer_color_index": _color,
                "Layer Glyph": newlayer,
            })
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
            self._selected_color_index = None
        else:
            i = int(layers[sel[0]]["layer_color_index"])
            self._selected_color_index = self._get_palette_color_ui_index_for_layer_color_index(i)
            if self._selected_color_index is None:
                self.w.colorpalette.setSelection([])
            else:
                self.w.colorpalette.setSelection([self._selected_color_index])
        self.w.preview.update()
    
    """example dropinfo:
        Something was dropped on the layer list:
{'rowIndex': 0, 'source': <objective-c class NSColorPanel at 0x7fff72b29ef0>, 'data': {
    "$archiver" = NSKeyedArchiver;
    "$objects" =     (
        "$null",
                {
            "$class" = "<CFKeyedArchiverUID 0x608000c2d220 [0x7fff70e30f00]>{value = 2}";
            NSColorSpace = 1;
            NSRGB = <30203020 3000>;
        },
                {
            "$classes" =             (
                NSColor,
                NSObject
            );
            "$classname" = NSColor;
        }
    );
    "$top" =     {
        root = "<CFKeyedArchiverUID 0x608000c33260 [0x7fff70e30f00]>{value = 1}";
    };
    "$version" = 100000;
}, 'dropOnRow': False, 'isProposal': True}
    """
    
    def _callback_layer_drop(self, sender=None, dropInfo=None):
        # a color has been dropped on the layer list
        if dropInfo["isProposal"]:
            # TODO: check if drop is acceptable
            return True
        else:
            print "DEBUG: dropped color on row %i" % dropInfo["rowIndex"]
            # TODO: accept the drop (actually do something)
            return True
    
    def _choose_svg_to_import(self, sender=None):
        self.showGetFile(["public.svg-image"], self._layer_add_svg_from_file)
    
    def _layer_add_svg_from_file(self, file_paths=None):
        # Add an SVG from external file
        if file_paths is not None:
            self.cfont.add_svg(self.glyph, file_paths[0])
            sel = self.w.glyph_list.getSelection()
            self._callback_update_ui_glyph_list()
            self.w.glyph_list.setSelection(sel)
    
    def getNSColor(self, hexrgba):
        # get NSColor for a HTML-style hex rgb(a) color
        r = float(int(hexrgba[1:3], 16)) / 255
        g = float(int(hexrgba[3:5], 16)) / 255
        b = float(int(hexrgba[5:7], 16)) / 255
        if len(hexrgba) == 9:
            a = float(int(hexrgba[7:9], 16)) / 255
        return NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, a)
    
    def getHexColor(self, nscolor):
        if nscolor.colorSpaceName != NSCalibratedRGBColorSpace:
            nscolor = nscolor.colorUsingColorSpaceName_(NSCalibratedRGBColorSpace)
        r = int(round(255 * float(nscolor.redComponent())))
        g = int(round(255 * float(nscolor.greenComponent())))
        b = int(round(255 * float(nscolor.blueComponent())))
        a = int(round(255 * float(nscolor.alphaComponent())))
        if a == 1:
            return "#%02x%02x%02x" % (r, g, b)            
        else:
            return "#%02x%02x%02x%02x" % (r, g, b, a)
    
    def _callback_set_show_only_glyphs_with_layers(self, sender):
        self.show_only_glyphs_with_layers = sender.get()
        self._callback_update_ui_glyph_list()
    
    def _callback_toggle_settings(self, sender):
        # show or hide the settings drawer
        self.d.toggle()
        
    def _callback_set_sbix_sizes(self, sender):
        sizes_str = sender.get().split(",")
        sizes = []
        for entry in sizes_str:
            entry = entry.strip("[], ")
            if entry != "":
                sizes.append(int(entry))
        self.cfont.bitmap_sizes = sizes
    
    def _callback_color_changed_foreground(self, sender):
        if sender is not None:
            self.color = sender.get()
            self._ui_update_palette(self.palette_index)
            i = self.w.colorpalette.getSelection()
            if i != []:
                if int(self.w.colorpalette.get()[i[0]]["Index"]) == 0xffff:
                    self.w.colorPaletteColorChooser.set(self.color)
            self._cache_color_info()
            self.w.preview.update()
    
    def _callback_color_changed_background(self, sender):
        if sender is not None:
            self.colorbg = sender.get()
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
                self.w.colorPaletteColorChooser.set(sel[i[0]]["Color"])
                self.w.colorPaletteColorChooser.enable(True)
    
    def _ui_update_palette_chooser(self):
        self.w.paletteswitch.setItems(["Palette %s" % i for i in range(len(self.cfont.palettes))])
    
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
    
    def paletteEditColorCell(self, sender):
        # double-click on a color cell in the palette
        print sender
    
    def _paletteWriteToColorFont(self):
        #print "DEBUG _paletteWriteToColorFont"
        # make a dict for active palette and write it to self.cfont.palettes
        _dict = {}
        for _color in sorted(self.w.colorpalette.get(), key=lambda _key: _key["Index"]):
            if _color["Index"] != 0xffff:
                _dict[str(_color["Index"])] = self.getHexColor(_color["Color"])
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
        newColorpalette = [{"Index": str(k), "Color": self.getNSColor(colorpalette[k])} for k in sorted(colorpalette.keys())]
        newColorpalette.append({"Index": 0xffff, "Color": self.color})
        
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
        # a color has been edited in the palette
        if sender is not None:
            _selected_color = self.w.colorpalette.getSelection()
            if _selected_color != []:
                _colors = self.w.colorpalette.get()
                _colors[_selected_color[0]]["Color"] = sender.get()
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
        #setGlyphViewDisplaySettings(self.oldDisplaySettings)
        self._ui_layer_list_save_to_cfont()
        if self.cfont.save_settings and self.currentPaletteChanged:
            self._paletteWriteToColorFont()
        if self.cfont.save_settings:
            self.cfont.save_to_rfont()
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
            # if no color glyphs in font, show all glyphs in list
            if len(self.cfont.keys()) == 0:
                self.show_only_glyphs_with_layers = False
                self.w.show_only_glyphs_with_layers.set(False)
                self.w.show_only_glyphs_with_layers.enable(False)
            else:
                self.w.show_only_glyphs_with_layers.enable(True)
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
    
    def _callback_update_ui_formats(self, sender=None):
        self.d.generateMSFormat.set(self.cfont.write_colr)
        self.d.generateAppleFormat.set(self.cfont.write_sbix)
        self.d.generateSVGFormat.set(self.cfont.write_svg)
        self.d.generateGoogleFormat.set(self.cfont.write_cbdt)
        self._check_bitmap_ui_active()
        self._check_export_ui_active()
        
    def _callback_select_formats(self, sender=None):
        self.cfont.write_colr = self.d.generateMSFormat.get()
        self.cfont.write_sbix = self.d.generateAppleFormat.get()
        self.cfont.write_svg = self.d.generateSVGFormat.get()
        self.cfont.write_cbdt = self.d.generateGoogleFormat.get()
        self._check_bitmap_ui_active()
        self._check_export_ui_active()
    
    def _check_bitmap_ui_active(self):
        _ui_active = self.cfont.write_sbix or self.cfont.write_cbdt
        self.d.generate_sbix_sizes.enable(_ui_active)
        self.d.preferPlacedImages.enable(_ui_active)
    
    def _check_export_ui_active(self):
        _ui_active = self.cfont.write_sbix or self.cfont.write_cbdt or self.cfont.write_colr or self.cfont.write_svg
        self.w.export_button.enable(_ui_active)
    
    def setFill(self, nscolor, opacity_factor=1):
        # set fill color for mojoDrawingTools, optionally with changed opacity
        if nscolor.colorSpaceName != NSCalibratedRGBColorSpace:
            nscolor = nscolor.colorUsingColorSpaceName_(NSCalibratedRGBColorSpace)
        fill(nscolor.redComponent(), nscolor.greenComponent(), nscolor.blueComponent(), nscolor.alphaComponent() * opacity_factor)
    
    def getColorDict(self):
        # returns the current UI color palette as dictionary {index: nscolor}
        return {int(_color["Index"]): _color["Color"] for _color in self.w.colorpalette.get()}
    
    def draw(self):
        # draw the color glyph on the canvas
        if self.font is not None:
            save()
            self.setFill(self.colorbg)
            rect(0, 0, 310, 200)
            self.setFill(self.color)
            scale(self.scale)
            translate(50.5, -self.metrics[0]+20.5)
            self._canvas_draw_metrics()
            g = RGlyph()
            for i in range(len(self.layer_glyphs)):
                layerGlyph = self.layer_glyphs[i]["Layer Glyph"]
                if self._selected_color_index is None:
                    op_factor = 1.0
                else:
                    if self._selected_color_index == self.layer_glyphs[i]["layer_color_index"]:
                        op_factor = 1.0
                    else:
                        op_factor = 0.2
                if layerGlyph in self.font:
                    if i < len(self.layer_colors):
                        _color = self.layer_colors[i]
                        self.setFill(_color, op_factor)
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
        # draw the color glyph in the glyph window
        ##print "DEBUG: _observer_draw_glyph_window"
        if self.glyphPreview in self.cfont.keys():
            ##print "DEBUG: draw glyph"
            save()
            self.setFill(self.color)
            g = RGlyph()
            for i in range(len(self.layer_glyphs_glyph_window)):
                layerGlyph = self.layer_glyphs_glyph_window[i]
                if layerGlyph in self.font:
                    if i < len(self.layer_colors_glyph_window):
                        _color = self.layer_colors_glyph_window[i]
                        self.setFill(_color)
                        drawGlyph(self.font[layerGlyph])
            restore()
        if self._debug_enable_live_editing:
            self.w.preview.update()

    def _callback_auto_layers(self, sender=None):
        print "Auto layers: %s" % self.cfont.auto_layer_regex
        if self.cfont.auto_layer_regex is not None:
            self.cfont.auto_layers()
            self.cfont.auto_palette()
            self.cfont.save_to_rfont()
            self.cfont.save_all_glyphs_to_rfont()
            self._ui_update_palette_chooser()
            self._ui_update_palette(self.palette_index)
            self._ui_update_layer_list()
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
        test_re = sender.get()
        try:
            compile(test_re)
            self.d.auto_layer_regex_ok.set(True)
            self.w.auto_layer_button.enable(True)
            self.cfont.auto_layer_regex = test_re
            self.d.regex_test_button.enable(True)
        except:
            self.d.auto_layer_regex_ok.set(False)
            self.w.auto_layer_button.enable(False)
            self.cfont.auto_layer_regex = None
            self.d.regex_test_button.enable(False)
    
    def _callback_test_regex(self, sender=None):
        # select glyphs based on current regex
        regex = compile(self.cfont.auto_layer_regex)
        _glyph_list = [glyphname for glyphname in self.font.glyphOrder if regex.search(glyphname)]
        #print "_callback_test_regex matched %i glyphs." % len(_glyph_list)
        self.font.selection = _glyph_list
    
    def _callback_prefer_placed_images(self, sender=None):
        self.cfont.prefer_placed_images = sender.get()
        
    def _callback_auto_layer_include_baseglyph(self, sender=None):
        self.cfont.auto_layer_include_baseglyph = sender.get()

if __name__ == "__main__":
    OpenWindow(ColorFontEditor)
