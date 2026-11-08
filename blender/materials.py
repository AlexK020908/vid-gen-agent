"""The fixed material palette. Every part names one of these; nothing else makes a shader.

Colors are linear (Blender's), picked against reference A's frames. `cut` is the section face a cutaway leaves:
orange with dark diagonal hatching in world space, so its lines run the same way on every part.
"""
from __future__ import annotations

import bpy

_made: dict[str, bpy.types.Material] = {}
ASSETS: dict[str, dict[str, str]] = {}   # Poly Haven texture id -> {"diff", "rough", "nor_gl"} paths, set by run.py

HAZE = (0.62, 0.70, 0.82)   # the far sky's color the ground and far things fade into


def get(name: str) -> bpy.types.Material:
    """A palette material by name. `cut:0.012` is the section face with its hatching 0.012 m apart, so a small
    machine's cut has lines as fine as a big one's look."""
    if name not in _made:
        base, _, arg = name.partition(":")
        _made[name] = _BUILD[base](name, float(arg)) if arg else _BUILD[base](name)
    return _made[name]


def hatch_for(size: float) -> str:
    """The `cut` material for a machine `size` meters across: about 22 lines across it."""
    return f"cut:{max(0.002, min(0.1, size / 22)):.4f}"


def assign(obj, name: str) -> None:
    obj.data.materials.clear()
    obj.data.materials.append(get(name))


# --- building blocks -------------------------------------------------------------------------------------------

def _new(name: str):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    bsdf = tree.nodes["Principled BSDF"]
    return mat, tree, bsdf


def _plain(name, color, metallic=0.0, roughness=0.5, emission=0.0, coat=0.0):
    mat, tree, bsdf = _new(name)
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Coat Weight"].default_value = coat
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*color, 1)
        bsdf.inputs["Emission Strength"].default_value = emission
    return mat


def _node(tree, kind, **inputs):
    node = tree.nodes.new(kind)
    for key, value in inputs.items():
        if key in node.inputs:
            node.inputs[key].default_value = value
        else:
            setattr(node, key, value)
    return node


def _world_position(tree):
    return _node(tree, "ShaderNodeNewGeometry").outputs["Position"]


def _noise(tree, scale, detail=4.0, coords=None):
    noise = _node(tree, "ShaderNodeTexNoise", Scale=scale, Detail=detail)
    if coords is not None:
        tree.links.new(coords, noise.inputs["Vector"])
    return noise.outputs["Fac"]


def _mix_color(tree, fac, a, b):
    mix = _node(tree, "ShaderNodeMix", data_type="RGBA")
    if isinstance(fac, float):
        mix.inputs["Factor"].default_value = fac
    else:
        tree.links.new(fac, mix.inputs["Factor"])
    for socket, value in ((mix.inputs[6], a), (mix.inputs[7], b)):
        if isinstance(value, tuple):
            socket.default_value = (*value, 1)
        else:
            tree.links.new(value, socket)
    return mix.outputs[2]


def _ramp(tree, fac, stops):
    """A color ramp from a factor: stops are (position, color) pairs."""
    ramp = _node(tree, "ShaderNodeValToRGB")
    tree.links.new(fac, ramp.inputs["Fac"])
    elements = ramp.color_ramp.elements
    while len(elements) > len(stops):
        elements.remove(elements[-1])
    while len(elements) < len(stops):
        elements.new(0.5)
    for element, (pos, color) in zip(elements, stops):
        element.position = pos
        element.color = (*color, 1) if len(color) == 3 else color
    return ramp.outputs["Color"]


