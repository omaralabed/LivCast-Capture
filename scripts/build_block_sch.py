#!/usr/bin/env python3
"""Generate a readable A2 landscape block-diagram schematic (no pin dumps)."""
from __future__ import annotations

import re
import subprocess
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "kicad"
SCH = ROOT / "LivCast_Capture.kicad_sch"
LIB = ROOT / "libs/livcast-capture/livcast-capture.kicad_sym"
BNC_LIB = ROOT / "libs/antmicro-sdi-mipi/sdi-mipi-bridge.kicad_sym"
KICAD = Path("/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")
PREVIEW = ROOT / "preview"


def uid() -> str:
    return str(uuid.uuid4())


def extract_symbol(text: str, name: str) -> str:
    token = f'(symbol "{name}"'
    i = text.find(token)
    if i < 0:
        raise SystemExit(f"missing symbol {name}")
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "(":
            depth += 1
        elif text[j] == ")":
            depth -= 1
            if depth == 0:
                return text[i : j + 1]
    raise SystemExit(f"unclosed {name}")


def prefix_lib(chunk: str, lib: str, name: str) -> str:
    """Rewrite (symbol \"Name\" -> (symbol \"lib:Name\" for sch embedding."""
    return chunk.replace(f'(symbol "{name}"', f'(symbol "{lib}:{name}"', 1)


def parse_pins(chunk: str) -> list[dict]:
    pins = []
    for m in re.finditer(
        r'\(pin (\w+) \w+\s*\(at ([-\d.]+) ([-\d.]+) (\d+)\)\s*\(length [-\d.]+\)\s*'
        r'\(name "([^"]+)"[\s\S]*?\(number "([^"]+)"',
        chunk,
    ):
        etype, x, y, rot, pname, pnum = m.groups()
        pins.append(
            {
                "etype": etype,
                "x": float(x),
                "y": float(y),
                "rot": int(rot),
                "name": pname,
                "num": pnum,
            }
        )
    return pins


def compact_hdmi_symbol(arch_text: str) -> tuple[str, list[dict]]:
    """Clone a known-good small connector (DTAP) as a 2-pin HDMI stub for the block sheet."""
    dtap = extract_symbol(arch_text, "livcast-capture:Conn_DTAP")
    hdmi = dtap.replace("livcast-capture:Conn_DTAP", "livcast-capture:Conn_HDMI_A", 1)
    hdmi = hdmi.replace("Conn_DTAP", "Conn_HDMI_A")
    # Rename pins for clarity in netlist
    hdmi = hdmi.replace('"VIN"', '"TMDS"').replace('"GND"', '"GND"')
    pins = parse_pins(hdmi)
    return hdmi, pins



def force_hide_pin_names(chunk: str) -> str:
    if re.search(r"\(pin_names\s*\n\s*\(hide yes\)", chunk) is None:
        if "(pin_names" in chunk:
            chunk = re.sub(
                r"\(pin_names(\s*\n\s*\(offset [-\d.]+\))?",
                "(pin_names\n\t\t(hide yes)\\1",
                chunk,
                count=1,
            )
        else:
            chunk = chunk.replace(
                '(exclude_from_sim',
                '(pin_names\n\t\t(hide yes)\n\t\t)\n\t\t(exclude_from_sim',
                1,
            )
    return chunk


