"""Build GDP_2025_Analysis_Dashboard.xlsx from analysis/source_data.json.

source_data.json holds numbers extracted from GDP_model_forecasting_2025.xlsx and the
Department of Treasury resource production sheet (2024 vs 2025). Every result in the
workbook is a live Excel formula, so changing an input cell updates the dashboard.

    python3 analysis/build_dashboard.py
"""
import json
import os

from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.chart.legend import Legend
from openpyxl.chart.label import DataLabelList
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, "source_data.json")))
OUT = os.path.join(HERE, "GDP_2025_Analysis_Dashboard.xlsx")

# ---- style: follows the colour code of GDP_model_forecasting_2025.xlsx -------------
FONT = "Arial"
RED = "C00000"     # hard numbers (data)
BLUE = "0000FF"    # assumptions
BLACK = "000000"   # formulas
GREEN = "008000"   # links to another tab
YELLOW = PatternFill("solid", fgColor="FFF2CC")   # assumption / judgement cells you may edit
HEAD = PatternFill("solid", fgColor="1F3864")
SUB = PatternFill("solid", fgColor="D9E1F2")
TOTAL = PatternFill("solid", fgColor="E2EFDA")
KPI = PatternFill("solid", fgColor="FCE4D6")
thin = Side(style="thin", color="BFBFBF")
BOX = Border(top=thin, bottom=thin, left=thin, right=thin)

KM = '#,##0;(#,##0);"-"'
KM1 = '#,##0.0;(#,##0.0);"-"'
PCT = '0.0%;(0.0%);"-"'
RATIO = "0.000"
VOL = "#,##0.000"


def f(color=BLACK, bold=False, size=10, italic=False, white=False):
    return Font(name=FONT, color="FFFFFF" if white else color, bold=bold, size=size, italic=italic)


def put(ws, ref, value, color=BLACK, fmt=None, bold=False, fill=None, note=None, wrap=False, italic=False):
    c = ws[ref]
    c.value = value
    c.font = f(color, bold, italic=italic)
    if fmt:
        c.number_format = fmt
    if fill:
        c.fill = fill
    if note:
        c.comment = Comment(note, "GDP dashboard")
    if wrap:
        c.alignment = Alignment(wrap_text=True, vertical="top")
    return c


def header(ws, row, labels, col=1):
    for i, lab in enumerate(labels):
        c = ws.cell(row, col + i, lab)
        c.font = f(bold=True, white=True)
        c.fill = HEAD
        c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        c.border = BOX
    ws.row_dimensions[row].height = 32


def title(ws, text, sub=None):
    ws["A1"].value = text
    ws["A1"].font = f(bold=True, size=14, color="1F3864")
    if sub:
        ws["A2"].value = sub
        ws["A2"].font = f(italic=True, color="595959")


def widths(ws, ws_widths):
    for col, w in ws_widths.items():
        ws.column_dimensions[col].width = w


def box(ws, r1, r2, c1, c2):
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            ws.cell(r, c).border = BOX


wb = Workbook()

# =====================================================================================
# 1. Guide
# =====================================================================================
g = wb.active
g.title = "Guide"
g.sheet_properties.tabColor = "1F3864"
title(g, "GDP Model - Analysis Dashboard (2025 estimate)",
      "A simple companion to GDP_model_forecasting_2025.xlsx and the 'GDP Model - Theory and Forecast' slides")
lines = [
    ("WHAT THIS WORKBOOK DOES", None),
    ("It rebuilds the 2025 constant-price (real) GDP estimate step by step, using the same method as the "
     "forecasting model, so you can see where every number comes from. 2024 is the base (actual NSO numbers); "
     "2025 is estimated from commodity-board volumes, government wages and judgement growth rates.", None),
    ("", None),
    ("THE THREE WAYS TO MEASURE GDP (slide 2)", None),
    ("Expenditure approach", "GDP = C + I + G + X - M  (household & government consumption, investment, exports less imports)"),
    ("Income approach", "GDP = wages & salaries + business profits + self-employed income + taxes on products - subsidies"),
    ("Production approach  <- this model", "GDP = sum over industries of (output - intermediate inputs) + taxes on products - subsidies"),
    ("", None),
    ("HOW THE FORECAST WORKS (slides 5-7)", None),
    ("Key idea", "Intermediate input shares are held constant, so real (constant-price) growth of value added = growth in physical volume."),
    ("Resource sector", "Real GVA 2025 = Real GVA 2024 x (2025 volume / 2024 volume), per commodity, using Dept. of Treasury volumes. "
                        "Nominal GVA also multiplies by the commodity price growth ratio."),
    ("Agriculture, forestry & fishing", "Formal commodities grow with their industry volumes (cocoa, coffee, palm oil, logs, fish...). "
                                        "Informal activity (food gardens, betel nut, informal fishing) grows with population."),
    ("Public admin, health, education", "Nominal growth = growth in government compensation of employees. "
                                        "Deflator growth = government wage growth. Real growth = nominal growth / deflator growth."),
    ("All other sectors", "Default: grow with population (2.6%). Override with a judgement growth rate where you have evidence (comments from the model are shown)."),
    ("Real -> nominal GDP", "Nominal GDP = real GDP x GDP deflator (IPD) / 100."),
    ("Contribution to growth", "Sector contribution (percentage points) = change in sector real GVA / total real GDP last year. Contributions add up to GDP growth."),
    ("", None),
    ("HOW TO USE IT", None),
    ("1. Dashboard", "Headline numbers, contributions to growth and charts. Read this first."),
    ("2. Resource", "Paste new DoT production numbers into the red cells; resource GVA updates automatically."),
    ("3. AFF", "Commodity-board volumes for agriculture, forestry and fishing; informal growth assumption."),
    ("4. Public_Admin", "Government compensation of employees and wage growth."),
    ("5. Other_Sectors", "Type a judgement growth rate in the yellow column to override the population default. Try it and watch the Dashboard change."),
    ("6. History", "Actual GDP 1993-2024 series (2006 onward shown) with the 2025 estimate appended."),
    ("7. Model_Check", "Issues found in GDP_model_forecasting_2025.xlsx that stop its 2025 column from calculating."),
    ("", None),
    ("COLOUR CODE (same as the forecasting model)", None),
    ("Red numbers", "Hard-coded data (NSO national accounts, DoT production, commodity boards)"),
    ("Blue numbers", "Assumptions (price growth, wage growth, population growth)"),
    ("Black numbers", "Formulas - do not type over these"),
    ("Yellow shading", "Assumptions or judgement calls you are expected to review and change"),
    ("", None),
    ("UNITS", "Kina millions unless stated. Growth rates are percent. Volumes as reported by DoT / commodity boards."),
]
r = 4
for a, b in lines:
    if b is None and a.isupper():
        put(g, f"A{r}", a, bold=True).fill = SUB
        g.merge_cells(f"A{r}:B{r}")
    elif b is None:
        put(g, f"A{r}", a, wrap=True)
        g.merge_cells(f"A{r}:B{r}")
        if a:
            g.row_dimensions[r].height = 42
    else:
        put(g, f"A{r}", a, bold=True, wrap=True)
        put(g, f"B{r}", b, wrap=True)
        if len(b) > 95:
            g.row_dimensions[r].height = 28
    r += 1
