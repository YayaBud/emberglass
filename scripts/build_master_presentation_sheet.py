"""
Emberglass Master Library Presentation Sheet Builder
Composes all 109 3D rendered assets into an ultra-high-resolution showcase sheet
matching the exact layout, styling, and typography of the reference image.
Includes realistic ambient drop shadows, precise typographic tracking, and pixel-perfect framing.
Saves to d:/assests/renders/emberglass_master_library_sheet.png
"""

import os
import sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import sys
# Allow a different sprite set / output path from the command line so the
# blockout sheet and the detailed sheet can both be built from one script.
SPRITES_DIR = sys.argv[1] if len(sys.argv) > 1 else "d:/assests/renders/sheet_sprites"
OUT_PATH = sys.argv[2] if len(sys.argv) > 2 else "d:/assests/renders/emberglass_master_library_sheet.png"

# Canvas Dimensions (2x resolution of 1536x1024)
CANVAS_W = 3072
CANVAS_H = 2048
SCALE = 2.0

# Refined Color Palette
BG_COLOR = (21, 28, 36)           # #151c24 deep slate
BORDER_COLOR = (42, 53, 66)       # #2a3542 elegant subtle box line
TITLE_COLOR = (160, 182, 204)     # #a0b6cc
LABEL_COLOR = (145, 165, 185)     # #91a5b9
HEADER_MAIN = (232, 240, 248)     # #e8f0f8
HEADER_SUB = (130, 150, 172)      # #8296ac
FOOTER_COLOR = (98, 118, 140)     # #62768c

# Fonts
FONT_SERIF_BOLD = "C:/Windows/Fonts/georgiab.ttf"
FONT_SERIF = "C:/Windows/Fonts/georgia.ttf"
FONT_SANS_BOLD = "C:/Windows/Fonts/segoeuib.ttf"
FONT_SANS = "C:/Windows/Fonts/segoeui.ttf"

def get_font(font_path, size):
    try:
        return ImageFont.truetype(font_path, int(size))
    except Exception:
        return ImageFont.load_default()

def draw_text_tracked(draw, xy, text, font, fill, tracking=0, anchor="lt"):
    """Draw text with custom letter tracking (spacing) aligned to typographic baseline."""
    ascent, descent = font.getmetrics()
    
    char_widths = []
    for ch in text:
        w = font.getlength(ch) if hasattr(font, 'getlength') else font.getbbox(ch)[2]
        char_widths.append(w)
        
    total_w = sum(char_widths) + max(0, len(text) - 1) * tracking
        
    start_x, start_y = xy
    if "r" in anchor:
        start_x -= total_w
    elif "m" in anchor or "c" in anchor:
        start_x -= total_w / 2.0
        
    baseline_y = start_y + ascent
    curr_x = start_x
    for ch, w in zip(text, char_widths):
        draw.text((curr_x, baseline_y), ch, font=font, fill=fill, anchor="ls")
        curr_x += w + tracking

def create_ambient_shadow(sprite, offset=(5, 9), blur_radius=7, opacity=0.55):
    """Creates a soft grounded contact shadow from the sprite alpha channel."""
    if sprite.mode != 'RGBA':
        sprite = sprite.convert('RGBA')
    alpha = sprite.split()[-1]
    
    # Shadow mask with soft dark slate color
    shadow = Image.new("RGBA", sprite.size, (8, 12, 16, 0))
    # Apply alpha
    shadow.putalpha(alpha)
    # Gaussian blur for soft ambient occlusion feel
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur_radius))
    
    # Scale alpha by opacity
    r, g, b, a = shadow.split()
    a = a.point(lambda p: int(p * opacity))
    shadow.putalpha(a)
    return shadow

