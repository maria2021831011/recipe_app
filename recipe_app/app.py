from flask import Flask, render_template, request, jsonify, session, redirect
from config import Config
from extensions import mysql, bcrypt
from datetime import datetime, timedelta
import secrets
import json
import os
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import openai

# ===================== FLASK APP =====================
app = Flask(__name__)
app.config.from_object(Config)

# ===================== DATABASE / EXTENSIONS =====================
mysql.init_app(app)
bcrypt.init_app(app)

# ===================== OPENAI / GEMINI =====================
load_dotenv()
openai.api_key = os.environ.get("OPENAI_API_KEY")

@app.route("/api/gemini/recipe", methods=["POST"])
def gemini_recipe():
    """
    Receives a search query from frontend,
    sends prompt to OpenAI, returns structured JSON recipe.
    """
    if not check_auth():
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data = request.get_json()
    query = data.get("prompt") or data.get("query")
    if not query:
        return jsonify({"success": False, "error": "No query provided"}), 400

    try:
        prompt = f"""
        Generate a complete recipe based on this query: "{query}".
        Provide output as valid JSON with keys:
        title (string), description (string), image_url (string), 
        ingredients (array of strings), instructions (array of strings), 
        category (string: breakfast/lunch/dinner/dessert/snack), 
        difficulty (string: easy/medium/hard), servings (integer),
        prep_time (integer in minutes), cook_time (integer in minutes).
        
        Example response format:
        {{
            "title": "Recipe Title",
            "description": "Recipe description",
            "image_url": "https://example.com/image.jpg",
            "ingredients": ["ingredient 1", "ingredient 2"],
            "instructions": ["step 1", "step 2"],
            "category": "dinner",
            "difficulty": "medium",
            "servings": 4,
            "prep_time": 15,
            "cook_time": 30
        }}
        """

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a professional chef. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )

        text = response.choices[0].message.content

        # Extract JSON from response
        import re
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            recipe = json.loads(json_match.group())
        else:
            # Try direct parsing
            try:
                recipe = json.loads(text)
            except:
                # Fallback recipe
                recipe = {
                    "title": f"Delicious {query}",
                    "description": f"A tasty {query} recipe created by AI",
                    "image_url": f"https://source.unsplash.com/600x400/?{query.replace(' ', ',')},food",
                    "ingredients": ["Main ingredient", "Seasoning", "Spices", "Oil"],
                    "instructions": ["Prepare ingredients", "Cook as directed", "Season to taste", "Serve hot"],
                    "category": "dinner",
                    "difficulty": "medium",
                    "servings": 4,
                    "prep_time": 15,
                    "cook_time": 30
                }

        # Add tags
        recipe["tags"] = [query.lower(), "ai-generated", "quick"]
        
        return jsonify({"success": True, **recipe})

    except Exception as e:
        print("OpenAI error:", str(e))
        # Return fallback recipe
        return jsonify({
            "success": True,
            "title": f"{query.title()} Recipe",
            "description": f"A quick and easy {query} recipe",
            "image_url": "https://source.unsplash.com/600x400/?food",
            "ingredients": ["Your choice of ingredients", "Spices", "Oil", "Seasoning"],
            "instructions": ["Prepare ingredients", "Cook as desired", "Add seasoning", "Serve and enjoy"],
            "category": "dinner",
            "difficulty": "easy",
            "servings": 2,
            "prep_time": 10,
            "cook_time": 20,
            "tags": [query.lower(), "simple", "easy"]
        })

