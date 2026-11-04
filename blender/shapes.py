"""Shapes built from code with bmesh (no bpy.ops, so they work the same with no window).

Sizes are meters. `lathe` turns a profile of (radius, height) points about the Z axis, which covers most turned
parts (pistons, nails, cups, rams). A part's origin is where `at` puts it; its own Z axis points up.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from blender import materials

SMOOTH_ANGLE = math.radians(35)


def _link(name: str, bm, material: str | None, at=(0, 0, 0), parent=None, smooth=True):
    mesh = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    if smooth:
        for poly in mesh.polygons:
            poly.use_smooth = True
        mesh.set_sharp_from_angle(angle=SMOOTH_ANGLE)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = Vector(at)
    if parent is not None:
        obj.parent = parent
    if material:
        materials.assign(obj, material)
    return obj


def _spin_profile(bm, points, closed: bool, segments: int, angle=2 * math.pi):
    verts = [bm.verts.new((r, 0.0, z)) for r, z in points]
    edges = [bm.edges.new((verts[i], verts[i + 1])) for i in range(len(verts) - 1)]
    if closed:
        edges.append(bm.edges.new((verts[-1], verts[0])))
    bmesh.ops.spin(bm, geom=verts + edges, cent=(0, 0, 0), axis=(0, 0, 1), angle=angle, steps=segments,
                   use_duplicate=False)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)


def lathe(name, points, material, at=(0, 0, 0), segments=64, parent=None):
    """A solid of revolution. `points` run from the axis (radius 0) out and back to the axis for a solid part, or
    form a closed loop off the axis for a hollow one (a tube, a cup's wall)."""
    bm = bmesh.new()
    closed = points[0][0] > 0 or points[-1][0] > 0
    _spin_profile(bm, points, closed=closed, segments=segments)
    return _link(name, bm, material, at, parent)


def cylinder(name, r, h, material, at=(0, 0, 0), bevel=0.0, segments=64, parent=None):
    """A solid cylinder standing on `at`, its edges rounded by `bevel` meters."""
    b = min(bevel, r / 3, h / 3)
    if b > 0:
        pts = [(0, 0), (r - b, 0), (r, b), (r, h - b), (r - b, h), (0, h)]
    else:
        pts = [(0, 0), (r, 0), (r, h), (0, h)]
    return lathe(name, pts, material, at, segments, parent)


def tube(name, r_out, r_in, h, material, at=(0, 0, 0), segments=64, parent=None):
    return lathe(name, [(r_in, 0), (r_out, 0), (r_out, h), (r_in, h)], material, at, segments, parent)


def box(name, size, material, at=(0, 0, 0), bevel=0.0, parent=None):
    """A box centered on `at`."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=3, affect="EDGES", profile=0.5)
    return _link(name, bm, material, at, parent)


def sphere(name, r, material, at=(0, 0, 0), segments=24, parent=None):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=segments // 2, radius=r)
    return _link(name, bm, material, at, parent)


def torus(name, major, minor, material, at=(0, 0, 0), arc=360.0, axis="Z", segments=48, ring=16, parent=None):
    """A ring of tube radius `minor` around a circle of radius `major`. `arc` under 360 leaves a C (a hook) with
    capped ends. `axis` is the ring's axis: Z lies flat, Y stands up facing the camera, X stands up side-on."""
    bm = bmesh.new()
    pts = [(major + minor * math.cos(t), minor * math.sin(t))
           for t in (2 * math.pi * i / ring for i in range(ring))]
    _spin_profile(bm, pts, closed=True, segments=segments, angle=math.radians(arc))
    if arc < 360:
        bmesh.ops.holes_fill(bm, edges=bm.edges, sides=0)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if axis != "Z":
        rot = Matrix.Rotation(math.pi / 2, 4, "X" if axis == "Y" else "Y")
        bmesh.ops.transform(bm, matrix=rot, verts=bm.verts)
    return _link(name, bm, material, at, parent)


def _rod(bm, p, q, r, segments=8):
    p, q = Vector(p), Vector(q)
    d = q - p
    rot = Vector((0, 0, 1)).rotation_difference(d.normalized()).to_matrix().to_4x4()
    m = Matrix.Translation((p + q) / 2) @ rot
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=r, radius2=r, depth=d.length, matrix=m)


