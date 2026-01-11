from flask import Flask, render_template, request, jsonify, session, redirect
from config import Config
from extensions import mysql, bcrypt
from datetime import datetime, timedelta
import secrets
import json
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config.from_object(Config)

mysql.init_app(app)
bcrypt.init_app(app)

# File upload configuration
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi'}
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    conn = mysql.connect()
    cursor = conn.cursor()
    return conn, cursor

def close_db_connection(conn, cursor):
    cursor.close()
    conn.close()

# Helper function to convert cursor result to dictionary
def dict_cursor(cursor, row):
    if cursor.description:
        desc = cursor.description
        return dict(zip([col[0] for col in desc], row))
    return {}

# Helper function to check authentication
def check_auth():
    return 'user_id' in session

# Helper function to get user info
def get_user_info():
    if not check_auth():
        return None
    
    conn, cursor = get_db_connection()
    cursor.execute("SELECT id, username, email FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()
    close_db_connection(conn, cursor)
    
    if user:
        return {
            'id': user[0],
            'username': user[1],
            'email': user[2]
        }
    return None

@app.route("/")
def index():
    if "user_id" in session:
        return redirect("/dashboard")
    return render_template("index.html")

# ================= REGISTER =================
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    hashed_pw = bcrypt.generate_password_hash(password).decode("utf-8")

    conn, cursor = get_db_connection()

    cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
    if cursor.fetchone():
        close_db_connection(conn, cursor)
        return jsonify({"success": False, "message": "Email already exists"})

    cursor.execute(
        "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
        (username, email, hashed_pw)
    )
    conn.commit()
    
    user_id = cursor.lastrowid
    
    # Create user settings and stats
    try:
        cursor.execute("INSERT INTO user_settings (user_id) VALUES (%s)", (user_id,))
        cursor.execute("INSERT INTO user_stats (user_id) VALUES (%s)", (user_id,))
        conn.commit()
    except Exception as e:
        print(f"Error creating user settings/stats: {e}")
        conn.rollback()
    
    close_db_connection(conn, cursor)

    # Auto login after registration
    session["user_id"] = user_id
    session["username"] = username
    
    return jsonify({"success": True})

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/")
    return render_template("dashboard.html", username=session["username"])

# ================= LOGIN =================
@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("username")
    password = data.get("password")

    conn, cursor = get_db_connection()

    cursor.execute(
        "SELECT id, username, password FROM users WHERE email=%s", (email,)
    )
    user = cursor.fetchone()

    close_db_connection(conn, cursor)

    if user and bcrypt.check_password_hash(user[2], password):
        session["user_id"] = user[0]
        session["username"] = user[1]
        
        # Update last active
        conn, cursor = get_db_connection()
        cursor.execute("UPDATE user_stats SET last_active = CURDATE() WHERE user_id = %s", (user[0],))
        conn.commit()
        close_db_connection(conn, cursor)
        
        return jsonify({"success": True})

    return jsonify({"success": False, "message": "Invalid credentials"})

# ================= CHECK AUTH =================
@app.route("/api/check-auth")
def check_auth_api():
    if check_auth():
        user = get_user_info()
        if user:
            # Get user stats
            conn, cursor = get_db_connection()
            cursor.execute("""
                SELECT us.recipe_count, us.like_count, us.follower_count, 
                       us.following_count, us.view_count, us.streak_days
                FROM user_stats us
                WHERE us.user_id = %s
            """, (session['user_id'],))
            stats_row = cursor.fetchone()
            close_db_connection(conn, cursor)
            
            if stats_row:
                stats = {
                    'recipe_count': stats_row[0],
                    'like_count': stats_row[1],
                    'follower_count': stats_row[2],
                    'following_count': stats_row[3],
                    'view_count': stats_row[4],
                    'streak_days': stats_row[5]
                }
                user.update(stats)
            
            return jsonify({
                "is_logged_in": True,
                "user": user
            })
    
    return jsonify({"is_logged_in": False})

# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()      
    return redirect('/')

# ================= FORGOT PASSWORD =================
@app.route("/api/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json()
    email = data.get("email")

    conn, cursor = get_db_connection()

    cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
    user = cursor.fetchone()

    if not user:
        close_db_connection(conn, cursor)
        return jsonify({"success": True})  # Still return success for security

    code = str(secrets.randbelow(1000000)).zfill(6)
    expires_at = datetime.now() + timedelta(minutes=10)

    cursor.execute("DELETE FROM password_resets WHERE email=%s", (email,))

    cursor.execute(
        "INSERT INTO password_resets (email, code, expires_at) VALUES (%s, %s, %s)",
        (email, code, expires_at)
    )
    conn.commit()

    print(f"[DEBUG] Reset code for {email}: {code}")

    close_db_connection(conn, cursor)

    return jsonify({"success": True})

@app.route("/api/verify-code", methods=["POST"])
def verify_code():
    data = request.get_json()
    email = data.get("email")
    code = str(data.get("code")).strip()

    conn, cursor = get_db_connection()

    cursor.execute(
        "SELECT id FROM password_resets WHERE email=%s AND code=%s AND expires_at > NOW()",
        (email, code)
    )

    record = cursor.fetchone()
    close_db_connection(conn, cursor)

    if record:
        session["reset_email"] = email
        return jsonify({"success": True})

    return jsonify({"success": False})

@app.route("/api/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json()
    password = data.get("password")
    email = session.get("reset_email")

    if not email:
        return jsonify({"success": False, "message": "Session expired"})

    hashed_pw = bcrypt.generate_password_hash(password).decode("utf-8")

    conn, cursor = get_db_connection()

    cursor.execute(
        "UPDATE users SET password=%s WHERE email=%s",
        (hashed_pw, email)
    )

    cursor.execute(
        "DELETE FROM password_resets WHERE email=%s",
        (email,)
    )

    conn.commit()
    close_db_connection(conn, cursor)

    session.pop("reset_email", None)

    return jsonify({"success": True})

# ================= DASHBOARD STATS =================
@app.route("/api/dashboard/stats", methods=["GET"])
def dashboard_stats():
    if not check_auth():
        return jsonify({"success": False, "message": "Please login first"}), 401
    
    conn, cursor = get_db_connection()
    
    # Get user stats
    cursor.execute("""
        SELECT 
            (SELECT COUNT(*) FROM recipes WHERE user_id = %s) as total_recipes,
            (SELECT COUNT(*) FROM likes l JOIN recipes r ON l.recipe_id = r.id WHERE r.user_id = %s) as total_likes,
            (SELECT COUNT(*) FROM followers WHERE following_id = %s) as total_followers,
            (SELECT COUNT(*) FROM recipe_views WHERE recipe_id IN (SELECT id FROM recipes WHERE user_id = %s)) as total_views,
            (SELECT COUNT(*) FROM recipes WHERE user_id = %s AND created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)) as weekly_recipes
    """, (session['user_id'], session['user_id'], session['user_id'], session['user_id'], session['user_id']))
    
    stats_row = cursor.fetchone()
    stats = {
        'total_recipes': stats_row[0] if stats_row else 0,
        'total_likes': stats_row[1] if stats_row else 0,
        'total_followers': stats_row[2] if stats_row else 0,
        'total_views': stats_row[3] if stats_row else 0,
        'weekly_recipes': stats_row[4] if stats_row else 0
    }
    
    # Get recent activity
    cursor.execute("""
        (SELECT 
            'like' as type,
            l.created_at,
            u.username,
            r.title as recipe_title,
            r.id as recipe_id
        FROM likes l
        JOIN recipes r ON l.recipe_id = r.id
        JOIN users u ON l.user_id = u.id
        WHERE r.user_id = %s
        ORDER BY l.created_at DESC
        LIMIT 3)
        
        UNION ALL
        
        (SELECT 
            'comment' as type,
            c.created_at,
            u.username,
            r.title as recipe_title,
            r.id as recipe_id
        FROM comments c
        JOIN recipes r ON c.recipe_id = r.id
        JOIN users u ON c.user_id = u.id
        WHERE r.user_id = %s
        ORDER BY c.created_at DESC
        LIMIT 3)
        
        UNION ALL
        
        (SELECT 
            'follow' as type,
            f.created_at,
            u.username,
            NULL as recipe_title,
            NULL as recipe_id
        FROM followers f
        JOIN users u ON f.follower_id = u.id
        WHERE f.following_id = %s
        ORDER BY f.created_at DESC
        LIMIT 3)
        
        ORDER BY created_at DESC
        LIMIT 5
    """, (session['user_id'], session['user_id'], session['user_id']))
    
    activities_rows = cursor.fetchall()
    activities = []
    for row in activities_rows:
        activities.append({
            'type': row[0],
            'created_at': row[1],
            'username': row[2],
            'recipe_title': row[3],
            'recipe_id': row[4]
        })
    
    # Get recent recipes
    cursor.execute("""
        SELECT r.*, 
               (SELECT COUNT(*) FROM likes WHERE recipe_id = r.id) as likes_count,
               (SELECT COUNT(*) FROM comments WHERE recipe_id = r.id) as comments_count
        FROM recipes r
        WHERE r.user_id = %s
        ORDER BY r.created_at DESC
        LIMIT 5
    """, (session['user_id'],))
    
    recipes_rows = cursor.fetchall()
    recent_recipes = []
    if recipes_rows:
        desc = cursor.description
        for row in recipes_rows:
            recipe_dict = dict(zip([col[0] for col in desc], row))
            # Parse JSON fields
            for field in ['ingredients', 'instructions', 'tags']:
                if recipe_dict.get(field):
                    try:
                        recipe_dict[field] = json.loads(recipe_dict[field])
                    except:
                        recipe_dict[field] = []
            recent_recipes.append(recipe_dict)
    
    close_db_connection(conn, cursor)
    
    return jsonify({
        "success": True,
        "stats": stats,
        "activities": activities,
        "recent_recipes": recent_recipes
    })

# ================= RECIPE APIs =================
@app.route("/api/recipes", methods=["GET"])
def get_recipes():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    category = request.args.get('category')
    difficulty = request.args.get('difficulty')
    search = request.args.get('search')
    
    offset = (page - 1) * per_page
    
    conn, cursor = get_db_connection()
    
    query = """
        SELECT r.*, u.username as author_name,
               (SELECT COUNT(*) FROM likes WHERE recipe_id = r.id) as likes_count,
               (SELECT COUNT(*) FROM comments WHERE recipe_id = r.id) as comments_count
        FROM recipes r
        LEFT JOIN users u ON r.user_id = u.id
        WHERE 1=1
    """
    params = []
    
    if category:
        query += " AND r.category = %s"
        params.append(category)
    
    if difficulty:
        query += " AND r.difficulty = %s"
        params.append(difficulty)
    
    if search:
        query += " AND (r.title LIKE %s OR r.description LIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])
    
    query += " ORDER BY r.created_at DESC LIMIT %s OFFSET %s"
    params.extend([per_page, offset])
    
    cursor.execute(query, params)
    recipes_rows = cursor.fetchall()
    
    # Convert to dictionary
    recipes = []
    if recipes_rows:
        desc = cursor.description
        for row in recipes_rows:
            recipe_dict = dict(zip([col[0] for col in desc], row))
            # Parse JSON fields
            for field in ['ingredients', 'instructions', 'tags']:
                if recipe_dict.get(field):
                    try:
                        recipe_dict[field] = json.loads(recipe_dict[field])
                    except:
                        recipe_dict[field] = []
            recipes.append(recipe_dict)
    
    # Get total count
    count_query = "SELECT COUNT(*) as total FROM recipes WHERE 1=1"
    count_params = []
    
    if category:
        count_query += " AND category = %s"
        count_params.append(category)
    
    if difficulty:
        count_query += " AND difficulty = %s"
        count_params.append(difficulty)
    
    if search:
        count_query += " AND (title LIKE %s OR description LIKE %s)"
        count_params.extend([f"%{search}%", f"%{search}%"])
    
    cursor.execute(count_query, count_params)
    total = cursor.fetchone()[0]
    
    close_db_connection(conn, cursor)
    
    return jsonify({
        "success": True,
        "recipes": recipes,
        "total": total,
        "page": page,
        "per_page": per_page
    })

@app.route("/api/recipes/<int:recipe_id>", methods=["GET"])
def get_recipe(recipe_id):
    conn, cursor = get_db_connection()
    
    # Update view count
    cursor.execute("UPDATE recipes SET views = views + 1 WHERE id = %s", (recipe_id,))
    
    # Record view in recipe_views table
    user_id = session.get('user_id')
    ip = request.remote_addr
    cursor.execute(
        "INSERT INTO recipe_views (recipe_id, user_id, ip_address) VALUES (%s, %s, %s)",
        (recipe_id, user_id, ip)
    )
    
    conn.commit()
    
    # Get recipe details
    cursor.execute("""
        SELECT r.*, u.username as author_name,
               (SELECT COUNT(*) FROM likes WHERE recipe_id = r.id) as likes_count,
               (SELECT COUNT(*) FROM comments WHERE recipe_id = r.id) as comments_count
        FROM recipes r
        LEFT JOIN users u ON r.user_id = u.id
        WHERE r.id = %s
    """, (recipe_id,))
    
    recipe_row = cursor.fetchone()
    
    if not recipe_row:
        close_db_connection(conn, cursor)
        return jsonify({"success": False, "message": "Recipe not found"}), 404
    
    # Convert to dictionary
    desc = cursor.description
    recipe = dict(zip([col[0] for col in desc], recipe_row))
    
    # Check if user liked this recipe
    is_liked = False
    is_favorited = False
    if user_id:
        cursor.execute("SELECT id FROM likes WHERE recipe_id = %s AND user_id = %s", 
                      (recipe_id, user_id))
        is_liked = cursor.fetchone() is not None
        
        cursor.execute("SELECT id FROM favorites WHERE recipe_id = %s AND user_id = %s", 
                      (recipe_id, user_id))
        is_favorited = cursor.fetchone() is not None
    
    # Parse JSON fields
    if recipe.get('ingredients'):
        try:
            recipe['ingredients'] = json.loads(recipe['ingredients'])
        except:
            recipe['ingredients'] = []
    
    if recipe.get('instructions'):
        try:
            recipe['instructions'] = json.loads(recipe['instructions'])
        except:
            recipe['instructions'] = []
    
    if recipe.get('tags'):
        try:
            recipe['tags'] = json.loads(recipe['tags'])
        except:
            recipe['tags'] = []
    
    recipe['is_liked'] = is_liked
    recipe['is_favorited'] = is_favorited
    
    close_db_connection(conn, cursor)
    
    return jsonify({"success": True, "recipe": recipe})

@app.route("/api/recipes", methods=["POST"])
def create_recipe():
    if not check_auth():
        return jsonify({"success": False, "message": "Please login first"}), 401
    
    try:
        data = request.form.to_dict()
        
        # Parse ingredients and instructions
        ingredients = data.get('ingredients', '[]')
        instructions = data.get('instructions', '[]')
        tags = data.get('tags', '[]')
        
        # Convert to JSON if they're strings
        if isinstance(ingredients, str):
            try:
                ingredients = json.loads(ingredients)
            except:
                ingredients = [ing.strip() for ing in ingredients.split('\n') if ing.strip()]
        
        if isinstance(instructions, str):
            try:
                instructions = json.loads(instructions)
            except:
                instructions = [inst.strip() for inst in instructions.split('\n') if inst.strip()]
        
        if isinstance(tags, str):
            tags = [tag.strip() for tag in tags.split(',') if tag.strip()]
        
        # Handle file uploads
        image_url = None
        video_url = None
        
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{session['user_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
                os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'images'), exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], 'images', filename))
                image_url = f"/static/uploads/images/{filename}"
        
        if 'video' in request.files:
            file = request.files['video']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{session['user_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
                os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'videos'), exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], 'videos', filename))
                video_url = f"/static/uploads/videos/{filename}"
        
        conn, cursor = get_db_connection()
        
        cursor.execute("""
            INSERT INTO recipes (user_id, title, description, category, difficulty, 
                                prep_time, cook_time, servings, ingredients, instructions,
                                image_url, video_url, tags)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            session['user_id'],
            data.get('title'),
            data.get('description'),
            data.get('category'),
            data.get('difficulty'),
            int(data.get('prep_time', 0)),
            int(data.get('cook_time', 0)),
            int(data.get('servings', 1)),
            json.dumps(ingredients),
            json.dumps(instructions),
            image_url,
            video_url,
            json.dumps(tags)
        ))
        
        recipe_id = cursor.lastrowid
        conn.commit()
        close_db_connection(conn, cursor)
        
        return jsonify({"success": True, "recipe_id": recipe_id})
        
    except Exception as e:
        print(f"Error creating recipe: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# Rest of the API endpoints would need similar fixes...
# For now, let me provide a simplified version with basic functionality

# ================= SIMPLIFIED VERSION =================
# Since you're having issues, let's create a simplified working version first

@app.route("/api/test", methods=["GET"])
def test_api():
    return jsonify({"success": True, "message": "API is working"})

@app.route("/api/me", methods=["GET"])
def get_me():
    if not check_auth():
        return jsonify({"success": False, "message": "Not logged in"}), 401
    
    conn, cursor = get_db_connection()
    cursor.execute("SELECT id, username, email FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()
    close_db_connection(conn, cursor)
    
    if user:
        return jsonify({
            "success": True,
            "user": {
                "id": user[0],
                "username": user[1],
                "email": user[2]
            }
        })
    
    return jsonify({"success": False, "message": "User not found"}), 404

# Simple recipe listing
@app.route("/api/simple/recipes", methods=["GET"])
def simple_recipes():
    conn, cursor = get_db_connection()
    cursor.execute("""
        SELECT r.id, r.title, r.description, r.category, r.image_url, 
               u.username as author_name, r.created_at
        FROM recipes r
        LEFT JOIN users u ON r.user_id = u.id
        ORDER BY r.created_at DESC
        LIMIT 20
    """)
    
    recipes_rows = cursor.fetchall()
    recipes = []
    if recipes_rows:
        for row in recipes_rows:
            recipes.append({
                'id': row[0],
                'title': row[1],
                'description': row[2],
                'category': row[3],
                'image_url': row[4],
                'author_name': row[5],
                'created_at': row[6].strftime('%Y-%m-%d %H:%M:%S') if row[6] else None
            })
    
    close_db_connection(conn, cursor)
    
    return jsonify({"success": True, "recipes": recipes})

# Create a simple recipe
@app.route("/api/simple/recipes", methods=["POST"])
def create_simple_recipe():
    if not check_auth():
        return jsonify({"success": False, "message": "Please login first"}), 401
    
    try:
        data = request.get_json()
        
        conn, cursor = get_db_connection()
        
        cursor.execute("""
            INSERT INTO recipes (user_id, title, description, category, difficulty, 
                                prep_time, cook_time, servings, ingredients, instructions, tags)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            session['user_id'],
            data.get('title'),
            data.get('description'),
            data.get('category', 'dinner'),
            data.get('difficulty', 'medium'),
            data.get('prep_time', 10),
            data.get('cook_time', 30),
            data.get('servings', 2),
            json.dumps(data.get('ingredients', [])),
            json.dumps(data.get('instructions', [])),
            json.dumps(data.get('tags', []))
        ))
        
        recipe_id = cursor.lastrowid
        conn.commit()
        close_db_connection(conn, cursor)
        
        return jsonify({"success": True, "recipe_id": recipe_id})
        
    except Exception as e:
        print(f"Error creating simple recipe: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

if __name__ == "__main__":
    # Create upload directories
    upload_dir = os.path.join(app.root_path, 'static', 'uploads')
    os.makedirs(os.path.join(upload_dir, 'images'), exist_ok=True)
    os.makedirs(os.path.join(upload_dir, 'videos'), exist_ok=True)
    os.makedirs(os.path.join(upload_dir, 'profiles'), exist_ok=True)
    
    app.run(debug=True)