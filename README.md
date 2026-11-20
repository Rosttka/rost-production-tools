# Rost Production Tools 4.4

Blender 5.2 add-on (Cycles): STEP pipeline, CAD Auto-Rig, Rost Light Rig, **Reveal Passes** (shell-to-glass reveal: gradient mask with plane or shape control, `alternative` / `line` view layers, wireframe collection, editable compositor, multilayer EXR), **Render Passes** (multi-view-layer render with per-pass DoF / alpha / path and quality presets), HUD graphics (Callout, Measure, Section, Volume Cut, Style, FUI), Proximity Alpha, Gradient Mask and scene utilities. Section, Volume Cut and Callout have preset lists. All panels live in the N-panel tab **Rost Tools**.

## Installation

1. Download `rost_production_tools_4.4.0.zip` (it contains the `rost_production_tools` folder with the add-on and all its libraries).
2. Blender → Edit → Preferences → Add-ons → ⌄ (top right) → **Install from Disk…** → pick the zip.
3. Enable **Rost Production Tools** in the list.

The add-on is a package: `rost_production_tools/__init__.py`, `render_passes.py`, `reveal_passes.py` and `rost_production_tools/library/` (HUD libraries, node groups, Proximity Alpha and Gradient Mask assets, Callout and Section presets). Nothing outside that folder is needed for the HUD tools, Reveal Passes, Render Passes, Proximity Alpha, Gradient Mask and CAD Auto-Rig.

Optional paths in the add-on preferences (empty = default location):

| Field | Default |
|---|---|
| HUD Library | `library/HUD` inside the package |
| Light Rig presets folder | Blender user presets |
| STEP Pipeline folder | `library/EXM_Pipeline` in the package (not bundled) |
| Section / Volume Cut presets folder | `<user scripts>/presets/rost_hud_section`, `rost_hud_volcut` |

STEP Pipeline also needs the CADder add-on and the pipeline scripts (`exm_pipeline.py`, `exm_rig.py`, …).

## Source layout

```
rost_production_tools/        add-on package (zip this folder)
  __init__.py
  render_passes.py
  reveal_passes.py
  library/
    HUD/                      HUD_Elements, HUD_FUI, HUD_Section, HUD_Style, HUD_VolumeCut,
                              Callout_Presets/, Section_Presets/
    PT_NodeGroups_and_Mats.blend
    fx_data.blend
    GN_Proximity_Mask.blend
docs/                         guide (GitHub Pages)
  guide.html
  img/
```

## Guide

Step-by-step guide with screenshots (Ukrainian): https://rosttka.github.io/rost-production-tools/guide.html

The **?** button in the Production Tools header opens the same page.