def _textured(tree, bsdf, asset: str, scale: float, box: bool = False, rotate=(0.0, 0.0, 0.0)):
    """Poly Haven maps on a part, tiled every 1/scale meters in object space. `box` projects from all six sides,
    for a block of wood whose sides show grain too; `rotate` turns the maps (radians about x, y, z)."""
    paths = ASSETS[asset]
    coords = _node(tree, "ShaderNodeTexCoord").outputs["Object"]
    mapping = _node(tree, "ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (scale, scale, scale)
    mapping.inputs["Rotation"].default_value = rotate
    tree.links.new(coords, mapping.inputs["Vector"])

    def image(key, color):
        img = bpy.data.images.load(paths[key], check_existing=True)
        img.colorspace_settings.name = "sRGB" if color else "Non-Color"
        node = _node(tree, "ShaderNodeTexImage", image=img)
        if box:
            node.projection = "BOX"
            node.projection_blend = 0.15
        tree.links.new(mapping.outputs["Vector"], node.inputs["Vector"])
        return node

    diff = image("diff", True)
    tree.links.new(diff.outputs["Color"], bsdf.inputs["Base Color"])
    rough = image("rough", False)
    tree.links.new(rough.outputs["Color"], bsdf.inputs["Roughness"])
    nor = image("nor_gl", False)
    normal = _node(tree, "ShaderNodeNormalMap", Strength=0.8)
    tree.links.new(nor.outputs["Color"], normal.inputs["Color"])
    tree.links.new(normal.outputs["Normal"], bsdf.inputs["Normal"])
    return diff


def hazed(mat, start=70.0, depth=450.0, most=0.7):
    """Fade a far surface into the sky's haze with distance from the camera, the aerial perspective A has."""
    tree = mat.node_tree
    out = tree.nodes["Material Output"]
    shader = out.inputs["Surface"].links[0].from_socket
    dist = _node(tree, "ShaderNodeCameraData").outputs["View Distance"]
    fade = _node(tree, "ShaderNodeMapRange", clamp=True)
    fade.inputs["From Min"].default_value = start
    fade.inputs["From Max"].default_value = start + depth
    fade.inputs["To Max"].default_value = most
    tree.links.new(dist, fade.inputs["Value"])
    glow = _node(tree, "ShaderNodeEmission", Strength=1.0)
    glow.inputs["Color"].default_value = (*HAZE, 1)
    mix = _node(tree, "ShaderNodeMixShader")
    tree.links.new(fade.outputs["Result"], mix.inputs["Fac"])
    tree.links.new(shader, mix.inputs[1])
    tree.links.new(glow.outputs["Emission"], mix.inputs[2])
    tree.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat


# --- the palette -----------------------------------------------------------------------------------------------

def _steel(name):
    mat, tree, bsdf = _new(name)
    bsdf.inputs["Base Color"].default_value = (0.42, 0.43, 0.45, 1)
    bsdf.inputs["Metallic"].default_value = 1.0
    rough = _ramp(tree, _noise(tree, 6.0), [(0.3, (0.34, 0.34, 0.34)), (0.7, (0.39, 0.39, 0.39))])
    tree.links.new(rough, bsdf.inputs["Roughness"])
    return mat


def _dark_steel(name):
    """A's pile: blue-grey painted steel with a little rust and dirt in patches."""
    mat, tree, bsdf = _new(name)
    grime = _ramp(tree, _noise(tree, 3.0, detail=8.0), [(0.55, (0, 0, 0)), (0.75, (1, 1, 1))])
    color = _mix_color(tree, grime, (0.030, 0.048, 0.080), (0.085, 0.055, 0.035))
    tree.links.new(color, bsdf.inputs["Base Color"])
    bsdf.inputs["Metallic"].default_value = 0.35
    bsdf.inputs["Roughness"].default_value = 0.55
    return mat


def _hazard(name):
    """Yellow and black diagonal stripes, 8 cm a pair, in object space."""
    mat, tree, bsdf = _new(name)
    coords = _node(tree, "ShaderNodeTexCoord").outputs["Object"]
    sep = _node(tree, "ShaderNodeSeparateXYZ")
    tree.links.new(coords, sep.inputs["Vector"])
    add = _node(tree, "ShaderNodeMath", operation="ADD")
    tree.links.new(sep.outputs["X"], add.inputs[0])
    tree.links.new(sep.outputs["Z"], add.inputs[1])
    stripes = _node(tree, "ShaderNodeMath", operation="PINGPONG")
    stripes.inputs[1].default_value = 0.04
    tree.links.new(add.outputs[0], stripes.inputs[0])
    step = _node(tree, "ShaderNodeMath", operation="GREATER_THAN")
    step.inputs[1].default_value = 0.02
    tree.links.new(stripes.outputs[0], step.inputs[0])
    mix = _node(tree, "ShaderNodeMix", data_type="RGBA")
    tree.links.new(step.outputs[0], mix.inputs["Factor"])
    mix.inputs[6].default_value = (0.70, 0.46, 0.02, 1)
    mix.inputs[7].default_value = (0.015, 0.015, 0.015, 1)
    tree.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.5
    return mat


def _cut(name, period=0.07, line=0.3):
    """The section face: orange with dark hatching at 45 degrees, `period` meters apart, in world space."""
    mat, tree, bsdf = _new(name)
    pos = _world_position(tree)
    sep = _node(tree, "ShaderNodeSeparateXYZ")
    tree.links.new(pos, sep.inputs["Vector"])
    add = _node(tree, "ShaderNodeMath", operation="ADD")
    tree.links.new(sep.outputs["X"], add.inputs[0])
    tree.links.new(sep.outputs["Z"], add.inputs[1])
    scaled = _node(tree, "ShaderNodeMath", operation="DIVIDE")
    scaled.inputs[1].default_value = period
    tree.links.new(add.outputs[0], scaled.inputs[0])
    frac = _node(tree, "ShaderNodeMath", operation="FRACT")
    tree.links.new(scaled.outputs[0], frac.inputs[0])
    lines = _node(tree, "ShaderNodeMath", operation="LESS_THAN")
    lines.inputs[1].default_value = line
    tree.links.new(frac.outputs[0], lines.inputs[0])
    mix = _node(tree, "ShaderNodeMix", data_type="RGBA")
    tree.links.new(lines.outputs[0], mix.inputs["Factor"])
    mix.inputs[6].default_value = (0.80, 0.17, 0.05, 1)
    mix.inputs[7].default_value = (0.36, 0.045, 0.015, 1)
    tree.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.65
    return mat


def _black_glass(name):
    """A cooktop's top: nearly black, with only a faint sheen until it's seen at a low angle, as dark glass is."""
    mat = _plain(name, (0.0035, 0.0035, 0.004), roughness=0.16)
    next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Specular IOR Level"].default_value = 0.12
    return mat


def _counter_wood(name):
    """A kitchen counter's top: plain warm oak, matte, its grain running along x so it stays level across a square shot."""
    mat, tree, bsdf = _new(name)
    _textured(tree, bsdf, "oak_veneer_01", scale=1.3, rotate=(0.0, 0.0, 1.5708))
    diff = bsdf.inputs["Base Color"].links[0].from_socket
    tint = _node(tree, "ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY")
    tint.inputs["Factor"].default_value = 1.0
    tree.links.new(diff, tint.inputs[6])
    tint.inputs[7].default_value = (0.86, 0.72, 0.66, 1)
    tree.links.new(tint.outputs[2], bsdf.inputs["Base Color"])
    for link in list(bsdf.inputs["Roughness"].links):
        tree.links.remove(link)
    bsdf.inputs["Roughness"].default_value = 0.62
    bsdf.inputs["Specular IOR Level"].default_value = 0.3
    return mat


def custom(name: str, color=(0.5, 0.5, 0.5), metal: float = 0.0, rough: float = 0.5, coat: float = 0.0, glow: float = 0.0, pores: float = 0.0,
           clear: float = 0.0):
    """A part's own paint, by name, for what the palette doesn't have (`color` is linear, each 0 to 1). `pores` is how wide the holes in it are, in
    meters, for something soft and full of them: a sponge, bread, pumice. `clear` is how much you see through it, 0 to 1: glass is nearly 1, and
    water about half."""
    if name not in _made:
        _made[name] = _plain(name, tuple(color), metallic=metal, roughness=rough, emission=glow, coat=coat)
        if pores:
            _with_pores(_made[name], float(pores))
        if clear:
            see_through(_made[name], tuple(color), float(clear))
    return _made[name]


CLEAR_TINT = 0.7      # how much of the light coming through something clear keeps its own color, rather than taking the thing's


def see_through(mat, color, clear: float) -> None:
    """You see through it where it faces you, by `clear`, tinted a little by its own color, and its edges catch the light as glass's do. It's
    blended, not dithered, so it's clean at any number of samples; blended glass has no depth for a camera to focus on, so a shot of it can't be
    shallow (scenes/spec.py says how deep it has to be)."""
    mat.surface_render_method = "BLENDED"
    mat.use_transparency_overlap = True      # glass behind glass still shows
    mat.use_transparent_shadow = True        # light comes through it
    tree = mat.node_tree
    output = next(n for n in tree.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output)
    before = output.inputs["Surface"].links[0].from_socket
    facing = _node(tree, "ShaderNodeLayerWeight", Blend=0.12)
    shows = _node(tree, "ShaderNodeMath", operation="MAXIMUM")
    tree.links.new(facing.outputs["Fresnel"], shows.inputs[0])
    shows.inputs[1].default_value = 1.0 - clear
    through = _node(tree, "ShaderNodeBsdfTransparent")
    through.inputs["Color"].default_value = (*[CLEAR_TINT + (1 - CLEAR_TINT) * c for c in color], 1)
    mix = _node(tree, "ShaderNodeMixShader")
    tree.links.new(shows.outputs[0], mix.inputs[0])
    tree.links.new(through.outputs[0], mix.inputs[1])
    tree.links.new(before, mix.inputs[2])
    tree.links.new(mix.outputs[0], output.inputs["Surface"])


def _with_pores(mat, size: float) -> None:
    """Holes all over a material, darker inside, with their edges catching the light."""
    pores_on(mat.node_tree, next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), size)


