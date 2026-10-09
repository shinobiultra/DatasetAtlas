"""Unmodified pure rendering functions from israfelsr/vlm-pathways.

Revision: 470944b3f6b44901a9055cf8d91aef18cee21671
File: data/generate_shapes_dataset.py
Upstream SHA-256: b5194a6a4b096713a41cfc4ef102bfbfc23041ac0ed63ac5907528fcb89b48fb

MIT License

Copyright (c) 2026 Israfel Salazar

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

"""
import math
import random
from itertools import combinations
from PIL import Image, ImageDraw

SHAPES = ["circle", "square", "triangle", "star", "diamond", "pentagon"]

SHAPES_RECOGNITION = [
    "circle",
    "square",
    "triangle",
    "star",
]

COLORS = {
    "red": (220, 50, 50),
    "blue": (50, 80, 220),
    "green": (50, 180, 70),
    "yellow": (230, 200, 40),
    "orange": (240, 140, 30),
    "purple": (150, 50, 200),
}

def draw_shape(draw, shape, center, size, color):
    """Draw a shape centered at (cx, cy) with given size and color."""
    cx, cy = center
    r = size // 2

    if shape == "circle":
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r], fill=color, outline=(0, 0, 0), width=2
        )

    elif shape == "square":
        draw.rectangle(
            [cx - r, cy - r, cx + r, cy + r], fill=color, outline=(0, 0, 0), width=2
        )

    elif shape == "triangle":
        points = [
            (cx, cy - r),  # top
            (cx - r, cy + r),  # bottom-left
            (cx + r, cy + r),  # bottom-right
        ]
        draw.polygon(points, fill=color, outline=(0, 0, 0), width=2)

    elif shape == "star":
        # 5-pointed star
        points = []
        for i in range(10):
            angle = math.radians(i * 36 - 90)
            radius = r if i % 2 == 0 else r * 0.4
            points.append(
                (cx + radius * math.cos(angle), cy + radius * math.sin(angle))
            )
        draw.polygon(points, fill=color, outline=(0, 0, 0), width=2)

    elif shape == "diamond":
        points = [
            (cx, cy - r),  # top
            (cx + r, cy),  # right
            (cx, cy + r),  # bottom
            (cx - r, cy),  # left
        ]
        draw.polygon(points, fill=color, outline=(0, 0, 0), width=2)

    elif shape == "pentagon":
        points = []
        for i in range(5):
            angle = math.radians(i * 72 - 90)
            points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        draw.polygon(points, fill=color, outline=(0, 0, 0), width=2)

def compute_relation(pos1, pos2):
    """Compute spatial relation of obj1 relative to obj2.

    Returns the primary spatial relation based on the larger offset axis.
    """
    c1x, c1y = pos1
    c2x, c2y = pos2

    dx = c1x - c2x  # positive = obj1 is to the right of obj2
    dy = c1y - c2y  # positive = obj1 is below obj2

    if abs(dx) > abs(dy):
        return "right" if dx > 0 else "left"
    else:
        return "below" if dy > 0 else "above"

def get_grid_positions(image_size, grid_rows, grid_cols, shape_size):
    """Compute cell center positions for a grid layout.

    Returns dict mapping (row, col) -> (cx, cy).
    """
    margin = shape_size
    usable_w = image_size - 2 * margin
    usable_h = image_size - 2 * margin

    positions = {}
    for r in range(grid_rows):
        for c in range(grid_cols):
            cx = margin + int(usable_w * (c + 0.5) / grid_cols)
            cy = margin + int(usable_h * (r + 0.5) / grid_rows)
            positions[(r, c)] = (cx, cy)

    return positions

