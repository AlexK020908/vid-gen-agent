"""Light that belongs to something. A glow lives on a thing's own surface or in a thin line along it, the way the reference has
it, and never as a ball of light floating in front: a surface's glow can't leave its edges, because it's on them.

  surface   a thing's own materials light up, whole or in a patch around a spot, keeping its shape
  line      a thin tube along a path, white-hot from strength, its color coming back in the bloom around it, with pulses or beads
            running along it
  ring      a clean thin circle spreading from a point, a constant width whatever its size
  tint      a thing's own color shifting over time: a steak browning
"""
from __future__ import annotations

import math

import bpy
from mathutils import Matrix, Vector

from blender import look

COLORS = {"green": (0.03, 1.0, 0.12), "red": (1.0, 0.04, 0.03), "blue": (0.04, 0.3, 1.0), "yellow": (1.0, 0.75, 0.03),
          "white": (1.0, 1.0, 1.0), "orange": (1.0, 0.32, 0.05), "cream": (1.0, 0.72, 0.36), "cyan": (0.22, 0.72, 1.0),
          "salmon": (1.0, 0.36, 0.33), "gold": (1.0, 0.56, 0.1), "ice": (0.5, 0.78, 1.0)}
UP = Vector((0, 0, 1))


def color_of(value) -> tuple:
    return tuple(value) if isinstance(value, (list, tuple)) else COLORS[value]


def _keys(socket, keys) -> None:
    for frame, value in keys:
        socket.default_value = value
        socket.keyframe_insert("default_value", frame=frame)


def _straight(tree) -> None:
    """Every key in a node tree runs in straight lines, so a clock keyed by its ends ticks evenly."""
    data = tree.animation_data
    if data and data.action:
        for curve in look._fcurves(data.action):
            for point in curve.keyframe_points:
                point.interpolation = "LINEAR"


def _math(tree, operation, a, b=None):
    node = tree.nodes.new("ShaderNodeMath")
    node.operation = operation
    for socket, value in zip(node.inputs, (a, b)):
        if value is None:
            continue
        if isinstance(value, (int, float)):
            socket.default_value = value
        else:
            tree.links.new(value, socket)
    return node.outputs[0]


def _envelope(begin: int, end: int, fade: int, last: int) -> list[tuple]:
    """How much of something shows, frame by frame: up from nothing at `begin`, and back down by `end` unless it runs on to the
    end of the scene."""
    keys = [(max(1, begin - 1), 0.0), (begin + max(1, fade), 1.0)]
    if end < last:
        keys += [(max(begin + fade + 1, end - fade), 1.0), (end, 0.0)]
    return keys


def _materials(meshes: list) -> list:
    found = []
    for obj in meshes:
        for slot in obj.material_slots:
            if slot.material is not None and slot.material not in found:
                found.append(slot.material)
    return found


def surface(meshes: list, color, begin: int, end: int, fade: int, last: int, strength: float = 1.0, cover: float = 0.92,
            centre=None, radius: float | None = None, edge: float = 0.55, rim: float = 0.0, soft: float = 0.75) -> None:
    """These meshes' own materials light up. With `centre` (an object riding on them) and `radius` (meters), only a patch does,
    strongest at the middle. The edges facing away from the lens run paler, so it keeps its shape as a lit object does. `rim`, from
    0 to 1, moves the light onto those edges: the middle keeps more of its own color, and the edges burn bright enough for a halo. `soft`
    is the share of a patch's radius it fades over: small for a crisp edge, as on the floor of a pan."""
    color = color_of(color)
    for mat in _materials(meshes):
        mat.use_nodes = True
        tree = mat.node_tree
        output = next(n for n in tree.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output)
        if not output.inputs["Surface"].links:
            continue
        before = output.inputs["Surface"].links[0].from_socket
        level = tree.nodes.new("ShaderNodeValue")
        _keys(level.outputs[0], _envelope(begin, end, fade, last))
        facing = tree.nodes.new("ShaderNodeLayerWeight")
        facing.inputs["Blend"].default_value = 0.35
        around = _math(tree, "POWER", facing.outputs["Facing"], 1.4)
        pale = _math(tree, "MULTIPLY", _math(tree, "POWER", facing.outputs["Facing"], 2.0), edge)
        shade = tree.nodes.new("ShaderNodeMix")
        shade.data_type = "RGBA"
        tree.links.new(pale, shade.inputs["Factor"])
        shade.inputs[6].default_value = (*color, 1)
        shade.inputs[7].default_value = (1.0, 0.93, 0.82, 1)
        light = tree.nodes.new("ShaderNodeEmission")
        tree.links.new(shade.outputs[2], light.inputs["Color"])
        tree.links.new(_math(tree, "MULTIPLY", strength, _math(tree, "ADD", 1.0, _math(tree, "MULTIPLY", around, rim * 3.0))), light.inputs["Strength"])
        amount = _math(tree, "MULTIPLY", level.outputs[0],
                       _math(tree, "MULTIPLY", cover, _math(tree, "ADD", 1.0 - rim, _math(tree, "MULTIPLY", around, rim))))
        if centre is not None and radius:
            coords = tree.nodes.new("ShaderNodeTexCoord")
            coords.object = centre
            distance = tree.nodes.new("ShaderNodeVectorMath")
            distance.operation = "LENGTH"
            tree.links.new(coords.outputs["Object"], distance.inputs[0])
            falloff = tree.nodes.new("ShaderNodeMapRange")
            falloff.interpolation_type = "SMOOTHERSTEP"
            falloff.inputs["From Min"].default_value = radius * (1 - soft)
            falloff.inputs["From Max"].default_value = radius
            falloff.inputs["To Min"].default_value = 1.0
            falloff.inputs["To Max"].default_value = 0.0
            tree.links.new(distance.outputs["Value"], falloff.inputs["Value"])
            amount = _math(tree, "MULTIPLY", amount, falloff.outputs["Result"])
        mix = tree.nodes.new("ShaderNodeMixShader")
        tree.links.new(amount, mix.inputs[0])
        tree.links.new(before, mix.inputs[1])
        tree.links.new(light.outputs[0], mix.inputs[2])
        tree.links.new(mix.outputs[0], output.inputs["Surface"])