def pores_on(tree, bsdf, size: float, object_scale: float = 1.0) -> None:
    """Holes all over one shader in a material, `size` meters wide on an object scaled by this."""
    coords = tree.nodes.new("ShaderNodeTexCoord")
    cells = tree.nodes.new("ShaderNodeTexVoronoi")
    cells.inputs["Scale"].default_value = object_scale / size
    tree.links.new(coords.outputs["Object"], cells.inputs["Vector"])
    holes = tree.nodes.new("ShaderNodeValToRGB")
    holes.color_ramp.elements[0].position, holes.color_ramp.elements[1].position = 0.16, 0.42
    tree.links.new(cells.outputs["Distance"], holes.inputs["Fac"])
    shade = tree.nodes.new("ShaderNodeMix")
    shade.data_type = "RGBA"
    shade.blend_type = "MULTIPLY"
    shade.inputs["Factor"].default_value = 1.0
    shade.inputs[6].default_value = bsdf.inputs["Base Color"].default_value
    lighten = tree.nodes.new("ShaderNodeMapRange")
    lighten.inputs["To Min"].default_value, lighten.inputs["To Max"].default_value = 0.3, 1.0
    tree.links.new(holes.outputs["Color"], lighten.inputs["Value"])
    combine = tree.nodes.new("ShaderNodeCombineColor")
    for socket in ("Red", "Green", "Blue"):
        tree.links.new(lighten.outputs["Result"], combine.inputs[socket])
    tree.links.new(combine.outputs["Color"], shade.inputs[7])
    tree.links.new(shade.outputs[2], bsdf.inputs["Base Color"])
    bump = tree.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.9
    bump.inputs["Distance"].default_value = size * 0.6
    tree.links.new(holes.outputs["Color"], bump.inputs["Height"])
    tree.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


