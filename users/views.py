import json
import os
from io import BytesIO
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.core.mail import send_mail
from elevenlabs.client import ElevenLabs

# Local imports
from .forms import CustomUserCreationForm
from .models import ProfessionalProfile, Booking, Review, JobOpening
from .ai_utils import ask_ai_agent, analyze_job_image


# ==========================================
# CORE PAGES
# ==========================================

def home(request):
    professions = ProfessionalProfile.PROFESSION_CHOICES
    jobs = JobOpening.objects.all().order_by('-created_at')
    return render(request, 'users/category_list.html', {
        'professions': professions,
        'jobs': jobs,
    })

def profession_detail(request, profession_slug):
    # Filter the professionals based on the slug from the URL
    pros = ProfessionalProfile.objects.filter(profession=profession_slug)
    
    # Get the display name (e.g., 'plumber' -> 'Plumber')
    display_name = dict(ProfessionalProfile.PROFESSION_CHOICES).get(profession_slug, profession_slug)
    
    return render(request, 'users/profession_detail.html', {
        'professionals': pros,
        'profession_name': display_name
    })

def professional_detail(request, pro_id):
    """Fallback profile page to satisfy the URL router"""
    pro = get_object_or_404(ProfessionalProfile, id=pro_id)
    return render(request, 'users/profile_detail.html', {'pro': pro})


@login_required
def book_professional(request, pro_id):
    pro = get_object_or_404(ProfessionalProfile, id=pro_id)
    
    if request.method == "POST":
        # ... (keep your existing POST logic here) ...
        request.session['pending_booking'] = {
            'pro_id': pro_id,
            'description': request.POST.get('job_description'),
            'date': request.POST.get('preferred_date'),
            'time_slot': request.POST.get('time_slot'), 
        }
        # Clear the draft now that they have submitted it!
        if 'draft_description' in request.session:
            del request.session['draft_description']
            
        return redirect('checkout') 

    # PASS THE DRAFT TO THE TEMPLATE!
    context = {
        'pro': pro,
        'draft_desc': request.session.get('draft_description', '')
    }
    return render(request, 'users/booking_form.html', context)


@login_required
def checkout(request):
    # Grab the temporary booking data
    pending = request.session.get('pending_booking')
    
    # If they somehow got here without filling out the form, send them home
    if not pending:
        return redirect('home')
        
    pro = get_object_or_404(ProfessionalProfile, id=pending['pro_id'])
    platform_fee = 50 # ₹50 INR platform fee
    
    if request.method == "POST":
        # 1. PROCESS PAYMENT HERE (Simulated for now)
        
        # 2. SAVE THE BOOKING TO THE DATABASE
        booking = Booking.objects.create(
            customer=request.user,
            professional=pro,
            job_description=pending['description'],
            preferred_date=pending['date'],
            preferred_time=pending.get('time') # <--- WE SAVE THE TIME HERE!
        )
        
        # Safely grab the time for the email
        time_str = pending.get('time', 'Not specified')
        
        # 3. NOTIFY THE PROFESSIONAL VIA EMAIL
        send_mail(
            subject=f"New Booking Request: {request.user.username}",
            message=f"Hello {pro.user.username},\n\nYou have a new booking request for {pending['date']} at {time_str}.\n\nClient Needs: {pending['description']}\n\nPlease log in to your LocalLink Dashboard to view their contact info.",
            from_email="notifications@locallink.com",
            recipient_list=[pro.user.email], # Sends to the Pro's email
            fail_silently=False,
        )
        
        # 4. CLEAR THE SESSION AND REDIRECT
        del request.session['pending_booking']
        return redirect('user_dashboard')

    return render(request, 'users/checkout.html', {'pro': pro, 'fee': platform_fee})

# ==========================================
# DASHBOARD & STATUS MANAGEMENT
# ==========================================