for rr in range(4, r):
    if g[f"A{rr}"].value == "Red numbers":
        g[f"A{rr}"].font = f(RED, True)
    if g[f"A{rr}"].value == "Blue numbers":
        g[f"A{rr}"].font = f(BLUE, True)
    if g[f"A{rr}"].value == "Yellow shading":
        g[f"A{rr}"].fill = YELLOW
widths(g, {"A": 34, "B": 120})

# =====================================================================================
# 2. Resource
# =====================================================================================
rs = wb.create_sheet("Resource")
rs.sheet_properties.tabColor = "70AD47"
title(rs, "Resource sector - 2025 estimate from Dept. of Treasury production volumes",
      "Step 1: production volumes (red, from DoT sheet). Step 2: volume growth x 2024 GVA = 2025 real GVA.")
header(rs, 4, ["Production (DoT)", "2024", "2025", "% change"])
row = 5
totals = {}           # commodity -> row of its total volume
current = None
dot = D["dot"]
i = 0
while i < len(dot):
    lab, v24, v25 = dot[i]
    lab = str(lab).strip()
    if lab in ("MINING", "OIL & GAS"):
        put(rs, f"A{row}", lab, bold=True).fill = SUB
        for c in "BCD":
            rs[f"{c}{row}"].fill = SUB
        row += 1
        i += 1
        continue
    if v24 is None and v25 is None:            # commodity heading
        current = lab
        put(rs, f"A{row}", lab, bold=True)
        row += 1
        i += 1
        continue
    # total line: followed by mine lines until next heading
    j = i + 1
    mines = []
    while j < len(dot) and not (dot[j][1] is None and dot[j][2] is None) and \
            str(dot[j][0]).strip() not in ("MINING", "OIL & GAS"):
        mines.append(dot[j])
        j += 1
    trow = row
    totals[current] = trow
    put(rs, f"A{trow}", lab, bold=True)
    if mines:
        first, last = trow + 1, trow + len(mines)
        for col in "BC":
            put(rs, f"{col}{trow}", f"=SUM({col}{first}:{col}{last})", fmt=VOL, bold=True)
        for k, (ml, m24, m25) in enumerate(mines):
            rr = trow + 1 + k
            put(rs, f"A{rr}", "    " + str(ml).strip())
            put(rs, f"B{rr}", m24, RED, VOL)
            put(rs, f"C{rr}", m25, RED, VOL)
            put(rs, f"D{rr}", f'=IF(B{rr}=0,"n/a",C{rr}/B{rr}-1)', fmt=PCT)
        row = last + 1
    else:
        put(rs, f"B{trow}", v24, RED, VOL, bold=True)
        put(rs, f"C{trow}", v25, RED, VOL, bold=True)
        row = trow + 1
    put(rs, f"D{trow}", f'=IF(B{trow}=0,"n/a",C{trow}/B{trow}-1)', fmt=PCT, bold=True)
    i = j
dot_end = row - 1
box(rs, 4, dot_end, 1, 4)
put(rs, f"A{row}", "Source: Resource Production numbers 2024 & 2025, Dept. of Treasury (user-supplied file). "
    "Paste next year's numbers into the red cells.", italic=True)

vol_map = {"Petroleum (oil)": "Petroleum", "LNG": "Gas", "Condensate": "Condensate", "Copper": "Copper",
           "Gold": "Gold", "Silver": "Silver", "Nickel": "Nickel", "Cobalt": "Cobalt"}
sub_map = {"Petroleum (oil)": "Oil & Gas", "LNG": "Oil & Gas", "Condensate": "Oil & Gas"}

calc0 = 4
cc = "F"  # calculation table starts in column F
hdr = ["Commodity", "Sub-sector", "Volume 2024", "Volume 2025", "Volume growth ratio",
       "Real GVA 2024 (K m)", "Real GVA 2025 (K m)", "Real growth %", "Price growth ratio 2025",
       "Nominal GVA 2024 (K m)", "Nominal GVA 2025 (K m)", "Nominal growth %"]