def _floorboards(name):
    """A gym's varnished floor: dark oak in long boards with dark seams, glossy enough to show a soft reflection."""
    mat, tree, bsdf = _new(name)
    diff = _textured(tree, bsdf, "oak_veneer_01", scale=0.7)
    for link in list(bsdf.inputs["Base Color"].links):
        tree.links.remove(link)
    boards = tree.nodes.new("ShaderNodeTexBrick")
    boards.offset = 0.5
    boards.squash = 1.0
    boards.inputs["Color1"].default_value = (0.42, 0.40, 0.38, 1)
    boards.inputs["Color2"].default_value = (0.30, 0.28, 0.26, 1)
    boards.inputs["Mortar"].default_value = (0.02, 0.015, 0.01, 1)
    boards.inputs["Scale"].default_value = 1.0
    boards.inputs["Mortar Size"].default_value = 0.004
    boards.inputs["Brick Width"].default_value = 1.6
    boards.inputs["Row Height"].default_value = 0.16
    coords = tree.nodes.new("ShaderNodeTexCoord")
    tree.links.new(coords.outputs["Object"], boards.inputs["Vector"])
    shade = tree.nodes.new("ShaderNodeVectorMath")
    shade.operation = "MULTIPLY"
    tree.links.new(diff.outputs["Color"], shade.inputs[0])
    tree.links.new(boards.outputs["Color"], shade.inputs[1])
    tree.links.new(shade.outputs["Vector"], bsdf.inputs["Base Color"])
    bsdf.inputs["Coat Weight"].default_value = 0.7
    bsdf.inputs["Coat Roughness"].default_value = 0.12
    return mat


