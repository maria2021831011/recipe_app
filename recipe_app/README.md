readme.md banai dw

# FlavorVerse - Recipe Sharing Platform 🍽️

FlavorVerse is a modern, full-featured recipe sharing platform where food enthusiasts can discover, create, and share their favorite recipes. The platform features AI-powered recipe generation, user-friendly dashboards, and a vibrant community for food lovers.

## 🌟 Features

### 🔐 User Authentication

* User registration and login
* Secure password hashing with bcrypt
* Session-based authentication
* User profile management

### 📊 Interactive Dashboard

* Recipe statistics and analytics
* Recent recipe activity
* User profile overview
* Quick access to all features

### 🍳 Recipe Management

* Create, read, update, and delete recipes
* Recipe categorization (breakfast, lunch, dinner, dessert, etc.)
* Difficulty levels (easy, medium, hard)
* Cooking time and servings information
* Ingredients and instructions management

### 🤖 AI-Powered Features

* AI recipe generation using OpenAI GPT
* Search for recipes with natural language
* Intelligent recipe suggestions
* Automated recipe formatting

### 🔍 Advanced Search

* Search by recipe name, ingredients, or category
* Filter by difficulty and cooking time
* AI-powered recipe discovery
* Real-time search results

### 📱 User Engagement

* Like and favorite recipes
* Comment on recipes
* User profiles with stats
* Recipe views tracking

## 🚀 Quick Start

### Prerequisites

* Python 3.8+
* MySQL 5.7+
* OpenAI API key

### Installation

1. **Clone the repository**

**bash**

```
git clone <repository-url>
cd flavorverse
```

2. **Create virtual environment**

**bash**

```
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**

**bash**

```
pip install -r requirements.txt
```

4. **Set up environment variables**
   Create a `.env` file in the root directory:

**env**

```
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=your-secret-key-here
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=yourpassword
MYSQL_DB=recipe_app_db
OPENAI_API_KEY=your-openai-api-key-here
```

5. **Set up the database**

**bash**

```
# Run the database schema
mysql -u root -p < schema.sql
```

6. **Run the application**

**bash**

```
python app.py
```

The application will be available at `http://localhost:5000`

## 📁 Project Structure

**text**

```
flavorverse/
├── app.py                    # Main Flask application
├── config.py                # Configuration settings
├── extensions.py            # Flask extensions
├── requirements.txt         # Python dependencies
├── schema.sql              # Database schema
├── .env                    # Environment variables
├── templates/              # HTML templates
│   ├── index.html         # Landing page
│   ├── login.html         # Login page
│   └── dashboard.html     # Main dashboard
├── static/                 # Static files
│   ├── css/              # Stylesheets
│   ├── js/               # JavaScript files
│   └── uploads/          # User uploads
└── README.md              # This file
```

## 🗄️ Database Schema

### Main Tables

* **users** : User accounts and profiles
* **recipes** : Recipe data with ingredients and instructions
* **likes** : Recipe likes tracking
* **comments** : Recipe comments
* **favorites** : User favorite recipes

### Sample Data

The application includes dummy recipes for demonstration:

* Creamy Garlic Pasta
* Grilled Salmon
* Blueberry Pancakes
* Bangladeshi Biryani
* Hilsha Fish Curry
* Pitha (traditional Bangladeshi dessert)

## 🔧 API Endpoints

### Authentication

* `POST /api/register` - User registration
* `POST /api/login` - User login
* `GET /api/me` - Get current user info
* `GET /api/check-auth` - Check authentication status
* `GET /logout` - User logout

### Recipes

* `GET /api/recipes` - Get all recipes (with filters)
* `POST /api/recipes` - Create new recipe
* `GET /api/recipes/<id>` - Get specific recipe
* `PUT /api/recipes/<id>` - Update recipe
* `DELETE /api/recipes/<id>` - Delete recipe

### AI Features

* `POST /api/gemini/recipe` - Generate AI recipe

### Social Features

* `POST /api/recipes/<id>/like` - Like a recipe
* `DELETE /api/recipes/<id>/like` - Remove like
* `POST /api/recipes/<id>/favorite` - Add to favorites
* `DELETE /api/recipes/<id>/favorite` - Remove from favorites
* `GET /api/recipes/<id>/comments` - Get comments
* `POST /api/recipes/<id>/comments` - Add comment

### User & Dashboard

* `GET /api/dashboard/stats` - Dashboard statistics
* `GET /api/categories` - Recipe categories
* `PUT /api/profile` - Update user profile

## 🎨 Frontend Features

### Dashboard Layout

* **Sidebar Navigation** : Quick access to all sections
* **Top Bar** : User info and search functionality
* **Stats Cards** : Recipe statistics at a glance
* **Recipe Grid** : Responsive recipe cards
* **Modal View** : Detailed recipe view with video support

### Recipe Cards

Each recipe card displays:

* Recipe image with video indicator
* Title and description
* Cooking time and servings
* Likes count
* Action buttons (View, Edit, Delete)

### Search Functionality

* Real-time search with debouncing
* Local recipe search
* AI-powered recipe generation
* Search results display

## 🤖 AI Integration

### OpenAI GPT Integration

The platform uses OpenAI's GPT-3.5-turbo to:

* Generate recipes from natural language queries
* Format recipes in structured JSON
* Provide cooking instructions and ingredients
* Suggest recipe variations

### How AI Recipe Generation Works

1. User enters search query (e.g., "chicken biryani")
2. Query is sent to OpenAI API
3. AI generates structured recipe data
4. Recipe is formatted and displayed
5. User can save or customize the AI-generated recipe

## 🛡️ Security Features

* **Password Hashing** : Bcrypt for secure password storage
* **Session Management** : Flask sessions for authentication
* **Input Validation** : All user inputs are validated
* **SQL Injection Protection** : Parameterized queries
* **CORS Configuration** : Configured for security

## 📱 Responsive Design

The application is fully responsive and works on:

* Desktop computers
* Tablets
* Mobile phones
* Different screen sizes

## 🚀 Deployment

### Local Development

**bash**

```
python app.py
```

### Production Deployment

1. Set `FLASK_ENV=production` in `.env`
2. Use Gunicorn or uWSGI for production server
3. Configure Nginx or Apache as reverse proxy
4. Set up SSL certificates
5. Configure production database

### Docker Deployment (Optional)

**dockerfile**

```
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
```

## 📈 Future Enhancements

### Planned Features

* Recipe sharing via social media
* Recipe rating system
* Meal planning calendar
* Shopping list generator
* Nutritional information calculator
* Video recipe uploads
* User follow system
* Recipe collections
* Advanced search filters
* Export recipes to PDF

### AI Enhancements

* Recipe image generation
* Dietary restriction filtering
* Cooking video generation
* Personalized recipe recommendations
