"""Centre of gravity and inertia of the equipment of an IDM-CIC model (decisions D-245, D-246).

The published description of the format fixes the *names* of the placement data (a translation,
three rotations in a named order, the shape sizes) but not, in words, how they combine or where a
shape has its origin. The conventions below were therefore inferred from the models themselves
and checked on them (DV-IDM5): the panels, angles and cleats of the platforms in the models close
into a box without gap or overlap under these conventions and not under the alternatives that
were tried (8 combinations of rotation order, handedness and translation; box origin at its corner
or at its centre). They are conventions of this tool, every number computed with them is marked
as an estimate, and anything they do not cover is left out, never guessed:

* a position is a rotation `R = R(axis1, a1) R(axis2, a2) R(axis3, a3)` (the product in the
  order the rotation order names, right-handed, degrees) and a translation `t` in the parent
  frame: `point_parent = R point + t`; only the transformation order `Translation_Rotation` is
  supported (all models seen use it);
* the frame of an occurrence is the frame of the coordinate system it is placed on, times its
  position; a coordinate system is placed on its parent (or, when it is the first one of an
  occurrence, on that occurrence) by its position; a sub-occurrence takes the position of the
  occurrence it was copied from;
* an articulation counts only when its reference value is 0 (it then changes nothing);
* a box has its origin at a corner and extends along +x, +y, +z by d1, d2, d3; a cylinder has its
  axis along z from the origin to the height d3; a prism has its section in the x-y plane (a
  triangle or a quadrangle from the origin along x) and extends along +z by its thickness;
* a cone and a hollow cylinder stand like the cylinder: base on the origin, axis along +z, whole
  turn only; a hollow wall is measured across the radius (so a hollow cone is taken only when its
  two radii are equal, where the radial and the normal thickness are the same thing); a tank is a
  hollow cylinder with hemispherical ends, its straight part from the origin to d3 along +z and
  the ends reaching beyond (the position of its origin along the axis is the least certain
  convention here: for a straight part of height h it moves the centre of gravity by h / 2);
* a shape of mass type Total is a body of uniform density; a shape of mass 0 is ignored.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from budget_core.idm.model import Equipment, Frame, IdmModel, Occurrence, Position, Shape

Array = np.ndarray
_ORDER = re.compile(r"R([XYZ])_R([XYZ])_R([XYZ])", re.IGNORECASE)
PLACEMENT = "IDM_GEOMETRY_PLACEMENT"
SHAPE = "IDM_GEOMETRY_SHAPE"


class GeometryError(Exception):
    """The geometry cannot be worked out with the conventions above. `code` is the finding."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


@dataclass(frozen=True)
class Rigid:
    r: Array  # 3x3 rotation
    t: Array  # translation

    def then(self, inner: Rigid) -> Rigid:
        """`self` applied after `inner` (the frame of `inner` placed in the frame of `self`)."""
        return Rigid(self.r @ inner.r, self.r @ inner.t + self.t)

    def point(self, p: Array) -> Array:
        return np.asarray(self.r @ p + self.t)


IDENTITY = Rigid(np.eye(3), np.zeros(3))


def _axis_rotation(axis: str, degrees: float) -> Array:
    a = math.radians(degrees)
    c, s = math.cos(a), math.sin(a)
    if axis == "X":
        return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])
    if axis == "Y":
        return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def position_transform(p: Position) -> Rigid:
    if p.transformation_order != "Translation_Rotation":
        raise GeometryError(PLACEMENT, "a transformation order other than Translation_Rotation")
    match = _ORDER.fullmatch(p.rotation_order)
    if match is None:
        raise GeometryError(PLACEMENT, "an unknown rotation order")
    r = np.eye(3)
    for axis, angle in zip(match.groups(), p.rotations_deg, strict=True):
        r = r @ _axis_rotation(axis.upper(), angle)
    return Rigid(r, np.array([p.x_m, p.y_m, p.z_m]))