@login_required
def user_dashboard(request):
    # 1. Grab ALL bookings where this user is the Customer (Outbound)
    my_outbound_bookings = Booking.objects.filter(customer=request.user).order_by('-id')
    
    # 2. Check if they have a Professional Profile
    pro_profile = ProfessionalProfile.objects.filter(user=request.user).first()
    
    # 3. Grab ALL bookings where this user is the Professional (Incoming)
    my_incoming_jobs = None
    if pro_profile:
        my_incoming_jobs = Booking.objects.filter(professional=pro_profile).order_by('-id')
        
    return render(request, 'users/dashboard.html', {
        'client_bookings': my_outbound_bookings,
        'pro_bookings': my_incoming_jobs,
        'is_pro': bool(pro_profile)
    })


@login_required
def update_booking_status(request, booking_id, new_status):
    # Find the booking
    booking = get_object_or_404(Booking, id=booking_id)
    
    # Check permissions
    is_customer = (booking.customer == request.user)
    is_professional = hasattr(request.user, 'professional_profile') and (booking.professional == request.user.professional_profile)
    
    if request.method == 'POST':
        # Professionals can Accept
        if new_status == 'accepted' and is_professional:
            booking.status = 'accepted'
            booking.save()
            
        # Both can Cancel/Decline (if it's not already completed)
        elif new_status == 'cancelled' and (is_customer or is_professional) and booking.status != 'completed':
            booking.status = 'cancelled'
            booking.save()
            
        # Professionals can mark as Completed
        elif new_status == 'completed' and is_professional:
            booking.status = 'completed'
            booking.save()

    return redirect('user_dashboard')


