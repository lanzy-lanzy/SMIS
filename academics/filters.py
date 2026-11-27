from .models import Subject


def select_school_year(requested, school_years):
    """Resolve a year filter, with an explicit option to show every year."""
    if requested in ('all', ''):
        return 'all', None
    selected = next((year for year in school_years if str(year.pk) == requested), None)
    if selected is None:
        selected = next((year for year in school_years if year.is_current), None)
    return (str(selected.pk), selected) if selected else ('all', None)


def subject_name_filter(subjects, selected_id):
    """Offer one choice per subject name and resolve it to all matching subject IDs."""
    groups = {}
    selected_key = None
    for subject in sorted(subjects, key=lambda subject: subject.pk):
        key = " ".join(subject.name.casefold().split())
        groups.setdefault(key, []).append(subject)
        if str(subject.pk) == selected_id:
            selected_key = key

    options = [groups[key][0] for key in sorted(groups)]
    if selected_key is None and selected_id.isascii() and selected_id.isdecimal() and len(selected_id) <= 19:
        name = Subject.objects.filter(pk=int(selected_id)).values_list("name", flat=True).first()
        if name:
            selected_key = " ".join(name.casefold().split())
    if selected_key not in groups:
        return options, "", []
    matches = groups[selected_key]
    return options, str(matches[0].pk), [subject.pk for subject in matches]
