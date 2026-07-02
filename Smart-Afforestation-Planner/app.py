from flask import Flask, render_template, request, redirect, session, url_for, flash
import sqlite3
from datetime import datetime
import ee
from geopy.geocoders import Nominatim
import requests
import Config
import os
import humanize


app = Flask(__name__)
app.secret_key = Config.SECRET_KEY # Needed for flash messages
app.config['UPLOAD_FOLDER'] = 'static/uploads'

DATABASE = "database/trees.db"

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# LANDING PAGE
@app.route("/")
def landing():
    return render_template("landing.html")

#REGISTER PAGE
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        conn.execute(
            "INSERT INTO users (name, email, password, created_at) VALUES (?, ?, ?, ?)",
            (name, email, password, datetime.now())
        )
        conn.commit()
        conn.close()

        flash("Registration Successful!", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

# LOGIN PAGE
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email=? AND password=?",
            (email, password)
        ).fetchone()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("landing"))
        else:
            flash("Invalid Credentials","danger")

    return render_template("login.html")


# Route to delete history record

@app.route('/delete/<int:id>', methods=['POST'])
def delete_history(id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM analysis_history WHERE id = ?", (id,))
    conn.commit()
    conn.close()

    flash("Record deleted successfully!", "success")

    return redirect('/history')

#openweathermap API key and function to get weather data

API_KEY = Config.OPENWEATHER_API_KEY
def get_weather(lat, lon):
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
    
    response = requests.get(url)
    data = response.json()

    temp = data['main']['temp']
    climate = data['weather'][0]['main']

    return temp, climate


# -----------------------------
# Initialize Google Earth Engine
# -----------------------------
try:
    ee.Initialize(project='afforestation-planner')
except Exception:
    ee.Authenticate()
    ee.Initialize(project='afforestation-planner')

# History page

@app.route("/history")
def history():
    if "user_id" not in session:
        return redirect(url_for("login"))
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, latitude, longitude, ndvi, temperature, climate, suitability, created_at 
        FROM analysis_history
        ORDER BY id ASC
    """)
    records = cursor.fetchall()

    # Stats calculation
    total = len(records)
    avg_ndvi = round(sum([row[3] for row in records]) / total, 2) if total > 0 else 0
    high_count = len([row for row in records if row[6] == "High"])
    low_count = len([row for row in records if row[6] == "Low"])

    ndvi_values = [row[3] for row in records]
    dates = [row[7] for row in records]

    conn.close()

    return render_template(
        "history.html",
        records=records,
        ndvi_values=ndvi_values,
        dates=dates,
        total=total,
        avg_ndvi=avg_ndvi,
        high_count=high_count,
        low_count=low_count
    )

# DETAILS PAGE (When user clicks map)

@app.route("/details")
def details():
    if "user_id" not in session:
        return redirect(url_for("login"))
    lat = float(request.args.get('lat'))
    lon = float(request.args.get('lon'))

    temperature, climate = get_weather(lat, lon)

    import random
    ndvi = round(random.uniform(0.2, 0.8), 2)

    if ndvi > 0.6:
        suitability = "High"
        plants = [
            {"name": "Neem", "image": "image/Neem.jpg"},
            {"name": "Peepal", "image": "image/Peepal.jpg"},
            {"name": "Banyan", "image": "image/Banyan.jpg"}
        ]
    elif ndvi > 0.3:
        suitability = "Moderate"
        plants = [
            {"name": "Mango", "image": "image/Mango.jpg"},
            {"name": "Eucalyptus", "image": "image/Eucalyptus.jpg"},
            {"name": "Oak", "image": "image/Oak.jpg"}
        ]
    else:
        suitability = "Low"
        plants = [
            {"name": "Acacia", "image": "image/Acacia.jpg"},
            {"name": "Teak", "image": "image/Teak.jpg"},
            {"name": "Eastern Redcedar", "image": "image/Eastern Redcedar.jpg"}
        ]

# Estimated Trees Calculation

    if ndvi < 0.3:
        estimated_trees = 1200
    elif ndvi < 0.6:
        estimated_trees = 800
    else:
        estimated_trees = 300

# Save to database

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO analysis_history
        (latitude, longitude, ndvi, suitability, temperature, climate, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
            lat,
            lon,
            ndvi,
            suitability,
            temperature,
            climate,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()

    return render_template(
        "details.html",
        lat=lat,
        lon=lon,
        ndvi=ndvi,
        suitability=suitability,
        temperature=temperature,
        climate=climate,
        estimated_trees=estimated_trees,
        plants=plants
    )

# HOME PAGE

@app.route("/index", methods=["GET", "POST"])
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        location = request.form["location"]
        return result(location)

    return render_template("index.html")


# RESULT PAGE

def result(location):

    # -------- Geocoding ----------
    geolocator = Nominatim(
        user_agent="smart_afforestation_planner",
        timeout=10
    )

    loc = geolocator.geocode(location + ", India")

    if loc is None:
        return "Location not found. Please enter full city name."

    center_lat = loc.latitude
    center_lon = loc.longitude

    # -------- Create Buffer (10 km radius) ----------
    point = ee.Geometry.Point([center_lon, center_lat])
    region = point.buffer(10000)

    # -------- Sentinel-2 Collection ----------
    collection = (
        ee.ImageCollection("COPERNICUS/S2")
        .filterBounds(region)
        .filterDate("2025-01-01", "2025-12-31")
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
    )

    if collection.size().getInfo() == 0:
        return "No satellite data available."

    image = collection.mosaic().clip(region)

    # -------- NDVI ----------
    ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")

    # -------- Suitability Classification ----------
    suitability = ndvi.expression(
        "(b('NDVI') > 0.6) ? 3"
        ": (b('NDVI') > 0.3) ? 2"
        ": 1"
    ).clip(region)

    vis_params = {
        "min": 1,
        "max": 3,
        "palette": ["red", "yellow", "green"],
    }

    map_id_dict = suitability.getMapId(vis_params)
    tile_url = map_id_dict["tile_fetcher"].url_format

    return render_template(
        "map_result.html",
        location=location,
        center_lat=center_lat,
        center_lon=center_lon,
        tile_url=tile_url,
    )

# DASHBOARD PAGE

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    plantations = conn.execute("""
        SELECT * FROM plantations 
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (session["user_id"],)).fetchall()

    # 🔢 Totals
    total_trees = sum([p["trees_planted"] for p in plantations]) if plantations else 0
    total_carbon = sum([p["carbon_reduced"] for p in plantations]) if plantations else 0

    # 🏅 Badge Logic
    if total_trees >= 500:
        badge = "🌳 Forest Guardian"
    elif total_trees >= 200:
        badge = "🌿 Green Warrior"
    elif total_trees >= 50:
        badge = "🌱 Eco Starter"
    else:
        badge = "🌼 Beginner"

    #Graph Data
    dates= [p["created_at"] for p in plantations]
    trees_data = [p["trees_planted"] for p in plantations]

    conn.close()

    return render_template(
        "dashboard.html",
        plantations=plantations,
        total_trees=total_trees,
        total_carbon=total_carbon,
        badge=badge,
        dates=dates,
        trees_data=trees_data
    )

