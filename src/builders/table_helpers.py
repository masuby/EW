"""Table utility functions for python-docx document building."""

from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.table import _Cell
from docx.shared import Pt, Cm, Emu


def set_cell_shading(cell: _Cell, hex_color: str):
    """Apply background color to a table cell.

    Args:
        cell: python-docx table cell
        hex_color: 6-character hex color string (e.g., "D32F2F")
    """
    tc_pr = cell._tc.get_or_add_tcPr()
    # Remove existing shading
    existing = tc_pr.findall(qn('w:shd'))
    for e in existing:
        tc_pr.remove(e)
    shading = OxmlElement('w:shd')
    shading.set(qn('w:val'), 'clear')
    shading.set(qn('w:color'), 'auto')
    shading.set(qn('w:fill'), hex_color)
    tc_pr.append(shading)


def set_cell_borders(cell: _Cell, top=None, bottom=None, left=None, right=None):
    """Set specific borders on a table cell.

    Each border parameter should be a dict with keys: 'sz' (size in eighths of a point),
    'val' (style, e.g., 'single'), 'color' (hex color).
    Pass None to leave unchanged, pass {'val': 'none'} to remove.
    """
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_borders = tc_pr.find(qn('w:tcBorders'))
    if tc_borders is None:
        tc_borders = OxmlElement('w:tcBorders')
        tc_pr.append(tc_borders)

    for edge, border_def in [('top', top), ('bottom', bottom),
                              ('left', left), ('right', right)]:
        if border_def is not None:
            elem = OxmlElement(f'w:{edge}')
            elem.set(qn('w:val'), border_def.get('val', 'single'))
            elem.set(qn('w:sz'), str(border_def.get('sz', 4)))
            elem.set(qn('w:color'), border_def.get('color', '000000'))
            elem.set(qn('w:space'), '0')
            # Remove existing edge if present
            existing = tc_borders.find(qn(f'w:{edge}'))
            if existing is not None:
                tc_borders.remove(existing)
            tc_borders.append(elem)


def remove_all_borders(cell: _Cell):
    """Remove all borders from a table cell."""
    no_border = {'val': 'none', 'sz': 0, 'color': 'FFFFFF'}
    set_cell_borders(cell, top=no_border, bottom=no_border,
                     left=no_border, right=no_border)


def set_cell_width(cell: _Cell, width):
    """Set the width of a table cell.

    Args:
        width: docx.shared dimension (Cm, Inches, Pt, etc.)
    """
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = tc_pr.find(qn('w:tcW'))
    if tc_w is None:
        tc_w = OxmlElement('w:tcW')
        tc_pr.append(tc_w)
    tc_w.set(qn('w:w'), str(int(width)))
    tc_w.set(qn('w:type'), 'dxa')


def set_cell_vertical_alignment(cell: _Cell, align: str = "center"):
    """Set vertical alignment of cell content.

    Args:
        align: "top", "center", or "bottom"
    """
    tc_pr = cell._tc.get_or_add_tcPr()
    v_align = tc_pr.find(qn('w:vAlign'))
    if v_align is None:
        v_align = OxmlElement('w:vAlign')
        tc_pr.append(v_align)
    v_align.set(qn('w:val'), align)


def set_cell_margins(cell: _Cell, top=0, bottom=0, left=0, right=0):
    """Set cell margins/padding in twips (1/20 of a point)."""
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.find(qn('w:tcMar'))
    if tc_mar is None:
        tc_mar = OxmlElement('w:tcMar')
        tc_pr.append(tc_mar)

    for edge, val in [('top', top), ('bottom', bottom),
                      ('start', left), ('end', right)]:
        elem = OxmlElement(f'w:{edge}')
        elem.set(qn('w:w'), str(val))
        elem.set(qn('w:type'), 'dxa')
        existing = tc_mar.find(qn(f'w:{edge}'))
        if existing is not None:
            tc_mar.remove(existing)
        tc_mar.append(elem)


def set_row_height(row, height, rule="exact"):
    """Set the height of a table row.

    Args:
        row: python-docx table row
        height: docx.shared dimension (Cm, Pt, etc.)
        rule: "exact", "atLeast", or "auto"
    """
    tr = row._tr
    tr_pr = tr.get_or_add_trPr()
    tr_height = tr_pr.find(qn('w:trHeight'))
    if tr_height is None:
        tr_height = OxmlElement('w:trHeight')
        tr_pr.append(tr_height)
    tr_height.set(qn('w:val'), str(int(height)))
    tr_height.set(qn('w:hRule'), rule)


def set_paragraph_shading(paragraph, hex_color: str):
    """Apply background shading to an entire paragraph."""
    p_pr = paragraph._p.get_or_add_pPr()
    existing = p_pr.findall(qn('w:shd'))
    for e in existing:
        p_pr.remove(e)
    shading = OxmlElement('w:shd')
    shading.set(qn('w:val'), 'clear')
    shading.set(qn('w:color'), 'auto')
    shading.set(qn('w:fill'), hex_color)
    p_pr.append(shading)


def set_table_fixed_layout(table):
    """Set table layout to fixed (prevents auto-resize of columns)."""
    tbl_pr = table._tbl.tblPr
    if tbl_pr is None:
        tbl_pr = OxmlElement('w:tblPr')
        table._tbl.insert(0, tbl_pr)
    # Remove existing layout
    existing = tbl_pr.find(qn('w:tblLayout'))
    if existing is not None:
        tbl_pr.remove(existing)
    layout = OxmlElement('w:tblLayout')
    layout.set(qn('w:type'), 'fixed')
    tbl_pr.append(layout)


def set_table_width(table, width_twips):
    """Set total table width in twips."""
    tbl_pr = table._tbl.tblPr
    if tbl_pr is None:
        tbl_pr = OxmlElement('w:tblPr')
        table._tbl.insert(0, tbl_pr)
    existing = tbl_pr.find(qn('w:tblW'))
    if existing is not None:
        tbl_pr.remove(existing)
    tbl_w = OxmlElement('w:tblW')
    tbl_w.set(qn('w:w'), str(int(width_twips)))
    tbl_w.set(qn('w:type'), 'dxa')
    tbl_pr.append(tbl_w)


def set_table_col_widths(table, widths_twips):
    """Set explicit grid column widths in twips.

    Args:
        table: python-docx table
        widths_twips: list of widths in twips (1 inch = 1440 twips, 1 cm = 567 twips)
    """
    tbl = table._tbl
    # Remove existing grid
    existing_grid = tbl.find(qn('w:tblGrid'))
    if existing_grid is not None:
        tbl.remove(existing_grid)
    # Create new grid
    grid = OxmlElement('w:tblGrid')
    for w in widths_twips:
        gc = OxmlElement('w:gridCol')
        gc.set(qn('w:w'), str(int(w)))
        grid.append(gc)
    # Insert grid after tblPr
    tbl_pr = tbl.tblPr
    tbl_pr.addnext(grid)

    # Also set each cell's width
    for row in table.rows:
        for i, cell in enumerate(row.cells):
            if i < len(widths_twips):
                set_cell_width(cell, widths_twips[i])


def create_no_border_table(doc, rows: int, cols: int):
    """Create a table with no visible borders."""
    table = doc.add_table(rows=rows, cols=cols)
    table.autofit = True

    # Remove all borders from every cell
    for row in table.rows:
        for cell in row.cells:
            remove_all_borders(cell)

    return table
