# LivCast Capture — Requirements


**Schematic:** single file [`kicad/LivCast_Capture.kicad_sch`](../kicad/LivCast_Capture.kicad_sch) (open via `LivCast_Capture.kicad_pro`); archived multi-sheet hierarchy in [`kicad/archive_sheets/`](../kicad/archive_sheets/).
Status: **I/O + dual-bridge ingest locked** (2026-07-25).

## Product

CM5-based capture box: camera → Livcast-iOS on iPhone over USB-C network video. Separate from **LivCast Bond**.

Quality priority: **best video quality** — no SDI→HDMI conversion in the capture path.

## Locked signal path

```
SDI in  ──► SDI RX ──► CSI bridge ──┐
                                    ├──► CM5 ──┬── USB-C data ───► iPhone
HDMI in ──► HDMI→CSI ───────────────┘          ├── HDMI out ─────► monitor
                                               ├── SDI out ──────► SDI deck
                                               └── 40-pin SPI ───► 3.5" preview

Power:  USB-C PD in (wall charger or D-Tap→USB-C adapter) ──► 5 V / 5 A rail
```

| Stage | Role |
|-------|------|
| SDI RX | Equalize + deserialize SDI from BNC |
| CSI bridge (SDI) | Parallel / link → MIPI CSI-2 into CM5 |
| HDMI→CSI | HDMI → MIPI CSI-2 into CM5 |
| Input select | Software: arm one CSI path at a time |

**Rejected:** SDI→HDMI into a shared HDMI switch/bridge (extra hop, worse quality).

## Ports

| Port | Direction | Job |
|------|-----------|-----|
| SDI in | In | Camera (BNC) |
| HDMI in | In | Camera |
| Input select | Software | HDMI **or** SDI |
| HDMI out | Out | Playback / external monitor |
| SDI out | Out | Playback / SDI deck via **GS2962A** from CM5 HDMI mirror (**not** input loop) |
| USB-C (phone) | Data + charge | Network video → iPhone (**not** UVC); **box also charges the phone** |
| USB-C (power) | In | PD sink: wall charger **or** D-Tap on box / D-Tap→USB-C |
| D-Tap | In | Camera battery (~12–17 V) → same 5 V system rail |
| 3.5" LCD | On box | SPI preview via 40-pin GPIO (Hosyond 480×320) |

## Power (locked)

- **No** built-in lithium. **No** onboard NP-F pack (D-Tap is the camera-battery tap).
- **Inlets:** USB-C PD **and** D-Tap (either can power the box).
- **Phone USB-C:** USB gadget (network video) **and** PD **source** to charge the iPhone (PD power-role swap: phone stays data host, box supplies VBUS/PD).
- **Budget:**
  - Box alone: ~15 W typ / ~20–25 W peak
  - Plus iPhone charge: plan **+15–30 W**
  - **Input design ≥60 W** (D-Tap + PD sink); system rail **5 V / 5 A** for CM5 side; PD source path to phone
- **Two USB-C ports:** power-in vs phone (data + charge-out). D-Tap is a third power inlet.
- Camera / D-Tap battery runtime is the operator’s responsibility (no charge-throttle policy on the box).

## Constraints

- **SoC:** Raspberry Pi CM5 on custom carrier (Pi 5 OK for proto).
- **Ingest:** Dual bridge → CSI; one active input.
- **iPhone path:** USB Ethernet gadget + IP video. No UVC. Phone USB-C also **charges** the iPhone (box = PD source).
- **HDMI out:** Native CM5 HDMI TX.
- **SDI out:** Real playback via **IT66021FN** (HDMI RX parallel from CM5 HDMI TX) → **GS2962A** → BNC — **not** Antmicro SDI-in reclocked loop.
- **Preview:** On-box 3.5" SPI; HDMI/SDI out for real monitoring.

## Format targets

| Format | Goal | Notes |
|--------|------|--------|
| 720p | Required | Hardware must pass; iOS handles display/encode path |
| 1080p | Required | Hardware must pass; lock fps later (25/30/50/60) |
| 1080i | Required | Silicon must support interlaced CSI/SDI; **deinterlace on Livcast-iOS** |

**Split:** Box passes formats through. **Livcast-iOS** owns deinterlace / scale / encode.

**HDMI silicon:** **IT6616** (ITE) — datasheet **CSI interlaced mode**. **Do not use TC358743.**

Hardware must **accept and deliver** 720p, 1080i, and 1080p on both HDMI and SDI.

## Open hardware choices (locked)

**Locked** — see [`CHIP_SHORTLIST.md`](CHIP_SHORTLIST.md) for full table, alternates, and format notes.

Primary MPNs: **CM5** (eMMC); **IT6616** (HDMI→CSI0, **CSI interlaced**); **GS2971A** + **LIF-MD6000-6JMG80I** CrossLink (SDI→CSI1, Antmicro sch); **IT66021FN** + **GS2962A** (SDI playback out from CM5 HDMI mirror; **GS2989** optional dual drive); **TPS25751** (PD sink ≥60 W + phone PD source); **LM76003** + **TPS62130A**; **TPS25947**; Hosyond 3.5" SPI LCD. **Rejected:** TC358743.

## Software split

| Side | Job |
|------|-----|
| Box (Linux) | Dual CSI capture, input select, packetize, USB gadget, SPI UI — pass formats through |
| Livcast-iOS | USB-net ingest; **format handling** (deinterlace / scale); Livcast uplink |

## Non-goals (this product)

- Multi-SIM bonding (→ LivCast Bond)
- UVC to iPhone
- SDI→HDMI in the capture path
- Dual simultaneous HDMI+SDI streaming (select one)
- Built-in battery / onboard NP-F pack
- Powering the **box** from the iPhone (phone is charged **by** the box, not the reverse)
- Shipping Antmicro-style SDI **input loop** (J2/GS2988) as the only / product **SDI out**
