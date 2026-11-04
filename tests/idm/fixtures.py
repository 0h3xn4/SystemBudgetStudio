"""Synthetic IDM-CIC model files, written by hand for the tests.

Every name and number here is invented. Nothing was copied or derived from a model file made by
IDM-CIC or from its documentation: the XML is built from the element names the reader has to know
and from our own understanding of how the objects relate (decision D-237). The archive is written
with fixed timestamps and order, so the same input gives the same bytes.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

BOM = b"\xef\xbb\xbf"
EL = "el.1_ss.SS1"


def _tag(name: str, text: str) -> str:
    return f"<{name}>{text}</{name}>"


def power_mode(mode_id: str, name: str, power: str, dissipation: str) -> str:
    return (
        f'<PowerMode id="{mode_id}" fullId="{EL}_eq.1_pm.{mode_id}">'
        + _tag("name", name)
        + _tag("power", power)
        + _tag("dissipation", dissipation)
        + "</PowerMode>"
    )


def shape(shape_id: str, owner: str, mass: str, body: str, mass_type: str = "Total") -> str:
    return (
        f'<Shape id="{shape_id}" fullId="{owner}_sh.{shape_id}">'
        + _tag("name", "Block " + shape_id)
        + '<massDefinition><MassDefinition fullId="'
        + f'{owner}_sh.{shape_id}_massDefinition">'
        + _tag("massType", mass_type)
        + _tag("massTotal", mass)
        + _tag("massPerSquareMeter", "0")
        + _tag("massPerCubeMeter", "0")
        + "</MassDefinition></massDefinition>"
        + f"<shapeDefinition>{body}</shapeDefinition>"
        + "</Shape>"
    )


def equipment(
    eq_id: str,
    name: str,
    *,
    origin: str = "ManualInput",
    mass: str = "0",
    maturity: str = "ToBeModified_10",
    margin: str = "0,1",
    power_margin: str = "0",
    optional: bool = False,
    default_enabled: bool = True,
    links: str = "",
    modes: str = "",
    shapes: str = "",
    temps: tuple[str, str, str, str] = ("0", "0", "0", "0"),
) -> str:
    full = f"{EL}_eq.{eq_id}"
    return (
        f'<Equipment id="{eq_id}" fullId="{full}">'
        + _tag("massMaturityLevel", maturity)
        + _tag("massMargin", margin)
        + _tag("mciDataOrigin", origin)
        + _tag("manualMass", mass)
        + f'<manualCog><Point fullId="{full}_manualCog">'
        + "<x>0,1</x><y>0</y><z>0,25</z></Point></manualCog>"
        + f'<manualInertiaMatrix><Matrix fullId="{full}_manualInertiaMatrix">'
        + "<xx>1</xx><xy>0</xy><xz>0</xz><yx>0</yx><yy>2</yy><yz>0</yz>"
        + "<zx>0</zx><zy>0</zy><zz>3</zz></Matrix></manualInertiaMatrix>"
        + _tag("canHaveCustomPower", "False")
        + _tag("powerMargin", power_margin)
        + _tag("temperatureOpMin", temps[0])
        + _tag("temperatureOpMax", temps[1])
        + _tag("temperatureNOpMin", temps[2])
        + _tag("temperatureNOpMax", temps[3])
        + f'<shapes maxId="1"><Array>{shapes}</Array></shapes>'
        + f'<powerModes maxId="2"><Array>{modes}</Array></powerModes>'
        + _tag("name", name)
        + _tag("isOptional", "True" if optional else "False")
        + _tag("defaultEnabledValue", "True" if default_enabled else "False")
        + f"<optionalUnitLinks><Array>{links}</Array></optionalUnitLinks>"
        + "</Equipment>"
    )


def mapping(owner: str, mode: str, power_mode: str) -> str:
    return (
        f'<ElementToEquipmentPowerMode id="{mode}" fullId="{owner}_eleqm.{mode}">'
        + f'<elementMode><ElementMode ref="el.1_elm.{mode}" /></elementMode>'
        + f'<powerMode><PowerMode ref="{EL}_eq.1_pm.{power_mode}" /></powerMode>'
        + "</ElementToEquipmentPowerMode>"
    )


def instance(
    eq_id: str, number: str, *, extra: str = "", tag: str = "EquipmentInstance", owner: str = EL
) -> str:
    full = f"{owner}_eqi.{eq_id}-{number}"
    return (
        f'<{tag} id="{eq_id}-{number}" fullId="{full}">'
        + f'<unit><Equipment ref="{EL}_eq.{eq_id}" /></unit>'
        + extra
        + f"</{tag}>"
    )


def widget_extra(owner: str) -> str:
    return (
        '<thermalModule><ThermalModule ref="el.1_thm.1" /></thermalModule>'
        "<elementToEquipmentPowerModes><Array>"
        + mapping(owner, "OFF", "2")
        + mapping(owner, "ON", "1")
        + "</Array></elementToEquipmentPowerModes>"
    )


def tank_content(owner: str) -> str:
    return (
        "<tankContents><Array>"
        f'<TankContent id="1" fullId="{owner}_tk.1">'
        "<defaultFillingPercentage>1</defaultFillingPercentage>"
        f'<tank><Tank ref="{EL}_eq.4_sh.1_tank" /></tank>'
        "<tankContentValues><Array>"
        f'<TankContentValue id="C1" fullId="{owner}_tk.1_cfg.C1">'
        "<fillingPercentage>0,25</fillingPercentage></TankContentValue>"
        "</Array></tankContentValues>"
        "</TankContent></Array></tankContents>"
    )


def model_xml(
    *,
    version: str = "3.4.1.1",
    margin_text: str = "0,5",
    extra_units: str = "",
    system_extra: str = "",
) -> str:
    box = (
        '<FilledBox fullId="'
        + f'{EL}_eq.2_sh.1_fbox"><d1>0,1</d1><d2>0,2</d2><d3>0,02</d3></FilledBox>'
    )
    tank = (
        f'<Tank fullId="{EL}_eq.4_sh.1_tank"><d1>0,1</d1><d3>0,3</d3><d4>0,001</d4>'
        "<capacity>8</capacity><maximalFilling>0,95</maximalFilling></Tank>"
    )
    widget_modes = power_mode("1", "On", "1,5E1", "1,2E1") + power_mode("2", "Off", "0", "0")
    units = (
        equipment(
            "1",
            "Widget",
            mass="2,5",
            modes=widget_modes,
            temps=("-20", "50", "-30", "60"),
            power_margin="0,05",
        )
        + equipment(
            "2", "Slab", origin="FromGeometry", shapes=shape("1", f"{EL}_eq.2", "3,25", box)
        )
        + equipment(
            "3",
            "Spare",
            mass="0,5",
            optional=True,
            default_enabled=False,
            links=f'<OptionalUnitLink id="C1" fullId="{EL}_eq.3_cfg.C1"><enabled>True</enabled>'
            "</OptionalUnitLink>",
        )
        + equipment(
            "4", "Reservoir", origin="FromGeometry", shapes=shape("1", f"{EL}_eq.4", "1,2", tank)
        )
        + f'<Assembly id="5" fullId="{EL}_ass.5">'
        + _tag("name", "Rack")
        + "<unitInstances><Array>"
        + instance("1", "1", owner=f"{EL}_ass.5")
        + "</Array></unitInstances></Assembly>"
        + extra_units
    )
    placed = (
        instance("1", "1", extra=widget_extra(f"{EL}_eqi.1-1"))
        + instance("1", "2", extra=widget_extra(f"{EL}_eqi.1-2"))
        + instance("2", "1")
        + instance("4", "1", extra=tank_content(f"{EL}_eqi.4-1"))
        + f'<AssemblyInstance id="5-1" fullId="{EL}_assi.5-1">'
        + f'<unit><Assembly ref="{EL}_ass.5" /></unit>'
        + "<unitOccurrences><Array>"
        + instance(
            "1",
            "1",
            tag="EquipmentOccurrence",
            owner=f"{EL}_assi.5-1",
            extra=widget_extra(f"{EL}_assi.5-1_eqi.1-1"),
        )
        + "</Array></unitOccurrences></AssemblyInstance>"
    )
    element_one = (
        '<Element id="1" fullId="el.1">'
        + _tag("name", "Alpha")
        + _tag("massTarget", "12,5")
        + _tag("massMargin", margin_text)
        + _tag("powerMargin", "0,1")
        + '<relatedSubsystems maxId="0"><Array>'
        + f'<RelatedSubsystem id="SS1" fullId="{EL}">'
        + '<subsystem><Subsystem ref="ss.SS1" /></subsystem>'
        + f'<units maxId="5"><Array>{units}</Array></units>'
        + f'<unitInstances maxId="0"><Array>{placed}</Array></unitInstances>'
        + "</RelatedSubsystem></Array></relatedSubsystems>"
        + "<elementModes><Array>"
        + '<ElementMode id="OFF" fullId="el.1_elm.OFF"><name>Off</name></ElementMode>'
        + '<ElementMode id="ON" fullId="el.1_elm.ON"><name>On</name></ElementMode>'
        + "</Array></elementModes>"
        + '<thermalModules><Array><ThermalModule id="1" fullId="el.1_thm.1">'
        + _tag("name", "Panel node")
        + "</ThermalModule></Array></thermalModules>"
        + "</Element>"
    )
    element_two = (
        '<Element id="2" fullId="el.2"><name>Beta</name><massTarget>0</massTarget>'
        "<massMargin>0</massMargin><powerMargin>0</powerMargin></Element>"
    )
    return (
        "<IDM>\r\n"
        f'<IdmData version="{version}">\r\n'
        '<MainSystem fullId="">'
        + _tag("projectName", "Test system")
        + _tag("propellantMassMargin", "0,02")
        + f'<elements maxId="2"><Array>{element_one}{element_two}</Array></elements>'
        + '<subsystems maxId="0"><Array><Subsystem id="SS1" fullId="ss.SS1"><name>Subsystem '
        "One</name></Subsystem></Array></subsystems>"
        + '<configurations maxId="1"><Array><Configuration id="C1" fullId="cfg.C1">'
        + _tag("name", "Configuration one")
        + '<enabledElements><Array><Element ref="el.1" /></Array></enabledElements>'
        + "</Configuration></Array></configurations>"
        + '<systemModes maxId="1"><Array><SystemMode id="M1" fullId="sm.M1">'
        + _tag("name", "Mode one")
        + _tag("dutyCycle", "0")
        + '<elementModes><Array><ElementMode ref="el.1_elm.ON" /></Array></elementModes>'
        + "</SystemMode></Array></systemModes>"
        + '<additionalPropertyDefinitions maxId="1"><Array>'
        + '<AdditionalPropertyDefinition id="Note" fullId="add.Note"><name>Free note</name>'
        + "</AdditionalPropertyDefinition></Array></additionalPropertyDefinitions>"
        + '<formulas maxId="1"><Array><Formula id="f1" fullId="for.f1">'
        + _tag("propertyName", "el.1_ss.SS1_eq.2_sh.1_fbox_d1")
        + _tag("formulaExpression", "1")
        + _tag("isValid", "False")
        + _tag("isConsistent", "True")
        + "</Formula></Array></formulas>"
        + system_extra
        + _tag("lastModification", "06/09/2023 08:38:12")
        + "</MainSystem>\r\n</IdmData>\r\n<ExternalData />\r\n</IDM>"
    )


def write_idm(
    path: Path,
    xml: str | bytes | None = None,
    *,
    bom: bool = True,
    extra: dict[str, bytes] | None = None,
    model_name: str | None = "model.xml",
) -> Path:
    """Write a deterministic archive: fixed timestamps, fixed order."""
    body = xml if xml is not None else model_xml()
    data = body.encode("utf-8") if isinstance(body, str) else body
    if bom:
        data = BOM + data
    entries: dict[str, bytes] = {}
    if model_name is not None:
        entries[model_name] = data
    entries.update(extra or {})
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)
    return path
