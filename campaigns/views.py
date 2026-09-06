import uuid

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator

from .models import Campaign, Donation, CATEGORY_CHOICES
from .forms import SignUpForm, CampaignForm, DonationForm
from .esewa_utils import build_esewa_payload, decode_esewa_response, verify_esewa_signature, check_esewa_status


def home(request):
    query = request.GET.get('q', '')
    category = request.GET.get('category', '')

    campaigns = Campaign.objects.filter(is_active=True, status='approved')

    if query:
        campaigns = campaigns.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )
    if category:
        campaigns = campaigns.filter(category=category)

    paginator = Paginator(campaigns, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'categories': CATEGORY_CHOICES,
        'query': query,
        'selected_category': category,
        'total_campaigns': Campaign.objects.filter(is_active=True, status='approved').count(),
        'total_raised': sum(c.raised_amount for c in Campaign.objects.filter(status='approved')),
    }
    return render(request, 'campaigns/home.html', context)


def campaign_detail(request, slug):
    campaign = get_object_or_404(Campaign, slug=slug)

    # Only the campaign's own creator or an admin/staff member can view a
    # campaign that hasn't been approved yet — everyone else gets a 404,
    # same as if it didn't exist.
    is_owner_or_staff = request.user.is_authenticated and (request.user == campaign.creator or request.user.is_staff)
    if not campaign.is_publicly_visible and not is_owner_or_staff:
        raise Http404("Campaign not found.")

    donations = campaign.donations.filter(payment_status='completed').select_related('donor')[:10]

    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.error(request, 'Please log in to donate.')
            return redirect('login')

        if campaign.status != 'approved':
            messages.error(request, 'This campaign is not yet approved and cannot accept donations.')
            return redirect('campaign_detail', slug=campaign.slug)

        form = DonationForm(request.POST)
        if form.is_valid():
            donation = form.save(commit=False)
            donation.campaign = campaign
            donation.donor = request.user
            donation.payment_status = 'pending'
            # A unique reference eSewa uses to identify this exact payment.
            donation.transaction_uuid = f"{campaign.slug[:20]}-{uuid.uuid4().hex[:12]}"
            donation.save()

            success_url = request.build_absolute_uri('/payment/esewa/success/')
            failure_url = request.build_absolute_uri('/payment/esewa/failure/')
            esewa_payload = build_esewa_payload(donation, success_url, failure_url)

            # Renders a page that auto-submits a form straight to eSewa's
            # payment page — this is how eSewa's ePay v2 flow works, it is
            # not an API call, it's a real browser form submission.
            return render(request, 'campaigns/esewa_redirect.html', {
                'esewa_payload': esewa_payload,
                'esewa_url': settings.ESEWA_FORM_URL,
            })
    else:
        form = DonationForm()

    context = {
        'campaign': campaign,
        'donations': donations,
        'form': form,
    }
    return render(request, 'campaigns/campaign_detail.html', context)


def esewa_payment_success(request):
    """
    eSewa redirects the user's browser here after a successful payment,
    with a base64-encoded 'data' query parameter.
    """
    encoded_data = request.GET.get('data')
    if not encoded_data:
        messages.error(request, 'Payment response was missing. Please contact support if you were charged.')
        return redirect('home')

    data = decode_esewa_response(encoded_data)
    if not data:
        messages.error(request, "We couldn't read eSewa's response. Please contact support if you were charged.")
        return redirect('home')

    transaction_uuid = data.get('transaction_uuid')
    donation = Donation.objects.filter(transaction_uuid=transaction_uuid).first()
    if not donation:
        messages.error(request, 'No matching donation found for this payment.')
        return redirect('home')

    # 1) Verify the signature eSewa sent actually matches — proves this
    #    response really came from eSewa and wasn't tampered with.
    signature_ok = verify_esewa_signature(data)

    # 2) Never trust the redirect alone — independently ask eSewa's own
    #    status API whether this transaction really completed. This is
    #    the real source of truth (a user could otherwise fake the
    #    browser redirect to this URL without ever paying).
    live_status = check_esewa_status(f"{donation.amount:.2f}", transaction_uuid)

    if signature_ok and data.get('status') == 'COMPLETE' and live_status == 'COMPLETE':
        if donation.payment_status != 'completed':
            donation.payment_status = 'completed'
            donation.esewa_ref_id = data.get('transaction_code', '')
            donation.save()

            donation.campaign.raised_amount += donation.amount
            donation.campaign.save()

        messages.success(
            request,
            f'Payment successful! Thank you for donating Rs. {donation.amount} to "{donation.campaign.title}".'
        )
    else:
        donation.payment_status = 'failed'
        donation.save()
        messages.error(request, 'Payment could not be verified as successful. Please try again.')

    return redirect('campaign_detail', slug=donation.campaign.slug)


def esewa_payment_failure(request):
    """
    eSewa redirects here if the user cancels or the payment fails.
    """
    messages.warning(request, 'Payment was cancelled or failed. You have not been charged.')
    return redirect('home')


@login_required
def create_campaign(request):
    if request.method == 'POST':
        form = CampaignForm(request.POST, request.FILES)
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.creator = request.user
            campaign.status = 'pending'
            campaign.save()
            messages.success(
                request,
                'Your campaign has been submitted for review. '
                'It will go live once an admin approves it — you can track its status on your dashboard.'
            )
            return redirect('dashboard')
    else:
        form = CampaignForm()

    return render(request, 'campaigns/campaign_form.html', {'form': form, 'title': 'Start a Campaign'})


@login_required
def edit_campaign(request, slug):
    campaign = get_object_or_404(Campaign, slug=slug, creator=request.user)

    if request.method == 'POST':
        form = CampaignForm(request.POST, request.FILES, instance=campaign)
        if form.is_valid():
            updated_campaign = form.save(commit=False)
            # If an already-approved campaign is edited, send it back for
            # re-review so an admin can't be bypassed by editing content
            # after approval.
            if campaign.status == 'approved':
                updated_campaign.status = 'pending'
                messages.info(request, 'Your changes were saved and the campaign has been resubmitted for admin review.')
            else:
                messages.success(request, 'Campaign updated.')
            updated_campaign.save()
            return redirect('dashboard')
    else:
        form = CampaignForm(instance=campaign)

    return render(request, 'campaigns/campaign_form.html', {'form': form, 'title': 'Edit Campaign'})


@login_required
def delete_campaign(request, slug):
    campaign = get_object_or_404(Campaign, slug=slug, creator=request.user)
    if request.method == 'POST':
        campaign.delete()
        messages.success(request, 'Campaign deleted.')
        return redirect('dashboard')
    return render(request, 'campaigns/campaign_confirm_delete.html', {'campaign': campaign})


@login_required
def dashboard(request):
    my_campaigns = Campaign.objects.filter(creator=request.user)
    my_donations = Donation.objects.filter(donor=request.user).select_related('campaign')

    context = {
        'my_campaigns': my_campaigns,
        'my_donations': my_donations,
        'total_donated': sum(d.amount for d in my_donations),
        'total_raised_by_me': sum(c.raised_amount for c in my_campaigns),
    }
    return render(request, 'campaigns/dashboard.html', context)

def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)

        if form.is_valid():
            user = form.save()

            # Automatically log the newly registered user in
            login(request, user)

            # Redirect the logged-in user to the home page
            return redirect('home')

    else:
        form = SignUpForm()

    return render(request, 'registration/signup.html', {'form': form})