header(rs, calc0, hdr, col=6)
r0 = calc0 + 1
res_rows = {}
for k, (name, v) in enumerate(D["resource"].items()):
    rr = r0 + k
    res_rows[name] = rr
    put(rs, f"F{rr}", name, bold=True)
    put(rs, f"G{rr}", sub_map.get(name, "Mining"))
    if name in vol_map:
        tr = totals[vol_map[name]]
        put(rs, f"H{rr}", f"=B{tr}", fmt=VOL)
        put(rs, f"I{rr}", f"=C{tr}", fmt=VOL)
        put(rs, f"J{rr}", f"=IF(H{rr}=0,1,I{rr}/H{rr})", fmt=RATIO)
    else:
        put(rs, f"H{rr}", "n/a")
        put(rs, f"I{rr}", "n/a")
        put(rs, f"J{rr}", 1.031, BLUE, RATIO, fill=YELLOW,
            note="No DoT volumes for household / small-scale mining. Model assumes 3.1% real growth "
                 "(its historical rate). Change if you have better information.")
    put(rs, f"K{rr}", v["con24"], RED, KM1, note="2024 constant-price GVA, NSO (Resource Sector tab)")
    put(rs, f"L{rr}", f"=K{rr}*J{rr}", fmt=KM1)
    put(rs, f"M{rr}", f"=J{rr}-1", fmt=PCT)
    put(rs, f"N{rr}", v["price25"], BLUE, RATIO, fill=YELLOW,
        note="2025 price growth ratio from 'Price Data & Assumptions' in the forecasting model "
             "(1.10 = prices up 10%). Condensate uses Brent crude as a proxy.")
    put(rs, f"O{rr}", v["cur24"], RED, KM1, note="2024 current-price GVA, NSO")
    put(rs, f"P{rr}", f"=O{rr}*J{rr}*N{rr}", fmt=KM1)
    put(rs, f"Q{rr}", f"=IF(O{rr}=0,0,P{rr}/O{rr}-1)", fmt=PCT)
rl = r0 + len(D["resource"]) - 1
RS_TOT = {}
for k, (lab, crit) in enumerate([("Oil & Gas", "Oil & Gas"), ("Mining", "Mining"), ("RESOURCE SECTOR TOTAL", None)]):
    rr = rl + 1 + k
    RS_TOT[lab] = rr
    put(rs, f"F{rr}", lab, bold=True)
    for col in "KLOP":
        if crit:
            frm = f'=SUMIF($G${r0}:$G${rl},"{crit}",{col}${r0}:{col}${rl})'
        else:
            frm = f"=SUM({col}{r0}:{col}{rl})"
        put(rs, f"{col}{rr}", frm, fmt=KM1, bold=True)
    put(rs, f"M{rr}", f"=IF(K{rr}=0,0,L{rr}/K{rr}-1)", fmt=PCT, bold=True)
    put(rs, f"Q{rr}", f"=IF(O{rr}=0,0,P{rr}/O{rr}-1)", fmt=PCT, bold=True)
    for c in range(6, 18):
        rs.cell(rr, c).fill = TOTAL
box(rs, calc0, rl + 3, 6, 17)
n = rl + 5
notes = [
    "How to read this table:",
    "Volume growth ratio = 2025 volume / 2024 volume (1.149 means volume up 14.9%).",
    "Real GVA 2025 = Real GVA 2024 x volume growth ratio  (intermediate input share held constant, slide 5).",
    "Nominal GVA 2025 = Nominal GVA 2024 x volume growth ratio x price growth ratio.",
    "Implied price deflator change = nominal growth vs real growth - e.g. gold: volume +15%, price +54%.",
]
for k, t in enumerate(notes):
    put(rs, f"F{n + k}", t, bold=(k == 0), italic=(k > 0))
widths(rs, {"A": 40, "B": 11, "C": 11, "D": 10, "E": 3, "F": 26, "G": 11, "H": 11, "I": 11, "J": 11,
            "K": 12, "L": 12, "M": 10, "N": 11, "O": 12, "P": 12, "Q": 10})
rs.freeze_panes = "A5"

# =====================================================================================
# 3. AFF
# =====================================================================================
af = wb.create_sheet("AFF")
af.sheet_properties.tabColor = "70AD47"
title(af, "Agriculture, Forestry & Fishing - 2025 real GVA",
      "Formal commodities grow with industry volumes (commodity boards); informal activity grows with population.")
put(af, "A3", "Informal sector growth (population growth, 2025)", bold=True)
put(af, "E3", D["pop_growth_25_assump"] / 100, BLUE, PCT, fill=YELLOW,
    note="'Other Assumptions'!AI18 in the forecasting model (population growth 2025)")
header(af, 5, ["Component", "Group", "Method", "Volume 2024 ('000 t / m3)", "Volume 2025",
               "Growth ratio", "Real GVA 2024 (K m)", "Real GVA 2025 (K m)", "Real growth %"])
r0 = 6
for k, a in enumerate(D["aff"]):
    rr = r0 + k
    put(af, f"A{rr}", a["name"], bold=True)
    put(af, f"B{rr}", a["group"])
    if a["method"] == "volume":
        put(af, f"C{rr}", "Industry volume")
        put(af, f"D{rr}", a["v24"], RED, VOL)
        put(af, f"E{rr}", a["v25"], RED, VOL,
            note="2025 volume as entered in the forecasting model's AFF tab (commodity boards / industry)")
        put(af, f"F{rr}", f"=IF(D{rr}=0,1,E{rr}/D{rr})", fmt=RATIO)
    elif a["method"] == "model":
        put(af, f"C{rr}", "Model assumption")
        put(af, f"F{rr}", 1 + a["growth"], BLUE, RATIO, fill=YELLOW,
            note="Formal livestock: model assumes nominal +15% deflated by livestock price growth (AFF tab rows 151-155)")
    else:
        put(af, f"C{rr}", "Population")
        put(af, f"F{rr}", f"=1+$E$3", fmt=RATIO)
    put(af, f"G{rr}", a["con24"], RED, KM1, note="2024 constant-price GVA, NSO (AFF tab)")
    put(af, f"H{rr}", f"=G{rr}*F{rr}", fmt=KM1)
    put(af, f"I{rr}", f"=F{rr}-1", fmt=PCT)