class Sch:
    def __init__(self) -> None:
        self.embeds: list[str] = []
        self.items: list[str] = []
        self.pin_meta: dict[str, list[dict]] = {}

    def add_embed(self, chunk: str, lib_id: str, pins: list[dict]) -> None:
        self.embeds.append(chunk)
        self.pin_meta[lib_id] = pins

    def rect(self, x1: float, y1: float, x2: float, y2: float) -> None:
        # Yellow outline, empty fill — block diagram boxes
        self.items.append(
            f"""\t(rectangle
\t\t(start {x1:g} {y1:g})
\t\t(end {x2:g} {y2:g})
\t\t(stroke
\t\t\t(width 0.508)
\t\t\t(type default)
\t\t\t(color 220 180 0 1)
\t\t)
\t\t(fill
\t\t\t(type none)
\t\t)
\t\t(uuid "{uid()}")
\t)"""
        )

    def text(
        self,
        msg: str,
        x: float,
        y: float,
        size: float = 2.54,
        bold: bool = False,
        justify: str = "left bottom",
    ) -> None:
        bold_s = "\n\t\t\t\t(bold yes)" if bold else ""
        self.items.append(
            f"""\t(text "{msg}"
\t\t(exclude_from_sim no)
\t\t(at {x:g} {y:g} 0)
\t\t(effects
\t\t\t(font
\t\t\t\t(size {size:g} {size:g}){bold_s}
\t\t\t)
\t\t\t(justify {justify})
\t\t)
\t\t(uuid "{uid()}")
\t)"""
        )

    def wire(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self.items.append(
            f"""\t(wire
\t\t(pts
\t\t\t(xy {x1:g} {y1:g}) (xy {x2:g} {y2:g})
\t\t)
\t\t(stroke
\t\t\t(width 0)
\t\t\t(type default)
\t\t)
\t\t(uuid "{uid()}")
\t)"""
        )

    def polyline(self, pts: list[tuple[float, float]]) -> None:
        xy = " ".join(f"(xy {x:g} {y:g})" for x, y in pts)
        self.items.append(
            f"""\t(polyline
\t\t(pts
\t\t\t{xy}
\t\t)
\t\t(stroke
\t\t\t(width 0)
\t\t\t(type default)
\t\t)
\t\t(uuid "{uid()}")
\t)"""
        )

    def glabel(
        self,
        name: str,
        x: float,
        y: float,
        shape: str = "bidirectional",
        rot: int = 0,
        justify: str = "left",
        size: float = 1.524,
    ) -> None:
        self.items.append(
            f"""\t(global_label "{name}"
\t\t(shape {shape})
\t\t(at {x:g} {y:g} {rot})
\t\t(effects
\t\t\t(font
\t\t\t\t(size {size:g} {size:g})
\t\t\t)
\t\t\t(justify {justify})
\t\t)
\t\t(uuid "{uid()}")
\t\t(property "Intersheetrefs" "${{INTERSHEET_REFS}}"
\t\t\t(at {x:g} {y:g} 0)
\t\t\t(hide yes)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t)
\t\t)
\t)"""
        )

    def place(
        self,
        lib_id: str,
        ref: str,
        value: str,
        x: float,
        y: float,
        rot: int = 0,
        mirror: str | None = None,
    ) -> dict[str, tuple[float, float]]:
        """Place symbol; return pin absolute positions {num: (x,y)}."""
        pins = self.pin_meta[lib_id]
        pin_uuids = "\n".join(
            f'\t\t(pin "{p["num"]}"\n\t\t\t(uuid "{uid()}")\n\t\t)' for p in pins
        )
        mir = f'\n\t\t(mirror {mirror})' if mirror else ""
        self.items.append(
            f"""\t(symbol
\t\t(lib_id "{lib_id}")
\t\t(at {x:g} {y:g} {rot}){mir}
\t\t(unit 1)
\t\t(exclude_from_sim no)
\t\t(in_bom yes)
\t\t(on_board yes)
\t\t(dnp no)
\t\t(uuid "{uid()}")
\t\t(property "Reference" "{ref}"
\t\t\t(at {x:g} {y + 8.89:g} 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t)
\t\t)
\t\t(property "Value" "{value}"
\t\t\t(at {x:g} {y - 8.89:g} 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t)
\t\t)
\t\t(property "Footprint" ""
\t\t\t(at {x:g} {y:g} 0)
\t\t\t(hide yes)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t)
\t\t)
{pin_uuids}
\t)"""
        )
        # Absolute pin positions (no rotation support beyond 0/180 for our uses)
        abs_pins: dict[str, tuple[float, float]] = {}
        for p in pins:
            px, py = p["x"], p["y"]
            if rot == 180:
                px, py = -px, -py
            elif rot == 90:
                px, py = -py, px
            elif rot == 270:
                px, py = py, -px
            if mirror == "x":
                py = -py
            elif mirror == "y":
                px = -px
            abs_pins[p["num"]] = (x + px, y + py)
        return abs_pins

    def link_h(
        self,
        x1: float,
        y: float,
        x2: float,
        label: str | None = None,
        shape: str = "bidirectional",
    ) -> None:
        """Horizontal wire with optional mid global label."""
        self.wire(x1, y, x2, y)
        if label:
            mx = (x1 + x2) / 2
            # Point label left if wire goes left-to-right
            self.glabel(label, mx, y, shape=shape, rot=0, justify="left")

    def arrow_tip(self, x: float, y: float, facing: str = "right") -> None:
        """Small polyline arrow head at end of a link."""
        if facing == "right":
            self.polyline([(x - 2.54, y + 1.27), (x, y), (x - 2.54, y - 1.27)])
        elif facing == "left":
            self.polyline([(x + 2.54, y + 1.27), (x, y), (x + 2.54, y - 1.27)])
        elif facing == "up":
            self.polyline([(x - 1.27, y - 2.54), (x, y), (x + 1.27, y - 2.54)])
        else:
            self.polyline([(x - 1.27, y + 2.54), (x, y), (x + 1.27, y + 2.54)])

    def write(self) -> None:
        parts = [
            "(kicad_sch",
            "\t(version 20250114)",
            '\t(generator "livcast_block")',
            '\t(generator_version "9.0")',
            f'\t(uuid "{uid()}")',
            '\t(paper "A2")',
            "\t(title_block",
            '\t\t(title "LivCast Capture - Block Schematic (Rev A)")',
            '\t\t(date "2026-07-25")',
            '\t\t(rev "A")',
            '\t\t(company "LivCast")',
            '\t\t(comment 1 "Readable architecture sheet. Dense pin sch archived as LivCast_Capture_dense_pins.kicad_sch")',
            '\t\t(comment 2 "Blocks + few wires + mid-wire labels. Connectors at edges only.")',
            "\t)",
            "\t(lib_symbols",
        ]
        parts.extend(self.embeds)
        parts.append("\t)")
        parts.extend(self.items)
        parts += [
            "\t(sheet_instances",
            '\t\t(path "/"',
            '\t\t\t(page "1")',
            "\t\t)",
            "\t)",
            "\t(embedded_fonts no)",
            ")",
        ]
        text = "\n".join(parts) + "\n"
        assert text.count("(") == text.count(")"), (
            text.count("("),
            text.count(")"),
        )
        SCH.write_text(text)
        print(f"Wrote {SCH} ({SCH.stat().st_size} bytes)")


def load_embeds(sch: Sch) -> None:
    lib = LIB.read_text()
    for name in ["Conn_DTAP", "Conn_USB_C_PWR", "Conn_USB_C_DATA"]:
        raw = extract_symbol(lib, name)
        # Upgrade path: use already-upgraded from dense sch if present
        chunk = force_hide_pin_names(prefix_lib(raw, "livcast-capture", name))
        # Prefer KiCad-expanded form from dense archive if available
        arch = (ROOT / "archive_sheets" / "LivCast_Capture_dense_pins.kicad_sch").read_text()
        token = f'(symbol "livcast-capture:{name}"'
        if token in arch:
            chunk = force_hide_pin_names(extract_symbol(arch, f"livcast-capture:{name}"))
        pins = parse_pins(chunk)
        if not pins:
            raise SystemExit(f"no pins for {name}")
        sch.add_embed(chunk, f"livcast-capture:{name}", pins)

    arch = (ROOT / "archive_sheets" / "LivCast_Capture_dense_pins.kicad_sch").read_text()

    # Compact HDMI stub (DTAP-sized) — full 14-pin body is unreadable on a block sheet
    hdmi, hpins = compact_hdmi_symbol(arch)
    sch.add_embed(hdmi, "livcast-capture:Conn_HDMI_A", hpins)

    # BNC from dense sch (already upgraded)
    bnc_id = "sdi-mipi-bridge:Conn_BNC_031-70526-21"
    bnc = force_hide_pin_names(extract_symbol(arch, bnc_id))
    bpins = parse_pins(bnc)
    if not bpins:
        raise SystemExit("no BNC pins")
    sch.add_embed(bnc, bnc_id, bpins)


def build_layout(sch: Sch) -> None:
    """
    A2 landscape 594 x 420 mm. Origin bottom-left, Y up.
    """
    # ---- Title / note ----
    sch.text(
        "LivCast Capture - Block Schematic (Rev A)",
        30,
        400,
        size=3.5,
        bold=True,
        justify="left bottom",
    )
    sch.text(
        "Readable architecture sheet. Dense pin sch archived as LivCast_Capture_dense_pins.kicad_sch",
        30,
        388,
        size=1.6,
        justify="left bottom",
    )

    # ---- Blocks (yellow empty rectangles) ----
    # POWER IN
    sch.rect(55, 305, 155, 365)
    sch.text("POWER IN", 62, 348, size=2.6, bold=True)
    sch.text("D-Tap + USB-C PD", 62, 332, size=1.5)
    sch.text("battery / wall", 62, 318, size=1.3)

    # REGULATORS
    sch.rect(185, 305, 295, 365)
    sch.text("5V / 3V3 REGULATORS", 192, 348, size=2.2, bold=True)
    sch.text("5V buck + 3V3 LDO", 192, 332, size=1.5)
    sch.text("CM5 + bridges", 192, 318, size=1.3)

    # CM5
    sch.rect(325, 195, 445, 335)
    sch.text("CM5", 365, 295, size=3.5, bold=True, justify="left bottom")
    sch.text("Compute Module 5", 340, 275, size=1.6, justify="left bottom")
    sch.text("CSI0 / CSI1 ingest", 340, 255, size=1.4, justify="left bottom")
    sch.text("USB gadget + HDMI TX", 340, 240, size=1.3, justify="left bottom")

    # HDMI IN / IT6616
    sch.rect(55, 175, 185, 255)
    sch.text("HDMI IN / IT6616", 62, 232, size=2.2, bold=True)
    sch.text("HDMI to MIPI CSI", 62, 212, size=1.5)
    sch.text("720p / 1080i / 1080p", 62, 195, size=1.3)

    # SDI IN / GS2971A + CrossLink
    sch.rect(55, 55, 185, 135)
    sch.text("SDI IN / GS2971A", 62, 112, size=2.2, bold=True)
    sch.text("+ CrossLink CSI", 62, 92, size=1.5)
    sch.text("Antmicro-class path", 62, 75, size=1.3)

    # HDMI OUT + SDI PLAYBACK
    sch.rect(455, 175, 530, 295)
    sch.text("HDMI OUT + SDI PLAY", 462, 270, size=1.9, bold=True)
    sch.text("IT66021 + GS2962A", 462, 245, size=1.5)
    sch.text("monitor + SDI deck", 462, 225, size=1.3)
    sch.text("(playback, not loop)", 462, 205, size=1.3)

    # USB-C PHONE
    sch.rect(455, 315, 530, 365)
    sch.text("USB-C PHONE", 462, 345, size=2.2, bold=True)
    sch.text("data + charge", 462, 328, size=1.4)

    # LCD
    sch.rect(455, 55, 530, 135)
    sch.text("LCD 40-pin", 462, 112, size=2.2, bold=True)
    sch.text("3.5 inch SPI preview", 462, 92, size=1.5)
    sch.text("Hosyond 480x320", 462, 75, size=1.3)

    # ---- Edge connectors ----
    dtap = sch.place(
        "livcast-capture:Conn_DTAP", "J_DTAP", "Conn_DTAP", 35, 340, mirror="y"
    )
    usbp = sch.place(
        "livcast-capture:Conn_USB_C_PWR",
        "J_USBC_PWR",
        "Conn_USB_C_PWR",
        35,
        318,
        mirror="y",
    )
    hdmi_in = sch.place(
        "livcast-capture:Conn_HDMI_A",
        "J_HDMI_IN",
        "Conn_HDMI_A",
        35,
        215,
        mirror="y",
    )
    sdi_in = sch.place(
        "sdi-mipi-bridge:Conn_BNC_031-70526-21",
        "J_SDI_IN",
        "BNC",
        35,
        95,
        mirror="y",
    )

    # Place just left of page edge so body stays on A2 (594mm)
    usbc = sch.place(
        "livcast-capture:Conn_USB_C_DATA",
        "J_USBC_PHONE",
        "Conn_USB_C_DATA",
        545,
        340,
    )
    hdmi_out = sch.place(
        "livcast-capture:Conn_HDMI_A",
        "J_HDMI_OUT",
        "Conn_HDMI_A",
        545,
        250,
    )
    sdi_out = sch.place(
        "sdi-mipi-bridge:Conn_BNC_031-70526-21",
        "J_SDI_OUT",
        "BNC",
        545,
        205,
    )

    sch.text("J_LCD", 535, 105, size=1.8, bold=True, justify="left bottom")
    sch.text("(40-pin FFC)", 535, 90, size=1.2, justify="left bottom")

    # ---- Connector wires ----
    px, py = dtap["1"]
    sch.wire(px, py, 55, py)
    px, py = usbp["1"]
    sch.wire(px, py, 55, py)
    px, py = hdmi_in["1"]
    sch.wire(px, py, 55, py)
    bnc_pin = next(iter(sdi_in))
    px, py = sdi_in[bnc_pin]
    sch.wire(px, py, 55, 95)

    px, py = usbc["1"]
    sch.wire(530, 340, px, py)
    px, py = hdmi_out["1"]
    sch.wire(530, 250, px, py)
    bnc_pin = next(iter(sdi_out))
    px, py = sdi_out[bnc_pin]
    sch.wire(530, 205, px, py)
    sch.wire(530, 95, 540, 95)

    # ---- Block links with mid labels ----
    sch.link_h(155, 335, 185, "+5V0", shape="output")
    sch.arrow_tip(185, 335, "right")

    sch.wire(295, 335, 310, 335)
    sch.wire(310, 335, 310, 265)
    sch.wire(310, 265, 325, 265)
    sch.arrow_tip(325, 265, "right")

    sch.link_h(445, 340, 455, "USB_NET", shape="output")
    sch.arrow_tip(455, 340, "right")

    sch.link_h(445, 250, 455, "HDMI_TX", shape="output")
    sch.arrow_tip(455, 250, "right")
    sch.link_h(445, 220, 455, "SDI_PLAY", shape="output")
    sch.arrow_tip(455, 220, "right")
    sch.text("GS2962A path", 448, 205, size=1.2)

    sch.wire(445, 210, 460, 210)
    sch.wire(460, 210, 460, 95)
    sch.link_h(460, 95, 455, "SPI_LCD", shape="output")
    sch.arrow_tip(455, 95, "right")

    sch.wire(185, 215, 250, 215)
    sch.wire(250, 215, 250, 235)
    sch.link_h(250, 235, 325, "CSI0", shape="output")
    sch.arrow_tip(325, 235, "right")

    sch.wire(185, 95, 270, 95)
    sch.wire(270, 95, 270, 215)
    sch.link_h(270, 215, 325, "CSI1", shape="output")
    sch.arrow_tip(325, 215, "right")

    sch.rect(30, 18, 350, 45)
    sch.text(
        "Legend: yellow boxes = blocks  |  mid-wire labels = nets  |  edge J* = connectors",
        38,
        28,
        size=1.3,
    )



def export_preview() -> None:
    PREVIEW.mkdir(parents=True, exist_ok=True)
    pdf = PREVIEW / "LivCast_Capture.pdf"
    png = PREVIEW / "LivCast_Capture_BLOCK.png"
    zoom = PREVIEW / "LivCast_Capture_ZOOM.png"
    # PDF
    subprocess.run(
        [
            str(KICAD),
            "sch",
            "export",
            "pdf",
            "-o",
            str(pdf),
            "--no-background-color",
            str(SCH),
        ],
        check=True,
    )
    print(f"PDF → {pdf}")
    # Full-page PNG via pdf plot pages as SVG then… use sch export svg + convert, or pdfium
    # KiCad 10: sch export svg
    svg_dir = PREVIEW / "_svg"
    svg_dir.mkdir(exist_ok=True)
    subprocess.run(
        [
            str(KICAD),
            "sch",
            "export",
            "svg",
            "-o",
            str(svg_dir),
            "--no-background-color",
            str(SCH),
        ],
        check=True,
    )
    svgs = list(svg_dir.glob("*.svg"))
    print("SVGs", svgs)
    # Rasterize with qlmanage or rsvg or magick
    # Rasterize PDF (full page, readable)
    import shutil

    tmp_prefix = PREVIEW / "LivCast_Capture_BLOCK_tmp"
    subprocess.run(
        ["pdftoppm", "-png", "-r", "150", str(pdf), str(tmp_prefix)],
        check=True,
    )
    page = Path(str(tmp_prefix) + "-1.png")
    if not page.exists():
        pages = list(PREVIEW.glob("LivCast_Capture_BLOCK_tmp*.png"))
        if not pages:
            raise SystemExit("pdftoppm produced no PNG")
        page = pages[0]
    shutil.move(str(page), str(png))
    subprocess.run(
        ["pdftoppm", "-png", "-r", "200", str(pdf), str(PREVIEW / "LivCast_Capture_ZOOM_tmp")],
        check=True,
    )
    zpage = PREVIEW / "LivCast_Capture_ZOOM_tmp-1.png"
    if zpage.exists():
        shutil.move(str(zpage), str(zoom))
    else:
        shutil.copy2(png, zoom)
    print(f"PNG → {png} and {zoom}")
    # Netlist (sparse OK)
    net = PREVIEW / "LivCast_Capture.net"
    try:
        subprocess.run(
            [str(KICAD), "sch", "export", "netlist", "-o", str(net), str(SCH)],
            check=True,
        )
        print(f"Netlist → {net} OK")
    except subprocess.CalledProcessError as e:
        print("Netlist failed", e)
        raise


def main() -> None:
    sch = Sch()
    load_embeds(sch)
    build_layout(sch)
    sch.write()
    export_preview()


if __name__ == "__main__":
    main()