def rods(name, pairs, r, material, at=(0, 0, 0), parent=None, segments=8):
    """Straight rods between point pairs, as one object: cables, lacing, rails."""
    bm = bmesh.new()
    for p, q in pairs:
        _rod(bm, p, q, r, segments)
    return _link(name, bm, material, at, parent, smooth=False)


def truss(name, length, width, bays, material, at=(0, 0, 0), chord=0.05, lace=0.025, parent=None):
    """A square lattice boom along +Z (a crane's): four chords and zigzag lacing on each face."""
    w = width / 2
    corners = [(-w, -w), (w, -w), (w, w), (-w, w)]
    pairs = [((x, y, 0), (x, y, length)) for x, y in corners]
    step = length / bays
    for i in range(4):
        (x0, y0), (x1, y1) = corners[i], corners[(i + 1) % 4]
        for b in range(bays):
            z0, z1 = b * step, (b + 1) * step
            a, c = ((x0, y0, z0), (x1, y1, z1)) if b % 2 == 0 else ((x1, y1, z0), (x0, y0, z1))
            pairs.append((a, c))
    bm = bmesh.new()
    for p, q in pairs:
        _rod(bm, p, q, chord if p[0] == q[0] and p[1] == q[1] else lace)
    return _link(name, bm, material, at, parent, smooth=False)