rl = r0 + len(D["aff"]) - 1
AF_TOT = {}
for k, grp in enumerate(["Crop & animal", "Forestry", "Fishing", "AFF TOTAL"]):
    rr = rl + 1 + k
    AF_TOT[grp] = rr
    put(af, f"A{rr}", grp if grp == "AFF TOTAL" else f"{grp} total", bold=True)
    for col in "GH":
        frm = f"=SUM({col}{r0}:{col}{rl})" if grp == "AFF TOTAL" else \
            f'=SUMIF($B${r0}:$B${rl},"{grp}",{col}${r0}:{col}${rl})'
        put(af, f"{col}{rr}", frm, fmt=KM1, bold=True)
    put(af, f"I{rr}", f"=IF(G{rr}=0,0,H{rr}/G{rr}-1)", fmt=PCT, bold=True)
    for c in range(1, 10):
        af.cell(rr, c).fill = TOTAL
box(af, 5, rl + 4, 1, 9)
put(af, f"A{rl + 6}", "Note: cocoa volumes jump 46% (41k -> 60k t) in the model inputs - check this with the Cocoa Board "
    "before relying on it; it alone adds ~K180m to real AFF GVA.", italic=True)
widths(af, {"A": 26, "B": 14, "C": 18, "D": 14, "E": 12, "F": 11, "G": 13, "H": 13, "I": 11})
af.freeze_panes = "A6"

# =====================================================================================
# 4. Public administration, health & education
# =====================================================================================
pa = wb.create_sheet("Public_Admin")
pa.sheet_properties.tabColor = "70AD47"
title(pa, "Public Administration, Education & Health - 2025 estimate",
      "Nominal growth = growth in government compensation of employees; deflator growth = government wage growth (slide 7).")
put(pa, "A4", "Govt compensation of employees 2024 (K m)", bold=True)
put(pa, "B4", D["coe"]["2024"], RED, KM1, note="Government Expenditure tab, forecasting model")
put(pa, "A5", "Govt compensation of employees 2025 (K m)", bold=True)
put(pa, "B5", D["coe"]["2025"], RED, KM1, note="Government Expenditure tab (2025 budget), forecasting model")
put(pa, "A6", "Nominal growth = CoE growth", bold=True)
put(pa, "B6", "=B5/B4-1", fmt=PCT)
put(pa, "A7", "Government wage growth (deflator growth)", bold=True)
put(pa, "B7", D["wage_growth_25"] / 100, BLUE, PCT, fill=YELLOW, note="'Other Assumptions'!AI20")
put(pa, "A8", "Implied real growth = (1+nominal)/(1+deflator) - 1", bold=True)
put(pa, "B8", "=(1+B6)/(1+B7)-1", fmt=PCT)
box(pa, 4, 8, 1, 2)
header(pa, 10, ["Sub-sector", "Nominal GVA 2024", "Real GVA 2024", "IPD 2024", "Nominal GVA 2025",
                "IPD 2025", "Real GVA 2025", "Real growth %"])
for k, p in enumerate(D["pa"]):
    rr = 11 + k
    put(pa, f"A{rr}", p["name"], bold=True)
    put(pa, f"B{rr}", p["cur24"], RED, KM1)
    put(pa, f"C{rr}", p["con24"], RED, KM1)
    put(pa, f"D{rr}", f"=B{rr}/C{rr}*100", fmt="0.0")
    put(pa, f"E{rr}", f"=B{rr}*(1+$B$6)", fmt=KM1)
    put(pa, f"F{rr}", f"=D{rr}*(1+$B$7)", fmt="0.0")
    put(pa, f"G{rr}", f"=E{rr}/F{rr}*100", fmt=KM1)
    put(pa, f"H{rr}", f"=G{rr}/C{rr}-1", fmt=PCT)
PA_TOT = 14
put(pa, "A14", "TOTAL", bold=True)
for col in "BCEG":
    put(pa, f"{col}14", f"=SUM({col}11:{col}13)", fmt=KM1, bold=True)
put(pa, "D14", "=B14/C14*100", fmt="0.0", bold=True)
put(pa, "F14", "=E14/G14*100", fmt="0.0", bold=True)
put(pa, "H14", "=G14/C14-1", fmt=PCT, bold=True)
for c in range(1, 9):
    pa.cell(14, c).fill = TOTAL
box(pa, 10, 14, 1, 8)
put(pa, "A16", "IPD (implicit price deflator) = nominal / real x 100. It measures the price level relative to the base year.",
    italic=True)
widths(pa, {"A": 46, "B": 14, "C": 14, "D": 10, "E": 15, "F": 10, "G": 14, "H": 12})

# =====================================================================================
# 5. Other sectors (BLS) and taxes
# =====================================================================================
os_ = wb.create_sheet("Other_Sectors")
os_.sheet_properties.tabColor = "70AD47"
title(os_, "Other sectors - population default or your judgement",
      "Leave the yellow column blank to use the default growth; type a rate (e.g. 4%) to override it.")
put(os_, "A3", "Default growth for sectors without data (population growth)", bold=True)
put(os_, "D3", D["bls_default_growth"] / 100, BLUE, PCT, fill=YELLOW,
    note="'Summary and Charts'!AI50 in the forecasting model (implied population growth)")
header(os_, 5, ["Sector", "Real GVA 2024 (K m)", "Judgement growth (optional)", "Growth used",
                "Real GVA 2025 (K m)", "Reasoning recorded in the model"])
