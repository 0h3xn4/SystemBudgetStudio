# Mass budget

Units and expendables carry a mass and a maturity class. The tool applies the mass margin of the class, then the system mass margin, and checks the total against the mass limits.

## Phases

`mission_phases` in `spacecraft.yaml` lists the phases you choose (for example launch, BOL, EOL); none are assumed. A unit may list the phases it is present in. An expendable gives its mass for **every** phase, with `0.0` written explicitly where it is gone. In the window, **Edit > Add expendable** (Ctrl+Shift+X) asks for the mass in every phase; a second propellant mass (an oxidizer) is a second expendable.

## Centre of gravity and inertia

Positions are the centres of mass of items in metres in one right-handed body frame described in words in `spacecraft.yaml`. An item can also give its inertia tensor about its own centre of mass (axes parallel to the body frame). Items without a position are excluded from the centre of gravity and reported with `MASS_PROPS_MISSING`; an item without inertia is treated as a point mass.

## Propellant and the propulsion budget

`config/propulsion.yaml` lists the propulsion systems (chemical or electric, with the specific impulse, optionally the thrust and the power) and the manoeuvres with their delta-v. `budget run --budget propulsion` works them backwards from the dry mass with the rocket equation: the propellant of each burn and system, the initial mass, the burn time, the electric power and energy, and the margin against the propellant the expendable named by the system loads. The delta-v of each manoeuvre is yours to give; burns are impulsive. In the window it is the *Propulsion* page of this area.

## Limits

`config/mass_limits.yaml` lists limits per phase. A total above its limit is reported as `MASS_LIMIT_EXCEEDED` with the margin still available.
