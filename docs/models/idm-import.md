# Reading IDM-CIC models

Reads models from IDM-CIC (© CNES). IDM-CIC is software of the French space agency CNES for the early design of satellites. System Budget Studio is an independent tool: it uses no CNES software, library or data, it needs none installed, and CNES does not endorse or support it. This page describes in our own words what the tool reads from a model file and how.

**Status (decisions D-237, D-240 to D-247, D-253, D-254).** The tool reads the model file into a typed model (this page), maps it onto a project and merges a later version of the model into the project; the command is `budget import idm` ([how to use it](../user-manual/idm-import.md)). The centre of gravity and the inertia come from the placements and shapes (below). The kind of each equipment is proposed from its name and subsystem, and the pointing, propulsion and power system files are prepared with placeholders (item 10 of *How the model becomes a project*).

**Supported format.** The reader was written for version **3.4.0.19** of the published model description. Files saved by versions 3.4.x are read without a message; a file of a newer minor version (for example 3.5) is read with the warning `IDM_VERSION_NEWER`, and objects it does not know are left out and counted, never guessed.

## The file

A model file (`.idm`) is a ZIP archive. The tool reads **one entry only**, `model.xml` at the root of the archive, and never extracts anything: pictures, 3D files and the data of other programs in the archive are ignored. The XML is UTF-8; the program writes a byte order mark and line endings of CR LF, which the reader accepts. A document type declaration or entity definition is refused (`IDM_XML_UNSAFE`): a model has no use for one. The sizes are bounded ([settings](settings.md#reading-idm-cic-models)): the file, the unpacked model, the number of entries, the nesting and the number of elements, so that a wrong or hostile file cannot use all the memory.

The **revision** of a model is the SHA-256 of the bytes of `model.xml`: the same bytes always give the same revision.

## Value formats

A number uses a comma as the decimal separator and may have an exponent (`15,54`, `0,1554E3`, `1554E-2`); a dot, a thousands separator, `nan` and `inf` are refused. A date is `dd/mm/yyyy hh:mm:ss`. A yes/no value is `True` or `False`. A value in another format is the error `IDM_VALUE_INVALID` and the model is not used: the problem names the field and the object, never the value. Formulas that the program keeps for some properties are **never evaluated**: the stored value is read; a formula that the file marks as not valid is listed so that the stored value can be treated with care.

## Objects and identity

Every object has a `fullId`, a path-like identifier (`el.2_ss.PWR_eq.1` is equipment 1 of subsystem PWR in element 2). The tool identifies objects by `fullId` and uses names for display only, because a name can be changed. A reference to an object is a node with a `ref` attribute holding the other object's `fullId`; a reference that points nowhere leaves the object out with the warning `IDM_REF_UNRESOLVED`.

What is read, with the units the tool uses (lengths in metres, masses in kilograms, power in watts, temperatures in degrees Celsius as the file gives them, margins and fillings as fractions):

| Object | Read |
|---|---|
| System | project name, comment, version text, last change, propellant mass margin |
| Subsystem, element | id, name; the element's mass target, mass margin, power margin, forced propellant mass and margin |
| Related subsystem (an element's use of a subsystem) | forced mass and forced mass margin, if given |
| Equipment definition | name, optional flag and its default, enabled state per configuration, maturity level and mass margin, power margin, origin of the mass properties (from geometry or entered), entered mass, centre of mass and inertia, the four temperature limits, power modes (power and dissipation), shapes (mass definition and the numeric parameters of the 3D object) |
| Assembly | name (its content is read through its placed copies) |
| Physical occurrence | see below; its power mappings per element mode and per system mode, its thermal module, its tank contents and fillings |
| Element mode, system mode, thermal module, configuration | ids, names, links; a system mode's duty cycle |
| Additional properties | the definitions are listed; none is mapped |

Scenarios, trajectories, attitude files, materials, layers, roles, notes and external references are ignored.

## Which occurrences are physical

An equipment is a definition; what is in the satellite is its **occurrences**. An assembly is a group of equipment: its definition holds instances of other units, and every placed copy of the assembly holds a copy of those instances. Only the occurrences reachable from the instances **placed in an element**, walking down through placed assemblies, are physical. The instances inside an assembly definition are templates and are not counted (decision D-238). The same equipment placed twice is two occurrences, and each counts in the budgets.

## Problems

The codes of this step are `IDM_FILE_UNREADABLE`, `IDM_ARCHIVE_LIMIT`, `IDM_MODEL_MISSING`, `IDM_XML_INVALID`, `IDM_XML_UNSAFE`, `IDM_STRUCTURE_INVALID`, `IDM_VALUE_INVALID`, `IDM_VERSION_NEWER`, `IDM_REF_UNRESOLVED` and `IDM_UNIT_KIND_UNKNOWN`; see [the problem list](../PROBLEMS.md#idm-cic-models-import).

## How the model becomes a project

The rules, in the order the importer applies them (decision D-240):

1. **Units.** One unit per physical occurrence. Id: the occurrence's `fullId` with `.` turned into `-` (`el-1_ss-PWR_eqi-1-1`). Name: `Element / assembly / equipment [occurrence]`. Subsystem: the subsystem's name. Bus: the one given with `--bus`.
2. **Presence.** The reference configuration is the defaults stored on the objects: an optional unit that is disabled by default is absent from it. Every saved configuration becomes a mission phase; a unit is present in a phase when its element is enabled in the configuration and, if the unit is optional, its link to the configuration says so. A unit present in every phase has no `phases`; a unit present nowhere is left out (`IDM_NEVER_ENABLED`).
3. **Mass.** `ManualInput`: the entered mass. `FromGeometry`: the sum of the shape masses when every shape has the mass type Total; otherwise the mass needs the geometry and is not estimated. The entered mass of a geometry-based equipment is a cached value that can be out of date and is never used for it.
4. **Margins.** The equipment's mass margin is its maturity level's (stored with the equipment) and its power margin. `raw`: they become the class `idm_m<mass %>_p<power %>`; `applied`: the values are multiplied by `1 + margin` and the class `idm_applied` has margin 0.
5. **Power modes.** A mode has power and dissipation. Both map to average and peak power (DV-IDM1). The heat share is dissipation / power, 1.0 when both are 0, and absent (so thermal results are n/a) when the dissipation exceeds the power or there is no power. An equipment without power modes gets *Passive*, 0 W (DV-IDM2).
6. **Spacecraft modes.** For a system mode and a unit: the element mode that the system mode names for the unit's element selects the unit's mapping to a power mode (or a custom power); otherwise the direct mapping of the system mode is used. Names come from `idm/mode_map.yaml`. A unit with no usable power mode in a system mode gets the power mode *Not mapped* (0 W, marked `estimate`) there, so that every unit is in every spacecraft mode; one warning for each system mode, `IDM_POWER_UNMAPPED`, carries the number of such units (DV-IDM6).
7. **Thermal.** A thermal module is a node (`<element>_thm-<id>`); units on no module are on the node `idm_unplaced`. Nodes have no capacity, conductance or surface: the model has none, and none is invented.
8. **Temperature limits.** Celsius to kelvin. A band is used only when its minimum is below its maximum; the model uses 0 and 0 for a band that is not set. A survival band that does not enclose the operating band is dropped (`IDM_TEMPERATURE_IGNORED`).
9. **Tanks.** An expendable per tank content. Its mass in a phase is the capacity of the tank times the filling of the configuration (the reference phase uses the default filling), and 0 where the equipment is not present (DV-IDM3). Its margin is the propellant margin of the system, or of the element when the element sets one. The tank's centre of gravity needs the geometry and is left out.
10. **Components** (2.10.0, D-254). The kind of an equipment is proposed from the words of its name and the subsystem (`budget_core/idm/classify.py`); the skeletons of the pointing, propulsion and power system files are built from the proposals and from the user's library `idm/components.yaml` (`budget_core/idm/components.py`). The model gives no data-sheet value, so none is written: a number is the library's, with its source, or a placeholder. The state file records what was written (`components`), so that a later import updates what the import wrote and keeps what the user changed (the same three-way merge as a unit).

## Centre of gravity and inertia

Added in 2.4.0 (decisions D-245, D-246, deviation DV-IDM5). They are worked out from where each equipment is and what its shapes are, and **every number is marked `estimate`**: the published description of the format fixes the names of the placement data but not, in words, how they combine, and no value of IDM-CIC was available to check against. The conventions below were inferred from the models and tested on them: with them the panels, angles and cleats of a platform close into a box with no gap and no overlap, and with the alternatives tried (eight combinations of rotation order, handedness and translation, and a box origin at the centre) they do not.

- **Placement.** A position is a translation `t` and three rotations, composed as the product of the three axis rotations in the order the rotation order names (`Rx_Ry_Rz` is `Rx(r1) Ry(r2) Rz(r3)`), right-handed, in degrees; a point of the object is at `R p + t` in the frame it is placed on. The frame of an equipment is the frame of the coordinate system it is placed on times its position; a coordinate system is placed on its parent, or, when it is the first of an occurrence, on that occurrence; an occurrence copied from a template takes the template's position. Only the transformation order `Translation_Rotation` is covered (all the models seen use it).
- **Articulations** (a rotation or translation of a coordinate system) count when their reference value is 0, which changes nothing; any other value leaves the equipment unplaced (`IDM_GEOMETRY_PLACEMENT`).
- **Shapes** (mass type Total, uniform density; a shape of mass 0 is ignored): a **box** has its origin at a corner and extends along +x, +y, +z by d1, d2, d3; a **whole cylinder** stands on its base, axis along z, radius d1, height d3; a **triangular** or **quadrangular prism** has its section in the x-y plane, starting at the origin along x, and extends along +z by its thickness. Added in 2.5.0 (D-247), on the same footing as the cylinder: a whole **cone** (radii d1 at the base and d2 at the top, height d3) and a **hollow cylinder** or **hollow cone** (wall thickness d4, measured across the radius) stand on their base along +z; a hollow cone is taken only when its two radii are equal, where radial and normal thickness are the same thing; a wall as thick as the radius is refused. A **tank** (the shell, not its content) is a hollow cylinder with hemispherical ends: radius d1, straight part d3 from the origin along +z, wall d4, the ends reaching beyond it; for a straight part of height h, the position of the origin along the axis is the least certain convention here and moves the centre of gravity by h / 2 (the tanks seen have h of 0 to 4 cm). The closed forms are tested against textbook values. Spheres, pipes, tori, paraboloids, cuts and unions, imported 3D files, boxes with rounded edges, parts of a turn and masses per area or volume are not covered (`IDM_GEOMETRY_SHAPE`) and the unit has no mass properties.
- **Entered values.** An equipment whose centre of gravity and inertia matrix were entered uses them in its own frame. The inertia is read as tensor entries about the centre of gravity, axes parallel to the equipment frame; the description does not say about which point it is given.
- **Result.** The position of the unit is its centre of gravity in the frame of the model (the body frame of a new project), and its inertia the tensor about that point with axes parallel to the model frame. `--mass-properties none` leaves both out.

## What is not done

Nothing is estimated. A value the file does not give stays absent. The tool never writes to the model file or to IDM-CIC.

Next: [Models](README.md) · [Docs index](../README.md).
