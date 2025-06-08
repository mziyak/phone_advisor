import streamlit as st
import pandas as pd
import re
from duckduckgo_search import DDGS

# Page Configuration
# FIX 4: Corrected typo - it should be st.set_page_config, not st.set_set_page_config
st.set_page_config(page_title="Developed by ZIYA", layout="wide")

# ------------------- Load Data -------------------
@st.cache_data
def load_data():
    try:
        # Using a raw string for the path to avoid issues with backslashes
        # IMPORTANT: Ensure this path is correct for your system
        df = pd.read_csv(r"C:\Ziya_workspace\ziya_data_science\Projects\file_cleaned.csv")
        
        # Robust data type conversion for numerical columns
        # 'errors='coerce'' will turn non-convertible values into NaN
        # 'dropna' will remove rows with NaN in these critical columns
        numeric_cols = [
            'launched_price_rs', 'ram_gb', 'storage_gb', 
            'battery_capacity_mah', 'back_camera_mp', 'screen_size_inches'
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Drop rows where critical numeric data couldn't be converted
        df.dropna(subset=numeric_cols, inplace=True)

        # FIX 1: Drop duplicates based on identifying columns to avoid repeated phone listings
        # This assumes that a unique phone is defined by brand, model, RAM, storage, and price.
        # Adjust these columns if a phone can genuinely have multiple entries with slightly different details
        df.drop_duplicates(subset=['brand', 'model', 'ram_gb', 'storage_gb', 'launched_price_rs'], inplace=True)
        
        print(f"Data loaded successfully. Total unique rows: {len(df)}") # DEBUG
        return df
    except FileNotFoundError:
        st.error("Error: 'file_cleaned.csv' not found. Please ensure the file is in the correct directory.")
        st.stop()
    except Exception as e:
        st.error(f"Error loading or processing data: {e}")
        st.stop()

df = load_data()

# ------------------- NLP Query Filters (Enhanced) -------------------
def extract_filters(query):
    filters = {}
    query_lower = query.lower()

    print(f"\n--- Extracting filters for query: '{query}' ---") # DEBUG
    
    # Price extraction - More flexible patterns
    price_match = re.search(r'(?:under|less than|below)\s*₹?\s*(\d+)', query_lower)
    if price_match:
        filters['price_max'] = int(price_match.group(1))
        print(f"  Extracted price_max: {filters['price_max']}") # DEBUG
    
    price_range_match = re.search(r'₹(\d+)\s*(?:to|-)\s*₹?(\d+)', query_lower)
    if price_range_match:
        filters['price_min'] = int(price_range_match.group(1))
        filters['price_max'] = int(price_range_match.group(2))
        print(f"  Extracted price_min: {filters['price_min']}, price_max: {filters['price_max']}") # DEBUG
    elif re.search(r'(?:over|above|more than)\s*₹?\s*(\d+)', query_lower):
        filters['price_min'] = int(re.search(r'(?:over|above|more than)\s*₹?\s*(\d+)', query_lower).group(1))
        print(f"  Extracted price_min: {filters['price_min']}") # DEBUG
    
    around_price_match = re.search(r'(?:around|about)\s*₹?\s*(\d+)', query_lower)
    if around_price_match:
        price = int(around_price_match.group(1))
        filters['price_min'] = price - 2000 if price > 2000 else 0
        filters['price_max'] = price + 2000
        print(f"  Extracted price_min (around): {filters['price_min']}, price_max (around): {filters['price_max']}") # DEBUG

    # RAM extraction - More flexible patterns
    # Prioritize 'ram' keyword if present
    ram_explicit_match = re.search(r'(\d+)\s*gb\s*ram', query_lower)
    if ram_explicit_match:
        filters['ram_min'] = int(ram_explicit_match.group(1))
        print(f"  Extracted ram_min (explicit): {filters['ram_min']}") # DEBUG
    else: # Fallback if 'ram' keyword is not explicit
        # Look for GB not followed by storage/rom
        # This regex tries to avoid capturing storage GB if it's explicitly mentioned with storage/rom
        ram_ambiguous_match = re.search(r'(\d+)\s*gb(?!\s*(?:storage|rom))', query_lower) 
        if ram_ambiguous_match:
            # Simple heuristic: if 'storage' is also present, it's ambiguous.
            # If storage_min is NOT yet set AND no explicit storage keyword
            if 'storage' not in query_lower and 'rom' not in query_lower:
                 filters['ram_min'] = int(ram_ambiguous_match.group(1))
                 print(f"  Extracted ram_min (ambiguous GB): {filters['ram_min']}") # DEBUG
        elif re.search(r'(?:min|at least)\s*(\d+)\s*gb(?:\s*ram)?', query_lower):
            filters['ram_min'] = int(re.search(r'(?:min|at least)\s*(\d+)\s*gb(?:\s*ram)?', query_lower).group(1))
            print(f"  Extracted ram_min (min): {filters['ram_min']}") # DEBUG
    
    # Storage extraction - More flexible patterns
    storage_explicit_match = re.search(r'(\d+)\s*gb(?:\s*storage|\s*rom)', query_lower)
    if storage_explicit_match:
        filters['storage_min'] = int(storage_explicit_match.group(1))
        print(f"  Extracted storage_min (explicit): {filters['storage_min']}") # DEBUG
    else: # Fallback if 'storage' or 'rom' keyword is not explicit
        # If no RAM extracted, and a general 'GB' is mentioned, assume it might be storage.
        # This is a weak heuristic and might need fine-tuning based on typical queries.
        if 'ram_min' not in filters: 
            storage_ambiguous_match = re.search(r'(\d+)\s*gb', query_lower)
            if storage_ambiguous_match:
                filters['storage_min'] = int(storage_ambiguous_match.group(1))
                print(f"  Extracted storage_min (ambiguous GB): {filters['storage_min']}") # DEBUG
        elif re.search(r'(?:min|at least)\s*(\d+)\s*gb(?:\s*storage|\s*rom)?', query_lower):
            filters['storage_min'] = int(re.search(r'(?:min|at least)\s*(\d+)\s*gb(?:\s*storage|\s*rom)?', query_lower).group(1))
            print(f"  Extracted storage_min (min): {filters['storage_min']}") # DEBUG

    # Battery Capacity Extraction 
    battery_match = re.search(r'(\d+)\s*mah(?:\s*battery)?', query_lower)
    if battery_match:
        filters['battery_capacity_mah'] = int(battery_match.group(1))
        print(f"  Extracted battery_capacity_mah: {filters['battery_capacity_mah']}") # DEBUG

    # Keyword extraction (more comprehensive)
    if any(k in query_lower for k in ["gaming", "game", "performance", "powerful"]):
        filters['keyword_gaming'] = True
    if any(k in query_lower for k in ["camera", "photo", "photography", "photos", "megapixel", "mp"]):
        filters['keyword_camera'] = True
    if any(k in query_lower for k in ["budget", "cheap", "affordable", "low cost"]):
        filters['keyword_budget'] = True
    if any(k in query_lower for k in ["battery", "long lasting", "endurance"]):
        filters['keyword_battery'] = True 
    if any(k in query_lower for k in ["display", "screen", "amoled", "oled", "fluid", "hz"]):
        filters['keyword_display'] = True
    if any(k in query_lower for k in ["fast charging", "quick charge"]):
        filters['keyword_fast_charging'] = True
    if any(k in query_lower for k in ["compact", "small"]):
        filters['keyword_compact'] = True 
    if any(k in query_lower for k in ["premium", "flagship"]):
        filters['keyword_premium'] = True

    # Brand extraction (improved, handle common variations)
    # Ensure brands list is unique and lowercased for efficient checking
    unique_brands_lower = [brand.lower() for brand in df['brand'].dropna().unique().tolist()]
    for brand in unique_brands_lower:
        if brand in query_lower or \
           (brand == "samsung" and "galaxy" in query_lower) or \
           (brand == "apple" and "iphone" in query_lower) or \
           (brand == "xiaomi" and "redmi" in query_lower) or \
           (brand == "oneplus" and "nord" in query_lower): 
            filters['brand'] = brand.capitalize() # Store capitalized brand
            print(f"  Extracted brand: {filters['brand']}") # DEBUG
            break

    print(f"  Final extracted filters: {filters}") # DEBUG
    return filters

def filter_data(df, filters):
    filtered_df = df.copy() 
    print(f"\n--- Filtering data with filters: {filters} ---") # DEBUG
    print(f"  Initial DataFrame size: {len(filtered_df)}") # DEBUG
    
    if 'price_max' in filters:
        initial_size = len(filtered_df) # DEBUG
        filtered_df = filtered_df[filtered_df['launched_price_rs'] <= filters['price_max']]
        print(f"  After price_max ({filters['price_max']}): {len(filtered_df)} rows (from {initial_size})") # DEBUG
    if 'price_min' in filters:
        initial_size = len(filtered_df) # DEBUG
        filtered_df = filtered_df[filtered_df['launched_price_rs'] >= filters['price_min']]
        print(f"  After price_min ({filters['price_min']}): {len(filtered_df)} rows (from {initial_size})") # DEBUG
    if 'ram_min' in filters:
        initial_size = len(filtered_df) # DEBUG
        filtered_df = filtered_df[filtered_df['ram_gb'] >= filters['ram_min']]
        print(f"  After ram_min ({filters['ram_min']}): {len(filtered_df)} rows (from {initial_size})") # DEBUG
    if 'storage_min' in filters:
        initial_size = len(filtered_df) # DEBUG
        filtered_df = filtered_df[filtered_df['storage_gb'] >= filters['storage_min']]
        print(f"  After storage_min ({filters['storage_min']}): {len(filtered_df)} rows (from {initial_size})") # DEBUG
    if 'brand' in filters:
        initial_size = len(filtered_df) # DEBUG
        filtered_df = filtered_df[filtered_df['brand'].str.lower() == filters['brand'].lower()]
        print(f"  After brand ({filters['brand']}): {len(filtered_df)} rows (from {initial_size})") # DEBUG

    # Apply Battery Capacity filter 
    if 'battery_capacity_mah' in filters:
        initial_size = len(filtered_df) # DEBUG
        filtered_df = filtered_df[filtered_df['battery_capacity_mah'] >= filters['battery_capacity_mah']] 
        print(f"  After battery_capacity_mah ({filters['battery_capacity_mah']}): {len(filtered_df)} rows (from {initial_size})") # DEBUG

    # Apply keyword-based filtering (example logic - tailor to your data)
    if 'keyword_gaming' in filters and filters['keyword_gaming']:
        initial_size = len(filtered_df) # DEBUG
        filtered_df = filtered_df[(filtered_df['ram_gb'] >= 6) & (filtered_df['Processor'].fillna('').str.contains('Snapdragon|Dimensity|Gaming', case=False, na=False))]
        print(f"  After keyword_gaming: {len(filtered_df)} rows (from {initial_size})") # DEBUG
    if 'keyword_camera' in filters and filters['keyword_camera']:
        initial_size = len(filtered_df) # DEBUG
        filtered_df = filtered_df[filtered_df['back_camera_mp'] >= 48]
        print(f"  After keyword_camera: {len(filtered_df)} rows (from {initial_size})") # DEBUG
    if 'keyword_budget' in filters and filters['keyword_budget']:
        initial_size = len(filtered_df) # DEBUG
        filtered_df = filtered_df.sort_values(by='launched_price_rs', ascending=True)
        if 'price_max' not in filters and 'price_min' not in filters: # If budget is primary, suggest a common budget range
             filtered_df = filtered_df[filtered_df['launched_price_rs'] <= 15000] # Default budget
        print(f"  After keyword_budget: {len(filtered_df)} rows (from {initial_size})") # DEBUG
    if 'keyword_battery' in filters and filters['keyword_battery']:
        initial_size = len(filtered_df) # DEBUG
        # This is a keyword filter, could apply a different battery threshold than numerical one
        if 'battery_capacity_mah' not in filters: # Only apply if not already numerically filtered
            filtered_df = filtered_df[filtered_df['battery_capacity_mah'] >= 4500] 
        print(f"  After keyword_battery: {len(filtered_df)} rows (from {initial_size})") # DEBUG
    if 'keyword_display' in filters and filters['keyword_display']:
        initial_size = len(filtered_df) # DEBUG
        filtered_df = filtered_df[filtered_df['screen_size_inches'] >= 6.0] 
        print(f"  After keyword_display: {len(filtered_df)} rows (from {initial_size})") # DEBUG
    if 'keyword_compact' in filters and filters['keyword_compact']:
        initial_size = len(filtered_df) # DEBUG
        filtered_df = filtered_df[filtered_df['screen_size_inches'] <= 6.0]
        print(f"  After keyword_compact: {len(filtered_df)} rows (from {initial_size})") # DEBUG
    if 'keyword_premium' in filters and filters['keyword_premium']:
        initial_size = len(filtered_df) # DEBUG
        # Filter for higher price range or specific flagship processors
        filtered_df = filtered_df[filtered_df['launched_price_rs'] >= 50000]
        print(f"  After keyword_premium: {len(filtered_df)} rows (from {initial_size})") # DEBUG

    print(f"  Final filtered DataFrame size: {len(filtered_df)}") # DEBUG
    return filtered_df

# ------------------- Image Fetch -------------------
@st.cache_data(ttl=3600)
def fetch_image_url(name):
    try:
        with DDGS() as ddgs:
            results = ddgs.images(f"{name} phone gsmarena", max_results=1)
            if results:
                return results[0]['image']
    except Exception as e:
        print(f"Error fetching image for {name}: {e}") # DEBUG
        pass
    return "https://placehold.co/200x200/000000/FFFFFF?text=No+Image"

# ------------------- Styling -------------------
st.markdown("""
<style>
/* General Body and Text Styling */
html, body {
    background-color: #0d1117; /* Dark background */
    color: #ffffff;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    margin: 0; /* Remove default body margin */
    padding: 0;
    height: 100%; /* Ensure body takes full height */
    overflow-x: hidden; /* Prevent horizontal scroll */
}

/* Streamlit Main App Container */
.stApp {
    background-color: #0d1117; /* Ensure main app container matches body */
    min-height: 100vh; /* Make app take full viewport height */
    display: flex;
    flex-direction: column; /* Allow content to flow vertically */
}

/* Header (removed Streamlit's default top header for a cleaner look) */
header {
    visibility: hidden;
    height: 0px !important;
}
/* This class targets a specific Streamlit header div - might change in future versions */
.st-emotion-cache-z5fcl4 { 
    visibility: hidden;
    height: 0px !important;
}

/* Custom Welcome Message Styling (like Gemini) */
.welcome-text {
    font-size: 4.5em; /* Large font size */
    font-weight: 600;
    text-align: center;
    padding-top: 15vh; /* Push down from top for vertical centering effect */
    margin-bottom: 20px;
    /* Gradient text color */
    background: linear-gradient(to right, #6A5ACD, #DC143C, #FFD700); /* Purple, Red, Gold */
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    color: #00ffff; /* Fallback for browsers that don't support text-fill-color */
}

/* Prompt Text Styling (like 'Ask Gemini') */
.prompt-text {
    font-size: 1.5em;
    color: #b0b0b0; /* Lighter grey */
    text-align: center;
    margin-bottom: 30px;
}

/* Streamlit Input Widget Styling (Search Bar) - Enhanced for wide, centered look */
.stTextInput {
    width: 100%;
    display: flex;
    justify-content: center;
    align-items: center;
    margin-bottom: 20px;
}

.stTextInput > div { /* Target the inner div that wraps the input */
    width: 100%;
    max-width: 700px;
    margin: 0 auto;
}

.stTextInput input {
    height: 4em;
    font-size: 1.5em;
    color: #DC143C;
    background-color: #1a1a1a;
    padding: 0 25px;
    box-shadow: none;
    transition: all 0.3s ease-in-out;
    width: 100%;
    box-sizing: border-box;
}

.stTextInput input:focus {
    box-shadow: none;
    border-color: #FFD700;
    outline: none;
}

/* Streamlit Button Styling */
.stButton > button {
    background-color: #DC143C; /* Button color set to Crimson Red */
    color: white; /* Changed text color for better contrast */
    font-size: 1.3em; /* Slightly larger font */
    border-radius: 15px; /* More rounded */
    border: none;
    padding: 15px 30px; /* More padding */
    margin-top: 30px; /* Add some space above the button */
    box-shadow: 0 8px 16px rgba(220, 20, 60, 0.4); /* Adjusted shadow to match new button color */
    transition: 0.3s ease;
    cursor: pointer;
    width: 60%; /* Adjust button width */
    max-width: 250px; /* Max width for button */
    display: block; /* Ensure it's a block element */
    margin-left: auto; /* Center button */
    margin-right: auto; /* Center button */
}

.stButton > button:hover {
    background-color: #B21230; /* Darker red on hover */
    transform: scale(1.05); /* More pronounced zoom effect */
    box-shadow: 0 10px 20px rgba(220, 20, 60, 0.6); /* Adjusted shadow on hover */
}

/* Results Header Styling */
h3 {
    color: #FFD700; /* Header color set to Gold from gradient */
    text-align: center;
    margin-top: 40px;
    margin-bottom: 20px;
    font-size: 2em;
}

/* Success and Warning Messages */
.stSuccess {
    background-color: #004d40;
    color: #ccffee;
    border-radius: 8px;
    padding: 10px;
    margin-top: 15px;
    margin-bottom: 15px;
    text-align: center;
}

.stWarning {
    background-color: #663300;
    color: #ffe0b2;
    border-radius: 8px;
    padding: 10px;
    margin-top: 15px;
    margin-bottom: 15px;
    text-align: center;
}

/* Result Card Styling */
.result-card {
    background-color: #1e1e1e;
    border: 1px solid #DC143C; /* Changed border color to Crimson Red */
    border-radius: 12px;
    padding: 20px;
    color: #f0f0f0;
    text-align: center;
    transition: all 0.3s ease;
    box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    margin-bottom: 20px;
    min-height: 480px; /* Increased height for more consistent display and image */
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    align-items: center;
}
.result-card:hover {
    transform: translateY(-8px);
    box-shadow: 0 8px 20px rgba(220, 20, 60, 0.3); /* Adjusted shadow to match new border color */
}

.result-card h4 {
    color: #FFD700; /* Changed title color to Gold for better readability against red border */
    margin-top: 10px;
    margin-bottom: 15px;
    font-size: 1.3em;
    min-height: 3em; /* Ensure consistent height for titles */
    display: flex;
    align-items: center;
    justify-content: center;
    text-shadow: none;
}

.result-card span {
    display: block;
    margin-bottom: 5px;
    font-size: 0.95em;
    color: #cccccc;
    text-align: left;
    width: 100%;
    padding-left: 5px;
}

/* Image Styling within cards */
.phone-image-container {
    height: 180px; /* Fixed height for image container */
    display: flex;
    justify-content: center;
    align-items: center;
    margin-bottom: 15px;
    width: 100%;
}
.phone-image-container img {
    border-radius: 8px;
    border: 1px solid #DC143C; /* Changed border color to Crimson Red */
    box-shadow: 0 2px 8px rgba(220, 20, 60, 0.2); /* Adjusted shadow to match new border color */
    object-fit: contain;
    max-height: 180px;
    width: auto;
}

/* Expander for table */
.streamlit-expanderHeader {
    background-color: #1a1a1a;
    color: #DC143C !important; /* Changed to Crimson Red */
    border-radius: 8px;
    padding: 10px 15px;
    margin-top: 20px;
    margin-bottom: 10px;
    border: 1px solid #DC143C; /* Changed border to Crimson Red */
    cursor: pointer;
    text-shadow: none;
}
.streamlit-expanderContent {
    background-color: #1a1a1a;
    border: 1px solid #DC143C; /* Changed border to Crimson Red */
    border-top: none;
    border-radius: 0 0 8px 8px;
    padding: 15px;
}

/* Streamlit Column Gaps - Target relevant classes for proper spacing */
.st-emotion-cache-nahz7x, .st-emotion-cache-1g83gq, .st-emotion-cache-uf99v8, .st-emotion-cache-1r6psv0 {
    gap: 1rem; /* Space between columns */
}

/* Chat Message Styling */
.stChatMessage {
    background-color: #1a1a1a; /* Darker background for chat messages */
    border-radius: 10px;
    padding: 10px 15px;
    margin-bottom: 10px;
}

.stChatMessage.st-user {
    background-color: #282828; /* Slightly different for user messages */
    border-left: 3px solid #DC143C; /* Crimson Red bar on user messages */
}

.stChatMessage.st-assistant {
    background-color: #1a1a1a;
    border-right: 3px solid #6A5ACD; /* Purple bar on assistant messages */
}

/* --- NEW CSS for Chat Input and Fixed Home Button --- */

/* Fixed Back to Home Button at bottom right of the viewport */
.fixed-bottom-right-home {
    position: fixed;
    bottom: 20px; /* Distance from bottom */
    right: 20px;  /* Distance from right */
    z-index: 1000; /* Ensure it's on top of other content */
}

.fixed-bottom-right-home .stButton > button {
    margin: 0; /* Remove auto margins */
    width: auto; /* Allow button to size itself */
    max-width: none; /* No max-width restriction */
    padding: 10px 20px; /* Adjust padding */
    font-size: 1.1em; /* Adjust font size */
    box-shadow: 0 5px 15px rgba(220, 20, 60, 0.4); /* Smaller shadow */
}
.fixed-bottom-right-home .stButton > button:hover {
    transform: scale(1.03); /* Slightly less pronounced hover for small button */
    box-shadow: 0 7px 18px rgba(220, 20, 60, 0.6); /* Corrected typo for box-shadow */
}


/* Chat input and buttons container - make it sticky to bottom of scrollable chat history */
/* This container is placed *below* the chat history and will stick to the bottom of the *viewport* */
/* This requires careful tuning with Streamlit's internal divs */
.chat-input-sticky-container {
    position: fixed; /* Changed from sticky to fixed for consistent bottom placement */
    bottom: 0; /* Stick to the very bottom of the viewport */
    left: 0;
    right: 0;
    background-color: #0d1117; /* Match background */
    padding: 15px 20px; /* Padding for visual separation */
    border-top: 1px solid #333; /* A subtle separator */
    z-index: 950; /* Below the fixed home button but above chat history */
    display: flex;
    flex-direction: column;
    align-items: center; /* Center content horizontally */
    box-shadow: 0 -5px 15px rgba(0,0,0,0.3); /* Add a shadow at the top */
}

/* Adjust the chat input itself within the sticky container */
.chat-input-sticky-container .stTextInput {
    width: 100%;
    max-width: 700px; /* Max width for input */
    margin-bottom: 10px; /* Space between input and button */
}
.chat-input-sticky-container .stTextInput > div {
    margin: 0 auto; /* Center the input within its full width parent */
}

/* Adjust the "Reset Chat and Search" button within the sticky container */
.chat-input-sticky-container .stButton > button {
    margin-top: 0px; /* No top margin as it's controlled by container padding */
    margin-bottom: 0; /* No bottom margin */
    width: 250px; /* Fixed width for the button */
    max-width: none; /* No max-width restriction */
    padding: 10px 20px;
    font-size: 1.1em;
    box-shadow: 0 5px 15px rgba(220, 20, 60, 0.4);
}

.chat-input-sticky-container .stButton > button:hover {
    transform: scale(1.03);
    box-shadow: 0 7px 18px rgba(220, 20, 60, 0.6); /* Corrected typo for box-shadow */
}

/* Ensure the main content area (where chat messages appear) has enough padding at the bottom
   so fixed elements don't overlap with the last chat message. */
.main .block-container {
    padding-bottom: 150px; /* Increased padding to make space for fixed chat input/buttons */
    flex-grow: 1; /* Allow it to take up available vertical space */
}

/* Target Streamlit's chat message container to enable its own scrolling */
/* This class might change with Streamlit updates! You may need to inspect the HTML. */
/* Using a more general approach targeting what *contains* the messages */
/* This is a common class for the overall app content wrapper */
.st-emotion-cache-1y4y1k7 { /* Example: adjust this class based on your deployed app's HTML */
    overflow-y: auto; /* Enable vertical scrolling */
    max-height: calc(100vh - 250px); /* Adjust based on header, fixed footer height, etc. */
    padding-bottom: 20px; /* Ensure space at the bottom of the scrollable area */
}
/* Another common container class that might wrap chat messages */
.st-emotion-cache-h5rb8w { /* This is often the div that contains the actual message blocks */
    overflow-y: auto;
    max-height: calc(100vh - 250px); /* Adjust to leave space for input/buttons */
    padding-bottom: 20px;
}
/* Specific class for the chat messages container itself */
.chat-messages-display {
    overflow-y: auto;
    flex-grow: 1; /* Allows it to take up available space and scroll */
    max-height: calc(100vh - 250px); /* Adjust this value. It should be (viewport height - height of fixed header - height of fixed chat input area) */
    padding-bottom: 20px; /* Padding inside the scrollable area */
}


</style>
""", unsafe_allow_html=True)

# ------------------- Session State -------------------
if 'query' not in st.session_state:
    st.session_state.query = ""
if 'filtered_df' not in st.session_state:
    st.session_state.filtered_df = pd.DataFrame()
if 'show_results' not in st.session_state:
    st.session_state.show_results = False
if 'messages' not in st.session_state:
    st.session_state.messages = [] # Stores chat history
if 'current_filters' not in st.session_state:
    st.session_state.current_filters = {} # Stores extracted filters for multi-turn
if 'mode' not in st.session_state:
    st.session_state.mode = None # 'chat' or 'direct_search'
if 'show_results_display' not in st.session_state:
    st.session_state.show_results_display = False # Controls visibility of phone cards
if 'awaiting_confirmation' not in st.session_state:
    st.session_state.awaiting_confirmation = False # To manage confirmation dialogue

# ------------------- Conversational Logic (Rule-Based) -------------------
def get_chatbot_response(user_message, current_filters):
    response = ""
    trigger_search = False
    user_message_lower = user_message.lower()

    # Step 1: Extract new filters from the current user message
    extracted_new_filters = extract_filters(user_message)
    
    # Check for direct search commands or explicit confirmation/denial
    if st.session_state.awaiting_confirmation:
        if any(keyword in user_message_lower for keyword in ["yes", "yep", "confirm", "ok", "go ahead", "search", "find", "show me"]):
            trigger_search = True
            st.session_state.awaiting_confirmation = False # Reset confirmation flag
            # FIX 5: If confirmed, explicitly remove the last assistant confirmation message to avoid repetition
            if st.session_state.messages and st.session_state.messages[-1]["role"] == "assistant" and "Does that sound right? Shall I search now" in st.session_state.messages[-1]["content"]:
                st.session_state.messages.pop() 
        elif any(keyword in user_message_lower for keyword in ["no", "nope", "cancel", "change", "not"]):
            st.session_state.awaiting_confirmation = False
            # Clear previous confirmation prompt from chat history
            if st.session_state.messages and st.session_state.messages[-1]["role"] == "assistant" and "Does that sound right? Shall I search now" in st.session_state.messages[-1]["content"]:
                st.session_state.messages.pop() 
            response = "No problem. What changes would you like to make, or what else are you looking for?"
            # Do NOT return here. Continue to process new filters if any were in the "no" message
        else:
            # If awaiting confirmation but user didn't confirm/deny clearly, try to parse new filters
            # and potentially re-ask for confirmation if no new clear instruction
            pass

    # Step 2: Update current_filters with newly extracted ones
    # New filters from the current turn override or add to existing ones
    # Only update if the user didn't explicitly deny/cancel without new info.
    if extracted_new_filters:
        current_filters.update(extracted_new_filters)

    # Step 3: Check for explicit search commands (always allow direct search trigger if filters exist)
    # This block should be checked AFTER processing confirmation and filter updates
    if not trigger_search and any(phrase in user_message_lower for phrase in ["search", "find phones", "show me", "go", "results", "ok search", "what do you have"]):
        if current_filters:
            trigger_search = True
            st.session_state.awaiting_confirmation = False # A direct search command overrides pending confirmation
        else:
            response = "I need some criteria (like price, RAM, or use case) before I can search for phones. What are you looking for?"
            return response, current_filters, trigger_search

    # If search was already triggered or the user explicitly confirmed, provide the search message
    if trigger_search:
        filter_summary_parts = []
        if 'brand' in current_filters: filter_summary_parts.append(f"a {current_filters['brand']} phone")
        if 'price_min' in current_filters and 'price_max' in current_filters:
            if current_filters['price_min'] == current_filters['price_max']:
                filter_summary_parts.append(f"around ₹{current_filters['price_min']}")
            else:
                filter_summary_parts.append(f"between ₹{current_filters['price_min']} and ₹{current_filters['price_max']}")
        elif 'price_max' in current_filters: filter_summary_parts.append(f"under ₹{current_filters['price_max']}")
        elif 'price_min' in current_filters: filter_summary_parts.append(f"over ₹{current_filters['price_min']}")
        
        if 'ram_min' in current_filters: filter_summary_parts.append(f"with at least {current_filters['ram_min']}GB RAM")
        if 'storage_min' in current_filters: filter_summary_parts.append(f"with at least {current_filters['storage_min']}GB storage")
        if 'battery_capacity_mah' in current_filters: filter_summary_parts.append(f"with at least {current_filters['battery_capacity_mah']} mAh battery")
        
        if 'keyword_gaming' in current_filters: filter_summary_parts.append("for gaming")
        if 'keyword_camera' in current_filters: filter_summary_parts.append("with a good camera")
        if 'keyword_battery' in current_filters and 'battery_capacity_mah' not in current_filters: # Only add if numeric battery wasn't captured
            filter_summary_parts.append("with long battery life")
        if 'keyword_display' in current_filters: filter_summary_parts.append("with a great display")
        if 'keyword_compact' in current_filters: filter_summary_parts.append("a compact size")
        if 'keyword_premium' in current_filters: filter_summary_parts.append("a premium/flagship model")

        if filter_summary_parts:
            response = f"Understood! Searching for {', '.join(filter_summary_parts)} now..."
        else:
            response = "Understood! Searching for phones based on what we've discussed."
        return response, current_filters, trigger_search

    # Step 4: Dialogue Management - Determine the next appropriate response
    # This logic only runs if a search was NOT triggered by confirmation or explicit command
    
    # Prioritize greetings
    if not response and any(greeting in user_message_lower for greeting in ["hi", "hello", "hey", "hii", "holla"]):
        response = "Hello! I'm your Phone Advisor. How can I assist you today? Tell me what kind of phone you are looking for. For example: 'I need a phone under ₹20000 with a good camera'."
    elif not response and ("thank you" in user_message_lower or "thanks" in user_message_lower):
        response = "You're most welcome! Happy to assist. Is there anything else you'd like to refine or search for?"
    elif not response and ("help" in user_message_lower or "what can you do" in user_message_lower):
        response = "I can help you find phones based on your preferences. You can ask for a phone 'under ₹25000', with '8GB RAM', for 'gaming', with 'good camera', or specific brands like 'Samsung'. Just tell me what you're looking for!"
    elif not response and not current_filters: # If no filters gathered yet
        response = "To help you better, please tell me what kind of phone you are looking for. For example, 'a phone under ₹15000' or 'a gaming phone with good battery'."
    elif not response: # If we have some filters but no search triggered yet and no specific greeting/thanks
        # Build a summary of current preferences
        summary = []
        if 'brand' in current_filters: summary.append(f"a {current_filters['brand']} phone")
        if 'price_min' in current_filters and 'price_max' in current_filters:
            if current_filters['price_min'] == current_filters['price_max']:
                summary.append(f"around ₹{current_filters['price_min']}")
            else:
                summary.append(f"between ₹{current_filters['price_min']} and ₹{current_filters['price_max']}")
        elif 'price_max' in current_filters: summary.append(f"under ₹{current_filters['price_max']}")
        elif 'price_min' in current_filters: summary.append(f"over ₹{current_filters['price_min']}")
        
        if 'ram_min' in current_filters: summary.append(f"with at least {current_filters['ram_min']}GB RAM")
        if 'storage_min' in current_filters: summary.append(f"with at least {current_filters['storage_min']}GB storage")
        if 'battery_capacity_mah' in current_filters: summary.append(f"with at least {current_filters['battery_capacity_mah']} mAh battery")
        
        # Add keywords
        if 'keyword_gaming' in current_filters: summary.append("for gaming")
        if 'keyword_camera' in current_filters: summary.append("with a good camera")
        if 'keyword_battery' in current_filters and 'battery_capacity_mah' not in current_filters: # Only add if numeric battery wasn't captured
            summary.append("with long battery life")
        if 'keyword_display' in current_filters: summary.append("with a great display")
        if 'keyword_compact' in current_filters: summary.append("a compact size")
        if 'keyword_premium' in current_filters: summary.append("a premium/flagship model")

        # Determine next question based on missing critical filters
        if 'price_max' not in current_filters and 'price_min' not in current_filters:
            response = "What's your budget for the phone?"
        elif 'ram_min' not in current_filters:
            response = "And how much RAM are you looking for? (e.g., '8GB RAM')"
        elif 'storage_min' not in current_filters:
            response = "What about storage? How much internal storage do you need? (e.g., '128GB storage')"
        elif 'battery_capacity_mah' not in current_filters and 'keyword_battery' not in current_filters:
            response = "How about battery life? Do you need a minimum battery capacity (e.g., '5000 mAh')?"
        elif 'brand' not in current_filters and len(summary) < 3: # If not enough details yet
            response = "Do you have a preferred brand, or any specific features like camera or display you prioritize?"
        else: # If we have collected sufficient filters, ask for confirmation to search
            if summary:
                response = f"So far, you're looking for {', '.join(summary)}. Does that sound right? Shall I search now or do you have more details?"
            else: # Fallback if summary is empty but filters exist (e.g. only a hidden keyword)
                response = "Okay, I've noted your preferences. Shall I search for phones based on these criteria now, or do you have more details to add?"
            st.session_state.awaiting_confirmation = True # Set flag to await confirmation
            
    # Default fallback if no specific response was generated (should ideally not happen with good logic)
    if not response:
        response = "I'm still learning! Could you please rephrase or tell me more about what you're looking for?"

    return response, current_filters, trigger_search

# ------------------- Main App Logic -------------------
# Initial UI - Choose between direct search or chatbot
if st.session_state.mode is None:
    col_left, col_center, col_right = st.columns([1, 4, 1])

    with col_center:
        st.markdown("<div class='welcome-text'>Hello, Ziya</div>", unsafe_allow_html=True)
        st.markdown("<p class='prompt-text'>How would you like to find your perfect phone?</p>", unsafe_allow_html=True)

        chat_mode_button = st.button("💬 Chat with Advisor", key="chat_mode_button")
        direct_search_mode_button = st.button("🔍 Direct Search", key="direct_search_mode_button")

        if chat_mode_button:
            st.session_state.mode = "chat"
            st.session_state.show_results = True
            st.session_state.messages.append({"role": "assistant", "content": "Hello! I'm your Phone Advisor. How can I assist you today? Tell me what you're looking for!"})
            st.rerun()
        elif direct_search_mode_button:
            st.session_state.mode = "direct_search"
            st.session_state.show_results = True
            st.rerun()

# ------------------- Content Section (for both modes) -------------------
if st.session_state.show_results:
    if st.session_state.mode == "direct_search":
        st.markdown(f"### Direct Search")

        # FIX 3: Moved 'Back to Home' button outside the form to resolve StreamlitException
        # The search input and button remain within the form.
        with st.form(key='search_form_direct', clear_on_submit=False):
            user_input_direct = st.text_input("", value=st.session_state.query,
                                        placeholder="Type your query here, e.g., 'phone under ₹14000 with 16GB RAM'",
                                        key="_query_input_form_direct",
                                        label_visibility="collapsed")
            
            submit_button_direct = st.form_submit_button(label='🔍 Search')

        # This button is now separate from the form.
        if st.button("🏠 Back to Home", key="back_to_home_direct_search_outside_form_unique"):
            st.session_state.query = ""
            st.session_state.filtered_df = pd.DataFrame()
            st.session_state.show_results = False
            st.session_state.mode = None
            st.session_state.show_results_display = False
            st.session_state.messages = []
            st.session_state.current_filters = {}
            st.session_state.awaiting_confirmation = False
            st.rerun()

        if submit_button_direct or st.session_state.show_results_display:
            if submit_button_direct:
                st.session_state.query = user_input_direct
                filters = extract_filters(st.session_state.query)
                st.session_state.filtered_df = filter_data(df, filters)
                st.session_state.show_results_display = True
                
            st.markdown(f"### Results for: **{st.session_state.query}**")
            if not st.session_state.filtered_df.empty:
                st.success(f"✅ Found {len(st.session_state.filtered_df)} phone(s)")
                num_cards = len(st.session_state.filtered_df)
                cols_per_row = 4
                with st.container():
                    for i in range(0, num_cards, cols_per_row):
                        cols = st.columns(cols_per_row)
                        for j in range(cols_per_row):
                            idx = i + j
                            if idx < num_cards:
                                row = st.session_state.filtered_df.iloc[idx]
                                with cols[j]:
                                    phone_name = f"{row['brand']} {row['model']}"
                                    img_url = row.get('image_url')
                                    # Attempt to fetch image only if 'image_url' is missing or empty
                                    if pd.isna(img_url) or img_url == "":
                                        img_url = fetch_image_url(phone_name)
                                    st.markdown(f"""
                                        <div class='result-card'>
                                            <div class='phone-image-container'>
                                                <img src="{img_url}" alt="{phone_name}" onerror="this.onerror=null;this.src='https://placehold.co/200x200/000000/FFFFFF?text=No+Image';">
                                            </div>
                                            <h4>{phone_name}</h4>
                                            <span>⚙️ <strong>Processor:</strong> {row.get('Processor', 'N/A')}</span>
                                            <span>📅 <strong>Year:</strong> {row.get('launched_year', 'N/A')}</span>
                                            <span>📱 <strong>RAM:</strong> {row.get('ram_gb', 'N/A')} GB</span>
                                            <span>🔋 <strong>Battery:</strong> {row.get('battery_capacity_mah', 'N/A')} mAh</span>
                                            <span>📷 <strong>Camera:</strong> {row.get('back_camera_mp', 'N/A')} MP</span>
                                            <span>💰 <strong>Price:</strong> ₹{row.get('launched_price_rs', 'N/A')}</span>
                                            <span>💾 <strong>Storage:</strong> {row.get('storage_gb', 'N/A')} GB</span>
                                            <span>📐 <strong>Screen:</strong> {row.get('screen_size_inches', 'N/A')} inches</span>
                                        </div>
                                        """, unsafe_allow_html=True)
            else:
                st.warning("⚠️ No phones found matching your query. Please try a different query.")
            
            st.markdown("---")
            with st.expander("🔍 View all results in table"):
                if not st.session_state.filtered_df.empty:
                    st.dataframe(st.session_state.filtered_df.reset_index(drop=True))
                else:
                    st.info("No data to display in table.")
            
    elif st.session_state.mode == "chat":
        st.markdown(f"### Chat with your Phone Advisor")
        st.markdown("---")

        # Container for chat messages with scrolling
        st.markdown("<div class='chat-messages-display'>", unsafe_allow_html=True)
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        st.markdown("</div>", unsafe_allow_html=True) # Close chat-messages-display div

        # Display results below chat history if available
        if not st.session_state.filtered_df.empty:
            st.success(f"✅ Found {len(st.session_state.filtered_df)} phone(s) matching your criteria!")
            
            num_cards = len(st.session_state.filtered_df)
            cols_per_row = 4
            with st.container():
                for i in range(0, num_cards, cols_per_row):
                    cols = st.columns(cols_per_row)
                    for j in range(cols_per_row):
                        idx = i + j
                        if idx < num_cards:
                            row = st.session_state.filtered_df.iloc[idx]
                            with cols[j]:
                                phone_name = f"{row['brand']} {row['model']}"
                                img_url = row.get('image_url')
                                if pd.isna(img_url) or img_url == "":
                                    img_url = fetch_image_url(phone_name)
                                st.markdown(f"""
                                    <div class='result-card'>
                                        <div class='phone-image-container'>
                                            <img src="{img_url}" alt="{phone_name}" onerror="this.onerror=null;this.src='https://placehold.co/200x200/000000/FFFFFF?text=No+Image';">
                                        </div>
                                        <h4>{phone_name}</h4>
                                        <span>⚙️ <strong>Processor:</strong> {row.get('Processor', 'N/A')}</span>
                                        <span>📅 <strong>Year:</strong> {row.get('launched_year', 'N/A')}</span>
                                        <span>📱 <strong>RAM:</strong> {row.get('ram_gb', 'N/A')} GB</span>
                                        <span>🔋 <strong>Battery:</strong> {row.get('battery_capacity_mah', 'N/A')} mAh</span>
                                        <span>📷 <strong>Camera:</strong> {row.get('back_camera_mp', 'N/A')} MP</span>
                                        <span>💰 <strong>Price:</strong> ₹{row.get('launched_price_rs', 'N/A')}</span>
                                        <span>💾 <strong>Storage:</strong> {row.get('storage_gb', 'N/A')} GB</span>
                                        <span>📐 <strong>Screen:</strong> {row.get('screen_size_inches', 'N/A')} inches</span>
                                    </div>
                                    """, unsafe_allow_html=True)
            st.markdown("---")
            with st.expander("🔍 View all results in table"):
                st.dataframe(st.session_state.filtered_df.reset_index(drop=True))
            
            # Clear results and filters AFTER displaying them so the next turn starts fresh
            st.session_state.filtered_df = pd.DataFrame() 
            st.session_state.current_filters = {} 
            st.session_state.awaiting_confirmation = False # Reset confirmation after showing results
        
        else: # This means filtered_df was empty AFTER a search was triggered.
              # Display warning if the last assistant message indicated no results from a search.
            # FIX 2 & 5: Changed the condition for displaying warning/no results message in chat mode.
            # Now it specifically checks for the "No phones found matching..." message after a triggered search.
            if st.session_state.messages and any("No phones found matching your combined criteria." in msg["content"] for msg in st.session_state.messages):
                st.warning("⚠️ No phones found matching your combined criteria. Let's try refining your search!")
                # Remove the "No phones found" message from chat history to avoid persistent display
                st.session_state.messages = [msg for msg in st.session_state.messages if "No phones found matching your combined criteria." not in msg["content"]]
        
        # --- Fixed Chat Input and Reset Button Container (for chat mode only) ---
        st.markdown("<div class='chat-input-sticky-container'>", unsafe_allow_html=True)
        prompt = st.chat_input("How can I help you find a phone?", key="chat_input_bar")
        
        if prompt:
            st.session_state.messages.append({"role": "user", "content": prompt})
            ai_response, updated_filters, trigger_search = get_chatbot_response(prompt, st.session_state.current_filters)
            st.session_state.current_filters = updated_filters
            
            # Append AI response to messages, but only if it's not the "search triggered" message
            # The actual search message will be handled by the display logic for results
            if "Understood! Searching for" not in ai_response:
                st.session_state.messages.append({"role": "assistant", "content": ai_response})

            if trigger_search:
                # Add a message to chat history indicating search is happening
                st.session_state.messages.append({"role": "assistant", "content": "Searching for phones now..."})
                st.session_state.filtered_df = filter_data(df, st.session_state.current_filters)
                if st.session_state.filtered_df.empty:
                    # If no results found after a triggered search, add a specific message.
                    st.session_state.messages.append({"role": "assistant", "content": "No phones found matching your combined criteria. Would you like to adjust your preferences?"})
                # Filters should be cleared AFTER a search attempt (success or failure)
                st.session_state.current_filters = {} 
            st.rerun() # Rerun to display new messages and results

        st.button("Reset Chat and Search", key="reset_chat_button", on_click=lambda: (
            st.session_state.update({
                'query': "", 'filtered_df': pd.DataFrame(), 'show_results': False,
                'messages': [], 'current_filters': {}, 'mode': None, 'show_results_display': False,
                'awaiting_confirmation': False
            }), st.rerun()
        ))
        st.markdown("</div>", unsafe_allow_html=True)


# Back to Home button (global, fixed position)
if st.session_state.show_results:
    st.markdown("<div class='fixed-bottom-right-home'>", unsafe_allow_html=True)
    if st.button("🏠 Back to Home", key="back_to_home_fixed_global"):
        st.session_state.query = ""
        st.session_state.filtered_df = pd.DataFrame()
        st.session_state.show_results = False
        st.session_state.messages = []
        st.session_state.current_filters = {}
        st.session_state.mode = None
        st.session_state.show_results_display = False
        st.session_state.awaiting_confirmation = False
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)