def tint(meshes: list, color, begin: int, end: int, amount: float = 1.0) -> None:
    """These meshes' own color multiplied toward `color` from `begin` to `end`, and staying there."""
    for mat in _materials(meshes):
        tree = mat.node_tree
        bsdf = next((n for n in tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None:
            continue
        base = bsdf.inputs["Base Color"]
        multiply = tree.nodes.new("ShaderNodeMix")
        multiply.data_type = "RGBA"
        multiply.blend_type = "MULTIPLY"
        if base.links:
            tree.links.new(base.links[0].from_socket, multiply.inputs[6])
        else:
            multiply.inputs[6].default_value = base.default_value
        multiply.inputs[7].default_value = (*color_of(color), 1)
        tree.links.new(multiply.outputs[2], base)
        _keys(multiply.inputs["Factor"], [(begin, 0.0), (max(begin + 1, end), amount)])


def _light_material(name: str) -> tuple:
    """A material that adds light to whatever's behind it. Returns it, its tree, and the emission to fill in."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.surface_render_method = "BLENDED"
    mat.use_transparent_shadow = True
    tree = mat.node_tree
    tree.nodes.clear()
    light = tree.nodes.new("ShaderNodeEmission")
    add = tree.nodes.new("ShaderNodeAddShader")
    tree.links.new(tree.nodes.new("ShaderNodeBsdfTransparent").outputs[0], add.inputs[0])
    tree.links.new(light.outputs[0], add.inputs[1])
    tree.links.new(add.outputs[0], tree.nodes.new("ShaderNodeOutputMaterial").inputs["Surface"])
    return mat, tree, light


def tube(name: str, points: list[Vector], radius: float, closed: bool = False, sides: int = 6):
    """A thin tube along points, with its U running 0 to 1 from end to end, for what's drawn along it. A closed loop's last ring
    sits on its first, so U jumps cleanly there."""
    points = [*points, points[0]] if closed else list(points)
    lengths = [0.0]
    for a, b in zip(points, points[1:]):
        lengths.append(lengths[-1] + (b - a).length)
    total = lengths[-1] or 1.0
    verts, faces, us = [], [], []
    side = None
    for i, point in enumerate(points):
        along = (points[min(i + 1, len(points) - 1)] - points[max(i - 1, 0)]).normalized()
        if side is None:
            side = along.cross(UP if abs(along.dot(UP)) < 0.9 else Vector((1, 0, 0))).normalized()
        side = (side - along * side.dot(along)).normalized()
        other = along.cross(side).normalized()
        for k in range(sides):
            angle = math.tau * k / sides
            verts.append(point + (side * math.cos(angle) + other * math.sin(angle)) * radius)
            us.append(lengths[i] / total)
    for i in range(len(points) - 1):
        for k in range(sides):
            a, b = i * sides + k, i * sides + (k + 1) % sides
            faces.append((a, b, b + sides, a + sides))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(v) for v in verts], [], faces)
    layer = mesh.uv_layers.new(name="along")
    for loop in mesh.loops:
        layer.data[loop.index].uv = (us[loop.vertex_index], 0.0)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def line_material(name: str, color, begin: int, end: int, fade: int, last: int, fps: int, steady: float = 7.0, peak: float = 46.0,
                  pulses: float = 4.0, speed: float = 1.0, duty: float = 0.3, reverse: float = 0.0):
    """Light along a tube: `steady` all along, and `pulses` brighter stretches running along it at `speed` a second. With
    `reverse`, in seconds, they turn back that often. Strong enough that its core goes white, with its color in the halo."""
    mat, tree, light = _light_material(name)
    light.inputs["Color"].default_value = (*color_of(color), 1)
    along = tree.nodes.new("ShaderNodeUVMap")
    along.uv_map = "along"
    split = tree.nodes.new("ShaderNodeSeparateXYZ")
    tree.links.new(along.outputs["UV"], split.inputs[0])
    clock = tree.nodes.new("ShaderNodeValue")
    span = max(1, end - begin)
    if reverse > 0:
        keys, at, phase, way = [(begin, 0.0)], begin, 0.0, 1
        step = max(1, round(reverse * fps))
        while at < end:
            at = min(end, at + step)
            phase += way * speed * reverse
            keys.append((at, phase))
            way = -way
        _keys(clock.outputs[0], keys)
    else:
        _keys(clock.outputs[0], [(begin, 0.0), (end, speed * span / fps)])
    _straight(tree)
    place = _math(tree, "FRACT", _math(tree, "SUBTRACT", _math(tree, "MULTIPLY", split.outputs["X"], pulses), clock.outputs[0]))
    # a soft-ended stretch: full in the middle of its share of the line, nothing outside it
    distance = _math(tree, "ABSOLUTE", _math(tree, "SUBTRACT", place, 0.5))
    stretch = tree.nodes.new("ShaderNodeMapRange")
    stretch.interpolation_type = "SMOOTHSTEP"
    stretch.inputs["From Min"].default_value = duty * 0.25
    stretch.inputs["From Max"].default_value = duty * 0.5
    stretch.inputs["To Min"].default_value = 1.0
    stretch.inputs["To Max"].default_value = 0.0
    tree.links.new(distance, stretch.inputs["Value"])
    strength = _math(tree, "ADD", steady, _math(tree, "MULTIPLY", stretch.outputs["Result"], peak))
    level = tree.nodes.new("ShaderNodeValue")
    _keys(level.outputs[0], _envelope(begin, end, fade, last))
    tree.links.new(_math(tree, "MULTIPLY", strength, level.outputs[0]), light.inputs["Strength"])
    return mat


def ring(name: str, at: Vector, facing: Vector, begin: int, life: int, reach: float, width: float, color, strength: float = 26.0):
    """A thin circle spreading from `at` out to `reach` meters and fading as it goes, facing `facing`. It's drawn on a flat disc by
    its distance from the middle, so its line stays one width and a true circle at any size."""
    bm_verts = [(reach * 1.08 * math.cos(math.tau * i / 16), reach * 1.08 * math.sin(math.tau * i / 16), 0.0) for i in range(16)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(bm_verts, [], [list(range(16))])
    mesh.update()
    disc = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(disc)
    disc.location = at
    disc.rotation_mode = "QUATERNION"
    disc.rotation_quaternion = UP.rotation_difference(facing)
    mat, tree, light = _light_material(name)
    light.inputs["Color"].default_value = (*color_of(color), 1)
    coords = tree.nodes.new("ShaderNodeTexCoord")
    distance = tree.nodes.new("ShaderNodeVectorMath")
    distance.operation = "LENGTH"
    tree.links.new(coords.outputs["Object"], distance.inputs[0])
    radius = tree.nodes.new("ShaderNodeValue")
    for i in range(0, life + 1, 2):
        share = i / max(1, life)
        radius.outputs[0].default_value = max(0.002, reach * (1 - (1 - share) ** 2))
        radius.outputs[0].keyframe_insert("default_value", frame=begin + i)
    off = _math(tree, "ABSOLUTE", _math(tree, "SUBTRACT", distance.outputs["Value"], radius.outputs[0]))
    band = tree.nodes.new("ShaderNodeMapRange")
    band.interpolation_type = "SMOOTHSTEP"
    band.inputs["From Min"].default_value = width * 0.3
    band.inputs["From Max"].default_value = width
    band.inputs["To Min"].default_value = 1.0
    band.inputs["To Max"].default_value = 0.0
    tree.links.new(off, band.inputs["Value"])
    level = tree.nodes.new("ShaderNodeValue")
    _keys(level.outputs[0], [(max(1, begin - 1), 0.0), (begin, 1.0), (begin + round(life * 0.6), 0.85), (begin + life, 0.0)])
    tree.links.new(_math(tree, "MULTIPLY", _math(tree, "MULTIPLY", band.outputs["Result"], strength), level.outputs[0]),
                   light.inputs["Strength"])
    mesh.materials.append(mat)
    return disc
