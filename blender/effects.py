"""Effects a machine short shows, animated by code rather than simulated, so a render is the same every time.

Each is one entry in a timeline's "effects" (blender/shots.py), placed in a machine's space ("model" and a part to
ride with, "in", default its root) or the world's. Times are seconds of the whole short.
  air       balls filling the space between a floor and the part above (the ram), crowding as it comes down;
            their colour keyed over time (blue, then white, then hot amber)
  spray     droplets fanning from a point toward another, with a soft mist cone
  glow      a glowing gas column between a floor and the part above, or a sphere; strength keyed, with a light
  fireball  a ball of fire growing and fading in a moment, with a light
  smoke     soft dark puffs rising and drifting, growing and fading
  ghost     see-through copies of parts, moved by their own keys (a missed landing, up and down only)
  ring      a shock ring growing and fading where something lands
  spark     a small flickering blue spark
  light     a light flashing on and off
"""
from __future__ import annotations

import math
import random

import bpy
from mathutils import Matrix, Vector

from blender import look, shapes


def _socket_key(socket, value, f):
    socket.default_value = value
    socket.keyframe_insert("default_value", frame=f)


def fx_material(name, color, strength=0.0, alpha=1.0, soft=False):
    """An effect's material: a colour that can glow (`strength`), see-through by `alpha` (a mix with transparent,
    keyable as the node 'Fade'), its edges softened when `soft` (smoke)."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.surface_render_method = "BLENDED"
    mat.use_transparent_shadow = True
    tree = mat.node_tree
    tree.nodes.clear()
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    if strength > 0:
        shade = tree.nodes.new("ShaderNodeEmission")
        shade.inputs["Color"].default_value = (*color, 1)
        shade.inputs["Strength"].default_value = strength
        shade.name = "Glow"
    else:
        shade = tree.nodes.new("ShaderNodeBsdfPrincipled")
        shade.inputs["Base Color"].default_value = (*color, 1)
        shade.inputs["Roughness"].default_value = 0.9 if soft else 0.4
        shade.name = "Surface"
    clear = tree.nodes.new("ShaderNodeBsdfTransparent")
    mix = tree.nodes.new("ShaderNodeMixShader")
    mix.name = "Fade"
    mix.inputs["Fac"].default_value = alpha
    if soft:   # alpha falls off toward the silhouette, so a sphere reads as a soft puff
        weight = tree.nodes.new("ShaderNodeLayerWeight")
        weight.inputs["Blend"].default_value = 0.6
        inv = tree.nodes.new("ShaderNodeMath")
        inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        tree.links.new(weight.outputs["Facing"], inv.inputs[1])
        mul = tree.nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.name = "FadeAmount"
        mul.inputs[1].default_value = alpha
        tree.links.new(inv.outputs[0], mul.inputs[0])
        tree.links.new(mul.outputs[0], mix.inputs["Fac"])
    tree.links.new(clear.outputs[0], mix.inputs[1])
    tree.links.new(shade.outputs[0], mix.inputs[2])
    tree.links.new(mix.outputs[0], out.inputs["Surface"])
    return mat


def _fade(mat, value, f):
    node = mat.node_tree.nodes.get("FadeAmount")
    if node is not None:
        _socket_key(node.inputs[1], value, f)
    else:
        _socket_key(mat.node_tree.nodes["Fade"].inputs["Fac"], value, f)


def _hide_outside(obj, f_in, f_out, f0):
    """Shown from f_in up to f_out, hidden otherwise; from the segment's first frame if it starts before it."""
    keys = [(f0, f_in > f0)] + ([(f_in, False)] if f_in > f0 else []) + [(max(f_out, f0 + 1), True)]
    for f, hidden in keys:
        obj.hide_render = obj.hide_viewport = hidden
        obj.keyframe_insert("hide_render", frame=f)
        obj.keyframe_insert("hide_viewport", frame=f)


