import json
import os

USERS_FILE = 'users.json'

# Load existing users.json
if os.path.exists(USERS_FILE):
    with open(USERS_FILE, 'r') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print("Error: users.json is malformed.")
            data = {}
else:
    print("users.json not found.")
    data = {}

# Normalize users to new format
normalized = {}
for username, value in data.items():
    if isinstance(value, str):
        # Old format: just a password string
        normalized[username] = {"password": value, "profile_pic": None}
    elif isinstance(value, dict):
        # Already new format, just ensure profile_pic exists
        normalized[username] = {
            "password": value.get("password", ""),
            "profile_pic": value.get("profile_pic", None)
        }
    else:
        # Fallback
        normalized[username] = {"password": "", "profile_pic": None}

# Save back to users.json
with open(USERS_FILE, 'w') as f:
    json.dump(normalized, f, indent=4)

print(f"Converted {len(normalized)} users to the new format with profile_pic field.")