def _wood(name):
    mat, tree, bsdf = _new(name)
    _textured(tree, bsdf, "oak_veneer_01", scale=6.0, box=True)
    bsdf.inputs["Coat Weight"].default_value = 0.4
    return mat


def _wave(tree, scale, direction, distortion=0.0, detail=2.0, coords=None):
    """Bands along `direction` (X, Y or Z) in object space, about 3.2 x `scale` bands a meter."""
    wave = _node(tree, "ShaderNodeTexWave", wave_type="BANDS", bands_direction=direction, Scale=scale,
                 Distortion=distortion, Detail=detail)
    tree.links.new(coords if coords is not None else _node(tree, "ShaderNodeTexCoord").outputs["Object"],
                   wave.inputs["Vector"])
    return wave.outputs["Fac"]


def _bump(tree, bsdf, height, strength, distance=0.001):
    bump = _node(tree, "ShaderNodeBump", Strength=strength, Distance=distance)
    tree.links.new(height, bump.inputs["Height"])
    tree.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


def _pale_wood(name):
    """A's block: plain pale wood, a few soft lengthwise streaks and a fine sanded ripple, no knots or loops."""
    mat, tree, bsdf = _new(name)
    streaks = _ramp(tree, _wave(tree, 9.0, "Y", distortion=3.0, detail=3.0),
                    [(0.0, (0.45, 0.34, 0.22)), (1.0, (0.38, 0.28, 0.17))])
    tree.links.new(streaks, bsdf.inputs["Base Color"])
    _bump(tree, bsdf, _wave(tree, 260.0, "Y", distortion=6.0, detail=2.0), strength=0.18)
    bsdf.inputs["Roughness"].default_value = 0.62
    return mat


def _wood_cut(name):
    """Sawn wood, as A shows the inside of the block the nail goes into: darker brown, with fine crosswise ridges
    broken into short dashes."""
    mat, tree, bsdf = _new(name)
    color = _ramp(tree, _noise(tree, 40.0, detail=3.0), [(0.3, (0.11, 0.068, 0.034)), (0.7, (0.145, 0.088, 0.042))])
    tree.links.new(color, bsdf.inputs["Base Color"])
    ridges = _wave(tree, 120.0, "Z", distortion=1.5, detail=1.0)
    breaks = _ramp(tree, _noise(tree, 180.0, detail=1.0), [(0.4, (0.2, 0.2, 0.2)), (0.6, (1, 1, 1))])
    dashes = _node(tree, "ShaderNodeMath", operation="MULTIPLY")
    tree.links.new(ridges, dashes.inputs[0])
    tree.links.new(breaks, dashes.inputs[1])
    _bump(tree, bsdf, dashes.outputs[0], strength=0.55)
    bsdf.inputs["Roughness"].default_value = 0.85
    return mat


def _sand(name):
    mat, tree, bsdf = _new(name)
    _textured(tree, bsdf, "red_sand", scale=0.35)
    # A's sand is a warm, even orange: push the photo toward it
    diff = bsdf.inputs["Base Color"].links[0].from_socket
    tint = _node(tree, "ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY")
    tint.inputs["Factor"].default_value = 1.0
    tree.links.new(diff, tint.inputs[6])
    tint.inputs[7].default_value = (0.70, 0.43, 0.16, 1)   # to A's #C8814A to #D39A63, under AgX in full sun
    tree.links.new(tint.outputs[2], bsdf.inputs["Base Color"])
    return hazed(mat, start=250.0, depth=600.0, most=0.15)   # A's far sand stays orange to the horizon


