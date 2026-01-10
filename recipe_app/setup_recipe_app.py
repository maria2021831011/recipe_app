import os

# Base project folder
base_folder = "recipe_app"

# Folder structure
folders = [
    "",  # base folder itself
    "instance",
    "static",
    "static/css",
    "static/js",
    "static/uploads",
    "templates",
    "templates/auth",
    "templates/recipes",
    "templates/admin",
]

# Files to create
files = [
    "app.py",
    "config.py",
    "requirements.txt",
    ".env",
    "templates/base.html",
    "templates/index.html",
]

# Create folders
for folder in folders:
    path = os.path.join(base_folder, folder)
    os.makedirs(path, exist_ok=True)
    print(f"Created folder: {path}")


for file in files:
    path = os.path.join(base_folder, file)
    with open(path, "w", encoding="utf-8") as f:
       
        if file.endswith(".html"):
            f.write(f"<!-- {file} -->\n")
        elif file == "requirements.txt":
            f.write("Flask\npython-dotenv\n")
        elif file == "app.py":
            f.write("# Main Flask app\n")
        elif file == "config.py":
            f.write("# Config file\n")
        elif file == ".env":
            f.write("# Environment variables\n")
    print(f"Created file: {path}")

print("\nRecipe app folder structure created successfully!")
