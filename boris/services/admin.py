# -*- coding: utf-8 -*-
from django import forms
from django.contrib import admin
from django.contrib.admin.utils import flatten_fieldsets
from django.http import HttpResponseRedirect
from django.utils.encoding import force_unicode
from django.utils.translation import ugettext_lazy as _

from boris.services.models.core import Encounter
from boris.clients.forms import ReadOnlyWidget
from boris.clients.models import Person
from boris.utils.admin import BorisBaseAdmin


def service_list(self, obj):
    return u'<br />'.join([u'<small>%s</small>' % unicode(s) for s in obj.services.all()])
service_list.short_description = _(u'Provedené výkony')
service_list.allow_tags = True


class EncounterInline(admin.TabularInline):
    model = Encounter
    classes = ('grp-collapse', 'grp-closed',)
    fieldsets = (
        (None, {
            'fields': ('performed_on', 'where', 'performed_by_verbose',
                'service_count', 'service_list', 'goto_link'),
        }),
    )
    readonly_fields = ('performed_by_verbose', 'service_count', 'service_list',
        'goto_link')
    extra = 0
    template = 'admin/services/encounter/encounter_inline.html'

    def has_add_permission(self, request, *args, **kwargs):
        return False

    def performed_by_verbose(self, obj):
        return u', '.join([unicode(u) for u in obj.performed_by.all()])
    performed_by_verbose.short_description = _(u'Provedli')

    def goto_link(self, obj):
        if obj.pk:
            return u'<a href="%s"><strong>%s &raquo;</strong></a>' % (obj.get_admin_url(), _(u'Přejít'))
        else:
            return _(u'Detaily kontaktu je možné editovat až po uložení.')
    goto_link.short_description = _(u'Přejít')
    goto_link.allow_tags = True

EncounterInline.service_list = service_list


class EncounterAdmin(BorisBaseAdmin):
    list_display = ('person_link', 'performed_on', 'where', 'is_by_phone',
        'service_list')
    list_display_links = None
    list_filter = ('performed_on', 'where', 'is_by_phone')
    search_fields = ('person__title', 'where__title',
        'performed_by__username', 'performed_by__first_name',
        'performed_by__last_name')
    fieldsets = (
        (None, {'fields': (('person', 'performed_on'), ('where', 'is_by_phone'),
            'performed_by')}),
    )
    raw_id_fields = ('where', 'person')
    date_hierarchy = 'performed_on'
    autocomplete_lookup_fields = {
        'fk': ['where', 'person']
    }

    def person_link(self, obj):
        """Redefined "person" pointing to the person's page."""
        person = obj.person.cast()
        return u'<a href="%s">%s</a>' % (person.get_admin_url(), person)
    person_link.allow_tags = True
    person_link.short_description = _('Osoba')

    def _prepare_for_prefilling(self, request, obj):
        """Enable field pre-filling based on existing records."""
        if "_addanother" in request.POST:
            verbose_name = obj._meta.verbose_name
            msg = _('The %(name)s "%(obj)s" was added successfully.') % {
                'name': force_unicode(verbose_name), 'obj': force_unicode(obj)}
            self.message_user(request, msg + ' ' + (
                _("You may add another %s below.") % force_unicode(verbose_name)))
            return HttpResponseRedirect("../add/?previous_id=%i" % obj.pk)

    def response_change(self, request, obj):
        redir_prefill = self._prepare_for_prefilling(request, obj)
        if redir_prefill is not None:
            return redir_prefill
        return super(EncounterAdmin, self).response_change(request, obj)

    def response_add(self, request, obj, post_url_continue='../%s/'):
        redir_prefill = self._prepare_for_prefilling(request, obj)
        if redir_prefill is not None:
            return redir_prefill
        return super(EncounterAdmin, self).response_add(request, obj,
            post_url_continue % obj.id)

    def _prefill_by_encounter(self, db_field, kwargs, encounter_id):
        if db_field.name in ('person', 'where', 'performed_by', 'performed_on'):
            try:
                encounter = Encounter.objects.get(pk=encounter_id)
            except Encounter.DoesNotExist:
                return
            if db_field.name == 'person':
                kwargs['initial'] = encounter.person_id
            elif db_field.name == 'where':
                kwargs['initial'] = encounter.where_id
            elif db_field.name == 'performed_by':
                kwargs['widget'] = forms.SelectMultiple(attrs={'style': 'height: 160px;'})
                kwargs['initial'] = encounter.performed_by.all()
                kwargs.pop('request')
                return db_field.formfield(**kwargs)
            elif db_field.name == 'performed_on':
                kwargs['initial'] = encounter.performed_on
            return super(EncounterAdmin, self).formfield_for_dbfield(db_field, **kwargs)

    def _prefill_by_person(self, db_field, kwargs, person_id):
        if db_field.name in ('person', 'where'):
            try:
                person = Person.objects.get(pk=person_id).cast()
            except Person.DoesNotExist:
                return
            if db_field.name == 'person':
                kwargs['widget'] = ReadOnlyWidget(person_id,
                    '%s %s' % (unicode(person._meta.verbose_name).lower(), person))
                kwargs['initial'] = person_id
                kwargs.pop('request')
                return db_field.formfield(**kwargs)
            elif db_field.name == 'where' and hasattr(person, 'town_id'):
                kwargs['initial'] = person.town_id
                return super(EncounterAdmin, self).formfield_for_dbfield(db_field, **kwargs)

    def formfield_for_dbfield(self, db_field, **kwargs):
        """Prefill values and change widgets in certain cases."""
        request = kwargs.get('request', None)
        if request and request.GET.get('previous_id'):
            formfield = self._prefill_by_encounter(db_field, kwargs, request.GET['previous_id'])
            if formfield: return formfield
        if request and request.GET.get('person_id'):
            formfield = self._prefill_by_person(db_field, kwargs, request.GET['person_id'])
            if formfield: return formfield
        if db_field.name == 'performed_by':
            kwargs['widget'] = forms.SelectMultiple(attrs={'style': 'height: 160px;'})
            kwargs['initial'] = (request.user,)
            kwargs.pop('request')
            return db_field.formfield(**kwargs)
        return super(EncounterAdmin, self).formfield_for_dbfield(db_field, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        if obj is not None and not obj.is_editable():
            if self.declared_fieldsets:
                return flatten_fieldsets(self.declared_fieldsets)
            else:
                return list(set(
                    [field.name for field in self.opts.local_fields] +
                    [field.name for field in self.opts.local_many_to_many]
                ))
        return super(EncounterAdmin, self).get_readonly_fields(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and not obj.is_editable():
            return False
        return super(EncounterAdmin, self).has_delete_permission(request, obj=obj)

    def change_button(self, obj):
        if obj is not None and not obj.is_editable():
            return u'<a href="%s" class="changelink cbutton">%s</a>' % (
                obj.get_admin_url(), _('zobrazit'))
        return u'<a href="%s" class="changelink cbutton">%s</a>' % (
            obj.get_admin_url(), _('upravit'))

    def show_save_and_add_another(self, obj):
        if obj is not None and not obj.is_editable():
            return False
        return bool(obj and obj.pk)

    def show_save(self, obj):
        return False

    def show_save_and_continue(self, obj):
        if obj is not None and not obj.is_editable():
            return False
        return True

    def button_captions(self, obj):
        if not obj or not obj.pk:
            return {'BO_SAVE_AND_CONT_CAPTION': _(u'Přidat výkony')}
        return {}

EncounterAdmin.service_list = service_list


admin.site.register(Encounter, EncounterAdmin)
