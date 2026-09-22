# Data migration: retire the leftover demo account seeded for the removed
# Principal role. It was reassigned to 'registrar' by 0002, but its username
# still implied the removed role and duplicated Registrar access with a weak
# default password. Rename it to a neutral username and deactivate it.

from django.db import migrations


def retire_principal_account(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    user = User.objects.filter(username='principal').first()
    if user is None:
        return
    # Avoid collision if a 'registrar2' account already exists.
    base = 'registrar2'
    candidate = base
    suffix = 1
    while User.objects.filter(username=candidate).exists():
        suffix += 1
        candidate = f'{base}{suffix}'
    user.username = candidate
    user.is_active = False
    user.save(update_fields=['username', 'is_active'])


def restore_principal_account(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    user = User.objects.filter(username__startswith='registrar2', is_active=False).first()
    if user is None:
        return
    user.username = 'principal'
    user.is_active = True
    user.save(update_fields=['username', 'is_active'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_alter_user_role'),
    ]

    operations = [
        migrations.RunPython(retire_principal_account, restore_principal_account),
    ]