# ===================== UPLOAD CONFIG =====================
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "mp4", "mov", "avi"}
UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
IMAGE_FOLDER = os.path.join(UPLOAD_FOLDER, "images")
VIDEO_FOLDER = os.path.join(UPLOAD_FOLDER, "videos")
PROFILE_FOLDER = os.path.join(UPLOAD_FOLDER, "profiles")
os.makedirs(IMAGE_FOLDER, exist_ok=True)
os.makedirs(VIDEO_FOLDER, exist_ok=True)
os.makedirs(PROFILE_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ===================== DATABASE HELPERS =====================
def get_db_connection():
    conn = mysql.connect()
    cursor = conn.cursor()
    return conn, cursor

def close_db_connection(conn, cursor):
    cursor.close()
    conn.close()

def check_auth():
    return 'user_id' in session

def get_user_info():
    if not check_auth():
        return None
    conn, cursor = get_db_connection()
    try:
        cursor.execute("""
            SELECT id, username, email, profile_image, bio, location, website 
            FROM users WHERE id = %s
        """, (session['user_id'],))
        user = cursor.fetchone()
        
        if user:
            return {
                'id': user[0], 
                'username': user[1], 
                'email': user[2],
                'profile_image': user[3],
                'bio': user[4],
                'location': user[5],
                'website': user[6]
            }
    except Exception as e:
        print(f"Error getting user info: {e}")
    finally:
        close_db_connection(conn, cursor)
    return None

# ===================== ROUTES =====================
@app.route("/")
def index():
    if "user_id" in session:
        return redirect("/dashboard")
    return render_template("index.html")

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/")
    return render_template("dashboard.html", username=session.get("username", "User"))

# ===================== AUTH =====================
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")
    
    if not username or not email or not password:
        return jsonify({"success": False, "message": "All fields are required"})
    
    hashed_pw = bcrypt.generate_password_hash(password).decode("utf-8")

    conn, cursor = get_db_connection()
    try:
        cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cursor.fetchone():
            return jsonify({"success": False, "message": "Email already exists"})

        cursor.execute(
            "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
            (username, email, hashed_pw)
        )
        conn.commit()
        user_id = cursor.lastrowid
        
        session["user_id"] = user_id
        session["username"] = username
        return jsonify({"success": True})
        
    except Exception as e:
        conn.rollback()
        print(f"Registration error: {e}")
        return jsonify({"success": False, "message": "Registration failed"})
    finally:
        close_db_connection(conn, cursor)

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email") or data.get("username")
    password = data.get("password")

    if not email or not password:
        return jsonify({"success": False, "message": "Email and password required"})

    conn, cursor = get_db_connection()
    try:
        cursor.execute("SELECT id, username, password FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()
        
        if user and bcrypt.check_password_hash(user[2], password):
            session["user_id"] = user[0]
            session["username"] = user[1]
            
            return jsonify({"success": True, "username": user[1]})
        return jsonify({"success": False, "message": "Invalid credentials"})
        
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({"success": False, "message": "Login failed"})
    finally:
        close_db_connection(conn, cursor)

@app.route("/api/me", methods=["GET"])
def get_current_user():
    if not check_auth():
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    user = get_user_info()
    if user:
        # Get user stats
        conn, cursor = get_db_connection()
        try:
            # Recipe count
            cursor.execute("SELECT COUNT(*) FROM recipes WHERE user_id = %s", (session['user_id'],))
            recipe_count = cursor.fetchone()[0] or 0
            
            # Like count (likes received on user's recipes)
            cursor.execute("""
                SELECT COUNT(*) FROM likes 
                WHERE recipe_id IN (SELECT id FROM recipes WHERE user_id = %s)
            """, (session['user_id'],))
            like_count = cursor.fetchone()[0] or 0
            
            # View count
            cursor.execute("SELECT IFNULL(SUM(views), 0) FROM recipes WHERE user_id = %s", (session['user_id'],))
            view_count = cursor.fetchone()[0] or 0
            
            user.update({
                'recipe_count': recipe_count,
                'like_count': like_count,
                'view_count': view_count
            })
        except Exception as e:
            print(f"Error getting user stats: {e}")
            user.update({
                'recipe_count': 0,
                'like_count': 0,
                'view_count': 0
            })
        finally:
            close_db_connection(conn, cursor)
        
        return jsonify({"success": True, "user": user})
    return jsonify({"success": False, "message": "User not found"})

@app.route("/api/check-auth")
def check_auth_api():
    if check_auth():
        user = get_user_info()
        if user:
            return jsonify({"is_logged_in": True, "user": user})
    return jsonify({"is_logged_in": False})

@app.route("/logout")
def logout():
    session.clear()
    return redirect('/')

# ===================== DASHBOARD STATS =====================
@app.route("/api/dashboard/stats", methods=["GET"])
def dashboard_stats():
    if not check_auth():
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    user_id = session["user_id"]
    conn, cursor = get_db_connection()
    try:
        # Get total recipes
        cursor.execute("SELECT COUNT(*) FROM recipes WHERE user_id=%s", (user_id,))
        total_recipes = cursor.fetchone()[0] or 0

        # Get total likes (likes received on user's recipes)
        cursor.execute("""
            SELECT COUNT(*) FROM likes 
            WHERE recipe_id IN (SELECT id FROM recipes WHERE user_id=%s)
        """, (user_id,))
        total_likes = cursor.fetchone()[0] or 0

        # Get total views
        cursor.execute("SELECT IFNULL(SUM(views),0) FROM recipes WHERE user_id=%s", (user_id,))
        total_views = cursor.fetchone()[0] or 0

        # Get recent recipes
        cursor.execute("""
            SELECT id, title, description, image_url, 
                   (SELECT COUNT(*) FROM likes WHERE recipe_id=recipes.id) as likes_count
            FROM recipes 
            WHERE user_id=%s
            ORDER BY created_at DESC 
            LIMIT 5
        """, (user_id,))
        
        recent_recipes = []
        for row in cursor.fetchall():
            recent_recipes.append({
                "id": row[0],
                "title": row[1],
                "description": row[2],
                "image_url": row[3],
                "likes": row[4] or 0
            })

        return jsonify({
            "success": True,
            "stats": {
                "total_recipes": total_recipes,
                "total_likes": total_likes,
                "total_views": total_views
            },
            "recent_recipes": recent_recipes
        })
    except Exception as e:
        print(f"Dashboard stats error: {e}")
        return jsonify({
            "success": True,
            "stats": {
                "total_recipes": 0,
                "total_likes": 0,
                "total_views": 0
            },
            "recent_recipes": []
        })
    finally:
        close_db_connection(conn, cursor)

# ===================== RECIPES API =====================
@app.route("/api/recipes", methods=["GET", "POST"])
def recipes():
    if not check_auth():
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    if request.method == "GET":
        # Get recipes with optional filters
        category = request.args.get('category')
        difficulty = request.args.get('difficulty')
        mine = request.args.get('mine')
        
        user_id = session['user_id']
        conn, cursor = get_db_connection()
        
        try:
            query = """
                SELECT r.*, u.username,
                       (SELECT COUNT(*) FROM likes WHERE recipe_id=r.id) as likes_count
                FROM recipes r
                LEFT JOIN users u ON r.user_id = u.id
            """
            conditions = []
            params = []
            
            if mine and mine == '1':
                conditions.append("r.user_id = %s")
                params.append(user_id)
            elif category:
                conditions.append("r.category = %s")
                params.append(category)
            if difficulty:
                conditions.append("r.difficulty = %s")
                params.append(difficulty)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY r.created_at DESC LIMIT 50"
            cursor.execute(query, tuple(params))
            
            recipes = []
            for row in cursor.fetchall():
                # Parse tags from string to list
                tags = []
                if row[11]:  # tags column
                    tags = row[11].split(',')
                
                recipes.append({
                    "id": row[0],
                    "user_id": row[1],
                    "title": row[2],
                    "description": row[3],
                    "category": row[4],
                    "difficulty": row[5],
                    "prep_time": row[6],
                    "cook_time": row[7],
                    "servings": row[8],
                    "ingredients": row[9].split('\n') if row[9] else [],
                    "instructions": row[10].split('\n') if row[10] else [],
                    "tags": tags,
                    "image_url": row[12],
                    "video_url": row[13],
                    "views": row[14] or 0,
                    "created_at": row[15].strftime('%Y-%m-%d') if row[15] else None,
                    "author": row[18],  # username from join
                    "likes_count": row[19] or 0
                })
            
            return jsonify({"success": True, "recipes": recipes})
            
        except Exception as e:
            print(f"Get recipes error: {e}")
            return jsonify({"success": False, "message": "Failed to fetch recipes"})
        finally:
            close_db_connection(conn, cursor)
    
    elif request.method == "POST":
        # Create new recipe
        data = request.get_json()
        
        required_fields = ['title', 'description', 'category', 'difficulty', 
                          'prep_time', 'cook_time', 'servings']
        for field in required_fields:
            if not data.get(field):
                return jsonify({"success": False, "message": f"{field} is required"})
        
        try:
            conn, cursor = get_db_connection()
            
            # Convert ingredients and instructions to text
            ingredients_text = '\n'.join(data.get('ingredients', []))
            instructions_text = '\n'.join(data.get('instructions', []))
            tags_text = ','.join(data.get('tags', []))
            
            cursor.execute("""
                INSERT INTO recipes (
                    user_id, title, description, category, difficulty,
                    prep_time, cook_time, servings, ingredients, instructions,
                    image_url, video_url, tags
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                session['user_id'],
                data['title'],
                data['description'],
                data['category'],
                data['difficulty'],
                data['prep_time'],
                data['cook_time'],
                data['servings'],
                ingredients_text,
                instructions_text,
                data.get('image_url', ''),
                data.get('video_url', ''),
                tags_text
            ))
            
            conn.commit()
            recipe_id = cursor.lastrowid
            
            return jsonify({"success": True, "recipe_id": recipe_id})
            
        except Exception as e:
            conn.rollback()
            print(f"Create recipe error: {e}")
            return jsonify({"success": False, "message": "Failed to create recipe"})
        finally:
            close_db_connection(conn, cursor)

@app.route("/api/recipes/<int:recipe_id>", methods=["GET", "PUT", "DELETE"])
def recipe_detail(recipe_id):
    if not check_auth():
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    conn, cursor = get_db_connection()
    
    if request.method == "GET":
        try:
            cursor.execute("""
                SELECT r.*, u.username,
                       (SELECT COUNT(*) FROM likes WHERE recipe_id=r.id) as likes_count
                FROM recipes r
                LEFT JOIN users u ON r.user_id = u.id
                WHERE r.id = %s
            """, (recipe_id,))
            
            row = cursor.fetchone()
            if not row:
                return jsonify({"success": False, "message": "Recipe not found"})
            
            # Parse tags
            tags = []
            if row[11]:  # tags column
                tags = row[11].split(',')
            
            # Increment view count
            cursor.execute("UPDATE recipes SET views = views + 1 WHERE id = %s", (recipe_id,))
            conn.commit()
            
            return jsonify({
                "success": True,
                "recipe": {
                    "id": row[0],
                    "user_id": row[1],
                    "title": row[2],
                    "description": row[3],
                    "category": row[4],
                    "difficulty": row[5],
                    "prep_time": row[6],
                    "cook_time": row[7],
                    "servings": row[8],
                    "ingredients": row[9].split('\n') if row[9] else [],
                    "instructions": row[10].split('\n') if row[10] else [],
                    "tags": tags,
                    "image_url": row[12],
                    "video_url": row[13],
                    "views": row[14] or 0,
                    "created_at": row[15].strftime('%Y-%m-%d %H:%M:%S') if row[15] else None,
                    "updated_at": row[16].strftime('%Y-%m-%d %H:%M:%S') if row[16] else None,
                    "author": row[18],  # username
                    "likes_count": row[19] or 0
                }
            })
            
        except Exception as e:
            print(f"Get recipe detail error: {e}")
            return jsonify({"success": False, "message": "Failed to fetch recipe"})
        finally:
            close_db_connection(conn, cursor)
    
    elif request.method == "PUT":
        # Update recipe
        data = request.get_json()
        
        try:
            # Check ownership
            cursor.execute("SELECT user_id FROM recipes WHERE id = %s", (recipe_id,))
            recipe = cursor.fetchone()
            
            if not recipe or recipe[0] != session['user_id']:
                return jsonify({"success": False, "message": "Not authorized"})
            
            # Convert ingredients and instructions to text
            ingredients_text = '\n'.join(data.get('ingredients', []))
            instructions_text = '\n'.join(data.get('instructions', []))
            tags_text = ','.join(data.get('tags', []))
            
            cursor.execute("""
                UPDATE recipes SET
                    title = %s,
                    description = %s,
                    category = %s,
                    difficulty = %s,
                    prep_time = %s,
                    cook_time = %s,
                    servings = %s,
                    ingredients = %s,
                    instructions = %s,
                    image_url = %s,
                    video_url = %s,
                    tags = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (
                data.get('title'),
                data.get('description'),
                data.get('category'),
                data.get('difficulty'),
                data.get('prep_time', 0),
                data.get('cook_time', 0),
                data.get('servings', 2),
                ingredients_text,
                instructions_text,
                data.get('image_url', ''),
                data.get('video_url', ''),
                tags_text,
                recipe_id
            ))
            
            conn.commit()
            return jsonify({"success": True, "message": "Recipe updated"})
            
        except Exception as e:
            conn.rollback()
            print(f"Update recipe error: {e}")
            return jsonify({"success": False, "message": "Failed to update recipe"})
        finally:
            close_db_connection(conn, cursor)
    
    elif request.method == "DELETE":
        try:
            # Check ownership
            cursor.execute("SELECT user_id FROM recipes WHERE id = %s", (recipe_id,))
            recipe = cursor.fetchone()
            
            if not recipe or recipe[0] != session['user_id']:
                return jsonify({"success": False, "message": "Not authorized"})
            
            cursor.execute("DELETE FROM recipes WHERE id = %s", (recipe_id,))
            conn.commit()
            
            return jsonify({"success": True, "message": "Recipe deleted"})
            
        except Exception as e:
            conn.rollback()
            print(f"Delete recipe error: {e}")
            return jsonify({"success": False, "message": "Failed to delete recipe"})
        finally:
            close_db_connection(conn, cursor)

# ===================== CATEGORIES =====================
@app.route("/api/categories", methods=["GET"])
def get_categories():
    if not check_auth():
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    conn, cursor = get_db_connection()
    try:
        cursor.execute("""
            SELECT DISTINCT category, COUNT(*) as count 
            FROM recipes 
            GROUP BY category 
            ORDER BY count DESC
        """)
        
        categories = []
        for row in cursor.fetchall():
            categories.append({
                "category": row[0],
                "count": row[1]
            })
        
        # Get some recipes from each category
        cursor.execute("""
            SELECT r.id, r.title, r.description, r.image_url, r.category,
                   (SELECT COUNT(*) FROM likes WHERE recipe_id=r.id) as likes_count
            FROM recipes r
            WHERE r.id IN (
                SELECT MIN(id) FROM recipes GROUP BY category
            ) OR r.id IN (
                SELECT id FROM recipes ORDER BY RAND() LIMIT 5
            )
            LIMIT 10
        """)
        
        recipes = []
        for row in cursor.fetchall():
            recipes.append({
                "id": row[0],
                "title": row[1],
                "description": row[2],
                "image_url": row[3],
                "category": row[4],
                "likes_count": row[5] or 0
            })
        
        return jsonify({"success": True, "categories": categories, "recipes": recipes})
    except Exception as e:
        print(f"Get categories error: {e}")
        # Return default categories
        default_categories = [
            {"category": "breakfast", "count": 0},
            {"category": "lunch", "count": 0},
            {"category": "dinner", "count": 0},
            {"category": "dessert", "count": 0},
            {"category": "vegetarian", "count": 0}
        ]
        return jsonify({"success": True, "categories": default_categories, "recipes": []})
    finally:
        close_db_connection(conn, cursor)

# ===================== PROFILE =====================
@app.route("/api/profile", methods=["PUT"])
def update_profile():
    if not check_auth():
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    data = request.get_json()
    
    conn, cursor = get_db_connection()
    try:
        cursor.execute("""
            UPDATE users SET
                username = %s,
                email = %s,
                bio = %s,
                location = %s,
                website = %s,
                profile_image = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (
            data.get('username'),
            data.get('email'),
            data.get('bio', ''),
            data.get('location', ''),
            data.get('website', ''),
            data.get('profile_image', ''),
            session['user_id']
        ))
        
        conn.commit()
        session['username'] = data.get('username')
        
        return jsonify({"success": True, "message": "Profile updated"})
    except Exception as e:
        conn.rollback()
        print(f"Update profile error: {e}")
        return jsonify({"success": False, "message": "Failed to update profile"})
    finally:
        close_db_connection(conn, cursor)

# ===================== LIKES =====================
@app.route("/api/recipes/<int:recipe_id>/like", methods=["POST", "DELETE"])
def like_recipe(recipe_id):
    if not check_auth():
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    user_id = session['user_id']
    conn, cursor = get_db_connection()
    
    try:
        if request.method == "POST":
            # Add like
            cursor.execute("""
                INSERT INTO likes (recipe_id, user_id) 
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE id=id
            """, (recipe_id, user_id))
            conn.commit()
            return jsonify({"success": True, "message": "Recipe liked"})
        
        elif request.method == "DELETE":
            # Remove like
            cursor.execute("DELETE FROM likes WHERE recipe_id = %s AND user_id = %s", 
                          (recipe_id, user_id))
            conn.commit()
            return jsonify({"success": True, "message": "Like removed"})
            
    except Exception as e:
        conn.rollback()
        print(f"Like operation error: {e}")
        return jsonify({"success": False, "message": "Operation failed"})
    finally:
        close_db_connection(conn, cursor)

# ===================== FAVORITES =====================
@app.route("/api/recipes/<int:recipe_id>/favorite", methods=["POST", "DELETE"])
def favorite_recipe(recipe_id):
    if not check_auth():
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    user_id = session['user_id']
    conn, cursor = get_db_connection()
    
    try:
        if request.method == "POST":
            # Add to favorites
            cursor.execute("""
                INSERT INTO favorites (recipe_id, user_id) 
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE id=id
            """, (recipe_id, user_id))
            conn.commit()
            return jsonify({"success": True, "message": "Added to favorites"})
        
        elif request.method == "DELETE":
            # Remove from favorites
            cursor.execute("DELETE FROM favorites WHERE recipe_id = %s AND user_id = %s", 
                          (recipe_id, user_id))
            conn.commit()
            return jsonify({"success": True, "message": "Removed from favorites"})
            
    except Exception as e:
        conn.rollback()
        print(f"Favorite operation error: {e}")
        return jsonify({"success": False, "message": "Operation failed"})
    finally:
        close_db_connection(conn, cursor)

# ===================== COMMENTS =====================
@app.route("/api/recipes/<int:recipe_id>/comments", methods=["GET", "POST"])
def recipe_comments(recipe_id):
    if not check_auth():
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    conn, cursor = get_db_connection()
    
    try:
        if request.method == "GET":
            # Get comments for recipe
            cursor.execute("""
                SELECT c.*, u.username, u.profile_image 
                FROM comments c
                JOIN users u ON c.user_id = u.id
                WHERE c.recipe_id = %s
                ORDER BY c.created_at DESC
            """, (recipe_id,))
            
            comments = []
            for row in cursor.fetchall():
                comments.append({
                    "id": row[0],
                    "recipe_id": row[1],
                    "user_id": row[2],
                    "content": row[3],
                    "created_at": row[4].strftime('%Y-%m-%d %H:%M:%S') if row[4] else None,
                    "username": row[5],
                    "profile_image": row[6]
                })
            
            return jsonify({"success": True, "comments": comments})
        
        elif request.method == "POST":
            # Add comment
            data = request.get_json()
            content = data.get('content')
            
            if not content:
                return jsonify({"success": False, "message": "Comment content required"})
            
            cursor.execute("""
                INSERT INTO comments (recipe_id, user_id, content)
                VALUES (%s, %s, %s)
            """, (recipe_id, session['user_id'], content))
            
            conn.commit()
            return jsonify({"success": True, "message": "Comment added"})
            
    except Exception as e:
        conn.rollback()
        print(f"Comments operation error: {e}")
        return jsonify({"success": False, "message": "Operation failed"})
    finally:
        close_db_connection(conn, cursor)

# ===================== ERROR HANDLERS =====================
@app.errorhandler(404)
def not_found(error):
    return jsonify({"success": False, "message": "Resource not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    print(f"Internal error: {error}")
    return jsonify({"success": False, "message": "Internal server error"}), 500

# ===================== RUN APP =====================
if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)