def _pile_paint(name, ring=0.6, band=4.2):
    """A's pile: the blue-grey steel with thin white rings every `ring` meters up its length and wider red-orange
    bands every `band`, red-orange at the tip, in the pile's own space so they ride with it as it sinks."""
    mat, tree, bsdf = _new(name)
    grime = _ramp(tree, _noise(tree, 3.0, detail=8.0), [(0.55, (0, 0, 0)), (0.75, (1, 1, 1))])
    steel = _mix_color(tree, grime, (0.030, 0.048, 0.080), (0.085, 0.055, 0.035))
    z = _node(tree, "ShaderNodeSeparateXYZ")
    tree.links.new(_node(tree, "ShaderNodeTexCoord").outputs["Object"], z.inputs["Vector"])

    def every(period, width):
        wrap = _node(tree, "ShaderNodeMath", operation="WRAP")
        wrap.inputs[1].default_value = period
        wrap.inputs[2].default_value = 0.0
        tree.links.new(z.outputs["Z"], wrap.inputs[0])
        on = _node(tree, "ShaderNodeMath", operation="LESS_THAN")
        on.inputs[1].default_value = width
        tree.links.new(wrap.outputs[0], on.inputs[0])
        return on.outputs[0]

    tip = _node(tree, "ShaderNodeMath", operation="LESS_THAN")
    tip.inputs[1].default_value = 0.25
    tree.links.new(z.outputs["Z"], tip.inputs[0])
    red = _node(tree, "ShaderNodeMath", operation="MAXIMUM")
    tree.links.new(every(band, 0.22), red.inputs[0])
    tree.links.new(tip.outputs[0], red.inputs[1])
    color = _mix_color(tree, every(ring, 0.045), steel, (0.72, 0.72, 0.70))
    color = _mix_color(tree, red.outputs[0], color, (0.60, 0.10, 0.03))
    tree.links.new(color, bsdf.inputs["Base Color"])
    bsdf.inputs["Metallic"].default_value = 0.35
    bsdf.inputs["Roughness"].default_value = 0.55
    return mat


