from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from .models import User


class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white',
        'placeholder': 'Username'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white',
        'placeholder': 'Password'
    }))


class UserCreationFormAdmin(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'role', 'phone', 'address')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white'
            })


class UserEditForm(forms.ModelForm):
    new_password1 = forms.CharField(
        label="New password",
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Leave blank to keep current password',
            'autocomplete': 'new-password',
        }),
        required=False,
        help_text="Leave blank to keep the current password.",
    )
    new_password2 = forms.CharField(
        label="Confirm new password",
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Repeat the new password',
            'autocomplete': 'new-password',
        }),
        required=False,
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'role', 'phone', 'address', 'is_active')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white'
            })

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('new_password1') or ''
        p2 = cleaned.get('new_password2') or ''
        if p1 or p2:
            if p1 != p2:
                self.add_error('new_password2', 'The two passwords do not match.')
            else:
                try:
                    validate_password(p1, self.instance)
                except forms.ValidationError as e:
                    self.add_error('new_password1', e)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        new_password = (self.cleaned_data or {}).get('new_password1')
        if new_password:
            user.set_password(new_password)
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'phone', 'address', 'profile_picture')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white'
            })


class PasswordChangeForm(forms.Form):
    old_password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white',
        'placeholder': 'Current Password'
    }))
    new_password1 = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white',
        'placeholder': 'New Password'
    }))
    new_password2 = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white',
        'placeholder': 'Confirm New Password'
    }))
