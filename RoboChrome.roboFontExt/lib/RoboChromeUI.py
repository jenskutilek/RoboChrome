from Cocoa import NSColorPboardType
from lib.cells.colorCell import RFColorCell
from mojo.canvas import Canvas
import vanilla

window_width = 500


def get_ui(window_controller, title):

    glyph_column_descriptions = [
        {
            "title": "Layers",
            "cell": vanilla.CheckBoxListCell(),
            "width": 35,
            "editable": False,
        },
        {
            "title": "Name",
            "typingSensitive": True,
            "editable": False,
        },
    ]

    layer_column_descriptions = [
        {
            "title": "Index",
            "key": "layer_index",
            "width": 45,
            "editable": True,
        },
        {
            "title": "ColorIndex",
            "key": "layer_color_index",
            "width": 45,
            "editable": True,
        },
        # {
        #     "title": "Color",
        #     "binding": "selectedValue",
        #     "cell": vanilla.PopUpButtonListCell([]),
        #     "width": 30,
        #     "editable": True,
        # },
        {
            "title": "Layer Glyph",
            "typingSensitive": True,
            "editable": True,
        },
    ]

    palette_column_descriptions = [
        {
            "title": "Index",
            # "cell": IntType, #TODO
            "width": 60,
            "typingSensitive": True,
        },
        {
            "title": "Color",
            "cell": RFColorCell.alloc().initWithDoubleClickCallback_(window_controller.paletteEditColorCell),
            "typingSensitive": False,
            "editable": False,
        },
    ]

    layer_drop_settings = {
        "type": NSColorPboardType,
        "allowDropBetweenRows": False,
        "allowDropOnRow": True,
        "callback": window_controller._callback_layer_drop,
    }

    col2 = int(round(window_width/2))
    y = 10

    w = vanilla.Window(
        (window_width, 496),
        "%s - RoboChrome" % title
    )
    w.preview = Canvas(
        (10, y, 320, 200),
        canvasSize=(318, 200),
        hasHorizontalScroller=False,
        hasVerticalScroller=False,
        delegate=window_controller,
    )
    w.paletteswitch = vanilla.PopUpButton(
        (340, y, -10, 20),
        [],
        callback=window_controller._paletteSwitchCallback,
    )
    w.colorpalette = vanilla.List(
        (340, y+30, -10, 170),
        [],
        columnDescriptions=palette_column_descriptions,
        drawFocusRing=True,
        editCallback=window_controller.paletteEdit,
        selectionCallback=window_controller._callback_color_select_in_palette,
        allowsMultipleSelection=False,
        enableDelete=True,
    )
    w.addPalette = vanilla.GradientButton(
        (340, 215, 24, 24),
        imagePath="../resources/iconColorFontPalette.pdf",
        callback=window_controller.paletteDuplicate,
    )
    w.deletePalette = vanilla.GradientButton(
        (363, 215, 24, 24),
        imagePath="../resources/iconColorFontPaletteMinus.pdf",
        callback=window_controller.paletteDelete,
    )
    w.addColorToPalette = vanilla.GradientButton(
        (410, 215, 24, 24),
        imagePath="../resources/iconColorFontPlus.pdf",
        callback=window_controller.addColorToPalette,
    )
    y += 210
    w.glyph_list_label = vanilla.TextBox(
        (10, y, 120, 20),
        "Glyphs with layers:",
        sizeStyle="small"
    )
    w.glyph_list_search_box = vanilla.SearchBox(
        (118, y-3, 114, 20),
        placeholder="Filter glyphs",
        callback=window_controller._callback_update_ui_glyph_list,
        sizeStyle="small",
    )
    w.colorChooser = vanilla.ColorWell(
        (240, y-4, 40, 22), 
        callback=window_controller._callback_color_changed_foreground,
        color=window_controller.color,
    )
    w.colorbgChooser = vanilla.ColorWell(
        (290, y-4, 40, 22), 
        color=window_controller.colorbg,
        callback=window_controller._callback_color_changed_background
    )
    w.colorPaletteColorChooser = vanilla.ColorWell(
        (450, y-4, 40, 22), 
        callback=window_controller._callback_color_changed_layer,
        color=window_controller.color,
    )
    y += 25
    w.glyph_list = vanilla.List(
        (10, y, col2-10, 150),
        [],
        columnDescriptions=glyph_column_descriptions,
        drawFocusRing=True,
        #editCallback=None,
        doubleClickCallback=window_controller._callback_goto_glyph,
        selectionCallback=window_controller._callback_ui_glyph_list_selection,
        allowsMultipleSelection=False,
        )
    w.layer_list = vanilla.List(
        (col2+10, y, -10, 150),
        [],
        columnDescriptions=layer_column_descriptions,
        drawFocusRing=True,
        editCallback=window_controller._callback_layer_edit,
        enableDelete=True,
        selectionCallback=window_controller._callback_layer_select,
        allowsMultipleSelection=False,
        otherApplicationDropSettings=layer_drop_settings,
        )
    y += 160
    w.show_only_glyphs_with_layers = vanilla.CheckBox(
        (10, y, 176, 20),
        "Show only glyphs with layers",
        callback=window_controller._callback_set_show_only_glyphs_with_layers,
        value=window_controller.show_only_glyphs_with_layers,
        sizeStyle="small"
    )
    w.add_layer_button = vanilla.GradientButton(
        (col2+10, y-10, 24, 24),
        imagePath="../resources/iconColorFontPlus.pdf",
        callback=window_controller._callback_layer_add,
    )
    # w.add_svg_button = vanilla.Button(
    #     (col2+43, y-10, 60, 24),
    #     "Add SVG",
    #     callback=window_controller._choose_svg_to_import,
    #     sizeStyle="small"
    # )
    y += 28
    w.selectButton = vanilla.Button(
        (10, y, col2-10, 20),
        "Select glyphs with layers",
        callback=window_controller._callback_select_glyphs_in_font_window,
    )
    w.auto_palette_button = vanilla.Button(
        (col2+10, y, 110, 20),
        "Mix palette",
        callback=window_controller._callback_auto_palette,
    )
    w.png_button = vanilla.Button(
        (380, y, 110, 20),
        "Export PNG",
        callback=window_controller._choose_png_to_export,
    )
    y += 31
    w.toggleSettingsButton = vanilla.Button(
        (10, y, 115, 20),
        "Settings...",
        callback=window_controller._callback_toggle_settings,
    )
    w.auto_layer_button = vanilla.Button(
        (135, y, 115, 20),
        "Auto layers",
        callback=window_controller._callback_auto_layers,
    )
    w.import_button = vanilla.Button(
        (col2+10, y, 110, 20),
        "Import font",
        callback=window_controller._choose_file_to_import,
    )
    w.export_button = vanilla.Button(
        (380, y, 110, 20),
        "Export to font",
        callback=window_controller._choose_file_to_export,
    )

    return w