r0 = 6
for k, b in enumerate(D["bls"]):
    rr = r0 + k
    put(os_, f"A{rr}", b["name"], bold=True)
    put(os_, f"B{rr}", b["con24"], RED, KM1)
    put(os_, f"C{rr}", None, BLUE, PCT, fill=YELLOW)
    put(os_, f"D{rr}", f'=IF(C{rr}="",$D$3,C{rr})', fmt=PCT)
    put(os_, f"E{rr}", f"=B{rr}*(1+D{rr})", fmt=KM1)
    put(os_, f"F{rr}", b["comment"], wrap=True, italic=True)
    if b["comment"] and len(str(b["comment"])) > 80:
        os_.row_dimensions[rr].height = 30
rl = r0 + len(D["bls"]) - 1
OS_TOT = rl + 1
put(os_, f"A{OS_TOT}", "TOTAL OTHER SECTORS", bold=True)
put(os_, f"B{OS_TOT}", f"=SUM(B{r0}:B{rl})", fmt=KM1, bold=True)
put(os_, f"E{OS_TOT}", f"=SUM(E{r0}:E{rl})", fmt=KM1, bold=True)
put(os_, f"D{OS_TOT}", f"=E{OS_TOT}/B{OS_TOT}-1", fmt=PCT, bold=True)
for c in range(1, 7):
    os_.cell(OS_TOT, c).fill = TOTAL
box(os_, 5, OS_TOT, 1, 6)
TX = OS_TOT + 3
header(os_, TX - 1, ["Taxes less subsidies on products", "Real 2024 (K m)", "", "Growth", "Real 2025 (K m)", "Source"])
put(os_, f"A{TX}", "Taxes less subsidies (constant prices)", bold=True)
put(os_, f"B{TX}", D["taxes"]["con24"], RED, KM1)
put(os_, f"E{TX}", D["taxes"]["con25"], BLUE, KM1, fill=YELLOW,
    note="From the forecasting model: 2025 nominal taxes less subsidies deflated by the tax IPD")
put(os_, f"D{TX}", f"=E{TX}/B{TX}-1", fmt=PCT)
put(os_, f"F{TX}", "Forecasting model: GDP Constant Price GVA row 35 (nominal revenue forecast / tax IPD)", italic=True)
box(os_, TX - 1, TX, 1, 6)
put(os_, f"A{TX + 2}", "Tip: the model's comments say Construction should be strong (higher govt capital spending, Connect PNG) and "
    "Transport ~7% (Air Niugini / PNG Air fleet, Porgera restart). Try entering those rates and watch the Dashboard.",
    italic=True)
widths(os_, {"A": 46, "B": 14, "C": 14, "D": 11, "E": 14, "F": 90})
os_.freeze_panes = "A6"

# =====================================================================================
# 6. Dashboard
# =====================================================================================
db = wb.create_sheet("Dashboard", 1)
db.sheet_properties.tabColor = "1F3864"
title(db, "PNG GDP 2025 Estimate - Dashboard", "Production approach, constant 2013 prices. Kina millions. All cells are formulas - change inputs on the green tabs.")

groups = [
    ("Oil & Gas", f"=Resource!K{RS_TOT['Oil & Gas']}", f"=Resource!L{RS_TOT['Oil & Gas']}", "Resource"),
    ("Mining", f"=Resource!K{RS_TOT['Mining']}", f"=Resource!L{RS_TOT['Mining']}", "Resource"),
    ("Agriculture, forestry & fishing", f"=AFF!G{AF_TOT['AFF TOTAL']}", f"=AFF!H{AF_TOT['AFF TOTAL']}", "Non-resource"),
    ("Public admin, education & health", f"=Public_Admin!C{PA_TOT}", f"=Public_Admin!G{PA_TOT}", "Non-resource"),
    ("Other sectors (manufacturing, services...)", f"=Other_Sectors!B{OS_TOT}", f"=Other_Sectors!E{OS_TOT}", "Non-resource"),
    ("Taxes less subsidies on products", f"=Other_Sectors!B{TX}", f"=Other_Sectors!E{TX}", "Non-resource"),
]
T0 = 12
header(db, T0, ["Sector", "Type", "Real GVA 2024", "Real GVA 2025", "Real growth %",
                "Share of GDP 2025", "Contribution to growth (pp)"])
for k, (name, a, b, typ) in enumerate(groups):
    rr = T0 + 1 + k
    put(db, f"A{rr}", name, bold=True)
    put(db, f"B{rr}", typ)
    put(db, f"C{rr}", a, GREEN, KM)
    put(db, f"D{rr}", b, GREEN, KM)
    put(db, f"E{rr}", f"=IF(C{rr}=0,0,D{rr}/C{rr}-1)", fmt=PCT)
    put(db, f"F{rr}", f"=D{rr}/$D${T0 + 7}", fmt=PCT)
    put(db, f"G{rr}", f"=(D{rr}-C{rr})/$C${T0 + 7}*100", fmt="0.00")
GT = T0 + 7
put(db, f"A{GT}", "GDP (constant prices)", bold=True)
for col in "CD":
    put(db, f"{col}{GT}", f"=SUM({col}{T0 + 1}:{col}{T0 + 6})", fmt=KM, bold=True)
put(db, f"E{GT}", f"=D{GT}/C{GT}-1", fmt=PCT, bold=True)
put(db, f"F{GT}", f"=SUM(F{T0 + 1}:F{T0 + 6})", fmt=PCT, bold=True)
put(db, f"G{GT}", f"=SUM(G{T0 + 1}:G{T0 + 6})", fmt="0.00", bold=True)
for c in range(1, 8):
    db.cell(GT, c).fill = TOTAL
