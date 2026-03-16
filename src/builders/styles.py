"""Styling constants extracted from reference PDF analysis."""

from docx.shared import Pt, Inches, Cm, RGBColor

# --- Page Setup (A4) ---
PAGE_WIDTH = Cm(21.0)
PAGE_HEIGHT = Cm(29.7)
MARGIN_TOP = Cm(1.27)
MARGIN_BOTTOM = Cm(1.27)
MARGIN_LEFT = Cm(1.27)
MARGIN_RIGHT = Cm(1.27)

# --- Colors ---
COLOR_BLUE_TMA = RGBColor(0x00, 0x70, 0xC0)       # TMA header text + issue line
COLOR_RED_MAJOR = RGBColor(0xD3, 0x2F, 0x2F)       # MAJOR WARNING / TAHADHARI KUBWA
COLOR_ORANGE_WARNING = RGBColor(0xE6, 0x7E, 0x22)  # WARNING / TAHADHARI
COLOR_YELLOW_ADVISORY = RGBColor(0xF1, 0xC4, 0x0F)  # ADVISORY / ANGALIZO label bg
COLOR_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
COLOR_BLACK = RGBColor(0x00, 0x00, 0x00)
COLOR_DARK_TEAL = RGBColor(0x1B, 0x6B, 0x72)       # Hazard panel headers (rain/waves/wind)
COLOR_DARK_BLUE = RGBColor(0x2E, 0x5F, 0xA1)       # Hazard panel header (floods)
COLOR_LIGHT_BLUE_BG = RGBColor(0xD6, 0xE8, 0xF0)   # Section heading bar background
COLOR_GRAY_PLACEHOLDER = RGBColor(0xCC, 0xCC, 0xCC)  # Map placeholder background
COLOR_DARK_GRAY = RGBColor(0x33, 0x33, 0x33)        # Day heading text

# Hex string versions (for XML manipulation)
HEX_RED_MAJOR = "D32F2F"
HEX_ORANGE_WARNING = "E67E22"
HEX_YELLOW_ADVISORY = "F1C40F"
HEX_DARK_TEAL = "1B6B72"
HEX_DARK_BLUE = "2E5FA1"
HEX_LIGHT_BLUE_BG = "D6E8F0"
HEX_GRAY_PLACEHOLDER = "CCCCCC"
HEX_WHITE = "FFFFFF"

# Alert level color mapping (hex)
ALERT_COLORS = {
    "MAJOR_WARNING": HEX_RED_MAJOR,
    "WARNING": HEX_ORANGE_WARNING,
    "ADVISORY": HEX_YELLOW_ADVISORY,
}

# Alert level text color mapping
ALERT_TEXT_COLORS = {
    "MAJOR_WARNING": COLOR_WHITE,
    "WARNING": COLOR_WHITE,
    "ADVISORY": COLOR_BLACK,
}

# Hazard panel header colors (hex)
HAZARD_HEADER_COLORS = {
    "HEAVY_RAIN": HEX_DARK_TEAL,
    "LARGE_WAVES": HEX_DARK_TEAL,
    "STRONG_WIND": HEX_DARK_TEAL,
    "FLOODS": HEX_DARK_BLUE,
}

# --- Fonts ---
FONT_PRIMARY = "Times New Roman"
FONT_FALLBACK = "Calibri"

# --- Font Sizes ---
SIZE_TITLE_LARGE = Pt(16)
SIZE_TITLE = Pt(14)
SIZE_SUBTITLE = Pt(12)
SIZE_BODY = Pt(11)
SIZE_BODY_SMALL = Pt(10)
SIZE_FOOTER = Pt(8)
SIZE_NO_WARNING = Pt(24)
SIZE_LABEL = Pt(10)
SIZE_SMALL = Pt(9)
SIZE_TINY = Pt(7)

# --- Map Image Dimensions ---
# 722E_4 maps (landscape) — matched to reference PDF measurements
MAP_DAY1_WIDTH = Cm(10.0)    # Reference: 10.1cm
MAP_DAY1_HEIGHT = Cm(7.8)    # Reference: 7.9cm
MAP_SMALL_WIDTH = Cm(5.0)    # Reference: ~5.0cm
MAP_SMALL_HEIGHT = Cm(4.5)   # Reference: ~4.5cm
MAP_PANEL_WIDTH = Cm(4.3)    # Multirisk hazard panel map
MAP_PANEL_HEIGHT = Cm(6.0)
MAP_SUMMARY_WIDTH = Cm(7.5)  # Multirisk summary map
MAP_SUMMARY_HEIGHT = Cm(9.5)

# --- Logo Dimensions ---
LOGO_COAT_WIDTH = Cm(1.8)
LOGO_COAT_HEIGHT = Cm(1.8)
LOGO_TMA_WIDTH = Cm(1.5)
LOGO_TMA_HEIGHT = Cm(1.5)
LOGO_PARTNER_WIDTH = Cm(2.5)
LOGO_PARTNER_HEIGHT = Cm(1.2)
