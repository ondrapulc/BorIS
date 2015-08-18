from django.contrib.admin.utils import flatten_fieldsets
from boris.utils.admin import BorisBaseAdmin

__author__ = 'ondrej'


class ReadOnlyAdmin(BorisBaseAdmin):
    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return self.readonly_fields

        if self.declared_fieldsets:
            fields = flatten_fieldsets(self.declared_fieldsets)
        else:
            form = self.get_formset(request, obj).form
            fields = form.base_fields.keys()
        return fields

    def has_delete_permission(self, request, obj=None):
        return False