for k, typ in enumerate(["Resource", "Non-resource"]):
    rr = GT + 1 + k
    put(db, f"A{rr}", f"  of which {typ} GDP", italic=True)
    for col in "CD":
        put(db, f"{col}{rr}", f'=SUMIF($B${T0 + 1}:$B${T0 + 6},"{typ}",{col}${T0 + 1}:{col}${T0 + 6})', fmt=KM)
    put(db, f"E{rr}", f"=D{rr}/C{rr}-1", fmt=PCT)
    put(db, f"F{rr}", f"=D{rr}/$D${GT}", fmt=PCT)
    put(db, f"G{rr}", f'=SUMIF($B${T0 + 1}:$B${T0 + 6},"{typ}",G${T0 + 1}:G${T0 + 6})', fmt="0.00")
RES_R, NRES_R = GT + 1, GT + 2
box(db, T0, NRES_R, 1, 7)

# nominal
NM = NRES_R + 2
header(db, NM, ["Nominal GDP", "", "2024", "2025", "Growth %", "", ""])
put(db, f"A{NM + 1}", "GDP deflator (IPD, 2013 = 100)", bold=True)
put(db, f"C{NM + 1}", D["gdp_ipd"]["2024"], RED, "0.0")
put(db, f"D{NM + 1}", D["gdp_ipd"]["2025"], BLUE, "0.0", fill=YELLOW,
    note="Forecasting model IPD!AI37: 2024 IPD grown by the 2025 GDP deflator assumption (Price Data & Assumptions row 108)")
put(db, f"E{NM + 1}", f"=D{NM + 1}/C{NM + 1}-1", fmt=PCT)
put(db, f"A{NM + 2}", "Nominal GDP = real GDP x IPD / 100", bold=True)
put(db, f"C{NM + 2}", f"=C{GT}*C{NM + 1}/100", fmt=KM)
put(db, f"D{NM + 2}", f"=D{GT}*D{NM + 1}/100", fmt=KM)
put(db, f"E{NM + 2}", f"=D{NM + 2}/C{NM + 2}-1", fmt=PCT)
put(db, f"A{NM + 3}", "Population", bold=True)
put(db, f"C{NM + 3}", D["history"]["population"][-1], RED, "#,##0")
put(db, f"D{NM + 3}", f"=C{NM + 3}*(1+Other_Sectors!D3)", fmt="#,##0")
put(db, f"E{NM + 3}", f"=D{NM + 3}/C{NM + 3}-1", fmt=PCT)
put(db, f"A{NM + 4}", "Real GDP per person (Kina)", bold=True)
put(db, f"C{NM + 4}", f"=C{GT}*1000000/C{NM + 3}", fmt="#,##0")
put(db, f"D{NM + 4}", f"=D{GT}*1000000/D{NM + 3}", fmt="#,##0")
put(db, f"E{NM + 4}", f"=D{NM + 4}/C{NM + 4}-1", fmt=PCT)
box(db, NM, NM + 4, 1, 5)

# check
CK = NM + 6
put(db, f"A{CK}", "Check: 2024 real GDP here vs forecasting model", bold=True)
put(db, f"C{CK}", f"=C{GT}", fmt=KM)
put(db, f"D{CK}", D["check"]["real24"], RED, KM, note="'GDP Constant Price GVA'!AH37 in the forecasting model")
put(db, f"E{CK}", f'=IF(ABS(C{CK}-D{CK})<5,"OK - matches","Check inputs")', bold=True)

# KPI tiles (rows 4-9)
kpis = [
    ("A", "Real GDP growth 2025", f"=E{GT}", PCT),
    ("C", "Real GDP 2025 (K m)", f"=D{GT}", KM),
    ("E", "Non-resource growth", f"=E{NRES_R}", PCT),
    ("G", "Resource growth", f"=E{RES_R}", PCT),
]
for col, lab, frm, fmt in kpis:
    c2 = get_column_letter(db[f"{col}4"].column + 1)
    db.merge_cells(f"{col}4:{c2}4")
    db.merge_cells(f"{col}5:{c2}6")
    put(db, f"{col}4", lab, bold=True, fill=KPI).alignment = Alignment(horizontal="center")
    c = put(db, f"{col}5", frm, fmt=fmt, fill=KPI)
    c.font = f(bold=True, size=20, color="1F3864")
    c.alignment = Alignment(horizontal="center", vertical="center")
kp2 = [
    ("A", "Nominal GDP 2025 (K m)", f"=D{NM + 2}", KM),
    ("C", "Nominal GDP growth", f"=E{NM + 2}", PCT),
    ("E", "GDP deflator growth", f"=E{NM + 1}", PCT),
    ("G", "Real GDP per person", f"=E{NM + 4}", PCT),
]
for col, lab, frm, fmt in kp2:
    c2 = get_column_letter(db[f"{col}8"].column + 1)
    db.merge_cells(f"{col}8:{c2}8")
    db.merge_cells(f"{col}9:{c2}10")
    put(db, f"{col}8", lab, bold=True, fill=SUB).alignment = Alignment(horizontal="center")
    c = put(db, f"{col}9", frm, fmt=fmt, fill=SUB)
    c.font = f(bold=True, size=16, color="1F3864")
    c.alignment = Alignment(horizontal="center", vertical="center")

# Resource volume table for chart
RV = CK + 3
header(db, RV, ["Resource commodity", "Volume change 2025", "Real GVA change (K m)"])
for k, name in enumerate(D["resource"].keys()):
    rr = RV + 1 + k
    put(db, f"A{rr}", name)
    put(db, f"B{rr}", f"=Resource!M{res_rows[name]}", GREEN, PCT)
    put(db, f"C{rr}", f"=Resource!L{res_rows[name]}-Resource!K{res_rows[name]}", GREEN, KM1)
RVL = RV + len(D["resource"])
box(db, RV, RVL, 1, 3)

# reading notes
RN = RVL + 2
put(db, f"A{RN}", "How to read this", bold=True).fill = SUB
for c in range(2, 8):
    db.cell(RN, c).fill = SUB
