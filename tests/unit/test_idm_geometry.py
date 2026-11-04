"""Centre of gravity and inertia from the placements and shapes of a model (D-245, D-246).

The conventions are those of DV-IDM5 (inferred from the models, not from IDM-CIC itself); these
tests pin them with closed-form results.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from budget_core.idm.geometry import (
    PLACEMENT,
    SHAPE,
    GeometryError,
    Placement,
    equipment_body,
    occurrence_properties,
    position_transform,
    shape_body,
)
from budget_core.idm.mapping import ImportOptions, map_model
from budget_core.idm.model import (
    Equipment,
    Frame,
    IdmModel,
    Inertia,
    Occurrence,
    Point,
    Position,
    Shape,
    Temperatures,
)
from budget_core.idm.reader import read_idm
from tests.idm.fixtures import write_idm


def pos(
    x: float = 0.0,
    y: float = 0.0,
    z: float = 0.0,
    rot: tuple[float, float, float] = (0.0, 0.0, 0.0),
    order: str = "Rx_Ry_Rz",
    transformation: str = "Translation_Rotation",
) -> Position:
    return Position(x, y, z, order, rot, transformation)


def shape(kind: str, mass: float, position: Position | None = None, **p: float) -> Shape:
    return Shape(
        "1", "s", "s", "Total", mass, 0.0, 0.0, kind, tuple(p.items()), "o", position or pos()
    )


def equipment(shapes: tuple[Shape, ...], origin: str = "FromGeometry", **kw: object) -> Equipment:
    base = dict(
        full_id="eq",
        element_id="1",
        subsystem_id="S",
        name="e",
        optional=False,
        default_enabled=True,
        optional_by_configuration=(),
        mci_origin=origin,
        maturity=None,
        mass_margin=None,
        power_margin=None,
        manual_mass_kg=None,
        manual_cog=None,
        manual_inertia=None,
        can_have_custom_power=False,
        temperatures=Temperatures(None, None, None, None),
        power_modes=(),
        shapes=shapes,
    )
    base.update(kw)
    return Equipment(**base)  # type: ignore[arg-type]


def test_a_translation_and_a_rotation_about_one_axis() -> None:
    rigid = position_transform(pos(1.0, 2.0, 3.0, (0.0, 0.0, 90.0)))
    np.testing.assert_allclose(rigid.point(np.array([1.0, 0.0, 0.0])), [1.0, 3.0, 3.0], atol=1e-12)


def test_rotations_are_a_product_in_the_listed_order_and_right_handed() -> None:
    rx = position_transform(pos(rot=(90.0, 0.0, 0.0), order="Rx_Ry_Rz")).r
    ry = position_transform(pos(rot=(0.0, 90.0, 0.0), order="Rx_Ry_Rz")).r
    both = position_transform(pos(rot=(90.0, 90.0, 0.0), order="Rx_Ry_Rz")).r
    np.testing.assert_allclose(both, rx @ ry, atol=1e-12)
    np.testing.assert_allclose(rx @ np.array([0.0, 1.0, 0.0]), [0.0, 0.0, 1.0], atol=1e-12)
    # the order names the axes, so the same angles in another order give another rotation
    zyx = position_transform(pos(rot=(90.0, 90.0, 0.0), order="Rz_Ry_Rx")).r
    assert not np.allclose(both, zyx)


def test_a_capital_order_and_a_repeated_axis_are_read() -> None:
    position_transform(pos(order="RX_RY_RZ"))
    position_transform(pos(order="Rx_Ry_Rx", rot=(10.0, 20.0, 30.0)))


@pytest.mark.parametrize(
    "bad", [pos(order="Rq_Ry_Rz"), pos(order="Rx_Ry"), pos(transformation="Rotation_Translation")]
)
def test_what_is_not_covered_is_refused(bad: Position) -> None:
    with pytest.raises(GeometryError) as info:
        position_transform(bad)
    assert info.value.code == PLACEMENT


def test_a_box_has_its_origin_at_a_corner() -> None:
    body = shape_body(shape("FilledBox", 12.0, d1=1.0, d2=2.0, d3=3.0))
    np.testing.assert_allclose(body.com, [0.5, 1.0, 1.5])
    np.testing.assert_allclose(np.diag(body.inertia), [13.0, 10.0, 5.0])  # m/12 (b2+c2) ...
    assert shape_body(shape("Box", 1.0, d1=1.0, d2=1.0, d3=1.0)).mass == 1.0


def test_a_box_with_rounded_edges_is_not_covered() -> None:
    with pytest.raises(GeometryError) as info:
        shape_body(shape("Box", 1.0, d1=1.0, d2=1.0, d3=1.0, r=0.1))
    assert info.value.code == SHAPE


def test_a_whole_cylinder_stands_on_its_base_along_z() -> None:
    body = shape_body(shape("FilledCylinder", 4.0, d1=0.5, d3=2.0, angle1=0.0, angle2=360.0, s=1.0))
    np.testing.assert_allclose(body.com, [0.0, 0.0, 1.0])
    np.testing.assert_allclose(
        np.diag(body.inertia), [4 * (3 * 0.25 + 4) / 12] * 2 + [4 * 0.25 / 2]
    )


@pytest.mark.parametrize("extra", [dict(angle2=180.0), dict(s=2.0)])
def test_a_part_of_a_cylinder_or_a_stretched_one_is_not_covered(extra: dict[str, float]) -> None:
    params = dict(d1=0.5, d3=2.0, angle1=0.0, angle2=360.0, s=1.0) | extra
    with pytest.raises(GeometryError):
        shape_body(shape("FilledCylinder", 1.0, **params))


def test_a_right_triangle_prism() -> None:
    body = shape_body(shape("ExtrudedTriangle", 6.0, d1=3.0, d2=4.0, d3=0.5, angle1=90.0))
    np.testing.assert_allclose(body.com, [1.0, 4.0 / 3.0, 0.25], atol=1e-12)
    # section moments of a right triangle about its centroid: b^2/18 and h^2/18
    ixx = 6.0 * (16.0 / 18.0 + 0.25 / 12.0)
    iyy = 6.0 * (9.0 / 18.0 + 0.25 / 12.0)
    izz = 6.0 * (16.0 / 18.0 + 9.0 / 18.0)
    np.testing.assert_allclose(np.diag(body.inertia), [ixx, iyy, izz], rtol=1e-12)
    np.testing.assert_allclose(body.inertia[0, 1], 6.0 * (-(-1.0 * 3.0 * 4.0 / 36.0)), rtol=1e-9)


def test_a_rectangular_quadrangle_prism_is_a_box() -> None:
    quad = shape_body(
        shape("ExtrudedQuadrangle", 2.0, d1=1.0, d2=2.0, d3=2.0, d4=0.5, angle1=90.0, angle2=90.0)
    )
    box = shape_body(shape("Box", 2.0, d1=1.0, d2=2.0, d3=0.5))
    np.testing.assert_allclose(quad.com, box.com, atol=1e-12)
    np.testing.assert_allclose(quad.inertia, box.inertia, atol=1e-12)


@pytest.mark.parametrize("kind", ["Sphere", "HollowCone", "Topology", "Line"])
def test_other_kinds_are_not_covered(kind: str) -> None:
    with pytest.raises(GeometryError) as info:
        shape_body(shape(kind, 1.0, d1=1.0))
    assert info.value.code == SHAPE


def test_a_mass_per_area_or_volume_is_not_covered() -> None:
    area = Shape("1", "s", "s", "Area", 4.8, 9.0, 0.0, "Box", (), "o", pos())
    with pytest.raises(GeometryError):
        shape_body(area)


def test_two_shapes_combine_with_the_parallel_axis_theorem() -> None:
    cube = dict(d1=1.0, d2=1.0, d3=1.0)
    e = equipment(
        (
            shape("Box", 1.0, pos(0.0, 0.0, 0.0), **cube),
            shape("Box", 1.0, pos(2.0, 0.0, 0.0), **cube),
        )
    )
    body = equipment_body(e)
    assert body is not None
    np.testing.assert_allclose(body.com, [1.5, 0.5, 0.5])
    np.testing.assert_allclose(body.mass, 2.0)
    # about the common centre: each cube is 1.0 away along x
    iyy = 2 * (1.0 / 6.0 + 1.0)
    ixx = 2 * (1.0 / 6.0)
    np.testing.assert_allclose(np.diag(body.inertia), [ixx, iyy, iyy], rtol=1e-12)


def test_a_shape_without_mass_is_ignored_whatever_its_kind() -> None:
    e = equipment((shape("Box", 2.0, d1=1.0, d2=1.0, d3=1.0), shape("Topology", 0.0)))
    body = equipment_body(e)
    assert body is not None and body.mass == 2.0


def test_entered_properties_are_used_as_given() -> None:
    e = equipment(
        (),
        origin="ManualInput",
        manual_mass_kg=3.0,
        manual_cog=Point(0.1, 0.2, 0.3),
        manual_inertia=Inertia((1.0, 0.0, 0.0, 0.0, 2.0, 0.0, 0.0, 0.0, 3.0)),
    )
    body = equipment_body(e)
    assert body is not None
    np.testing.assert_allclose(body.com, [0.1, 0.2, 0.3])
    np.testing.assert_allclose(np.diag(body.inertia), [1.0, 2.0, 3.0])


def test_entered_properties_that_are_missing_are_refused() -> None:
    with pytest.raises(GeometryError):
        equipment_body(equipment((), origin="ManualInput", manual_mass_kg=3.0))


def occurrence() -> Occurrence:
    return Occurrence("occ", "eq", "1", "S", (), None, (), (), ())


def frames(*items: Frame) -> IdmModel:
    return IdmModel(
        "m.idm", "0" * 64, "3.4.1.1", None, None, None, None, None,
        (), (), (), (), (), (), (), frames=items,
    )  # fmt: skip


def test_a_chain_of_placements() -> None:
    """occurrence -> coordinate system of a mother occurrence -> the mother -> the model."""
    model = frames(
        Frame(
            "mother", "occurrence", pos(10.0, 0.0, 0.0, (0.0, 0.0, 90.0)), None, None, None, None
        ),
        Frame("mother_co.2", "coordinate_system", pos(1.0, 0.0, 0.0), None, "def", "mother", None),
        Frame("occ", "occurrence", pos(0.0, 2.0, 0.0), "mother_co.2", None, None, None),
    )
    world = Placement(model).world("occ")
    # in the mother's frame the occurrence is at (1, 2, 0); the mother turns x into y
    np.testing.assert_allclose(world.t, [10.0 - 2.0, 1.0, 0.0], atol=1e-12)


def test_a_sub_occurrence_takes_the_position_of_the_one_it_was_copied_from() -> None:
    model = frames(
        Frame("template", "occurrence", pos(0.0, 0.0, 5.0), None, None, None, None),
        Frame("occ", "occurrence", None, None, "template", None, None),
    )
    np.testing.assert_allclose(Placement(model).world("occ").t, [0.0, 0.0, 5.0])


def test_an_articulation_at_zero_changes_nothing_and_any_other_value_is_refused() -> None:
    zero = frames(
        Frame("co", "coordinate_system", pos(1.0, 0.0, 0.0), None, None, None, 0.0),
        Frame("occ", "occurrence", pos(), "co", None, None, None),
    )
    np.testing.assert_allclose(Placement(zero).world("occ").t, [1.0, 0.0, 0.0])
    for value in (0.5, float("nan")):
        moved = frames(
            Frame("co", "coordinate_system", pos(), None, None, None, value),
            Frame("occ", "occurrence", pos(), "co", None, None, None),
        )
        with pytest.raises(GeometryError) as info:
            Placement(moved).world("occ")
        assert info.value.code == PLACEMENT


def test_a_circular_or_missing_chain_is_refused() -> None:
    loop = frames(
        Frame("a", "occurrence", pos(), "b", None, None, None),
        Frame("b", "coordinate_system", pos(), "a", None, None, None),
    )
    with pytest.raises(GeometryError):
        Placement(loop).world("a")
    with pytest.raises(GeometryError):
        Placement(frames()).world("nothing")


def test_the_centre_and_the_inertia_in_the_model_frame() -> None:
    e = equipment((shape("Box", 12.0, d1=1.0, d2=2.0, d3=3.0),))
    model = frames(
        Frame("occ", "occurrence", pos(1.0, 0.0, 0.0, (0.0, 0.0, 90.0)), None, None, None, None)
    )
    found = occurrence_properties(Placement(model), occurrence(), e)
    assert found is not None
    np.testing.assert_allclose(found.position_m, [1.0 - 1.0, 0.5, 1.5], atol=1e-12)
    # turned 90 degrees about z, the xx and yy moments swap
    np.testing.assert_allclose(found.inertia[:3], [10.0, 13.0, 5.0], atol=1e-12)


# ---- through the whole import ------------------------------------------------------------------


def mapped(tmp_path: Path, **options: str) -> dict[str, dict[str, object]]:
    read = read_idm(write_idm(tmp_path / "m.idm"))
    assert read.model is not None
    return map_model(read.model, ImportOptions(**options)).units


def test_an_imported_unit_gets_its_centre_of_gravity_marked_as_an_estimate(tmp_path: Path) -> None:
    units = mapped(tmp_path)
    slab = units["el-1_ss-SS1_eqi-2-1"]
    props = slab["mass_properties"]
    assert isinstance(props, dict)
    # the slab is 0.1 x 0.2 x 0.02 m, placed at x = 2 and turned 90 degrees about z
    np.testing.assert_allclose(props["position_m"], [2.0 - 0.1, 0.05, 0.01], atol=1e-12)
    m = 3.25
    inertia = props["inertia"]
    assert isinstance(inertia, dict)
    np.testing.assert_allclose(
        [inertia["ixx_kgm2"], inertia["iyy_kgm2"], inertia["izz_kgm2"]],
        [m / 12 * (0.1**2 + 0.02**2), m / 12 * (0.2**2 + 0.02**2), m / 12 * (0.1**2 + 0.2**2)],
        rtol=1e-12,
    )
    prov = slab["provenance"]
    assert isinstance(prov, dict)
    assert prov["mass_properties.position_m"]["status"] == "estimate"
    assert "DV-IDM5" in prov["mass_properties.position_m"]["note"]
    assert prov["mass_properties.inertia.ixx_kgm2"]["status"] == "estimate"


def test_entered_properties_of_a_widget_are_taken(tmp_path: Path) -> None:
    props = mapped(tmp_path)["el-1_ss-SS1_eqi-1-1"]["mass_properties"]
    assert isinstance(props, dict)
    np.testing.assert_allclose(props["position_m"], [0.1, 0.0, 0.25])


def test_none_leaves_them_out(tmp_path: Path) -> None:
    units = mapped(tmp_path, mass_properties="none")
    assert all("mass_properties" not in u for u in units.values())
    assert not any("mass_properties" in str(u.get("provenance")) for u in units.values())


def test_math_is_not_hiding_a_sign_error() -> None:
    """A rotation of +90 degrees about x takes y to z (right-handed)."""
    r = position_transform(pos(rot=(90.0, 0.0, 0.0))).r
    assert math.isclose((r @ np.array([0.0, 1.0, 0.0]))[2], 1.0)
