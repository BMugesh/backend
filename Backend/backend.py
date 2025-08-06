import os
import requests
import re
import ast
import time
import hashlib
import feedparser
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import google.generativeai as genai
from urllib.parse import quote

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")  # Optional NewsAPI key

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
NEWS_CACHE_DURATION = 300  # 5 minutes cache for news (for real-time updates)

# Health-related RSS feeds for real-time news
HEALTH_RSS_FEEDS = {
    'English': [
        'https://feeds.feedburner.com/ndtvnews-health',
        'https://timesofindia.indiatimes.com/rssfeeds/3908999.cms',
        'https://www.thehindu.com/sci-tech/health/feeder/default.rss',
        'https://indianexpress.com/section/lifestyle/health/feed/',
    ],
    'Hindi': [
        'https://feeds.feedburner.com/ndtvnews-health',
        'https://navbharattimes.indiatimes.com/rssfeeds/5880659.cms',
    ],
    'Tamil': [
        'https://tamil.thehindu.com/health/feeder/default.rss',
    ],
    'Telugu': [
        'https://telugu.thehindu.com/health/feeder/default.rss',
    ],
    'Gujarati': [
        'https://gujarati.thehindu.com/health/feeder/default.rss',
    ],
    'Bengali': [
        'https://bengali.thehindu.com/health/feeder/default.rss',
    ],
    'Marathi': [
        'https://marathi.thehindu.com/health/feeder/default.rss',
    ]
}

# NewsAPI sources for different languages
NEWS_API_SOURCES = {
    'English': ['bbc-news', 'reuters', 'the-times-of-india', 'the-hindu'],
    'Hindi': ['the-times-of-india'],
    'Tamil': ['the-hindu'],
    'Telugu': ['the-hindu'],
    'Gujarati': ['the-times-of-india'],
    'Bengali': ['the-times-of-india'],
    'Marathi': ['the-times-of-india']
}

app = Flask(__name__)
CORS(app, origins=["*"],  # Allow all origins for production, or specify your Vercel domain
     methods=["GET", "POST", "OPTIONS"], 
     allow_headers=["Content-Type", "Accept", "Authorization"])

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

def fetch_rss_news(language):
    """Fetch real-time news from RSS feeds"""
    feeds = HEALTH_RSS_FEEDS.get(language, HEALTH_RSS_FEEDS.get('English', []))
    all_articles = []
    
    for feed_url in feeds:
        try:
            # Parse RSS feed
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:3]:  # Get top 3 articles from each feed
                # Extract article data
                title = entry.get('title', 'No title')
                description = entry.get('summary', entry.get('description', 'No description'))
                link = entry.get('link', '#')
                published = entry.get('published', datetime.now().strftime('%Y-%m-%d'))
                source = feed.feed.get('title', 'Health News')
                
                # Clean description (remove HTML tags)
                description = re.sub(r'<[^>]+>', '', description)
                description = description.strip()[:200] + '...' if len(description) > 200 else description
                
                all_articles.append({
                    'title': title,
                    'description': description,
                    'content': description,  # Use description as content for RSS
                    'url': link,
                    'source': source,
                    'date': published
                })
                
        except Exception as e:
            print(f"Error fetching RSS feed {feed_url}: {e}")
            continue
    
    return all_articles