class Placement:
    """The frames of a model: `world(id)` is the transform from an object to the model frame."""

    def __init__(self, model: IdmModel) -> None:
        self._frames: dict[str, Frame] = {f.full_id: f for f in model.frames}
        self._memo: dict[str, Rigid] = {}

    def _position(self, frame: Frame, seen: set[str]) -> Position | None:
        node: Frame | None = frame
        while node is not None:
            if node.position is not None:
                return node.position
            if node.origin is None or node.origin in seen:
                return None
            seen.add(node.origin)
            node = self._frames.get(node.origin)
        return None

    def _articulation(self, frame: Frame) -> float | None:
        node: Frame | None = frame
        seen: set[str] = set()
        while node is not None and node.full_id not in seen:
            seen.add(node.full_id)
            if node.articulation is not None:
                return node.articulation
            node = self._frames.get(node.origin) if node.origin else None
        return None

    def world(self, full_id: str, _stack: tuple[str, ...] = ()) -> Rigid:
        if full_id in self._memo:
            return self._memo[full_id]
        frame = self._frames.get(full_id)
        if frame is None or full_id in _stack:
            raise GeometryError(PLACEMENT, "a placement that is missing or circular")
        if frame.kind == "coordinate_system":
            art = self._articulation(frame)
            if art is not None and (math.isnan(art) or art != 0.0):
                raise GeometryError(PLACEMENT, "an articulation that is not at 0")
        position = self._position(frame, {full_id})
        local = position_transform(position) if position is not None else IDENTITY
        parent = frame.parent or frame.owner
        base = self.world(parent, (*_stack, full_id)) if parent else IDENTITY
        self._memo[full_id] = base.then(local)
        return self._memo[full_id]


# ---- bodies of uniform density -----------------------------------------------------------------


@dataclass(frozen=True)
class Body:
    mass: float
    com: Array  # in the frame of the body
    inertia: Array  # tensor about `com`, axes of the body frame


def _param(shape: Shape, name: str, default: float | None = None) -> float:
    for key, value in shape.parameters:
        if key == name:
            return value
    if default is None:
        raise GeometryError(SHAPE, "a shape size that is missing")
    return default


def _polygon_prism(points: list[tuple[float, float]], thickness: float, mass: float) -> Body:
    """A prism of uniform density with the section `points` in x-y, from z = 0 to `thickness`."""
    pts = np.array(points, dtype=float)
    x, y = pts[:, 0], pts[:, 1]
    x1, y1 = np.roll(x, -1), np.roll(y, -1)
    cross = x * y1 - x1 * y
    area = cross.sum() / 2.0
    if abs(area) < 1e-18 or thickness <= 0.0:
        raise GeometryError(SHAPE, "a shape with no volume")
    sign = 1.0 if area > 0 else -1.0
    area *= sign
    cx = sign * ((x + x1) * cross).sum() / (6.0 * area)
    cy = sign * ((y + y1) * cross).sum() / (6.0 * area)
    # second moments of the section about the origin, then about its centroid
    ixx_o = sign * ((y * y + y * y1 + y1 * y1) * cross).sum() / 12.0  # integral of y^2 dA
    iyy_o = sign * ((x * x + x * x1 + x1 * x1) * cross).sum() / 12.0  # integral of x^2 dA
    ixy_o = sign * ((x * y1 + 2 * x * y + 2 * x1 * y1 + x1 * y) * cross).sum() / 24.0
    mean_yy = ixx_o / area - cy * cy
    mean_xx = iyy_o / area - cx * cx
    mean_xy = ixy_o / area - cx * cy
    d2 = thickness * thickness / 12.0
    inertia = mass * np.array(
        [
            [mean_yy + d2, -mean_xy, 0.0],
            [-mean_xy, mean_xx + d2, 0.0],
            [0.0, 0.0, mean_xx + mean_yy],
        ]
    )
    return Body(mass, np.array([cx, cy, thickness / 2.0]), inertia)


_GAUSS_X, _GAUSS_W = np.polynomial.legendre.leggauss(6)  # exact for polynomials up to degree 11