for k, t in enumerate([
    "Real growth uses constant 2013 prices, so it measures change in volume of production only - not price changes.",
    "Contribution (pp) = how many percentage points of total GDP growth come from that sector. They add up to total growth.",
    "A big sector growing slowly can contribute more than a small sector growing fast - compare columns E and G.",
    "Nominal GDP adds price changes (the deflator). Gold and copper prices push nominal resource GVA up far more than real.",
    "Resource GDP is volatile (one mine or LNG shutdown swings it); non-resource GDP is what most people feel.",
]):
    put(db, f"A{RN + 1 + k}", f"- {t}", italic=True)
widths(db, {"A": 40, "B": 16, "C": 16, "D": 16, "E": 14, "F": 14, "G": 16, "H": 14})

# =====================================================================================
# 7. History
# =====================================================================================
hs = wb.create_sheet("History")
hs.sheet_properties.tabColor = "4472C4"
title(hs, "GDP history 2006-2024 (NSO actuals, from the forecasting model) + 2025 estimate",
      "Kina millions. Constant prices are 2013 prices.")
H = D["history"]
cols = ["Year", "Nominal GDP (K bn)", "Real GDP (K bn)", "Real growth %", "Nominal growth %",
        "GDP deflator", "Oil & Gas", "Mining", "AFF", "Public admin, educ & health", "Other sectors",
        "Taxes less subsidies", "Resource share of real GDP", "Population", "Real GDP per person (K)"]
header(hs, 4, cols)
for k, y in enumerate(H["years"]):
    rr = 5 + k
    put(hs, f"A{rr}", str(y), bold=True)
    put(hs, f"B{rr}", H["nominal"][k], RED, "0.0")
    put(hs, f"C{rr}", H["real"][k], RED, "0.0")
    if k:
        put(hs, f"D{rr}", f"=C{rr}/C{rr - 1}-1", fmt=PCT)
        put(hs, f"E{rr}", f"=B{rr}/B{rr - 1}-1", fmt=PCT)
    put(hs, f"F{rr}", f"=B{rr}/C{rr}*100", fmt="0.0")
    for col, key in zip("GHIJKL", ["oil_gas", "mining", "aff", "pahe", "bls", "taxes"]):
        put(hs, f"{col}{rr}", H[key][k], RED, KM)
    put(hs, f"M{rr}", f"=(G{rr}+H{rr})/SUM(G{rr}:L{rr})", fmt=PCT)
    put(hs, f"N{rr}", H["population"][k], RED, "#,##0")
    put(hs, f"O{rr}", f"=C{rr}*1000000000/N{rr}", fmt="#,##0")
E25 = 5 + len(H["years"])
put(hs, f"A{E25}", "2025e", bold=True)
put(hs, f"B{E25}", f"=Dashboard!D{NM + 2}/1000", GREEN, "0.0")
put(hs, f"C{E25}", f"=Dashboard!D{GT}/1000", GREEN, "0.0")
put(hs, f"D{E25}", f"=C{E25}/C{E25 - 1}-1", fmt=PCT)
put(hs, f"E{E25}", f"=B{E25}/B{E25 - 1}-1", fmt=PCT)
put(hs, f"F{E25}", f"=B{E25}/C{E25}*100", fmt="0.0")
for col, rr_ in zip("GHIJKL", range(T0 + 1, T0 + 7)):
    put(hs, f"{col}{E25}", f"=Dashboard!D{rr_}", GREEN, KM)
put(hs, f"M{E25}", f"=(G{E25}+H{E25})/SUM(G{E25}:L{E25})", fmt=PCT)
put(hs, f"N{E25}", f"=Dashboard!D{NM + 3}", GREEN, "#,##0")
put(hs, f"O{E25}", f"=C{E25}*1000000000/N{E25}", fmt="#,##0")
for c in range(1, 16):
    hs.cell(E25, c).fill = YELLOW
box(hs, 4, E25, 1, 15)
put(hs, f"A{E25 + 2}", "Source: 'Summary and Charts' tab of GDP_model_forecasting_2025.xlsx (NSO national accounts). "
    "2025e row (yellow) is this workbook's estimate. Note: big jumps in 2014-2015 are PNG LNG starting production.",
    italic=True)
widths(hs, {get_column_letter(c): 13 for c in range(1, 16)})
hs.column_dimensions["A"].width = 8
hs.freeze_panes = "B5"

# =====================================================================================
# 8. Model check
# =====================================================================================
mc = wb.create_sheet("Model_Check")
mc.sheet_properties.tabColor = "C00000"
title(mc, "Issues found in GDP_model_forecasting_2025.xlsx",
      "Why the model's 2025+ columns show DIV/0 errors or zero, and how this workbook handles each one.")