def fetch_newsapi_news(language):
    """Fetch news from NewsAPI if API key is available"""
    if not NEWS_API_KEY:
        return []
    
    try:
        # Map language to country code for NewsAPI
        country_map = {
            'English': 'in',
            'Hindi': 'in',
            'Tamil': 'in',
            'Telugu': 'in',
            'Gujarati': 'in',
            'Bengali': 'in',
            'Marathi': 'in'
        }
        
        country = country_map.get(language, 'in')
        
        # NewsAPI endpoint
        url = f"https://newsapi.org/v2/top-headlines"
        params = {
            'apiKey': NEWS_API_KEY,
            'country': country,
            'category': 'health',
            'pageSize': 10
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            articles = []
            
            for article in data.get('articles', [])[:5]:  # Get top 5 articles
                articles.append({
                    'title': article.get('title', 'No title'),
                    'description': article.get('description', 'No description'),
                    'content': article.get('content', article.get('description', 'No content')),
                    'url': article.get('url', '#'),
                    'source': article.get('source', {}).get('name', 'News Source'),
                    'date': article.get('publishedAt', datetime.now().isoformat())
                })
            
            return articles
            
    except Exception as e:
        print(f"Error fetching NewsAPI: {e}")
    
    return []

def format_realtime_news(articles, language):
    """Format real-time news articles into the expected format"""
    if not articles:
        return ""
    
    formatted_news = []
    
    for i, article in enumerate(articles[:6], 1):  # Limit to 6 articles
        formatted_article = f"""Title: {article['title']}
Description: {article['description']}
Content: {article['content']}
URL: {article['url']}
Source: {article['source']}
Date: {article['date']}"""
        
        formatted_news.append(formatted_article)
    
    return "\n\n".join(formatted_news)

def translate_news_if_needed(articles, target_language):
    """Translate news to target language if needed using Gemini"""
    if target_language == 'English' or not articles:
        return articles
    
    try:
        # Prepare articles for translation
        articles_text = ""
        for article in articles[:3]:  # Translate top 3 articles to save API calls
            articles_text += f"Title: {article['title']}\nDescription: {article['description']}\n\n"
        
        # Translation prompt
        translation_prompt = f"""Translate the following health news articles to {target_language}. 
        Keep the same format and structure. Make sure medical terms are accurately translated.
        
        {articles_text}
        
        Provide the translation in the same format:
        Title: [translated title]
        Description: [translated description]
        """
        
        response = gemini_model.generate_content(translation_prompt)
        translated_text = response.text
        
        # Parse translated articles back
        translated_articles = []
        sections = translated_text.split('\n\n')
        
        for i, section in enumerate(sections):
            if 'Title:' in section and i < len(articles):
                lines = section.split('\n')
                title_line = next((line for line in lines if line.startswith('Title:')), '')
                desc_line = next((line for line in lines if line.startswith('Description:')), '')
                
                if title_line and desc_line:
                    translated_articles.append({
                        'title': title_line.replace('Title:', '').strip(),
                        'description': desc_line.replace('Description:', '').strip(),
                        'content': desc_line.replace('Description:', '').strip(),
                        'url': articles[i]['url'],
                        'source': articles[i]['source'],
                        'date': articles[i]['date']
                    })
        
        # Combine translated articles with remaining original articles
        result = translated_articles + articles[len(translated_articles):]
        return result
        
    except Exception as e:
        print(f"Translation error: {e}")
        return articles  # Return original if translation fails

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint to verify the server is running"""
    return jsonify({
        "status": "healthy",
        "message": "GramAroghya Backend is running",
        "timestamp": datetime.now().isoformat(),
        "endpoints": [
            "/ask",
            "/doctors", 
            "/hospitals",
            "/health-centers",
            "/news",
            "/news-realtime"
        ]
    })

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

# Hospital Data with comprehensive information
HOSPITAL_DATABASE = [
    {
        "id": 1,
        "name": "All India Institute of Medical Sciences (AIIMS)",
        "type": "Government Hospital",
        "specialties": ["Cardiology", "Neurology", "Oncology", "General Surgery", "Orthopedics", "Emergency Medicine"],
        "rating": 4.8,
        "phone": "+91-11-2658-8500",
        "availability": "24/7",
        "location": "New Delhi",
        "state": "Delhi",
        "description": "Premier medical institute with advanced healthcare facilities",
        "beds": 2478,
        "established": 1956
    },
    {
        "id": 2,
        "name": "Apollo Hospitals",
        "type": "Private Hospital",
        "specialties": ["Cardiology", "Cardiac Surgery", "Neurology", "Oncology", "Transplant Surgery"],
        "rating": 4.6,
        "phone": "+91-44-2829-3333",
        "availability": "24/7",
        "location": "Chennai",
        "state": "Tamil Nadu",
        "description": "Leading private healthcare provider with advanced medical technology",
        "beds": 550,
        "established": 1983
    },
    {
        "id": 3,
        "name": "Fortis Hospital",
        "type": "Private Hospital",
        "specialties": ["Cardiology", "Neurosurgery", "Orthopedics", "Gastroenterology", "Emergency Medicine"],
        "rating": 4.4,
        "phone": "+91-124-496-2200",
        "availability": "24/7",
        "location": "Gurgaon",
        "state": "Haryana",
        "description": "Multi-specialty hospital with cutting-edge medical facilities",
        "beds": 355,
        "established": 2001
    },
    {
        "id": 4,
        "name": "Manipal Hospital",
        "type": "Private Hospital",
        "specialties": ["Cardiology", "Neurology", "Oncology", "Nephrology", "Orthopedics"],
        "rating": 4.5,
        "phone": "+91-80-2502-4444",
        "availability": "24/7",
        "location": "Bangalore",
        "state": "Karnataka",
        "description": "Comprehensive healthcare with specialized treatment centers",
        "beds": 650,
        "established": 1991
    },
    {
        "id": 5,
        "name": "King George's Medical University",
        "type": "Government Hospital",
        "specialties": ["General Medicine", "Surgery", "Pediatrics", "Obstetrics", "Emergency Medicine"],
        "rating": 4.2,
        "phone": "+91-522-2257-450",
        "availability": "24/7",
        "location": "Lucknow",
        "state": "Uttar Pradesh",
        "description": "Leading medical university hospital with teaching facilities",
        "beds": 1840,
        "established": 1911
    },
    {
        "id": 6,
        "name": "Christian Medical College",
        "type": "Private Hospital",
        "specialties": ["Internal Medicine", "Surgery", "Pediatrics", "Obstetrics", "Emergency Medicine"],
        "rating": 4.7,
        "phone": "+91-416-228-4000",
        "availability": "24/7",
        "location": "Vellore",
        "state": "Tamil Nadu",
        "description": "Renowned medical college hospital with excellent patient care",
        "beds": 2718,
        "established": 1900
    },
    {
        "id": 7,
        "name": "Max Super Specialty Hospital",
        "type": "Private Hospital",
        "specialties": ["Cardiology", "Oncology", "Neurosurgery", "Orthopedics", "Gastroenterology"],
        "rating": 4.3,
        "phone": "+91-11-2651-5050",
        "availability": "24/7",
        "location": "Delhi",
        "state": "Delhi",
        "description": "Advanced super specialty hospital with international standards",
        "beds": 315,
        "established": 2006
    },
    {
        "id": 8,
        "name": "Tata Memorial Hospital",
        "type": "Government Hospital",
        "specialties": ["Oncology", "Radiation Oncology", "Surgical Oncology", "Medical Oncology"],
        "rating": 4.6,
        "phone": "+91-22-2417-7000",
        "availability": "24/7",
        "location": "Mumbai",
        "state": "Maharashtra",
        "description": "Premier cancer treatment and research center",
        "beds": 629,
        "established": 1941
    },
    {
        "id": 9,
        "name": "Sankara Nethralaya",
        "type": "Private Hospital",
        "specialties": ["Ophthalmology", "Retina Surgery", "Corneal Transplant", "Pediatric Ophthalmology"],
        "rating": 4.5,
        "phone": "+91-44-2827-1616",
        "availability": "6 AM - 10 PM",
        "location": "Chennai",
        "state": "Tamil Nadu",
        "description": "Leading eye care hospital with specialized treatments",
        "beds": 100,
        "established": 1978
    },
    {
        "id": 10,
        "name": "Medanta - The Medicity",
        "type": "Private Hospital",
        "specialties": ["Cardiology", "Neurosurgery", "Oncology", "Gastroenterology", "Orthopedics"],
        "rating": 4.4,
        "phone": "+91-124-414-1414",
        "availability": "24/7",
        "location": "Gurgaon",
        "state": "Haryana",
        "description": "Multi-super specialty hospital with advanced medical technology",
        "beds": 1250,
        "established": 2009
    }
]

# Condition to specialty mapping for better hospital matching
CONDITION_SPECIALTY_MAP = {
    "heart": ["Cardiology", "Cardiac Surgery", "Interventional Cardiology"],
    "brain": ["Neurology", "Neurosurgery", "Neuropsychiatry"],
    "cancer": ["Oncology", "Radiation Oncology", "Surgical Oncology", "Medical Oncology"],
    "bone": ["Orthopedics", "Rheumatology", "Sports Medicine"],
    "kidney": ["Nephrology", "Urology", "Renal Transplant"],
    "liver": ["Hepatology", "Gastroenterology", "Liver Transplant"],
    "lung": ["Pulmonology", "Thoracic Surgery", "Respiratory Medicine"],
    "stomach": ["Gastroenterology", "General Surgery", "Digestive Diseases"],
    "skin": ["Dermatology", "Plastic Surgery", "Dermatopathology"],
    "eye": ["Ophthalmology", "Retina Surgery", "Corneal Transplant"],
    "child": ["Pediatrics", "Pediatric Surgery", "Neonatology"],
    "pregnancy": ["Obstetrics", "Gynecology", "Maternal Medicine"],
    "mental": ["Psychiatry", "Psychology", "Mental Health"],
    "emergency": ["Emergency Medicine", "Trauma Surgery", "Critical Care"]
}

def find_hospitals_by_condition_location(condition, location, specialty=None):
    """Find hospitals based on condition, location and specialty"""
    
    # Get relevant specialties for the condition
    condition_lower = condition.lower()
    relevant_specialties = []
    
    for keyword, specialties in CONDITION_SPECIALTY_MAP.items():
        if keyword in condition_lower:
            relevant_specialties.extend(specialties)
    
    # If specialty is specifically mentioned, use it
    if specialty:
        relevant_specialties.append(specialty)
    
    # Filter hospitals
    matching_hospitals = []
    location_lower = location.lower()
    
    for hospital in HOSPITAL_DATABASE:
        # Check location match (city or state)
        location_match = (
            location_lower in hospital["location"].lower() or
            location_lower in hospital["state"].lower() or
            hospital["location"].lower() in location_lower or
            hospital["state"].lower() in location_lower
        )
        
        # Check specialty match
        specialty_match = False
        if relevant_specialties:
            specialty_match = any(
                any(spec.lower() in hospital_spec.lower() for hospital_spec in hospital["specialties"])
                for spec in relevant_specialties
            )
        else:
            specialty_match = True  # If no specific specialty needed, match all
        
        if location_match or specialty_match:
            # Calculate relevance score
            score = 0
            if location_match:
                score += 50
            if specialty_match:
                score += 30
            score += hospital["rating"] * 5  # Rating bonus
            
            hospital_info = hospital.copy()
            hospital_info["relevance_score"] = score
            hospital_info["address"] = f"{hospital['location']}, {hospital['state']}"
            hospital_info["distance"] = f"{round(score/10, 1)} km"  # Mock distance based on relevance
            
            matching_hospitals.append(hospital_info)
    
    # Sort by relevance score
    matching_hospitals.sort(key=lambda x: x["relevance_score"], reverse=True)
    
    # Add suggested specialty info
    suggested_specialty = relevant_specialties[0] if relevant_specialties else None
    
    return {
        "hospitals": matching_hospitals[:6],  # Return top 6 results
        "suggestedSpecialty": suggested_specialty,
        "totalFound": len(matching_hospitals)
    }

@app.route("/hospitals", methods=["POST"])
def find_hospitals():
    """Find hospitals based on condition, location and specialty"""
    try:
        data = request.json
        condition = data.get("condition", "").strip()
        location = data.get("location", "").strip()
        specialty = data.get("specialty", "").strip()
        
        if not location:
            return jsonify({"error": "Location is required"}), 400
        
        # Check cache first
        cache_key = get_cache_key(f"{condition}_{location}_{specialty}", "hospitals")
        cached_result = get_from_cache(cache_key)
        if cached_result:
            return jsonify(cached_result)
        
        # Find hospitals
        result = find_hospitals_by_condition_location(condition, location, specialty)
        
        if not result["hospitals"]:
            # Fallback: return some hospitals for the location
            fallback_hospitals = []
            location_lower = location.lower()
            
            for hospital in HOSPITAL_DATABASE:
                if (location_lower in hospital["location"].lower() or 
                    location_lower in hospital["state"].lower()):
                    hospital_info = hospital.copy()
                    hospital_info["address"] = f"{hospital['location']}, {hospital['state']}"
                    hospital_info["distance"] = f"{round(hospital['rating'] * 2, 1)} km"
                    fallback_hospitals.append(hospital_info)
            
            if fallback_hospitals:
                result = {
                    "hospitals": fallback_hospitals[:3],
                    "suggestedSpecialty": None,
                    "totalFound": len(fallback_hospitals)
                }
            else:
                return jsonify({"error": "No hospitals found in the specified location"}), 404
        
        # Cache the result
        set_cache(cache_key, result)
        
        return jsonify(result)
        
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

@app.route("/news-realtime", methods=["POST"])
def get_realtime_news():
    """Get real-time news from RSS feeds and NewsAPI"""
    try:
        data = request.json
        language = data.get("language", "English")
        
        # Check cache with shorter duration for real-time updates
        cache_key = get_cache_key(language, "realtime_news")
        if cache_key in cache:
            item, timestamp = cache[cache_key]
            if time.time() - timestamp < NEWS_CACHE_DURATION:  # 5 minutes cache
                return jsonify(item)
            else:
                del cache[cache_key]
        
        print(f"Fetching real-time news for language: {language}")
        
        # Fetch from multiple sources
        all_articles = []
        
        # Try RSS feeds first (free and reliable)
        try:
            rss_articles = fetch_rss_news(language)
            all_articles.extend(rss_articles)
            print(f"Fetched {len(rss_articles)} articles from RSS feeds")
        except Exception as e:
            print(f"RSS fetch error: {e}")
        
        # Try NewsAPI if available
        try:
            newsapi_articles = fetch_newsapi_news(language)
            all_articles.extend(newsapi_articles)
            print(f"Fetched {len(newsapi_articles)} articles from NewsAPI")
        except Exception as e:
            print(f"NewsAPI fetch error: {e}")
        
        # If we have articles, process them
        if all_articles:
            # Remove duplicates based on title similarity
            unique_articles = []
            seen_titles = set()
            
            for article in all_articles:
                title_key = article['title'].lower().strip()[:50]  # First 50 chars for similarity
                if title_key not in seen_titles:
                    seen_titles.add(title_key)
                    unique_articles.append(article)
            
            # Limit to 6 articles and sort by date (newest first)
            unique_articles = unique_articles[:6]
            
            # Translate if needed (for non-English languages)
            if language != 'English':
                try:
                    unique_articles = translate_news_if_needed(unique_articles, language)
                except Exception as e:
                    print(f"Translation error: {e}")
            
            # Format the news
            formatted_news = format_realtime_news(unique_articles, language)
            
            result = {
                "news": formatted_news,
                "source": "realtime",
                "articles_count": len(unique_articles),
                "last_updated": datetime.now().isoformat()
            }
            
            # Cache the result
            cache[cache_key] = (result, time.time())
            
            return jsonify(result)
        
        else:
            # Fallback to AI-generated news if no real-time sources available
            print("No real-time articles found, falling back to AI generation")
            
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            fallback_prompt = f"""Generate 4 current healthcare news articles in {language} for India. Make them realistic and relevant to today's date.

            Format EXACTLY:

            Title: [Specific health news title]
            Description: [One line summary]
            Content: [2-3 sentences with key details]
            URL: https://mohfw.gov.in/news/realtime-{1}
            Source: Health News India
            Date: {current_date}

            Focus on current health topics like seasonal health, vaccination updates, health schemes, or medical breakthroughs."""
            
            fallback_response = gemini_model.generate_content(fallback_prompt)
            fallback_news = fallback_response.text
            
            # Clean up formatting
            cleaned_news = re.sub(r'\*\*|\*|#{1,6}\s*', '', fallback_news)
            cleaned_news = re.sub(r'\n{3,}', '\n\n', cleaned_news)
            cleaned_news = cleaned_news.strip()
            
            result = {
                "news": cleaned_news,
                "source": "ai_fallback",
                "articles_count": 4,
                "last_updated": datetime.now().isoformat()
            }
            
            # Cache the fallback result
            cache[cache_key] = (result, time.time())
            
            return jsonify(result)
            
    except Exception as e:
        print(f"Error in get_realtime_news: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
