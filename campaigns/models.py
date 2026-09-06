from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.text import slugify
from django.utils import timezone


CATEGORY_CHOICES = [
    ('medical', 'Medical'),
    ('education', 'Education'),
    ('disaster', 'Disaster Relief'),
    ('community', 'Community Project'),
    ('animal', 'Animal Welfare'),
    ('other', 'Other'),
]


STATUS_CHOICES = [
    ('pending', 'Pending Review'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
]


class Campaign(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    image = models.ImageField(upload_to='campaign_images/', blank=True, null=True)
    goal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    raised_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='campaigns')
    deadline = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    rejection_reason = models.CharField(max_length=300, blank=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Campaign.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('campaign_detail', kwargs={'slug': self.slug})

    @property
    def progress_percentage(self):
        if self.goal_amount and self.goal_amount > 0:
            pct = (self.raised_amount / self.goal_amount) * 100
            return min(round(pct, 1), 100)
        return 0

    @property
    def is_expired(self):
        if self.deadline:
            return timezone.now().date() > self.deadline
        return False

    @property
    def donor_count(self):
        return self.donations.count()

    @property
    def is_approved(self):
        return self.status == 'approved'

    @property
    def is_publicly_visible(self):
        return self.status == 'approved' and self.is_active


class Donation(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='donations')
    donor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='donations')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    message = models.CharField(max_length=250, blank=True)
    is_anonymous = models.BooleanField(default=False)
    payment_status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('completed', 'Completed'), ('failed', 'Failed')],
        default='pending',
    )
    # eSewa ePay v2 transaction tracking
    transaction_uuid = models.CharField(max_length=100, unique=True, blank=True, null=True)
    esewa_ref_id = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.donor.username} -> {self.campaign.title} : {self.amount}"