header(mc, 4, ["#", "Where (sheet / cells)", "What is wrong", "Effect", "Suggested fix (handled here as...)"])
issues = [
    ("Resource Sector, column AI (2025): mine-level volume rows e.g. 61-64, 83, 99, 120, 137-148, 165-174, 190, 206",
     "2025 production volumes have not been entered.",
     "Volume growth = 0/2024, so resource GVA 2025 = 0 and 2026+ = DIV/0 errors. Total GDP 2025 cannot be calculated.",
     "Paste the DoT 2025 numbers (this workbook's Resource tab uses them)."),
    ("Resource Sector rows 190 & 206 (Nickel, Cobalt industry volumes)",
     "These are typed numbers, not SUMs of mine rows like gold/silver.",
     "Fine for 2024 but the 2025 cell is empty.", "Enter Ramu 2025 volume (DoT: nickel 32,846 t, cobalt 3,088 t)."),
    ("Resource Sector row 215 (HH constant price growth ratio) 2025+",
     "Blank - no assumption entered.", "HH GVA 2025 = 0.",
     "Enter 1.031 (3.1% historical growth) - used here as a yellow assumption."),
    ("Public Administration rows 5-6, 13-14, 21-22, 29-30, column AI onward",
     "2025 GVA cells are empty (no formula yet).",
     "Public admin, education and health = 0 in 2025, pulling GDP down by ~K8bn.",
     "Nominal = 2024 x (1 + CoE growth); IPD = 2024 IPD x (1 + wage growth); real = nominal / IPD (slide 7)."),
    ("AFF rows 60-64, 99-103, 112-116, 125-129, 138-142, 161-165, 174-178 (formal commodities)",
     "2025 real GVA is computed as current-price growth / price growth, but 2025 current-price GVA is blank.",
     "DIV/0 errors for AFF 2025, which flows to GDP.",
     "Use volume growth (row 'Volumes from Industry') like coffee already does (row 77) - matches slide 5."),
    ("AFF rows 74, 80, 87, 100, 113 (2023 column)", "REF errors in 2023 constant-price GVA / growth.",
     "Historical growth rates for coffee, tea, copra and copra oil cannot be read.", "Re-link to the NSO 2023 numbers."),
    ("Summary and Charts rows 58-79 (judgement growth)",
     "Comments are written but no growth rates entered.",
     "All other sectors fall back to population growth (2.6%), ignoring the reasoning in the comments.",
     "Type the chosen rates - this workbook's Other_Sectors tab has a column for them."),
    ("Summary and Charts row 4 (current price GDP) 2025+",
     "No formula beyond 2024.", "Nominal GDP and nominal growth % show -100% / DIV/0 errors.",
     "Link to 'GDP Current Price GVA'!AI37/1000 like row 5 does for real GDP."),
    ("Summary row 50 vs 'Other Assumptions' row 18",
     "Two population growth rates: 2.645% (implied, used for sectors) vs 2.6% (used for informal AFF).",
     "Small inconsistency.", "Pick one source; both are kept here so the numbers match the model."),
]
for k, (where, what, eff, fix) in enumerate(issues):
    rr = 5 + k
    put(mc, f"A{rr}", k + 1, bold=True)
    put(mc, f"B{rr}", where, wrap=True)
    put(mc, f"C{rr}", what, wrap=True)
    put(mc, f"D{rr}", eff, wrap=True)
    put(mc, f"E{rr}", fix, wrap=True)
    mc.row_dimensions[rr].height = 58
box(mc, 4, 4 + len(issues), 1, 5)
widths(mc, {"A": 4, "B": 42, "C": 42, "D": 42, "E": 50})

# =====================================================================================
# Charts on the dashboard
# =====================================================================================
def style_chart(ch, t, w=16, h=7.5):
    ch.title = t
    ch.width, ch.height = w, h
    ch.legend = None
    ch.x_axis.delete = False
    ch.y_axis.delete = False
    return ch


def value_labels(ch, fmt):
    ch.dataLabels = DataLabelList()
    ch.dataLabels.showVal = True
    for flag in ("showSerName", "showCatName", "showLegendKey", "showPercent"):
        setattr(ch.dataLabels, flag, False)
    ch.dataLabels.numFmt = fmt
    ch.x_axis.tickLblSkip = 1

c1 = BarChart()
c1.type = "bar"
style_chart(c1, "Contribution to 2025 real GDP growth (percentage points)", h=10)
c1.add_data(Reference(db, min_col=7, min_row=T0, max_row=T0 + 6), titles_from_data=True)
c1.set_categories(Reference(db, min_col=1, min_row=T0 + 1, max_row=T0 + 6))
value_labels(c1, "0.00")
c1.y_axis.numFmt = "0.0"
c1.y_axis.majorGridlines = None
db.add_chart(c1, "J3")

c2 = BarChart()
style_chart(c2, "Real GDP growth, 2007-2025e")
c2.add_data(Reference(hs, min_col=4, min_row=5, max_row=E25), titles_from_data=False)
c2.set_categories(Reference(hs, min_col=1, min_row=6, max_row=E25))
c2.series[0].val.numRef.f = f"History!$D$6:$D${E25}"
c2.y_axis.numFmt = "0%"
c2.x_axis.tickLblSkip = 1
c2.y_axis.majorGridlines = None
db.add_chart(c2, "J24")

c3 = BarChart()
c3.type = "bar"
style_chart(c3, "Resource volumes: change 2024 -> 2025 (DoT)")
c3.add_data(Reference(db, min_col=2, min_row=RV, max_row=RVL), titles_from_data=True)
c3.set_categories(Reference(db, min_col=1, min_row=RV + 1, max_row=RVL))
value_labels(c3, "0%")
c3.y_axis.numFmt = "0%"
c3.y_axis.majorGridlines = None
db.add_chart(c3, "J40")

c4 = LineChart()
style_chart(c4, "Real GDP: resource vs non-resource (K m, 2013 prices)")
# build resource / non-resource series on History via helper columns
put(hs, "Q4", "Resource", bold=True)
put(hs, "R4", "Non-resource", bold=True)
for rr in range(5, E25 + 1):
    put(hs, f"Q{rr}", f"=G{rr}+H{rr}", fmt=KM)
    put(hs, f"R{rr}", f"=SUM(I{rr}:L{rr})", fmt=KM)
c4.add_data(Reference(hs, min_col=17, max_col=18, min_row=4, max_row=E25), titles_from_data=True)
c4.set_categories(Reference(hs, min_col=1, min_row=5, max_row=E25))
c4.y_axis.numFmt = "#,##0"
for sr in c4.series:
    sr.smooth = False
c4.legend = Legend()
c4.legend.position = "b"
db.add_chart(c4, "J56")

for ws in wb.worksheets:
    ws.sheet_view.showGridLines = False

wb.save(OUT)
print("wrote", OUT)