def generate_center_paired_dataset(n_pairs, image_size, grid_spec, shape_size, seed=42):
    """Generate paired samples with center layout for cross-object patching.

    One object (obj2, the reference) is always at the grid center.
    The other object (obj1, asked-about) is at a cardinal position.

    Each pair: same objects, obj1 moves to a different cardinal position → relation changes.
    The center object's image patches are identical between paired images (same visual
    content, same position), enabling clean cross-object patching experiments.

    Args:
        n_pairs: Number of pairs to generate.
        image_size: Image width/height in pixels.
        grid_spec: Tuple (rows, cols) for position grid. Should have odd dimensions for center.
        shape_size: Shape diameter in pixels.
        seed: Random seed.

    Returns:
        List of sample dicts with extra fields: obj1_position, obj2_position,
        shape_size, image_size. Samples at 2*i and 2*i+1 form a pair.
    """
    rng = random.Random(seed)
    grid_rows, grid_cols = grid_spec
    grid_positions = get_grid_positions(image_size, grid_rows, grid_cols, shape_size)

    # Center cell
    center_row = grid_rows // 2
    center_col = grid_cols // 2
    center_cell = (center_row, center_col)
    center_pos = grid_positions[center_cell]

    # Cardinal neighbors only (no diagonals)
    cardinal_offsets = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    cardinal_cells = []
    for dr, dc in cardinal_offsets:
        r, c = center_row + dr, center_col + dc
        if (r, c) in grid_positions:
            cardinal_cells.append((r, c))

    if len(cardinal_cells) < 2:
        raise ValueError(
            f"Need at least 2 cardinal neighbors. Grid {grid_spec} gives {len(cardinal_cells)}."
        )

    # Generate pair options: two different cardinal positions with different relations
    pair_options = []
    for c1, c2 in combinations(cardinal_cells, 2):
        # obj1 at c1/c2 (peripheral), obj2 at center (reference)
        # Question: "Where is obj1 in relation to obj2?"
        rel_a = compute_relation(grid_positions[c1], center_pos)
        rel_b = compute_relation(grid_positions[c2], center_pos)
        if rel_a != rel_b:
            pair_options.append((c1, c2, rel_a, rel_b))

    if not pair_options:
        raise ValueError("No valid pair options found with different relations.")

    samples = []
    for pair_id in range(n_pairs):
        c1, c2, rel_a, rel_b = rng.choice(pair_options)

        # Pick objects
        shape1 = rng.choice(SHAPES)  # peripheral (obj1)
        shape2 = rng.choice(SHAPES)  # center (obj2)
        color_names = list(COLORS.keys())
        cn1, cn2 = rng.sample(color_names, 2)

        obj1_name = f"{cn1} {shape1}"
        obj2_name = f"{cn2} {shape2}"

        pos_a = grid_positions[c1]  # obj1 in image A
        pos_b = grid_positions[c2]  # obj1 in image B

        # Image A: obj1 at cardinal position c1, obj2 at center
        img_a = Image.new("RGB", (image_size, image_size), (255, 255, 255))
        draw_a = ImageDraw.Draw(img_a)
        draw_shape(draw_a, shape1, pos_a, shape_size, COLORS[cn1])
        draw_shape(draw_a, shape2, center_pos, shape_size, COLORS[cn2])

        # Image B: obj1 at cardinal position c2, obj2 at center
        img_b = Image.new("RGB", (image_size, image_size), (255, 255, 255))
        draw_b = ImageDraw.Draw(img_b)
        draw_shape(draw_b, shape1, pos_b, shape_size, COLORS[cn1])
        draw_shape(draw_b, shape2, center_pos, shape_size, COLORS[cn2])

        for img, pos, rel in [(img_a, pos_a, rel_a), (img_b, pos_b, rel_b)]:
            samples.append(
                {
                    "image": img,
                    "objects": [obj1_name, obj2_name],
                    "preposition": rel,
                    "pair_id": pair_id,
                    "obj1_position": list(pos),
                    "obj2_position": list(center_pos),
                    "shape_size": shape_size,
                    "image_size": image_size,
                }
            )

    return samples

