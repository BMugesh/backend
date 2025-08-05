import os
import requests
import re
import ast
import time
import hashlib
from datetime import datetime, timedelta
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

from flask import Flask, request, jsonify
from flask_cors import CORS
from langdetect import detect

genai.configure(api_key=GEMINI_API_KEY)
# Use faster model configuration for quicker responses
gemini_model = genai.GenerativeModel(
    'gemini-1.5-flash',
    generation_config=genai.types.GenerationConfig(
        temperature=0.7,
        top_p=0.8,
        top_k=40,
        max_output_tokens=1024,  # Limit for faster responses
    )
)

# Simple in-memory cache for faster responses
cache = {}
CACHE_DURATION = 3600  # 1 hour cache

app = Flask(__name__)
CORS(app)

def get_cache_key(text, prefix=""):
    """Generate cache key from text"""
    return f"{prefix}_{hashlib.md5(text.encode()).hexdigest()}"

def get_from_cache(key):
    """Get item from cache if not expired"""
    if key in cache:
        item, timestamp = cache[key]
        if time.time() - timestamp < CACHE_DURATION:
            return item
        else:
            del cache[key]
    return None

def set_cache(key, value):
    """Set item in cache with timestamp"""
    cache[key] = (value, time.time())

def is_healthcare_question(question):
    """Quick check if question is healthcare-related"""
    healthcare_keywords = [
        'health', 'medical', 'symptom', 'disease', 'illness', 'pain', 'fever', 'headache',
        'cough', 'cold', 'flu', 'infection', 'medicine', 'treatment', 'doctor', 'hospital',
        'medication', 'therapy', 'diagnosis', 'wellness', 'fitness', 'nutrition', 'diet',
        'exercise', 'mental health', 'depression', 'anxiety', 'stress', 'sleep', 'fatigue',
        'injury', 'wound', 'bleeding', 'nausea', 'vomiting', 'diarrhea', 'constipation',
        'diabetes', 'hypertension', 'blood pressure', 'heart', 'lung', 'kidney', 'liver',
        'stomach', 'skin', 'allergy', 'asthma', 'cancer', 'pregnancy', 'child', 'elderly',
        'vaccination', 'immunization', 'prevention', 'hygiene', 'sanitation', 'covid',
        'coronavirus', 'vaccine', 'mask', 'sanitizer', 'quarantine', 'isolation'
    ]

    question_lower = question.lower()
    return any(keyword in question_lower for keyword in healthcare_keywords)

def remove_markdown(text):
    text = re.sub(r'\*\*.*?\*\*', '', text)
    text = re.sub(r'[\*\-] ', '', text)
    text = re.sub(r'[#\*_\[\]()]', '', text)
    text = re.sub(r'\n+', '\n', text).strip()
    return text

def format_text(text):
    sections = text.split("\n")
    return "\n\n".join(section.strip() for section in sections if section.strip())

def clean_and_format_response(raw_response):
    if "data=" in raw_response:
        raw_response = raw_response.split("data=")[-1].strip()
    raw_response = raw_response.strip("()'")
    try:
        raw_response = ast.literal_eval(f"'''{raw_response}'''")
    except Exception:
        pass
    match = re.search(r"https?://\S+\nSource:.*?\nDate: .*?\n\n", raw_response, re.DOTALL)
    if match:
        articles_part = raw_response[:match.end()].strip()
        summary_part = raw_response[match.end():].strip()
    else:
        return raw_response.strip()
    formatted_articles = re.sub(r"\n{3,}", "\n\n", articles_part)
    formatted_summary = re.sub(r"\n{3,}", "\n\n", summary_part)
    return f"{formatted_articles}\n\n{'-'*100}\n\n{formatted_summary}"

