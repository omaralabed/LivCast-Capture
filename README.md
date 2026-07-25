# LivCast Capture

Compact **CM5** HDMI/SDI capture box for **Livcast-iOS** on iPhone.

Camera in → on-box preview → USB-C **network video** to phone. Bonding is a separate product (**LivCast Bond**).

## Locked I/O

| Port | Direction | Job |
|------|-----------|-----|
| SDI in | In | Camera (BNC) |
| HDMI in | In | Camera |
| Input select | Software | HDMI **or** SDI (dual CSI bridges) |
| HDMI out | Out | Playback / external monitor |
| SDI out | Out | Playback / SDI deck |
| USB-C (phone) | Data + charge | Network video → iPhone; **box charges phone** |
| USB-C (power) | In | PD: wall charger or adapter |
| D-Tap | In | Camera battery power |
| 3.5" LCD | On box | SPI preview via 40-pin GPIO (Hosyond 480×320) |

## Locked ingest (best quality)

**Dual bridge — no SDI→HDMI hop:**

```
SDI in  ──► SDI RX ──► CSI bridge ──┐
                                    ├──► CM5 ──┬── USB-C data ───► iPhone
HDMI in ──► HDMI→CSI ───────────────┘          ├── HDMI out ─────► monitor
                                               ├── SDI out ──────► SDI deck
                                               └── 40-pin SPI ───► 3.5" preview

Power:  D-Tap and/or USB-C PD in ──► box rail
        USB-C phone ──► data (gadget) + charge out to iPhone
```

Software picks which CSI stream is live (one input at a time). **Phone port charges the iPhone** (PD source) while carrying network video. **D-Tap + USB-C PD** power the box. No built-in battery.

## Why USB network, not UVC

iPhone does **not** expose UVC as `AVCaptureDevice.external` (that path is iPadOS). LivCast Capture presents as a USB Ethernet gadget and streams video over IP to Livcast-iOS.

## Format targets

Design for **720p / 1080i / 1080p** as a hard requirement. HDMI path uses **IT6616** (CSI interlaced). Livcast-iOS handles deinterlace.

## Repo

- Spec: [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md)
- Chips: [`docs/CHIP_SHORTLIST.md`](docs/CHIP_SHORTLIST.md)
- Hardware: [`kicad/LivCast_Capture.kicad_pro`](kicad/LivCast_Capture.kicad_pro) (Rev A block schematic)
- Firmware: Linux CSI capture + USB gadget + IP video
- Phone: Livcast-iOS USB-network ingest (separate app repo)

## Related

- Hardware remote: https://github.com/omaralabed/LivCast-Capture
- Livcast-iOS: companion app (USB-net ingest required for iPhone path)
- LivCast Bond: multi-SIM uplink box (separate product)