def _revolution(r2: Callable[[Array], Array], z0: float, z1: float) -> Body:
    """A solid of revolution about z of unit density, with the radius squared as a polynomial in z.

    The mass of the returned body is its volume. The integrals are exact for the cones, cylinders
    and spheres used here (the radius squared is a polynomial of degree 2 at most).
    """
    z = 0.5 * (z1 - z0) * _GAUSS_X + 0.5 * (z1 + z0)
    w = 0.5 * (z1 - z0) * _GAUSS_W
    q = r2(z)
    volume = float(math.pi * (w * q).sum())
    if volume <= 0.0:
        raise GeometryError(SHAPE, "a shape with no volume")
    zc = float(math.pi * (w * q * z).sum()) / volume
    izz = float(math.pi * (w * q * q).sum()) / 2.0
    ixx_o = float(math.pi * (w * (q * q / 4.0 + q * z * z)).sum())  # about the origin
    ixx = ixx_o - volume * zc * zc
    return Body(volume, np.array([0.0, 0.0, zc]), np.diag([ixx, ixx, izz]))


def _scaled(body: Body, mass: float) -> Body:
    k = mass / body.mass
    return Body(mass, body.com, body.inertia * k)


def _frustum(r1: float, r2: float, h: float) -> Body:
    if h <= 0.0 or r1 < 0.0 or r2 < 0.0:
        raise GeometryError(SHAPE, "a shape with no volume")
    return _revolution(lambda z: (r1 + (r2 - r1) * z / h) ** 2, 0.0, h)


def _whole_turn(shape: Shape) -> None:
    start, end = _param(shape, "angle1", 0.0), _param(shape, "angle2", math.degrees(math.tau))
    if not math.isclose(abs(end - start), math.degrees(math.tau)) or _param(shape, "s", 1.0) != 1.0:
        raise GeometryError(SHAPE, "a shape that is not whole or is stretched")


def _wall(shape: Shape, radius: float) -> float:
    thickness = _param(shape, "d4")
    if not 0.0 < thickness < radius:
        raise GeometryError(SHAPE, "a wall that is not thinner than the radius")
    return thickness


def _sphere_section(centre: float, radius: float) -> Callable[[Array], Array]:
    """The radius squared of a sphere centred at `centre` on the axis, as a function of z."""

    def section(z: Array) -> Array:
        return radius * radius - (z - centre) ** 2

    return section


def _tank_body(radius: float, height: float, thickness: float) -> Body:
    """The empty tank: a cylindrical shell and two hemispherical shells, unit density."""
    inner = radius - thickness
    bodies: list[Body] = []
    if height > 0.0:
        bodies += [_frustum(radius, radius, height), _negative(_frustum(inner, inner, height))]
    for centre, sign in ((0.0, -1.0), (height, 1.0)):  # the end below and the end above
        for rad, factor in ((radius, 1.0), (inner, -1.0)):
            lo, hi = sorted((centre, centre + sign * rad))
            ball = _revolution(_sphere_section(centre, rad), lo, hi)
            bodies.append(ball if factor > 0 else _negative(ball))
    return _combine(bodies)


def _negative(body: Body) -> Body:
    return Body(-body.mass, body.com, -body.inertia)