def load_and_fit_sprite(fname, target_w, target_h):
    """Loads a rendered sprite, trims transparency, and fits inside target size."""
    path = os.path.join(SPRITES_DIR, fname)
    if not os.path.exists(path):
        root_path = os.path.join("d:/assests/renders", fname)
        if os.path.exists(root_path):
            path = root_path
        else:
            print(f"Warning: Sprite not found: {fname}")
            return None
            
    try:
        im = Image.open(path).convert("RGBA")
        bbox = im.getbbox()
        if bbox:
            im = im.crop(bbox)
        
        im_w, im_h = im.size
        if im_w == 0 or im_h == 0:
            return None
            
        ratio = min(target_w / float(im_w), target_h / float(im_h))
        new_w = max(1, int(im_w * ratio))
        new_h = max(1, int(im_h * ratio))
        im_resized = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
        return im_resized
    except Exception as e:
        print(f"Error loading sprite {fname}: {e}")
        return None

# =========================================================================
# SECTION DEFINITIONS
# Coordinates in 1536x1024 reference space, scaled by 2.0
# =========================================================================

SECTIONS = [
    # 1. HOUSES & BUILDINGS (8 cols x 2 rows = 16 buildings)
    {
        "id": "houses",
        "title": "HOUSES & BUILDINGS",
        "box": (12, 62, 946, 353),
        "cols": 8,
        "rows": 2,
        "items": [
            # Row 1
            {"file": "bld_cottage.png", "label": "cottage"},
            {"file": "bld_townhouse.png", "label": "townhouse"},
            {"file": "bld_tenement.png", "label": "tenement"},
            {"file": "bld_tavern.png", "label": "tavern"},
            {"file": "bld_shop.png", "label": "shop"},
            {"file": "bld_blacksmith.png", "label": "blacksmith"},
            {"file": "bld_stables.png", "label": "stables"},
            {"file": "bld_warehouse.png", "label": "warehouse"},
            # Row 2
            {"file": "monument_noble_manor.png", "label": "noble manor"},
            {"file": "monument_guildhouse.png", "label": "guildhouse"},
            {"file": "monument_chapel.png", "label": "chapel"},
            {"file": "monument_church.png", "label": "church"},
            {"file": "monument_windmill.png", "label": "windmill"},
            {"file": "monument_watchtower.png", "label": "watchtower"},
            {"file": "monument_gatehouse.png", "label": "gatehouse"},
            {"file": "monument_keep.png", "label": "keep"},
        ]
    },
    
    # 2. VARIATIONS / STATES (4 cols x 1 row = 4 items)
    {
        "id": "variations",
        "title": "VARIATIONS / STATES",
        "box": (954, 62, 1524, 353),
        "cols": 4,
        "rows": 1,
        "items": [
            {"file": "variation_normal.png", "label": "normal"},
            {"file": "variation_with_stall.png", "label": "with stall"},
            {"file": "variation_damaged.png", "label": "damaged"},
            {"file": "variation_ruin.png", "label": "ruin"},
        ]
    },

    # 3. WALLS & FORTIFICATIONS (8 cols x 1 row = 8 items)
    {
        "id": "walls",
        "title": "WALLS & FORTIFICATIONS",
        "box": (12, 361, 830, 497),
        "cols": 8,
        "rows": 1,
        "items": [
            {"file": "wall_straight.png", "label": "wall_straight"},
            {"file": "wall_corner.png", "label": "wall_corner"},
            {"file": "wall_tower.png", "label": "wall_tower"},
            {"file": "wall_gatehouse.png", "label": "gatehouse"},
            {"file": "castle_gate.png", "label": "castle_gate"},
            {"file": "retaining_wall.png", "label": "retaining_wall"},
            {"file": "cliff_wall.png", "label": "cliff_wall"},
            {"file": "ruin_wall.png", "label": "ruin_wall"},
        ]
    },

    # 4. STAIRS, RAMPS & ELEVATION (6 cols x 1 row = 6 items)
    {
        "id": "stairs",
        "title": "STAIRS, RAMPS & ELEVATION",
        "box": (838, 361, 1524, 497),
        "cols": 6,
        "rows": 1,
        "items": [
            {"file": "stairs_small.png", "label": "stairs_small"},
            {"file": "stairs_large.png", "label": "stairs_large"},
            {"file": "ramp.png", "label": "ramp"},
            {"file": "platform.png", "label": "platform"},
            {"file": "arch_bridge.png", "label": "arch_bridge"},
            {"file": "stone_bridge.png", "label": "stone_bridge"},
        ]
    },

    # 5. STREET & GROUND TILES (8 cols x 1 row = 8 items)
    {
        "id": "tiles",
        "title": "STREET & GROUND TILES",
        "box": (12, 505, 722, 617),
        "cols": 8,
        "rows": 1,
        "items": [
            {"file": "stone_road.png", "label": "stone_road"},
            {"file": "cobblestone.png", "label": "cobblestone"},
            {"file": "dirt_road.png", "label": "dirt_road"},
            {"file": "plaza_tile.png", "label": "plaza_tile"},
            {"file": "wooden_deck.png", "label": "wooden_deck"},
            {"file": "dock_tile.png", "label": "dock_tile"},
            {"file": "grassy_ground.png", "label": "grassy_ground"},
            {"file": "cliff_edge.png", "label": "cliff_edge"},
        ]
    },

    # 6. FENCES & BARRIERS (8 cols x 1 row = 8 items)
    {
        "id": "fences",
        "title": "FENCES & BARRIERS",
        "box": (730, 505, 1524, 617),
        "cols": 8,
        "rows": 1,
        "items": [
            {"file": "wood_fence.png", "label": "wood_fence"},
            {"file": "stone_fence.png", "label": "stone_fence"},
            {"file": "iron_fence.png", "label": "iron_fence"},
            {"file": "railing.png", "label": "railing"},
            {"file": "post_chain.png", "label": "post_chain"},
            {"file": "hedge.png", "label": "hedge"},
            {"file": "spikes.png", "label": "spikes"},
            {"file": "gate_small.png", "label": "gate_small"},
        ]
    },

    # 7. MARKET & STREET PROPS (9 cols x 1 row = 9 items)
    {
        "id": "market",
        "title": "MARKET & STREET PROPS",
        "box": (12, 625, 722, 737),
        "cols": 9,
        "rows": 1,
        "items": [
            {"file": "market_stall_a.png", "label": "market_stall_a"},
            {"file": "market_stall_b.png", "label": "market_stall_b"},
            {"file": "cart.png", "label": "cart"},
            {"file": "wagon.png", "label": "wagon"},
            {"file": "crates.png", "label": "crates"},
            {"file": "barrels.png", "label": "barrels"},
            {"file": "sacks.png", "label": "sacks"},
            {"file": "signpost.png", "label": "signpost"},
            {"file": "notice_board.png", "label": "notice_board"},
        ]
    },

    # 8. DECORATIONS & SMALL PROPS (12 cols x 1 row = 12 items)
    {
        "id": "decorations",
        "title": "DECORATIONS & SMALL PROPS",
        "box": (730, 625, 1524, 737),
        "cols": 12,
        "rows": 1,
        "items": [
            {"file": "street_lamp.png", "label": "street_lamp"},
            {"file": "wall_lantern.png", "label": "wall_lantern"},
            {"file": "hanging_lantern.png", "label": "hanging_lantern"},
            {"file": "well.png", "label": "well"},
            {"file": "bench.png", "label": "bench"},
            {"file": "planter.png", "label": "planter"},
            {"file": "fountain.png", "label": "fountain"},
            {"file": "statue.png", "label": "statue"},
            {"file": "tree_small.png", "label": "tree_small"},
            {"file": "tree_large.png", "label": "tree_large"},
            {"file": "bush.png", "label": "bush"},
            {"file": "flower_box.png", "label": "flower_box"},
        ]
    },

    # 9. DOCKS & WATERFRONT (8 cols x 1 row = 8 items)
    {
        "id": "docks",
        "title": "DOCKS & WATERFRONT",
        "box": (12, 745, 722, 857),
        "cols": 8,
        "rows": 1,
        "items": [
            {"file": "dock_post.png", "label": "dock_post"},
            {"file": "dock_platform.png", "label": "dock_platform"},
            {"file": "pier.png", "label": "pier"},
            {"file": "small_boat.png", "label": "small_boat"},
            {"file": "sail_boat.png", "label": "sail_boat"},
            {"file": "crane.png", "label": "crane"},
            {"file": "net_stack.png", "label": "net_stack"},
            {"file": "fish_barrels.png", "label": "fish_barrels"},
        ]
    },

    # 10. MISCELLANEOUS (10 cols x 1 row = 10 items)
    {
        "id": "misc",
        "title": "MISCELLANEOUS",
        "box": (730, 745, 1524, 857),
        "cols": 10,
        "rows": 1,
        "items": [
            {"file": "clothesline.png", "label": "clothesline"},
            {"file": "banners.png", "label": "banners"},
            {"file": "flags.png", "label": "flags"},
            {"file": "awning.png", "label": "awning"},
            {"file": "balcony.png", "label": "balcony"},
            {"file": "chimney_smoke.png", "label": "chimney_smoke"},
            {"file": "bookshelf.png", "label": "bookshelf"},
            {"file": "table_set.png", "label": "table_set"},
            {"file": "hay_stack.png", "label": "hay_stack"},
            {"file": "wood_pile.png", "label": "wood_pile"},
        ]
    },

    # 11. ENVIRONMENT / NATURE (10 cols x 1 row = 10 items)
    {
        "id": "nature",
        "title": "ENVIRONMENT / NATURE",
        "box": (12, 865, 755, 977),
        "cols": 10,
        "rows": 1,
        "items": [
            {"file": "rock_large.png", "label": "rock_large"},
            {"file": "rock_small.png", "label": "rock_small"},
            {"file": "boulder.png", "label": "boulder"},
            {"file": "grass_patch.png", "label": "grass_patch"},
            {"file": "flowers.png", "label": "flowers"},
            {"file": "tree_group.png", "label": "tree_group"},
            {"file": "vines.png", "label": "vines"},
            {"file": "ivy_wall.png", "label": "ivy_wall"},
            {"file": "dead_tree.png", "label": "dead_tree"},
            {"file": "ruins_pillar.png", "label": "ruins_pillar"},
        ]
    },

    # 12. INTERIOR / OPTIONAL (10 cols x 1 row = 10 items)
    {
        "id": "interior",
        "title": "INTERIOR / OPTIONAL",
        "box": (763, 865, 1524, 977),
        "cols": 10,
        "rows": 1,
        "items": [
            {"file": "bed.png", "label": "bed"},
            {"file": "table.png", "label": "table"},
            {"file": "chair.png", "label": "chair"},
            {"file": "shelf.png", "label": "shelf"},
            {"file": "fireplace.png", "label": "fireplace"},
            {"file": "rug.png", "label": "rug"},
            {"file": "curtain.png", "label": "curtain"},
            {"file": "chest.png", "label": "chest"},
            {"file": "ladder.png", "label": "ladder"},
            {"file": "stairs_interior.png", "label": "stairs_interior"},
        ]
    },
]

