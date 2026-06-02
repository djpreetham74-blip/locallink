from django.db import models
from django.contrib.auth.models import AbstractUser

# 1. The Core User Model
class User(AbstractUser):
    is_customer = models.BooleanField(default=False)
    is_professional = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=15, blank=True, null=True)

    def __str__(self):
        return self.username

# 2. Customer Specific Data
class CustomerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
    location_pin = models.CharField(max_length=10, blank=True) # e.g., Hassan pin codes

    def __str__(self):
        return f"Customer: {self.user.username}"

# 3. Professional Specific Data
class ProfessionalProfile(models.Model):
    # The expanded list of professions!
    PROFESSION_CHOICES = [
        ('plumber', 'Plumber'),
        ('electrician', 'Electrician'),
        ('cleaner', 'House Cleaner'),
        ('carpenter', 'Carpenter'),
        ('painter', 'Painter'),
        ('landscaper', 'Landscaper'),
        ('hvac', 'HVAC Technician'),
        ('beautician', 'Beautician / Makeup Artist'),
        ('tailor', 'Tailor / Alterations'),
        ('tutor', 'Academic Tutor'),
        ('photographer', 'Photographer'),
        ('mechanic', 'Auto Mechanic'),
        ('pet_sitter', 'Pet Sitter / Dog Walker'),
        ('trainer', 'Personal Trainer'),
        ('other', 'Other'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='professional_profile')
    bio = models.TextField(blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=15, default="Not Provided")
    hourly_rate = models.IntegerField(null=True, blank=True)
    profession = models.CharField(max_length=50, choices=PROFESSION_CHOICES, default='other')

    def __str__(self):
        return f"{self.user.username} - {self.get_profession_display()}"
        
    @property
    def average_rating(self):
        # Find all reviews linked to jobs this professional has done
        reviews = Review.objects.filter(booking__professional=self)
        if reviews.exists():
            total = sum(review.rating for review in reviews)
            return round(total / reviews.count(), 1)
        return 0.0
    

class Booking(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending (Awaiting Approval)'),
        ('accepted', 'Accepted & Scheduled'),
        ('completed', 'Job Completed'),
        ('cancelled', 'Cancelled/Declined'),
    )
    
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings_made')
    professional = models.ForeignKey(ProfessionalProfile, on_delete=models.CASCADE, related_name='bookings_received')
    job_description = models.TextField()
    preferred_date = models.DateField()
    
    # NEW: The Time Field added here!
    preferred_time = models.TimeField(null=True, blank=True)
    
    # The Status Field
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer.username} booked {self.professional.user.username} ({self.status})"


# NEW: The Review Model
class Review(models.Model):
    # Linking it to the Booking ensures they can only review jobs that actually happened!
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='review')
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)]) # 1 to 5 stars
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.rating} Stars for {self.booking.professional.user.username}"