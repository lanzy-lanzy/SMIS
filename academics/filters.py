def select_school_year(requested, school_years):
    """Resolve a year filter, with an explicit option to show every year."""
    if requested in ('all', ''):
        return 'all', None
    selected = next((year for year in school_years if str(year.pk) == requested), None)
    if selected is None:
        selected = next((year for year in school_years if year.is_current), None)
    return (str(selected.pk), selected) if selected else ('all', None)