def build_sheet():
    print(f"Creating Emberglass Master Sheet ({CANVAS_W}x{CANVAS_H})...")
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (*BG_COLOR, 255))
    draw = ImageDraw.Draw(canvas)

    # 1. Top Header Typography
    font_title = get_font(FONT_SERIF_BOLD, 70)
    font_subtitle = get_font(FONT_SANS_BOLD, 22)
    font_tagline = get_font(FONT_SANS_BOLD, 20)
    font_footer = get_font(FONT_SANS, 18)

    # Header Left
    draw_text_tracked(draw, (24 * SCALE, 12 * SCALE), "EMBERGLASS", font_title, HEADER_MAIN, tracking=10)
    draw_text_tracked(draw, (26 * SCALE, 46 * SCALE), "MODULAR ASSETS LIBRARY", font_subtitle, HEADER_SUB, tracking=5)

    # Header Right
    draw_text_tracked(draw, (1512 * SCALE, 18 * SCALE), "SAME PIECES, BIGGER STORIES", font_tagline, LABEL_COLOR, tracking=3, anchor="ra")
    draw_text_tracked(draw, (1512 * SCALE, 34 * SCALE), "A LIVING CITY, ONE BRICK AT A TIME", font_tagline, LABEL_COLOR, tracking=3, anchor="ra")

    # 2. Section Boxes & Sprites
    font_sec_title = get_font(FONT_SANS_BOLD, 20)
    font_item_label = get_font(FONT_SANS, 15)
    font_item_small = get_font(FONT_SANS, 13)

    for sec in SECTIONS:
        rx1, ry1, rx2, ry2 = sec["box"]
        x1 = int(rx1 * SCALE)
        y1 = int(ry1 * SCALE)
        x2 = int(rx2 * SCALE)
        y2 = int(ry2 * SCALE)

        # Draw clean 2px outline for box
        draw.rectangle([x1, y1, x2, y2], outline=BORDER_COLOR, width=2)

        # Draw Section Title Header
        title_text = sec["title"]
        draw_text_tracked(draw, (x1 + 16, y1 + 12), title_text, font_sec_title, TITLE_COLOR, tracking=3)

        # Content area geometry
        pad_top = 40
        pad_bottom = 10
        pad_left = 12
        pad_right = 12

        inner_x = x1 + pad_left
        inner_y = y1 + pad_top
        inner_w = (x2 - x1) - (pad_left + pad_right)
        inner_h = (y2 - y1) - (pad_top + pad_bottom)

        cols = sec["cols"]
        rows = sec["rows"]
        items = sec["items"]

        col_w = inner_w / float(cols)
        row_h = inner_h / float(rows)

        for idx, itm in enumerate(items):
            c = idx % cols
            r = idx // cols

            cell_cx = inner_x + c * col_w + col_w / 2.0
            cell_cy = inner_y + r * row_h + row_h / 2.0

            label_h = 24
            sprite_max_w = col_w * 0.92
            sprite_max_h = (row_h - label_h) * 0.94

            sprite = load_and_fit_sprite(itm["file"], sprite_max_w, sprite_max_h)
            if sprite:
                sw, sh = sprite.size
                sx = int(cell_cx - sw / 2.0)
                # Bottom-align sprite slightly above the label line for uniform ground alignment
                label_y = int(inner_y + r * row_h + (row_h - label_h))
                sy = int(label_y - sh - 4)

                # 1. Paste ambient contact drop shadow
                shadow = create_ambient_shadow(sprite, offset=(4, 8), blur_radius=6, opacity=0.50)
                canvas.paste(shadow, (sx + 4, sy + 8), shadow)

                # 2. Paste crisp sprite
                canvas.paste(sprite, (sx, sy), sprite)

            # Centered label
            lbl_font = font_item_label if len(itm["label"]) < 12 else font_item_small
            draw.text((cell_cx, inner_y + r * row_h + (row_h - label_h) + 2), itm["label"], font=lbl_font, fill=LABEL_COLOR, anchor="mt")

    # 3. Bottom Footer
    draw_text_tracked(draw, (24 * SCALE, 996 * SCALE), "EMBERGLASS   |   MODULAR ASSETS", font_footer, FOOTER_COLOR, tracking=3)
    draw_text_tracked(draw, (1512 * SCALE, 996 * SCALE), "FOR CITIES, TOWNS, OUTPOSTS AND EVERYTHING IN BETWEEN", font_footer, FOOTER_COLOR, tracking=3, anchor="ra")

    # Convert to RGB and save high quality
    final_canvas = canvas.convert("RGB")
    print(f"Saving final image to {OUT_PATH}...")
    final_canvas.save(OUT_PATH, quality=96)
    print("Master Sheet created successfully!")

if __name__ == "__main__":
    build_sheet()
