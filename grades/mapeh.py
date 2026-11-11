"""Shared helpers for merging MAPEH component grades.

Music and Arts (MA) and Physical Education and Health (PEH) are encoded as
separate subjects but report as a single MAPEH grade: the whole-number
average of the component term grades.
"""

from decimal import Decimal, ROUND_HALF_UP


MAPEH_COMPONENTS = (
    ('ma', 'Music and Arts', {'music and arts', 'ma'}),
    ('peh', 'Physical Education and Health', {'physical education and health', 'pe and health', 'peah'}),
)


def _key(name):
    return ' '.join((name or '').lower().split())


def mapeh_component(name):
    """Return 'ma' / 'peh' when *name* is a MAPEH component subject, else None."""
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