"""Shared helpers for MAPEH grading.

MAPEH is one learning area but is encoded as two components (Music and Arts,
Physical Education and Health) per learner per term. In this system MAPEH is a
single ``Subject`` and the two components are distinguished by the
``Grade.component`` field ('ma' / 'peh'); reports roll the two component grades
up to a whole-number average for the MAPEH parent row.

The legacy two-subject layout (separate 'Music and Arts' and 'Physical
Education and Health' Subjects) is still recognised by ``mapeh_component`` so
older data keeps rendering; new encoding uses ``is_mapeh_subject`` on the
combined 'MAPEH' subject name.
"""

from decimal import Decimal, ROUND_HALF_UP


MAPEH_COMPONENTS = (
    ('ma', 'Music and Arts', {'music and arts', 'ma'}),
    ('peh', 'Physical Education and Health', {'physical education and health', 'pe and health', 'peah'}),
)

# Subject names that identify the combined MAPEH learning area (one Subject,
# two Grade.component rows per learner/term).
MAPEH_SUBJECT_ALIASES = {'mapeh'}


def _key(name):
    return ' '.join((name or '').lower().split())


def is_mapeh_subject(name):
    """True when *name* is the combined MAPEH subject (not a component)."""
    return _key(name) in MAPEH_SUBJECT_ALIASES


def mapeh_component(name):
    """Return 'ma' / 'peh' when *name* is a MAPEH component subject, else None.

    Only the legacy two-subject layout matches here; the combined 'MAPEH'
    subject returns ``None`` because it is the parent, not a component.
    """
    key = _key(name)
    for component, _label, aliases in MAPEH_COMPONENTS:
        if key in aliases:
            return component
    return None


def mapeh_component_label(name):
    component = mapeh_component(name)
    if component is None:
        return None
    return next(label for key, label, _aliases in MAPEH_COMPONENTS if key == component)


def merge_mapeh_grades(values):
    """Whole-number average of the given component grades, or None when empty."""
    present = [Decimal(value) for value in values if value is not None]
    if not present:
        return None
    return int((sum(present) / Decimal(len(present))).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def merge_mapeh_periods(period_maps):
    """Merge ``{period order: value}`` maps into one ``{order: merged value}``."""
    merged = {}
    orders = sorted({order for period_map in period_maps for order in period_map})
    for order in orders:
        value = merge_mapeh_grades(period_map.get(order) for period_map in period_maps)
        if value is not None:
            merged[order] = value
    return merged