def generate_single_position_pairs(n_pairs, image_size, grid_spec, shape_size, seed=42):
    """Generate paired single-object images for absolute position causal tracing.

    Each pair: same object at two opposite positions (left↔right or above↔below).
    One object per image, clearly on one side.

    Positions use the 4 cardinal cells of the grid (mid-left, mid-right, top-center, bottom-center).
    """
    rng = random.Random(seed)
    grid_rows, grid_cols = grid_spec
    grid_positions = get_grid_positions(image_size, grid_rows, grid_cols, shape_size)

    center_row = grid_rows // 2
    center_col = grid_cols // 2

    # Axis-opposite pairs using cardinal neighbors of grid center.
    # Same positions as the peripheral object in controlled_shapes_pairs (center layout).
    axis_pairs = []
    # Left-right: one step left/right of center
    left_cell = (center_row, center_col - 1)
    right_cell = (center_row, center_col + 1)
    if left_cell in grid_positions and right_cell in grid_positions:
        axis_pairs.append((left_cell, right_cell, "left", "right"))
    # Above-below: one step above/below center
    above_cell = (center_row - 1, center_col)
    below_cell = (center_row + 1, center_col)
    if above_cell in grid_positions and below_cell in grid_positions:
        axis_pairs.append((above_cell, below_cell, "above", "below"))

    if not axis_pairs:
        raise ValueError(f"No axis pairs found with grid {grid_spec}")

    samples = []
    for pair_id in range(n_pairs):
        c1, c2, rel_a, rel_b = rng.choice(axis_pairs)
        pos_a = grid_positions[c1]
        pos_b = grid_positions[c2]

        # Pick one shape+color
        shape = rng.choice(SHAPES_RECOGNITION)
        color_name = rng.choice(list(COLORS.keys()))
        obj_name = f"{color_name} {shape}"

        for pos, rel in [(pos_a, rel_a), (pos_b, rel_b)]:
            img = Image.new("RGB", (image_size, image_size), (255, 255, 255))
            draw = ImageDraw.Draw(img)
            draw_shape(draw, shape, pos, shape_size, COLORS[color_name])

            samples.append(
                {
                    "image": img,
                    "objects": [obj_name],
                    "preposition": rel,
                    "pair_id": pair_id,
                    "obj1_position": list(pos),
                    "shape_size": shape_size,
                    "image_size": image_size,
                }
            )

    return samples

def generate_single_recognition_pairs(
    n_pairs, image_size, grid_spec, shape_size, seed=42
):
    """Generate paired single-object images for recognition causal tracing.

    Each pair: two different shapes at the same position, same color.
    The ground truth is the shape name (stored in 'preposition' for pipeline compatibility).
    """
    rng = random.Random(seed)
    grid_rows, grid_cols = grid_spec
    grid_positions = get_grid_positions(image_size, grid_rows, grid_cols, shape_size)

    center_row = grid_rows // 2
    center_col = grid_cols // 2

    # Use cardinal positions (not center — object should be clearly somewhere)
    cardinal_cells = []
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        cell = (center_row + dr, center_col + dc)
        if cell in grid_positions:
            cardinal_cells.append(cell)

    # Shape pairs (different shapes)
    shape_pairs = []
    for i, s1 in enumerate(SHAPES_RECOGNITION):
        for s2 in SHAPES_RECOGNITION[i + 1 :]:
            shape_pairs.append((s1, s2))

    samples = []
    for pair_id in range(n_pairs):
        cell = rng.choice(cardinal_cells)
        pos = grid_positions[cell]
        s1, s2 = rng.choice(shape_pairs)
        color_name = rng.choice(list(COLORS.keys()))

        for shape in [s1, s2]:
            obj_name = f"{color_name} {shape}"
            img = Image.new("RGB", (image_size, image_size), (255, 255, 255))
            draw = ImageDraw.Draw(img)
            draw_shape(draw, shape, pos, shape_size, COLORS[color_name])

            samples.append(
                {
                    "image": img,
                    "objects": [obj_name],
                    "preposition": shape,  # GT is the shape name
                    "pair_id": pair_id,
                    "obj1_position": list(pos),
                    "shape_size": shape_size,
                    "image_size": image_size,
                }
            )

    return samples
