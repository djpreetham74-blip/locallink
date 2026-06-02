import os
import json
from PIL import Image
from dotenv import load_dotenv
from google import genai
from google.genai import types
from .models import ProfessionalProfile

def get_ai_context():
    # Grab all professionals
    professionals = ProfessionalProfile.objects.all()
    
    # --- THIS IS STEP 2: The Instructions ---
    context_text = (
        "System Instructions: You are a helpful AI assistant for LocalLink. "
        "When a user asks for a specific service, you MUST check the 'Profession' "
        "field first to find a match, and then check their 'Bio' for secondary skills.\n\n"
    )
    
    # --- THIS IS STEP 1: The Database Context ---
    context_text += "Here are the available professionals in the database:\n"
    
    for pro in professionals:
        # We added the get_profession_display() here!
        context_text += f"- Name: {pro.user.username} | Profession: {pro.get_profession_display()} | Rate: ₹{pro.hourly_rate}/hr | Rating: {pro.average_rating} | Bio: {pro.bio}\n"
        
    return context_text

# 1. Load the API key and initialize the modern client
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# 2. THE NATIVE DJANGO FUNCTION
def search_professionals(category_keyword: str) -> str:
    """Searches the database for verified service professionals based on a category or keyword like 'plumber' or 'electrician'."""
    
    pros = ProfessionalProfile.objects.filter(
        is_verified=True, 
        bio__icontains=category_keyword
    )
    
    if not pros.exists():
        return json.dumps({"status": "error", "message": f"No pros found for {category_keyword}."})
    
    # Format the results
    results = []
    for pro in pros:
        results.append({
            "name": pro.user.username,
            "rating": str(pro.average_rating)
        })
    return json.dumps(results)

# 3. THE CHAT FUNCTION
# Make sure your imports are at the top, something like:
# from google import genai
# import os

def ask_ai_agent(prompt):
    try:
        # Your existing AI setup code goes here
        # (Keep whatever you already have for the client and generate_content)
        client = genai.Client() 
        response = client.models.generate_content(
            model='gemini-2.5-flash', # Or whichever model you are using
            contents=prompt
        )
        return response.text
        
    except Exception as e:
        # If Google's servers are busy (or your WiFi drops), do this instead of crashing!
        print(f"AI Error intercepted: {e}")
        return "I apologize, but my AI brain is experiencing unusually high traffic right now! Please wait a few moments and try asking again."


# Add this below your existing ask_ai_agent function
def analyze_job_image(image_file):
    try:
        # 1. Open the uploaded image
        img = Image.open(image_file)
        
        # 2. Tell the AI exactly what we want back (A strict JSON format)
        prompt = """
        You are a home service expert. Look at this image of an issue.
        1. Identify the problem and write a clear, technical 2-3 sentence job description.
        2. Determine which of these specific professional categories is best suited to fix it: 
           [plumber, electrician, cleaner, carpenter, painter, landscaper, hvac, beautician, tailor, tutor, photographer, mechanic, pet_sitter, trainer, other]
        
        Return ONLY a valid JSON object in this exact format, with no extra text:
        {
            "description": "The technical explanation...",
            "category": "plumber"
        }
        """
        
        client = genai.Client() # Uses your existing setup
        response = client.models.generate_content(
            model='gemini-2.5-flash', # Flash is super fast and handles images!
            contents=[prompt, img]
        )
        
        # 3. Clean up the response in case the AI added formatting ticks
        raw_text = response.text.replace('```json', '').replace('```', '').strip()
        
        # 4. Turn the text into a real Python dictionary
        return json.loads(raw_text)
        
    except Exception as e:
        print(f"Vision AI Error: {e}")
        return None