def extrude(name, outline, depth, material, at=(0, 0, 0), parent=None, bevel=0.0):
    """A flat outline of [x, z] points in the x-z plane, thick along y and centered on it: brackets, cams, levers. `bevel`
    rounds the edges of its two flat faces, in meters, so light catches them as it does a real object's."""
    bm = bmesh.new()
    verts = [bm.verts.new((x, -depth / 2, z)) for x, z in outline]
    face = bm.faces.new(verts)
    grown = bmesh.ops.extrude_face_region(bm, geom=[face])
    moved = [g for g in grown["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, depth, 0), verts=moved)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if bevel > 0:
        rims = [e for e in bm.edges if abs(e.verts[0].co.y - e.verts[1].co.y) < 1e-9]
        bmesh.ops.bevel(bm, geom=rims, offset=bevel, segments=3, affect="EDGES", profile=0.5, clamp_overlap=True)
    return _link(name, bm, material, at, parent)


def _filleted(path, bend: float, steps: int = 6):
    """The path with each inner corner replaced by an arc of radius about `bend` (a pipe's elbow)."""
    pts = [Vector(p) for p in path]
    if bend <= 0 or len(pts) < 3:
        return pts
    out = [pts[0]]
    for a, b, c in zip(pts, pts[1:], pts[2:]):
        u, v = (a - b), (c - b)
        if u.length < 1e-9 or v.length < 1e-9:
            continue
        cut = min(bend, u.length / 2, v.length / 2)
        p, q = b + u.normalized() * cut, b + v.normalized() * cut
        for i in range(steps + 1):   # a quadratic Bezier from p through the corner to q
            t = i / steps
            out.append(p * (1 - t) ** 2 + b * 2 * t * (1 - t) + q * t * t)
    out.append(pts[-1])
    return out


def pipe(name, path, r, material, at=(0, 0, 0), bend=0.0, segments=16, parent=None):
    """A round tube of radius `r` along a path of [x, y, z] points, its corners rounded by `bend` meters."""
    pts = _filleted(path, bend)
    curve = bpy.data.curves.new(f"{name}.curve", "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = r
    curve.bevel_resolution = max(2, segments // 4)
    curve.use_fill_caps = True
    spline = curve.splines.new("POLY")
    spline.points.add(len(pts) - 1)
    for point, p in zip(spline.points, pts):
        point.co = (p.x, p.y, p.z, 1.0)
    temp = bpy.data.objects.new(f"{name}.tmp", curve)
    bpy.context.scene.collection.objects.link(temp)
    mesh = bpy.data.meshes.new_from_object(temp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(temp, do_unlink=True)
    bpy.data.curves.remove(curve)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bpy.data.meshes.remove(mesh)
    return _link(name, bm, material, at, parent)


def spiral_path(r_in, r_out, turns, per_turn=64):
    """A flat spiral in the x-y plane, from radius `r_in` out to `r_out`, with even gaps between its turns."""
    n = max(8, int(turns * per_turn))
    return [((r_in + (r_out - r_in) * i / n) * math.cos(2 * math.pi * turns * i / n),
             (r_in + (r_out - r_in) * i / n) * math.sin(2 * math.pi * turns * i / n), 0.0) for i in range(n + 1)]


def spiral(name, r_in, r_out, turns, wire, material, at=(0, 0, 0), parent=None):
    """A flat coil of round wire `wire` thick, lying in the x-y plane on its origin: a cooker's coil, a clock's spring."""
    return pipe(name, spiral_path(r_in, r_out, turns), wire / 2, material, at=at, segments=8, parent=parent)


def spring(name, r, wire, turns, h, material, at=(0, 0, 0), parent=None):
    """A coil of `turns` turns, radius `r`, from z 0 to `h`, of round wire `wire` thick. Scaling it along z
    squashes it, which a spring's slide joint does."""
    n = max(24, int(turns * 24))
    path = [(r * math.cos(2 * math.pi * turns * i / n), r * math.sin(2 * math.pi * turns * i / n), h * i / n)
            for i in range(n + 1)]
    return pipe(name, path, wire / 2, material, at=at, segments=8, parent=parent)


def text(name, body, height, material, depth=0.0, at=(0, 0, 0), parent=None):
    """Letters standing in the x-z plane, facing -y (the camera's usual side), `height` meters tall, raised
    `depth`: a name printed on a can ("GASOLINE"), a plate's stamp."""
    curve = bpy.data.curves.new(f"{name}.font", "FONT")
    curve.body = body
    curve.size = height
    curve.extrude = depth / 2
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    temp = bpy.data.objects.new(f"{name}.tmp", curve)
    bpy.context.scene.collection.objects.link(temp)
    temp.rotation_euler = (math.pi / 2, 0, 0)
    bpy.context.view_layer.update()
    mesh = bpy.data.meshes.new_from_object(temp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    mesh.transform(temp.matrix_basis)
    bpy.data.objects.remove(temp, do_unlink=True)
    bpy.data.curves.remove(curve)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bpy.data.meshes.remove(mesh)
    return _link(name, bm, material, at, parent, smooth=False)


def cut_away(objs, keep_y_above=0.0, size=40.0, name="Cutaway", material="cut", x_range=None):
    """Cut the camera's half (y below `keep_y_above`) off `objs`, or with `x_range` (x from, x to) only a notch that
    wide, whose side walls show. The cut faces take the cutter's material: `cut` comes out hatched like a section
    drawing, `wood_cut` as sawn wood. Returns the cutter, which a shot can move."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    width = size if x_range is None else x_range[1] - x_range[0]
    middle = 0.0 if x_range is None else (x_range[0] + x_range[1]) / 2
    bmesh.ops.scale(bm, vec=(width, size, size), verts=bm.verts)
    cutter = _link(name, bm, material, at=(middle, keep_y_above - size / 2, 0), smooth=False)
    cutter.hide_render = True
    cutter.display_type = "WIRE"
    for obj in objs:
        mod = obj.modifiers.new("Cutaway", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.solver = "EXACT"
        mod.material_mode = "TRANSFER"
        mod.object = cutter
    return cutter