# ADD PLANTATION
@app.route("/add_plantation", methods=["POST"])
def add_plantation():

    if "user_id" not in session:
        return redirect(url_for("login"))

    trees = int(request.form.get("trees"))
    experience = request.form.get("experience")
    image = request.files['image']
    image_filename=None
    if image:
        image_filename=image.filename
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
    
    # 🌿 Carbon Auto Calculation
    carbon = trees * 21

    conn = get_db()
    conn.execute("""
        INSERT INTO plantations 
        (user_id, trees_planted, carbon_reduced, experience, created_at,image)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        session["user_id"],
        trees,
        carbon,
        experience,
        datetime.now(),
        image_filename
    ))
    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))
    

# LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


# CERTIFICATE PAGE

@app.route('/certificate/<int:plantation_id>')
def certificate(plantation_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    plantation = conn.execute(
        "SELECT * FROM plantations WHERE id = ? AND user_id = ?",
        (plantation_id, session["user_id"])
    ).fetchone()

    if not plantation:
        conn.close()
        return "Unauthorized Access ❌"

    user = conn.execute(
        "SELECT name FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    conn.close()

    return render_template(
        "certificate.html",
        plantation=plantation,
        user_name=user["name"],
        date=datetime.now().strftime("%d-%m-%Y")
    )

@app.route("/community")
def community():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    posts = conn.execute("""
        SELECT plantations.*, users.name 
        FROM plantations
        JOIN users ON plantations.user_id = users.id
        ORDER BY plantations.created_at DESC
    """).fetchall()

    updated_posts = []
    for p in posts:
        post = dict(p)
        post["times_ago"] = humanize.naturaltime(datetime.now() - datetime.strptime(p["created_at"], "%Y-%m-%d %H:%M:%S.%f"))
        updated_posts.append(p)

    conn.close()

    return render_template("community.html", posts=updated_posts)

@app.route('/like/<int:post_id>')
def like(post_id):

    conn = get_db()

    conn.execute(
        "UPDATE plantations SET likes = likes + 1 WHERE id = ?",
        (post_id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for('community'))

# -----------------------------
# RUN SERVER
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)