def shape_body(shape: Shape) -> Body:
    """The body of a shape of mass type Total, in the frame of the shape."""
    mass = shape.mass_total_kg
    if shape.mass_type != "Total" or mass is None:
        raise GeometryError(SHAPE, "a mass per area or per volume")
    kind = shape.kind
    if kind in ("Box", "FilledBox"):
        if _param(shape, "r", 0.0) != 0.0:
            raise GeometryError(SHAPE, "a box with rounded edges")
        a, b, c = (_param(shape, k) for k in ("d1", "d2", "d3"))
        inertia = mass / 12.0 * np.diag([b * b + c * c, a * a + c * c, a * a + b * b])
        return Body(mass, np.array([a / 2.0, b / 2.0, c / 2.0]), inertia)
    if kind == "FilledCylinder":
        start, end = _param(shape, "angle1", 0.0), _param(shape, "angle2", math.degrees(math.tau))
        if (
            not math.isclose(abs(end - start), math.degrees(math.tau))
            or _param(shape, "s", 1.0) != 1.0
        ):
            raise GeometryError(SHAPE, "a cylinder that is not whole or is stretched")
        r, h = _param(shape, "d1"), _param(shape, "d3")
        ixx = mass * (3.0 * r * r + h * h) / 12.0
        inertia = np.diag([ixx, ixx, mass * r * r / 2.0])
        return Body(mass, np.array([0.0, 0.0, h / 2.0]), inertia)
    if kind == "ExtrudedTriangle":
        d1, d2, d3 = (_param(shape, k) for k in ("d1", "d2", "d3"))
        a = math.radians(_param(shape, "angle1"))
        return _polygon_prism(
            [(0.0, 0.0), (d1, 0.0), (d2 * math.cos(a), d2 * math.sin(a))], d3, mass
        )
    if kind == "ExtrudedQuadrangle":
        d1, d2, d3, d4 = (_param(shape, k) for k in ("d1", "d2", "d3", "d4"))
        a1, a2 = math.radians(_param(shape, "angle1")), math.radians(_param(shape, "angle2"))
        quad = [
            (0.0, 0.0),
            (d1, 0.0),
            (d1 - d3 * math.cos(a2), d3 * math.sin(a2)),
            (d2 * math.cos(a1), d2 * math.sin(a1)),
        ]
        return _polygon_prism(quad, d4, mass)
    if kind == "FilledCone":
        _whole_turn(shape)
        r1, r2, h = (_param(shape, k) for k in ("d1", "d2", "d3"))
        return _scaled(_frustum(r1, r2, h), mass)
    if kind in ("HollowCylinder", "HollowCone"):
        _whole_turn(shape)
        r1, h = _param(shape, "d1"), _param(shape, "d3")
        r2 = _param(shape, "d2") if kind == "HollowCone" else r1
        if not math.isclose(r1, r2):
            raise GeometryError(SHAPE, "a hollow cone whose two radii differ")
        t = _wall(shape, r1)
        return _scaled(
            _combine([_frustum(r1, r1, h), _negative(_frustum(r1 - t, r1 - t, h))]), mass
        )
    if kind == "Tank":
        r, h = _param(shape, "d1"), _param(shape, "d3", 0.0)
        return _scaled(_tank_body(r, h, _wall(shape, r)), mass)
    raise GeometryError(SHAPE, "a kind of shape that is not covered")


def _combine(parts: list[Body]) -> Body:
    total = sum(p.mass for p in parts)
    com = sum((p.mass * p.com for p in parts), np.zeros(3)) / total
    inertia = np.zeros((3, 3))
    for p in parts:
        d = p.com - com
        inertia += p.inertia + p.mass * (float(d @ d) * np.eye(3) - np.outer(d, d))
    return Body(total, com, inertia)


def equipment_body(eq: Equipment) -> Body | None:
    """Mass properties of an equipment in its own frame; None when it has no mass."""
    if eq.mci_origin == "ManualInput":
        if eq.manual_mass_kg is None or eq.manual_cog is None or eq.manual_inertia is None:
            raise GeometryError(SHAPE, "entered mass properties that are incomplete")
        if eq.manual_mass_kg == 0.0:
            return None
        c = eq.manual_cog
        return Body(
            eq.manual_mass_kg,
            np.array([c.x_m, c.y_m, c.z_m]),
            np.array(eq.manual_inertia.entries).reshape(3, 3),
        )
    parts: list[Body] = []
    for shape in eq.shapes:
        if shape.mass_total_kg == 0.0 and shape.mass_type == "Total":
            continue  # a shape without mass adds nothing, whatever its kind
        body = shape_body(shape)
        if shape.position is None:
            raise GeometryError(PLACEMENT, "a shape without a position")
        rigid = position_transform(shape.position)
        parts.append(Body(body.mass, rigid.point(body.com), rigid.r @ body.inertia @ rigid.r.T))
    return _combine(parts) if parts else None


@dataclass(frozen=True)
class MassProperties:
    position_m: tuple[float, float, float]
    inertia: tuple[float, float, float, float, float, float]  # xx yy zz xy xz yz, tensor entries


def occurrence_properties(
    placement: Placement, occ: Occurrence, eq: Equipment
) -> MassProperties | None:
    """Centre of gravity (model frame) and inertia about it (axes of the model frame)."""
    body = equipment_body(eq)
    if body is None:
        return None
    frame = placement.world(occ.full_id)
    com = frame.point(body.com)
    i = frame.r @ body.inertia @ frame.r.T
    return MassProperties(
        (float(com[0]), float(com[1]), float(com[2])),
        (
            float(i[0, 0]),
            float(i[1, 1]),
            float(i[2, 2]),
            float(i[0, 1]),
            float(i[0, 2]),
            float(i[1, 2]),
        ),
    )