def _glass_rod(name):
    """A's guide rods: clear and glassy near the top, darkening to near black toward the bottom."""
    mat, tree, bsdf = _new(name)
    z = _node(tree, "ShaderNodeSeparateXYZ")
    tree.links.new(_node(tree, "ShaderNodeTexCoord").outputs["Generated"], z.inputs["Vector"])
    shade = _ramp(tree, z.outputs["Z"], [(0.0, (0.01, 0.01, 0.012)), (0.45, (0.05, 0.05, 0.055)),
                                         (0.75, (0.6, 0.62, 0.65))])
    tree.links.new(shade, bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.08
    bsdf.inputs["Coat Weight"].default_value = 0.6
    bsdf.inputs["Specular IOR Level"].default_value = 0.8
    return mat


def _stripes(name, a, b, width=0.25):
    """Two colours in diagonal stripes `width` meters a pair, in object space: a site barrier, a cone's bands."""
    mat, tree, bsdf = _new(name)
    coords = _node(tree, "ShaderNodeTexCoord").outputs["Object"]
    sep = _node(tree, "ShaderNodeSeparateXYZ")
    tree.links.new(coords, sep.inputs["Vector"])
    add = _node(tree, "ShaderNodeMath", operation="ADD")
    tree.links.new(sep.outputs["X"], add.inputs[0])
    tree.links.new(sep.outputs["Z"], add.inputs[1])
    wave = _node(tree, "ShaderNodeMath", operation="PINGPONG")
    wave.inputs[1].default_value = width / 2
    tree.links.new(add.outputs[0], wave.inputs[0])
    step = _node(tree, "ShaderNodeMath", operation="GREATER_THAN")
    step.inputs[1].default_value = width / 4
    tree.links.new(wave.outputs[0], step.inputs[0])
    tree.links.new(_mix_color(tree, step.outputs[0], a, b), bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.5
    return mat


def _soil(name, color, grain=6.0):
    """A soil layer in the ground's cutaway: a flat earth colour with a little mottling."""
    mat, tree, bsdf = _new(name)
    dark = tuple(c * 0.8 for c in color)
    tree.links.new(_ramp(tree, _noise(tree, grain, detail=5.0), [(0.35, dark), (0.65, color)]),
                   bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.9
    return mat


def _far(name):
    return hazed(_plain(name, (0.40, 0.45, 0.52), roughness=0.6), start=40.0, depth=250.0, most=0.6)


_BUILD = {
    "steel": _steel,
    "dark_steel": _dark_steel,
    "pile_paint": _pile_paint,
    "glass_rod": _glass_rod,
    "safety_yellow": lambda n: _plain(n, (0.62, 0.38, 0.03), roughness=0.42, coat=0.1),
    "hazard_stripes": _hazard,
    "cut": _cut,
    "chrome": lambda n: _plain(n, (0.85, 0.85, 0.86), metallic=1.0, roughness=0.08),
    "bright_steel": lambda n: _plain(n, (0.70, 0.70, 0.71), metallic=0.75, roughness=0.3),   # a nail, a polished rod
    "black_steel": lambda n: _plain(n, (0.035, 0.035, 0.038), metallic=0.85, roughness=0.24),  # a hammer's head
    "copper": lambda n: _plain(n, (0.86, 0.40, 0.15), metallic=1.0, roughness=0.3),      # a sword guard's rim, a cooker's coil
    "cord": lambda n: _plain(n, (0.20, 0.09, 0.035), metallic=0.1, roughness=0.62),      # cord wound on a grip
    "floorboards": _floorboards,
    "gym_wall": lambda n: _plain(n, (0.02, 0.20, 0.62), roughness=0.55),                 # a saturated painted blue
    "gym_panel": lambda n: _plain(n, (0.16, 0.52, 0.95), roughness=0.4),                 # a lighter blue window panel
    "gym_trim": lambda n: _plain(n, (0.70, 0.80, 0.92), roughness=0.45),
    "impact_red": lambda n: _plain(n, (1.0, 0.04, 0.03), emission=7.0),                  # shock rings on a hit
    "spark": lambda n: _plain(n, (1.0, 0.95, 0.85), emission=9.0),
    "stainless": lambda n: _plain(n, (0.56, 0.56, 0.57), metallic=1.0, roughness=0.24),    # a good steel pan
    "cast_iron": lambda n: _plain(n, (0.17, 0.16, 0.15), metallic=0.92, roughness=0.4),    # a seasoned iron pan
    "black_glass": _black_glass,                                                           # a cooktop's top
    "bakelite": lambda n: _plain(n, (0.012, 0.012, 0.013), roughness=0.38),                # a pan's handle
    "counter_wood": _counter_wood,
    "rubber": lambda n: _plain(n, (0.02, 0.02, 0.02), roughness=0.75),
    "white_paint": lambda n: _plain(n, (0.62, 0.62, 0.61), roughness=0.5),
    "red_paint": lambda n: _plain(n, (0.55, 0.025, 0.015), roughness=0.45),
    "blue_paint": lambda n: _plain(n, (0.02, 0.09, 0.36), roughness=0.45),
    "orange_paint": lambda n: _plain(n, (0.85, 0.22, 0.02), roughness=0.5),            # a traffic cone
    "barrier_stripes": lambda n: _stripes(n, (0.85, 0.22, 0.02), (0.8, 0.8, 0.78)),     # a site barrier
    "soil_top": lambda n: _soil(n, (0.62, 0.20, 0.06)),       # A's ground in section: orange under the sand,
    "soil_mid": lambda n: _soil(n, (0.32, 0.13, 0.05)),       # a brown band,
    "soil_low": lambda n: _soil(n, (0.52, 0.38, 0.22)),       # tan,
    "soil_deep": lambda n: _soil(n, (0.16, 0.20, 0.26)),      # and blue-grey at the bottom
    "air": lambda n: _plain(n, (0.46, 0.68, 0.87), roughness=0.25, emission=0.12),
    "clear_glass": lambda n: custom(n, (0.78, 0.8, 0.83), metal=1.0, rough=0.04, clear=0.96),     # a tube, a beaker, a dish, a pane: what's in it shows. Its mirror's
                                                                                                    # toned down: at a grazing angle a full one is the studio's white
    "wood": _wood,             # varnished oak with its grain: a hammer's handle
    "pale_wood": _pale_wood,
    "wood_cut": _wood_cut,
    "sand": _sand,
    "far": _far,
}
PALETTE = tuple(_BUILD)
