from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from .models import Campaign, Donation


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('title', 'creator', 'category', 'status_badge', 'goal_amount', 'raised_amount', 'is_active', 'created_at')
    list_filter = ('status', 'category', 'is_active')
    search_fields = ('title', 'description', 'creator__username')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('reviewed_at',)
    actions = ['approve_campaigns', 'reject_campaigns']

    fieldsets = (
        ('Campaign Info', {
            'fields': ('title', 'slug', 'description', 'category', 'image', 'creator')
        }),
        ('Funding', {
            'fields': ('goal_amount', 'raised_amount', 'deadline')
        }),
        ('Review / Moderation', {
            'fields': ('status', 'rejection_reason', 'reviewed_at', 'is_active'),
            'description': 'Set status to "Approved" to make this campaign publicly visible, '
                           'or "Rejected" (optionally with a reason the creator will understand).'
        }),
    )

    def status_badge(self, obj):
        colors = {'pending': '#f0ad4e', 'approved': '#5cb85c', 'rejected': '#d9534f'}
        return format_html(
            '<span style="color: white; background-color: {}; padding: 2px 10px; border-radius: 10px; font-size: 11px;">{}</span>',
            colors.get(obj.status, '#777'),
            obj.get_status_display(),
        )
    status_badge.short_description = 'Status'

    def save_model(self, request, obj, form, change):
        if 'status' in form.changed_data and obj.status in ('approved', 'rejected'):
            obj.reviewed_at = timezone.now()
        super().save_model(request, obj, form, change)

    @admin.action(description='Approve selected campaigns')
    def approve_campaigns(self, request, queryset):
        updated = queryset.update(status='approved', reviewed_at=timezone.now())
        self.message_user(request, f'{updated} campaign(s) approved and are now live.')

    @admin.action(description='Reject selected campaigns')
    def reject_campaigns(self, request, queryset):
        updated = queryset.update(status='rejected', reviewed_at=timezone.now())
        self.message_user(request, f'{updated} campaign(s) rejected.')


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = ('donor', 'campaign', 'amount', 'payment_status', 'created_at')
    list_filter = ('payment_status',)
    search_fields = ('donor__username', 'campaign__title', 'transaction_uuid')
    readonly_fields = ('transaction_uuid', 'esewa_ref_id')