def get_nearest_health_centers(latitude, longitude):
    lat_offset = 0.09  
    lon_offset = 0.09  
    import math
    lon_offset = 0.09 / math.cos(math.radians(latitude))
    
    # Define bounding box
    south = latitude - lat_offset
    north = latitude + lat_offset
    west = longitude - lon_offset
    east = longitude + lon_offset

    search_queries = [
       
        f"https://nominatim.openstreetmap.org/search?format=json&amenity=hospital&bounded=1&viewbox={west},{north},{east},{south}&limit=10",
        
        f"https://nominatim.openstreetmap.org/search?format=json&amenity=clinic&bounded=1&viewbox={west},{north},{east},{south}&limit=10",
       
        f"https://nominatim.openstreetmap.org/search?format=json&amenity=doctors&bounded=1&viewbox={west},{north},{east},{south}&limit=10",
        
        f"https://nominatim.openstreetmap.org/search?format=json&healthcare=*&bounded=1&viewbox={west},{north},{east},{south}&limit=10",
    ]
    
    headers = {'User-Agent': 'GramAroghya-HealthApp/1.0'}
    all_results = []
    
    for search_url in search_queries:
        try:
            response = requests.get(search_url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                all_results.extend(data)
                # Add small delay to be respectful to the API
                import time
                time.sleep(0.1)
        except Exception as e:
            print(f"Search failed for {search_url}: {e}")
            continue
    
    if not all_results:

        try:
            reverse_url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={latitude}&lon={longitude}&zoom=10"
            reverse_response = requests.get(reverse_url, headers=headers)
            if reverse_response.status_code == 200:
                reverse_data = reverse_response.json()
                country = reverse_data.get("address", {}).get("country", "")
                if country:
                    # Search within the country
                    country_search_url = f"https://nominatim.openstreetmap.org/search?format=json&amenity=hospital&countrycodes={get_country_code(country)}&limit=10"
                    country_response = requests.get(country_search_url, headers=headers)
                    if country_response.status_code == 200:
                        all_results = country_response.json()
        except Exception as e:
            print(f"Country search failed: {e}")
    
    if not all_results:
        return {"error": "No health centers found nearby"}
    
    
    seen_locations = set()
    results = []
    
    for place in all_results:
        location_key = (float(place["lat"]), float(place["lon"]))
        if location_key not in seen_locations:
            seen_locations.add(location_key)
            
            
            distance = calculate_distance(latitude, longitude, float(place["lat"]), float(place["lon"]))
            
            
            if distance <= 50:
                name = place.get("display_name", "Unknown Health Center")
                
                facility_name = name.split(",")[0].strip()
                
                results.append({
                    "name": facility_name,
                    "address": place.get("display_name", "No address available"),
                    "latitude": float(place["lat"]),
                    "longitude": float(place["lon"]),
                    "distance": distance
                })
    
    
    results.sort(key=lambda x: x.get("distance", float('inf')))
    return results[:10]

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points using Haversine formula"""
    import math
    
    
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    
    r = 6371
    return c * r

def get_country_code(country_name):
    """Get ISO country code for common countries"""
    country_codes = {
        "India": "IN",
        "United States": "US", 
        "United Kingdom": "GB",
        "Canada": "CA",
        "Australia": "AU",
        "Germany": "DE",
        "France": "FR",
        "Japan": "JP",
        "China": "CN",
        "Brazil": "BR"
    }
    return country_codes.get(country_name, "IN")  

def get_route(start_lat, start_lon, end_lat, end_lon):
    
    url = f"https://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}?overview=full&geometries=polyline"
    headers = {'User-Agent': 'GramAroghya-HealthApp/1.0'}
    response = requests.get(url, headers=headers)
    data = response.json()
    
    if "routes" not in data or not data["routes"]:
        return {"error": "No route found"}
    
    route = data["routes"][0]
    return {
        "route_polyline": route["geometry"],
        "distance": route.get("distance", 0),
        "duration": route.get("duration", 0)
    }

@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.json
        question = data.get("question", "").strip()
        if not question:
            return jsonify({"error": "No question provided"}), 400

        # Quick healthcare topic validation
        if not is_healthcare_question(question):
            return jsonify({
                "response": "I'm ArogyaMitra, your healthcare AI assistant. I can only help with health and medical-related questions. Please ask me about symptoms, health conditions, medical advice, wellness tips, or any healthcare concerns you may have.",
                "summary": "Please ask healthcare-related questions only."
            })

        # Check cache first for faster responses
        cache_key = get_cache_key(question, "health")
        cached_result = get_from_cache(cache_key)
        if cached_result:
            return jsonify(cached_result)

        # Detect language for response
        try:
            output_language = detect(question)
        except:
            output_language = "en"  # Default to English if detection fails

        # Optimized prompt for faster, focused healthcare responses
        main_prompt = f"""You are ArogyaMitra, a healthcare AI. Provide a quick, focused response in {output_language}.

        Health Query: {question}

        Respond with:
        1. ASSESSMENT: What this likely indicates (1-2 sentences)
        2. IMMEDIATE ACTIONS: What to do now (3 bullet points)
        3. MEDICAL CONSULTATION: When to see a doctor
        4. PREVENTION: Key preventive tip

        Keep concise but helpful. Include disclaimer about consulting healthcare providers."""

        # Generate main response
        main_response = gemini_model.generate_content(main_prompt)
        agent_answer = remove_markdown(main_response.text)
        agent_answer = format_text(agent_answer)

        # Quick summary generation
        summary_prompt = f"""Summarize in {output_language} in 3 points:
        {agent_answer}

        Format:
        1. Likely Issue: [brief]
        2. Action: [key step]
        3. Doctor Visit: [when needed]

        Under 80 words."""

        summary_response = gemini_model.generate_content(summary_prompt)
        summary = remove_markdown(summary_response.text)
        summary = format_text(summary)

        # Cache the result for faster future responses
        result = {"response": agent_answer, "summary": summary}
        set_cache(cache_key, result)

        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/doctors", methods=["POST"])
def find_doctors():
    try:
        data = request.json
        condition = data.get("condition", "")
        location = data.get("location", "")
        if not condition or not location:
            return jsonify({"error": "Condition and location required"}), 400
        
        # Use Gemini for doctor recommendations
        doctor_prompt = f"""Find and recommend doctors for the following:
        Medical Condition: {condition}
        Location: {location}
        
        Please provide a list of doctors with their specialties, clinic names, and contact information if available. 
        Format the response as a structured list with clear information for each doctor."""
        
        doctor_response = gemini_model.generate_content(doctor_prompt)
        doctors_text = remove_markdown(doctor_response.text)
        doctors_formatted = format_text(doctors_text)
        
        return jsonify({"doctors": doctors_formatted})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/health-centers", methods=["POST"])
def find_health_centers():
    try:
        data = request.json
        latitude = data.get("latitude")
        longitude = data.get("longitude")
        if not latitude or not longitude:
            return jsonify({"error": "Latitude and longitude are required"}), 400
        health_centers = get_nearest_health_centers(latitude, longitude)
        if "error" in health_centers:
            return jsonify(health_centers), 400
        if health_centers:
            first_center = health_centers[0]
            route = get_route(latitude, longitude, first_center["latitude"], first_center["longitude"])
            return jsonify({"nearest_health_centers": health_centers, "route": route})
        else:
            return jsonify({"error": "No health centers found nearby"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/news", methods=["POST"])
def get_news():
    try:
        data = request.json
        language = data.get("language", "")
        if not language:
            return jsonify({"error": "Language selection is required"}), 400

        # Check cache first for faster news delivery
        cache_key = get_cache_key(language, "news")
        cached_news = get_from_cache(cache_key)
        if cached_news:
            return jsonify(cached_news)

        # Current date for realistic news
        current_date = datetime.now().strftime("%Y-%m-%d")

        # Optimized healthcare news generation
        news_prompt = f"""Generate 6 current healthcare news articles in {language} for India. Make them realistic and relevant.

        Format EXACTLY:

        Title: [Specific health news title]
        Description: [One line summary]
        Content: [2-3 sentences with key details]
        URL: https://mohfw.gov.in/news/article-{1}
        Source: Ministry of Health & Family Welfare
        Date: {current_date}

        Topics (pick 6):
        1. Winter health precautions and seasonal diseases
        2. Vaccination drive updates (COVID/routine immunization)
        3. Ayushman Bharat scheme expansions
        4. Digital health initiatives and telemedicine
        5. Maternal and child health programs
        6. Non-communicable disease prevention
        7. Mental health awareness campaigns
        8. Nutrition and food safety guidelines
        9. Healthcare infrastructure in rural areas
        10. Disease surveillance and outbreak prevention

        Make content India-specific, actionable, and current."""

        # Generate news with faster model settings
        news_response = gemini_model.generate_content(news_prompt)
        news_text = news_response.text

        # Clean up formatting while preserving structure
        cleaned_news = re.sub(r'\*\*|\*|#{1,6}\s*', '', news_text)
        cleaned_news = re.sub(r'\n{3,}', '\n\n', cleaned_news)
        cleaned_news = cleaned_news.strip()

        # Cache the result for faster future requests
        result = {"news": cleaned_news}
        set_cache(cache_key, result)

        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