class Effects:
    def __init__(self, seg):
        self.seg = seg
        self.n = 0

    def _host(self, e):
        """The object an effect rides with: a machine's part ("in"), its root, or nothing (world space)."""
        if "model" not in e:
            return None
        model = self.seg.models[e["model"]]
        return model.objects[e["in"]] if e.get("in") else self.seg.roots[e["model"]]

    def _local_z(self, part_name, host, f):
        """Where a machine part's origin is, along z in the host's space, at frame f."""
        bpy.context.scene.frame_set(f)
        obj = self.seg.resolve(part_name)[0]
        return (host.matrix_world.inverted() @ obj.matrix_world.translation).z

    def add(self, e):
        self.n += 1
        getattr(self, e["kind"])(e)

    # --- air -------------------------------------------------------------------------------------------------

    def air(self, e):
        seg, host = self.seg, self._host(e)
        f_in, f_out = seg.frame(e["from"]), seg.frame(e["to"])
        rng = random.Random(e.get("seed", 3))
        count, radius, r = int(e.get("count", 40)), float(e.get("radius", 0.6)), float(e.get("r", 0.035))
        floor = float(e.get("floor", 0.55))
        mat = fx_material(f"air{self.n}", tuple(e.get("color", (0.5, 0.75, 0.95))), alpha=1.0)
        surface = mat.node_tree.nodes["Surface"]
        surface.inputs["Emission Strength"].default_value = 0.15
        for t, color in e.get("colors") or []:
            f = seg.frame(t)
            _socket_key(surface.inputs["Base Color"], (*color, 1), f)
            _socket_key(surface.inputs["Emission Color"], (*color, 1), f)
        balls = []
        for i in range(count):
            rr = radius * math.sqrt(rng.random())
            ang = rng.uniform(0.15, math.pi - 0.15)       # the back half: the front is cut away
            balls.append((rr, ang, rng.random(), rng.uniform(0, 6.3), rng.uniform(1.5, 3.0)))
        objs = []
        for i in range(count):
            obj = shapes.sphere(f"Air{self.n}_{i}", r, None, segments=12)
            obj.data.materials.append(mat)
            obj.parent = host
            obj["group"] = f"air{self.n}"
            _hide_outside(obj, f_in, f_out, seg.f0)
            objs.append(obj)
        ceiling = e.get("under", "ph.ram")
        for f in range(max(f_in, seg.f0), min(f_out, seg.f1) + 1, 2):
            top = self._local_z(ceiling, host, f) - 0.03
            for obj, (rr, ang, u, phase, speed) in zip(objs, balls):
                wob = 0.04 * math.sin(phase + f * speed / seg.fps * 2 * math.pi)
                a = ang + 0.05 * math.sin(phase * 1.7 + f / seg.fps * speed)
                h = floor + r + min(max(u + wob, 0.0), 1.0) * max(top - floor - 2 * r, 0.0)
                look.key(obj, f, location=(rr * math.cos(a), rr * math.sin(a) + 0.02, h))
        for obj in objs:
            look.ease(obj, "LINEAR")
        if objs:   # the label's dot: a ball low and near the cut, where a falling ram's edge won't cover it
            near = min(range(count), key=lambda i: balls[i][0] * math.sin(balls[i][1]) + 0.3 * balls[i][2])
            seg.fx_anchors[e.get("anchor", "air")] = (objs[near], (0, 0, 0))

    # --- spray --------------------------------------------------------------------------------------------------

    def spray(self, e):
        seg, host = self.seg, self._host(e)
        f_in, f_out = seg.frame(e["from"]), seg.frame(e["to"])
        origin, toward = Vector(e["origin"]), Vector(e["toward"])
        spread = math.radians(e.get("spread", 25))
        rng = random.Random(e.get("seed", 5))
        color = tuple(e.get("color", (0.95, 0.95, 0.9)))
        mat = fx_material(f"spray{self.n}", color, strength=e.get("glow", 0.6), alpha=0.85)
        life = int(e.get("life", 0.35) * seg.fps)
        axis = (toward - origin)
        length = axis.length
        axis.normalize()
        side = axis.cross(Vector((0, 0, 1)))
        if side.length < 1e-6:
            side = Vector((1, 0, 0))
        side.normalize()
        up = side.cross(axis).normalized()
        count = int(e.get("count", 36))
        for i in range(count):
            born = f_in + int((f_out - f_in - life) * i / max(1, count - 1)) if f_out - f_in > life else f_in
            a, b = rng.uniform(-spread, spread), rng.uniform(-spread / 2, spread / 2)
            d = (axis + side * math.tan(a) + up * math.tan(b)).normalized()
            reach = length * rng.uniform(0.7, 1.1)
            obj = shapes.sphere(f"Drop{self.n}_{i}", float(e.get("size", 0.014)), None, segments=8)
            obj.data.materials.append(mat)
            obj.parent = host
            _hide_outside(obj, born, born + life, seg.f0)
            look.key(obj, born, location=origin.copy())
            look.key(obj, born + life, location=origin + d * reach)
            look.ease(obj, "LINEAR")
        if e.get("mist", True):
            cone = shapes.lathe(f"Mist{self.n}", [(0, 0), (0.02, 0), (length * math.tan(spread) * 0.9, length),
                                                   (0, length)], None, segments=32)
            mist = fx_material(f"mist{self.n}", color, strength=0.3, alpha=0.0)
            cone.data.materials.append(mist)
            cone.parent = host
            cone.location = origin
            cone.rotation_mode = "QUATERNION"
            cone.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(axis)
            _hide_outside(cone, f_in, f_out, seg.f0)
            for f, v in ((f_in, 0.0), (f_in + 4, e.get("mist_alpha", 0.35)), (max(f_in + 5, f_out - 4),
                                                                                   e.get("mist_alpha", 0.35)),
                         (f_out, 0.0)):
                _fade(mist, v, f)
            seg.fx_anchors[e.get("anchor", "spray")] = (cone, (0, 0, length * 0.6))

    # --- glow and fire ---------------------------------------------------------------------------------------

    def glow(self, e):
        seg, host = self.seg, self._host(e)
        f_in, f_out = seg.frame(e["from"]), seg.frame(e["to"])
        color = tuple(e.get("color", (1.0, 0.75, 0.4)))
        mat = fx_material(f"glow{self.n}", color, strength=1.0, alpha=float(e.get("alpha", 0.85)))
        glow_node = mat.node_tree.nodes["Glow"]
        for t, s in e.get("keys") or [[e["from"], 8.0], [e["to"], 0.0]]:
            _socket_key(glow_node.inputs["Strength"], s, seg.frame(t))
        for t, c in e.get("colors") or []:
            _socket_key(glow_node.inputs["Color"], (*c, 1), seg.frame(t))
        if e.get("shape", "column") == "column":
            r = float(e.get("radius", 0.66))
            obj = shapes.cylinder(f"Gas{self.n}", r, 1.0, None, segments=48)
            obj.data.materials.append(mat)
            obj.parent = host
            floor = float(e.get("floor", 0.45))
            for f in range(max(f_in, seg.f0), min(f_out, seg.f1) + 1, 2):
                top = self._local_z(e.get("under", "ph.ram"), host, f)
                obj.location = (0, 0, floor)
                obj.scale = (1, 1, max(0.01, top - floor))
                obj.keyframe_insert("location", frame=f)
                obj.keyframe_insert("scale", frame=f)
            look.ease(obj, "LINEAR")
            seg.fx_anchors[e.get("anchor", "gas")] = (obj, (r * 0.7, 0.2, 0.5))
        else:
            obj = shapes.sphere(f"Glow{self.n}", float(e.get("radius", 0.5)), None, segments=32)
            obj.data.materials.append(mat)
            obj.parent = host
            obj.location = Vector(e.get("at", (0, 0, 0)))
        _hide_outside(obj, f_in, f_out, seg.f0)
        if e.get("light", 0):
            self._light(host, obj.location if e.get("shape") == "sphere" else Vector((0, 0.3, e.get("floor", 0.45) + 0.3)),
                        color, e.get("keys") or [[e["from"], 8.0], [e["to"], 0.0]], float(e["light"]))

    def fireball(self, e):
        seg, host = self.seg, self._host(e)
        f_in = seg.frame(e["t"])
        life = max(2, int(e.get("life", 0.3) * seg.fps))
        color = tuple(e.get("color", (1.0, 0.6, 0.25)))
        mat = fx_material(f"fire{self.n}", color, strength=float(e.get("strength", 12)), alpha=float(e.get("alpha", 0.9)),
                          soft=bool(e.get("soft")))   # a big one needs it: with a hard edge it reads as a flat disc
        r0, r1 = e.get("r", [0.3, 1.2])
        obj = shapes.sphere(f"Fire{self.n}", 1.0, None, segments=32)
        obj.data.materials.append(mat)
        obj.parent = host
        obj.location = Vector(e.get("at", (0, 0, 0)))
        sx = e.get("stretch", [1, 1, 1])
        look.key(obj, f_in, scale=Vector([r0 * k for k in sx]))
        look.key(obj, f_in + life, scale=Vector([r1 * k for k in sx]))
        look.ease(obj, "out")
        _fade(mat, float(e.get("alpha", 0.9)), f_in)
        _fade(mat, 0.0, f_in + life)
        _hide_outside(obj, f_in, f_in + life + 1, seg.f0)
        if e.get("light", 0):
            self._light(host, obj.location, color, [[e["t"], 1.0], [e["t"] + life / seg.fps, 0.0]], float(e["light"]))

    def _light(self, host, at, color, keys, energy):
        data = bpy.data.lights.new(f"FxLight{self.n}", "POINT")
        data.color = color
        data.shadow_soft_size = 0.3
        light = bpy.data.objects.new(f"FxLight{self.n}", data)
        bpy.context.scene.collection.objects.link(light)
        light.parent = host
        light.location = at
        peak = max(s for _t, s in keys) or 1.0
        first = self.seg.frame(min(t for t, _s in keys))
        data.energy = 0.0          # dark until the effect starts: a key's value would otherwise hold before it
        data.keyframe_insert("energy", frame=first - 1)
        for t, s in keys:
            data.energy = energy * s / peak
            data.keyframe_insert("energy", frame=self.seg.frame(t))
        data.energy = 0.0
        data.keyframe_insert("energy", frame=self.seg.frame(max(t for t, _s in keys)) + 1)

    def light(self, e):
        self._light(self._host(e), Vector(e.get("at", (0, 0, 0))), tuple(e.get("color", (1, 0.8, 0.6))),
                    e["keys"], float(e.get("energy", 2000)))

    # --- smoke --------------------------------------------------------------------------------------------------

    def smoke(self, e):
        seg, host = self.seg, self._host(e)
        f_in, f_out = seg.frame(e["from"]), seg.frame(e["to"])
        rng = random.Random(e.get("seed", 9))
        origin = Vector(e.get("origin", (0, 0, 0)))
        drift = Vector(e.get("drift", (0.4, 0, 0.8)))
        life = int(e.get("life", 1.6) * seg.fps)
        s0, s1 = e.get("size", [0.25, 0.9])
        color = tuple(e.get("color", (0.03, 0.03, 0.035)))
        puffs = int(e.get("puffs", 10))
        for i in range(puffs):
            born = f_in + int((f_out - f_in) * i / max(1, puffs))
            obj = shapes.sphere(f"Puff{self.n}_{i}", 1.0, None, segments=20)
            mat = fx_material(f"puff{self.n}_{i}", color, alpha=float(e.get("alpha", 0.85)), soft=True)
            obj.data.materials.append(mat)
            obj.parent = host
            obj["group"] = f"smoke{self.n}"   # a puff in front of the labelled one is still the smoke
            jitter = Vector((rng.uniform(-0.2, 0.2), rng.uniform(-0.1, 0.1), rng.uniform(-0.1, 0.1)))
            look.key(obj, born, location=origin + jitter, scale=Vector((s0, s0, s0)))
            end = born + life
            look.key(obj, end, location=origin + jitter + drift * (life / seg.fps) * rng.uniform(0.8, 1.2),
                     scale=Vector((s1, s1, s1)) * rng.uniform(0.8, 1.2))
            look.ease(obj, "out")
            _fade(mat, float(e.get("alpha", 0.85)), born)
            _fade(mat, 0.0, end)
            _hide_outside(obj, born, end, seg.f0)
            if i == min(2, puffs - 1):
                seg.fx_anchors[e.get("anchor", "smoke")] = (obj, (0.6, 0, 0.3))

    # --- ghosts, rings, sparks ------------------------------------------------------------------------------------

    def ghost(self, e):
        seg = self.seg
        model = seg.models[e["model"]]
        host = model.objects[e.get("in", "hammer")] if e.get("in", "hammer") in model.objects else seg.roots[e["model"]]
        mat = fx_material(f"ghost{self.n}", tuple(e.get("color", (1.0, 0.25, 0.2))), strength=0.6,
                          alpha=float(e.get("alpha", 0.3)))
        pivot = bpy.data.objects.new(f"Ghost{self.n}", None)
        bpy.context.scene.collection.objects.link(pivot)
        pivot.parent = host
        for pid in e.get("parts", ["ram", "ram_eye"]):
            src = model.objects[pid]
            dup = bpy.data.objects.new(f"Ghost{self.n}.{pid}", src.data.copy())
            bpy.context.scene.collection.objects.link(dup)
            dup.data.materials.clear()
            dup.data.materials.append(mat)
            dup.parent = pivot
            base = model.objects[e.get("parts", ["ram"])[0]]
            dup.matrix_basis = (base.matrix_basis.inverted() @ src.matrix_basis) if src is not base else \
                dup.matrix_basis
        keys = e["keys"]
        for k in keys:
            f = seg.frame(k["t"])
            look.key(pivot, f, location=Vector(k["at"]),
                     rotation_euler=tuple(math.radians(a) for a in k.get("rot", (0, 0, 0))))
        look.ease(pivot, e.get("ease_mode", "BEZIER"))
        for child in pivot.children:
            _hide_outside(child, seg.frame(keys[0]["t"]), seg.frame(keys[-1]["t"]), seg.f0)
        _fade(mat, float(e.get("alpha", 0.3)), seg.frame(keys[0]["t"]))
        _fade(mat, float(e.get("alpha", 0.3)), max(seg.frame(keys[0]["t"]), seg.frame(keys[-1]["t"]) - 6))
        _fade(mat, 0.0, seg.frame(keys[-1]["t"]))

    def ring(self, e):
        seg, host = self.seg, self._host(e)
        f_in = seg.frame(e["t"])
        life = max(2, int(e.get("life", 0.15) * seg.fps))
        r0, r1 = e.get("r", [0.5, 2.0])
        obj = shapes.torus(f"Ring{self.n}", 1.0, 0.03, None, segments=64, ring=8)
        mat = fx_material(f"ring{self.n}", (0.9, 0.92, 0.95), strength=1.5, alpha=0.6)
        obj.data.materials.append(mat)
        obj.parent = host
        obj.location = Vector(e.get("at", (0, 0, 0)))
        look.key(obj, f_in, scale=Vector((r0, r0, r0 * 0.5)))
        look.key(obj, f_in + life, scale=Vector((r1, r1, r1 * 0.5)))
        look.ease(obj, "out")
        _fade(mat, 0.6, f_in)
        _fade(mat, 0.0, f_in + life)
        _hide_outside(obj, f_in, f_in + life + 1, seg.f0)

    def spark(self, e):
        seg, host = self.seg, self._host(e)
        f_in, f_out = seg.frame(e["from"]), seg.frame(e["to"])
        mat = fx_material(f"spark{self.n}", tuple(e.get("color", (0.45, 0.65, 1.0))), strength=20.0, alpha=0.95)
        obj = shapes.sphere(f"Spark{self.n}", float(e.get("r", 0.04)), None, segments=12)
        obj.data.materials.append(mat)
        obj.parent = host
        obj.location = Vector(e.get("at", (0, 0, 0)))
        rng = random.Random(e.get("seed", 1))
        node = mat.node_tree.nodes["Glow"]
        for f in range(f_in, f_out + 1):
            _socket_key(node.inputs["Strength"], rng.choice((4.0, 25.0, 12.0, 30.0)), f)
        _hide_outside(obj, f_in, f_out, seg.f0)