def get_drawer(window_controller):
    # Settings drawer
    d = vanilla.Drawer(
        (window_width, 204),
        window_controller.w,
        preferredEdge='bottom',
        forceEdge=True
    )

    y = 22
    d.generate_formats_label = vanilla.TextBox(
        (10, y+2, 160, 20),
        "Generate formats:",
        sizeStyle="small"
    )
    y += 20
    d.generateMSFormat = vanilla.CheckBox(
        (10, y, 200, 20),
        "COLR/CPAL (Windows)",
        callback=window_controller._callback_select_formats,
        value=False,
        sizeStyle="small"
    )
    d.generateAppleFormat = vanilla.CheckBox(
        (235, y, 200, 20),
        "sbix (Mac OS/iOS)",
        callback=window_controller._callback_select_formats,
        value=False,
        sizeStyle="small"
    )
    y += 20
    d.generateSVGFormat = vanilla.CheckBox(
        (10, y, 200, 20),
        "SVG (Mozilla/Adobe)",
        callback=window_controller._callback_select_formats,
        value=False,
        sizeStyle="small",
    )
    d.generateGoogleFormat = vanilla.CheckBox(
        (235, y, 200, 20),
        "CBDT/CBLC (Google)",
        callback=window_controller._callback_select_formats,
        value=False,
        sizeStyle="small",
    )
    y += 32
    d.generate_sizes_label = vanilla.TextBox(
        (10, y, 160, 20),
        "Generate bitmap sizes:",
        sizeStyle="small"
    )
    d.auto_layer_suffix_label = vanilla.TextBox(
        (235, y, 160, 20),
        "Auto layer suffix regex:",
        sizeStyle="small"
    )
    d.regex_test_button = vanilla.Button(
        (-70, y-3, -30, 20),
        "Test",
        callback=window_controller._callback_test_regex,
        sizeStyle="small",
    )
    y += 25
    d.generate_sbix_sizes = vanilla.EditText(
        (10, y, 200, 36),
        callback=window_controller._callback_set_sbix_sizes,
        text="",
        sizeStyle="small"
    )
    d.auto_layer_regex_box = vanilla.EditText(
        (235, y, 178, 20),
        callback=window_controller._callback_check_regex,
        text="",
        sizeStyle="small"
    )
    d.auto_layer_regex_ok = vanilla.CheckBox(
        (-22, y, 20, 20),
        "",
        callback=None,
        value=window_controller._auto_layer_regex_ok,
        sizeStyle="small",
    )
    y += 26
    d._add_base_layer = vanilla.CheckBox(
        (235, y, -10, 20),
        "Auto layers include base glyph",
        callback=window_controller._callback_auto_layer_include_baseglyph,
        value=False,
        sizeStyle="small",
    )
    d.preferPlacedImages = vanilla.CheckBox(
        (10, y+16, 280, 20),
        "Prefer placed images over outlines",
        callback=window_controller._callback_prefer_placed_images,
        value=False,
        sizeStyle="small",
    )
    d.infoButton = vanilla.Button(
        (-150, -30, -80, -10),
        "Debug",
        callback=window_controller._show_font_info,
    )
    d.resetButton = vanilla.Button(
        (-70, -30, -10, -10),
        "Reset",
        callback=window_controller._reset_color_data,
    )

    return d