@login_required
def leave_review(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    
    # Security: Only the client can review, and only IF the job is completed!
    if booking.customer != request.user or booking.status != 'completed':
        return redirect('user_dashboard')
        
    # Prevent them from leaving multiple reviews for the same job
    if hasattr(booking, 'review'):
        return redirect('user_dashboard')
        
    if request.method == 'POST':
        rating = request.POST.get('rating')
        comment = request.POST.get('comment')
        
        Review.objects.create(
            booking=booking,
            rating=int(rating),
            comment=comment
        )
        return redirect('user_dashboard')
        
    return render(request, 'users/leave_review.html', {'booking': booking})


# ==========================================
# AUTHENTICATION
# ==========================================

def signup(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        account_type = request.POST.get('account_type') 
        
        if form.is_valid():
            # 1. Save the new User to the database
            user = form.save()
            
            # 2. If they chose 'professional', create their linked profile
            if account_type == 'professional':
                
                # Safely handle the optional hourly rate
                rate_input = request.POST.get('hourly_rate')
                final_rate = int(rate_input) if rate_input else None

                ProfessionalProfile.objects.create(
                    user=user,
                    phone_number=request.POST.get('phone_number', 'Not Provided'),
                    hourly_rate=final_rate,
                    bio=request.POST.get('bio', 'No bio provided.'),
                    profession=request.POST.get('profession', 'other') 
                )
                
            # 3. Log them in automatically and send them to the homepage
            login(request, user)
            return redirect('home')
    else:
        form = CustomUserCreationForm()
        
    return render(request, 'users/signup.html', {'form': form})


def user_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('user_dashboard')
    else:
        form = AuthenticationForm()
        
    return render(request, 'users/login.html', {'form': form})


def user_logout(request):
    logout(request)
    return redirect('home')


# ==========================================
# AI API
# ==========================================

def ai_chat_api(request):
    if request.method == "POST":
        data = json.loads(request.body)
        user_text = data.get('message', '')
        
        # 1. Grab all professionals
        pros = ProfessionalProfile.objects.all()
        
        # 2. Build the live cheat sheet for the AI
        db_context = "You are the AI assistant for LocalLink. Here are the professionals currently registered:\n"
        
        if not pros.exists():
            db_context += "There are currently NO professionals registered.\n"
        else:
            for pro in pros:
                rate = f"₹{pro.hourly_rate}" if pro.hourly_rate else "Not Set"
                db_context += f"- Name: {pro.user.username}, Trade: {pro.get_profession_display()} (Category Slug: {pro.profession}), Rating: {pro.average_rating}/5, Hourly Rate: {rate}\n"
                
        # 3. Give the AI strict formatting instructions for the button!
        master_prompt = f"""{db_context}
        
        User request: '{user_text}'
        
        Instructions:
        1. Answer the user in a friendly, conversational way.
        2. Do NOT list out every single professional's name, rating, and rate. Instead, summarize (e.g., "We currently have 5 plumbers available on the platform!").
        3. If the user asks for a specific profession, you MUST add this exact HTML code at the very end of your response to create a button:
        <br><br><a href="/category/SLUG/" class="inline-block bg-blue-600 text-white text-sm font-bold py-2 px-4 rounded-lg shadow-sm hover:bg-blue-700 transition" style="text-decoration:none;">View all SLUGs</a>
        
        CRITICAL: Replace the word 'SLUG' in the HTML above with the exact 'Category Slug' from the database list (e.g., 'plumber', 'electrician', 'cleaner').
        """
        
        try:
            ai_reply = ask_ai_agent(master_prompt)
            return JsonResponse({'reply': ai_reply})
        except Exception as e:
            print(f"AI Error: {e}")
            return JsonResponse({'reply': "I apologize, but my AI brain is experiencing unusually high traffic right now! Please wait a few moments and try again."})
        
    return JsonResponse({'error': 'Invalid request method.'}, status=400)


def ai_magic_polish(request):
    if request.method == "POST":
        data = json.loads(request.body)
        raw_text = data.get('text', '')
        
        # Give the AI strict instructions
        prompt = f"Rewrite the following home service job description to be extremely clear, professional, and concise for a contractor to read. Only output the polished text, no conversational filler: '{raw_text}'"
        
        polished_reply = ask_ai_agent(prompt)
        
        return JsonResponse({'polished_text': polished_reply})
    return JsonResponse({'error': 'Invalid request'}, status=400)


def api_analyze_image(request):
    if request.method == "POST" and request.FILES.get('image'):
        image_file = request.FILES['image']
        ai_data = analyze_job_image(image_file)
        
        if ai_data:
            # 1. Save the generated description in their background session
            if 'description' in ai_data:
                request.session['draft_description'] = ai_data['description']
                
            # 2. Tell the frontend where to redirect the user!
            category = ai_data.get('category', 'other')
            return JsonResponse({
                'success': True,
                'redirect_url': f'/category/{category}/'
            })
            
        else:
            return JsonResponse({'error': 'AI could not process the image.'}, status=500)
            
    return JsonResponse({'error': 'Invalid request or missing image.'}, status=400)

# ==========================================
# ELEVENLABS VOICE API (TTS + STT)
# ==========================================

def job_audio_tts(request, job_id):
    job = get_object_or_404(JobOpening, id=job_id)
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        return JsonResponse({"error": "ELEVENLABS_API_KEY missing"}, status=500)

    eleven_client = ElevenLabs(api_key=api_key)
    script = (
        f"Job opening for {job.title} at {job.employer_name} in {job.location_area}. "
        f"Pay is {job.wage}. Tap the green button to apply on WhatsApp."
    )
    audio_stream = eleven_client.text_to_speech.convert(
        text=script,
        voice_id="JBFqnCBsd6RMkjVDRZzb",
        model_id="eleven_v4_turbo",
        output_format="mp3_44100_128",
    )
    return HttpResponse(b"".join(audio_stream), content_type="audio/mpeg")


def voice_job_search(request):
    if request.method == "POST" and request.FILES.get("audio"):
        api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not api_key:
            return JsonResponse({"error": "ELEVENLABS_API_KEY missing"}, status=500)

        eleven_client = ElevenLabs(api_key=api_key)
        transcription = eleven_client.speech_to_text.convert(
            file=BytesIO(request.FILES["audio"].read()),
            model_id="scribe_v3",
            language_code=None,
        )
        return JsonResponse({"transcript": transcription.text})
    return JsonResponse({"error": "No audio uploaded"}, status=400)