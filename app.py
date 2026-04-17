from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
import smtplib
import random 
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from werkzeug.utils import secure_filename

# --- DATABASE TOOLS ---
from pymongo import MongoClient
from bson.objectid import ObjectId

app = Flask(__name__)
import os

@app.route('/debug')
def debug():
    # This will list everything inside your templates folder
    try:
        files = os.listdir('templates/customer')
        return f"I found the customer folder! Inside are: {files}"
    except Exception as e:
        return f"Error: I can't even find the folder. Error message: {e}"
# --- THE HANDSHAKE TOOL (CORS) ---
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# Allow up to 16MB for image uploads
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

# --- FESTIVE UPLOAD CONFIG ---
FESTIVE_UPLOAD_FOLDER = 'static/uploads/festive'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

if not os.path.exists(FESTIVE_UPLOAD_FOLDER):
    os.makedirs(FESTIVE_UPLOAD_FOLDER)

app.config['FESTIVE_UPLOAD_FOLDER'] = FESTIVE_UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- EMAIL CONFIGURATION ---
EMAIL_SENDER = "simeonjohn118@gmail.com" 
EMAIL_PASSWORD = "qvsmwldprxaktxri" 
EMAIL_RECEIVER = "simeonjohn118@gmail.com" 

# --- MONGODB CLOUD SETUP ---
MONGO_URI = "mongodb+srv://simeonjohn118_db_user:Simeon3991@cluster0.9j6otzp.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client['oxela_kitchen']
menu_collection = db['menu']

# --- DATABASE SETUP ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

USERS_DB = os.path.join(BASE_DIR, 'users.json')
ORDERS_DB = os.path.join(BASE_DIR, 'orders.json')
SPECIAL_ORDERS_DB = os.path.join(BASE_DIR, 'special_orders.json')
MENU_DB = os.path.join(BASE_DIR, 'menu.json') 
STAFF_DB = os.path.join(BASE_DIR, 'staff.json') 
MESSAGES_DB = os.path.join(BASE_DIR, 'messages.json')
COMPLAINTS_DB = os.path.join(BASE_DIR, 'complaints.json')
CONFIG_DB = os.path.join(BASE_DIR, 'config.json') 
DELIVERY_DB = os.path.join(BASE_DIR, 'delivery_zones.json')

# --- FILE INITIALIZER ---
for db_file in [USERS_DB, ORDERS_DB, SPECIAL_ORDERS_DB, MENU_DB, STAFF_DB, MESSAGES_DB, COMPLAINTS_DB, DELIVERY_DB]:
    if not os.path.exists(db_file):
        with open(db_file, 'w') as f:
            json.dump([], f)

if not os.path.exists(CONFIG_DB):
    with open(CONFIG_DB, 'w') as f:
        json.dump({
            "open_time": "08:00", 
            "close_time": "22:00", 
            "manual_closed": False,
            "promo_type": "None",
            "discount_percent": 0
        }, f)

pending_verifications = {}
password_reset_codes = {}

def load_data(file_path):
    if not os.path.exists(file_path): return []
    try:
        with open(file_path, 'r') as f: return json.load(f)
    except: return []

def save_data(file_path, data):
    with open(file_path, 'w') as f: json.dump(data, f, indent=4)

# --- HELPER FOR MONGODB ---
def get_all_menu_from_db():
    items = list(menu_collection.find())
    for item in items:
        item['id'] = str(item['_id'])
        del item['_id']
    return items

# --- PWA & ASSET ROUTES ---

@app.route('/manifest.json')
def serve_manifest():
    static_path = os.path.join(BASE_DIR, 'static')
    response = send_from_directory(static_path, 'manifest.json', mimetype='application/manifest+json')
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

@app.route('/favicon.ico')
def favicon():
    icon_path = os.path.join(BASE_DIR, 'static', 'icons')
    return send_from_directory(icon_path, 'icon-512.png', mimetype='image/png')

# --- SOCIAL PROOF TICKER ROUTE ---
@app.route('/get_order_ticker', methods=['GET'])
def get_order_ticker():
    orders = load_data(ORDERS_DB)
    recent = orders[-10:] 
    ticker_data = []
    for o in recent:
        name = o.get('customer_name', 'A Customer')
        masked_name = name[0] + "***" + name[-1] if len(name) > 2 else "User"
        ticker_data.append({
            "msg": f"{masked_name} just ordered a {o.get('total')} combo! 🔥",
            "time": o.get('timestamp')
        })
    return jsonify(ticker_data[::-1]), 200

# --- DELIVERY ZONE ROUTES ---

@app.route('/get_delivery_zones', methods=['GET'])
def get_delivery_zones():
    zones = load_data(DELIVERY_DB)
    return jsonify(zones), 200

@app.route('/update_delivery_zone', methods=['POST'])
def update_delivery_zone():
    data = request.json
    zones = load_data(DELIVERY_DB)
    location = data.get('location')
    price = data.get('price')
    zone_id = data.get('id')

    if zone_id: 
        for z in zones:
            if str(z.get('id')) == str(zone_id):
                z['location'] = location
                z['price'] = price
                break
    else: 
        new_zone = {
            "id": str(len(zones) + 1),
            "location": location,
            "price": price
        }
        zones.append(new_zone)
    
    save_data(DELIVERY_DB, zones)
    return jsonify({"status": "success"}), 200

# --- ADMIN NEGOTIATION ROUTES ---

@app.route('/get_all_special_orders', methods=['GET'])
def get_all_special_orders():
    specials = load_data(SPECIAL_ORDERS_DB)
    return jsonify(specials), 200

@app.route('/get_order_details/<order_id>', methods=['GET'])
def get_order_details(order_id):
    specials = load_data(SPECIAL_ORDERS_DB)
    order = next((o for o in specials if o.get('order_id') == order_id), None)
    if order: return jsonify(order), 200
    return jsonify({"error": "Order not found"}), 404

@app.route('/admin_reply_special', methods=['POST'])
def admin_reply_special():
    data = request.json
    order_id = data.get('order_id')
    reply = data.get('reply')
    specials = load_data(SPECIAL_ORDERS_DB)
    found = False
    for o in specials:
        if o.get('order_id') == order_id:
            o['admin_reply'] = reply
            o['status'] = 'REVIEWING'
            found = True
            break
    if found:
        save_data(SPECIAL_ORDERS_DB, specials)
        return jsonify({"status": "success", "message": "Reply sent to customer"}), 200
    return jsonify({"status": "error", "message": "Order ID not found"}), 404

# --- STORE CONFIG ROUTES ---

@app.route('/get_store_status', methods=['GET'])
def get_store_status():
    config = load_data(CONFIG_DB)
    return jsonify({"config": config}), 200

@app.route('/update_store_config', methods=['POST'])
def update_store_config():
    data = request.json
    save_data(CONFIG_DB, data)
    return jsonify({"status": "success"}), 200

def send_smtp_email(target_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
        msg['To'] = target_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"❌ Email failed: {e}")
        return False

def send_order_notification(order_data, order_type="REGULAR"):
    subject = f"🔔 NEW {order_type} ORDER: {order_data['order_id']} ({order_data['status']})"
    body = f"O'XELA KITCHEN - New Request Received\n{'='*30}\n"
    body += f"Status: {order_data['status']}\nOrder ID: {order_data['order_id']}\n"
    body += f"Account: {order_data.get('user_email', 'N/A')}\n"
    body += f"Customer: {order_data.get('customer_name', 'Unknown')}\n"
    body += f"Phone: {order_data.get('customer_phone', 'Unknown')}\n"
    if order_type == "SPECIAL":
        body += f"Details: {order_data.get('description')}\nBudget: {order_data.get('budget', 'Not Specified')}\n"
    elif order_type == "COMPLAINT":
        body += f"Issue: {order_data.get('issue')}\n"
    else:
        body += f"Total: {order_data.get('total')}\nAddress: {order_data.get('delivery_address', 'N/A')}\n"
        items = order_data.get('items', [])
        if items:
            body += "\nItems Ordered:\n"
            for item in items:
                qty = item.get('quantity', 1)
                body += f"- {item.get('name')} (Qty: {qty}) - {item.get('price')}\n"
    send_smtp_email(EMAIL_RECEIVER, subject, body)

@app.route('/get_menu', methods=['GET'])
def get_menu():
    try:
        # NOW FETCHING FROM CLOUD DB
        return jsonify(get_all_menu_from_db()), 200
    except Exception as e:
        return jsonify({"message": f"Error loading menu: {str(e)}"}), 500

@app.route('/send_verification', methods=['POST'])
def send_verification():
    email = request.json.get('email')
    if not email: return jsonify({"message": "Email is required"}), 400
    code = str(random.randint(100000, 999999))
    pending_verifications[email] = code
    body = f"Hello,\n\nYour O'Xela Kitchen registration code is: {code}"
    if send_smtp_email(email, f"Verify Your Account: {code}", body):
        return jsonify({"message": "Code sent successfully!"}), 200
    else:
        return jsonify({"message": "Email server busy", "status": "debug", "test_code": code}), 200

@app.route('/forgot_password', methods=['POST'])
def forgot_password():
    email = request.json.get('email')
    users = load_data(USERS_DB)
    if not any(u.get('email') == email for u in users):
        return jsonify({"message": "Email not found", "status": "error"}), 404
    code = str(random.randint(100000, 999999))
    password_reset_codes[email] = code
    body = f"Your password reset code is: {code}"
    if send_smtp_email(email, "Password Reset Code", body):
        return jsonify({"message": "Code sent!"}), 200
    return jsonify({"message": "Check terminal for code", "status": "debug"}), 200

@app.route('/reset_password', methods=['POST'])
def reset_password():
    data = request.json
    email, code, new_pass = data.get('email'), data.get('code'), data.get('new_password')
    if password_reset_codes.get(email) != code:
        return jsonify({"message": "Invalid code"}), 400
    users = load_data(USERS_DB)
    for u in users:
        if u.get('email') == email:
            u['password'] = new_pass
            break
    save_data(USERS_DB, users)
    if email in password_reset_codes: del password_reset_codes[email]
    return jsonify({"message": "Password updated!", "status": "success"}), 200

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    email = data.get('email')
    if pending_verifications.get(email) != data.get('verification_code'):
        return jsonify({"message": "Invalid code"}), 400
    users = load_data(USERS_DB)
    if any(u.get('email') == email for u in users):
        return jsonify({"message": "User exists"}), 400
    if email in pending_verifications: del pending_verifications[email]
    users.append(data)
    save_data(USERS_DB, users)
    return jsonify({"status": "success"}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    input_email = str(data.get('email', '')).strip().lower()
    input_password = str(data.get('password', '')).strip()
    users = load_data(USERS_DB)
    user = next((u for u in users if 
                  str(u.get('email', '')).strip().lower() == input_email and 
                  str(u.get('password', '')).strip() == input_password), None)
    if user: return jsonify({"status": "success", "user": user}), 200
    return jsonify({"message": "Invalid login"}), 401

@app.route('/submit_order', methods=['POST'])
def submit_order():
    data = request.json
    orders = load_data(ORDERS_DB)
    
    # Updated Stock logic for MongoDB
    for cart_item in data.get('items', []):
        db_item = menu_collection.find_one({'_id': ObjectId(cart_item.get('id'))})
        if db_item:
            current_stock = int(db_item.get('quantity', 0))
            order_qty = int(cart_item.get('quantity', 1))
            if current_stock < order_qty:
                return jsonify({"message": f"Sorry, {db_item.get('name')} just sold out!"}), 400
            menu_collection.update_one({'_id': db_item['_id']}, {'$set': {'quantity': current_stock - order_qty}})

    now = datetime.now()
    all_combined = orders + load_data(SPECIAL_ORDERS_DB)
    today_str = now.strftime('%Y-%m-%d')
    today_count = len([o for o in all_combined if str(o.get('timestamp', '')).startswith(today_str)])
    
    data['order_id'] = f"OX-{now.strftime('%Y%m%d')}-{(today_count + 1):03d}"
    data['timestamp'] = now.strftime("%Y-%m-%d %H:%M:%S")
    data['status'] = "PENDING"
    
    if 'user_email' not in data: return jsonify({"message": "User session missing"}), 400
    
    orders.append(data)
    save_data(ORDERS_DB, orders)
    send_order_notification(data, "REGULAR")
    return jsonify({"status": "success", "order_id": data['order_id'], "order_status": "PENDING"}), 201

@app.route('/submit_special_order', methods=['POST'])
def submit_special_order():
    data = request.json
    specials = load_data(SPECIAL_ORDERS_DB)
    orders = load_data(ORDERS_DB)
    now = datetime.now()
    all_combined = orders + specials
    today_str = now.strftime('%Y-%m-%d')
    today_count = len([o for o in all_combined if str(o.get('timestamp', '')).startswith(today_str)])
    data['order_id'] = f"SP-{now.strftime('%Y%m%d')}-{(today_count + 1):03d}"
    data['timestamp'] = now.strftime("%Y-%m-%d %H:%M:%S")
    data['status'] = "PENDING"
    specials.append(data)
    save_data(SPECIAL_ORDERS_DB, specials)
    send_order_notification(data, "SPECIAL")
    return jsonify({"status": "success", "order_id": data['order_id'], "order_status": "PENDING"}), 201

@app.route('/submit_complaint', methods=['POST'])
def submit_complaint():
    data = request.json
    complaints = load_data(COMPLAINTS_DB)
    now = datetime.now()
    data['order_id'] = f"CMP-{now.strftime('%Y%m%d')}-{random.randint(100, 999)}"
    data['timestamp'] = now.strftime("%Y-%m-%d %H:%M:%S")
    data['status'] = "OPEN"
    complaints.append(data)
    save_data(COMPLAINTS_DB, complaints)
    send_order_notification(data, "COMPLAINT")
    return jsonify({"status": "success", "order_id": data['order_id']}), 201

@app.route('/user_orders/<email>', methods=['GET'])
def get_user_orders(email):
    orders = load_data(ORDERS_DB)
    specials = load_data(SPECIAL_ORDERS_DB)
    combined = [o for o in orders if o.get('user_email') == email] + \
                [s for s in specials if s.get('user_email') == email]
    return jsonify(combined), 200

@app.route('/get_profile/<email>', methods=['GET'])
def get_profile(email):
    users = load_data(USERS_DB)
    user = next((u for u in users if u.get('email') == email), None)
    if user:
        return jsonify({
            "name": user.get('name'), "email": user.get('email'),
            "phone": user.get('phone'), "address": user.get('address')
        }), 200
    return jsonify({"message": "User not found"}), 404

@app.route('/update_profile', methods=['POST'])
def update_profile_data():
    data = request.json
    email = data.get('email')
    users = load_data(USERS_DB)
    for user in users:
        if user.get('email') == email:
            user['name'] = data.get('name', user.get('name'))
            user['phone'] = data.get('phone', user.get('phone'))
            user['address'] = data.get('address', user.get('address'))
            save_data(USERS_DB, users)
            return jsonify({"status": "success", "message": "Profile updated!"}), 200
    return jsonify({"status": "error", "message": "User not found"}), 404

@app.route('/admin_register', methods=['POST'])
def admin_register():
    data = request.json
    staff = load_data(STAFF_DB)
    if any(s.get('email') == data.get('email') for s in staff):
        return jsonify({"error": "Admin already exists"}), 400
    staff.append(data)
    save_data(STAFF_DB, staff)
    return jsonify({"message": "Registration successful", "name": data.get('name')}), 201

@app.route('/admin_login', methods=['POST'])
def admin_login():
    data = request.json
    staff = load_data(STAFF_DB)
    user = next((s for s in staff if s.get('email') == data.get('email') and s.get('password') == data.get('password')), None)
    if user: return jsonify({"message": "Login successful", "name": user.get('name')}), 200
    return jsonify({"error": "Invalid email or password"}), 401

@app.route('/update_menu_item', methods=['POST'])
def update_menu_item():
    try:
        data = request.json
        item_id = data.get('id')
        if item_id:
            update_fields = {k: v for k, v in data.items() if k != 'id'}
            # Ensure number types
            if 'price' in update_fields: update_fields['price'] = int(update_fields['price'])
            if 'quantity' in update_fields: update_fields['quantity'] = int(update_fields['quantity'])
            
            menu_collection.update_one({'_id': ObjectId(item_id)}, {'$set': update_fields})
            return jsonify({"status": "success", "message": "Menu updated!"}), 200
        return jsonify({"error": "No ID provided"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/add_menu_item', methods=['POST'])
def add_menu_item():
    try:
        data = request.json
        if 'image' not in data: data['image'] = ""
        if 'quantity' not in data: data['quantity'] = 0
        if 'category' not in data: data['category'] = "Main"
        
        # Numbers check
        data['quantity'] = int(data['quantity'])
        data['price'] = int(data['price'])
        
        result = menu_collection.insert_one(data)
        return jsonify({"status": "success", "id": str(result.inserted_id)}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/delete_menu_item/<item_id>', methods=['DELETE'])
def delete_menu_item(item_id):
    try:
        result = menu_collection.delete_one({'_id': ObjectId(item_id)})
        if result.deleted_count > 0:
            return jsonify({"success": True}), 200
        return jsonify({"error": "Item not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_all_orders', methods=['GET'])
def get_all_orders():
    return jsonify({"regular": load_data(ORDERS_DB), "special": load_data(SPECIAL_ORDERS_DB), "complaints": load_data(COMPLAINTS_DB)}), 200

@app.route('/confirm_order', methods=['POST'])
def confirm_order():
    data = request.json
    order_id, new_status = data.get('order_id'), data.get('status', 'SUCCESSFUL')
    for db_path in [ORDERS_DB, SPECIAL_ORDERS_DB, COMPLAINTS_DB]:
        items = load_data(db_path)
        for i in items:
            if i.get('order_id') == order_id:
                i['status'] = new_status
                save_data(db_path, items)
                return jsonify({"status": "success"}), 200
    return jsonify({"status": "error"}), 404

@app.route('/get_sales_stats', methods=['GET'])
def get_sales_stats():
    orders = load_data(ORDERS_DB)
    specials = load_data(SPECIAL_ORDERS_DB)
    all_completed = [o for o in (orders + specials) if o.get('status') == "SUCCESSFUL"]
    today_str = datetime.now().strftime('%Y-%m-%d')
    daily_revenue = total_revenue = 0
    monthly_groups = {}
    for o in all_completed:
        val = str(o.get('total') or o.get('budget') or '0').replace('₦', '').replace(',', '').strip()
        amount = int(float(val)) if val else 0
        total_revenue += amount
        if str(o.get('timestamp', '')).startswith(today_str): daily_revenue += amount
        try: month_key = datetime.strptime(o.get('timestamp'), "%Y-%m-%d %H:%M:%S").strftime("%B %Y")
        except: month_key = "Unknown Period"
        if month_key not in monthly_groups: monthly_groups[month_key] = {"total": 0, "transactions": []}
        monthly_groups[month_key]["total"] += amount
        monthly_groups[month_key]["transactions"].append(o)
    return jsonify({"daily_revenue": daily_revenue, "total_revenue": total_revenue, "monthly_data": monthly_groups}), 200

@app.route('/send_message', methods=['POST'])
def send_message():
    data = request.json
    order_id = data.get('order_id', '')
    if order_id.startswith('OX-'): return jsonify({"message": "Chat disabled for regular orders."}), 403
    messages = load_data(MESSAGES_DB)
    new_msg = {"order_id": order_id, "sender": data.get('sender'), "text": data.get('text'), "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    messages.append(new_msg)
    save_data(MESSAGES_DB, messages)
    return jsonify({"status": "success"}), 201

@app.route('/get_chat/<order_id>', methods=['GET'])
def get_chat(order_id):
    all_messages = load_data(MESSAGES_DB)
    return jsonify([m for m in all_messages if m.get('order_id') == order_id])

@app.route('/get_active_chats', methods=['GET'])
def get_active_chats():
    try:
        all_messages = load_data(MESSAGES_DB)
        all_complaints = load_data(COMPLAINTS_DB)
        unique_chats = {}
        for c in all_complaints:
            oid = c.get('order_id')
            if oid:
                unique_chats[oid] = {
                    "order_id": oid, 
                    "last_msg": c.get('issue', 'New Complaint'),
                    "timestamp": c.get('timestamp', '')
                }
        for m in all_messages:
            oid = m.get('order_id')
            if oid:
                unique_chats[oid] = {
                    "order_id": oid, 
                    "last_msg": m.get('text', ''),
                    "timestamp": m.get('timestamp', '')
                }
        sorted_chats = sorted(
            unique_chats.values(), 
            key=lambda x: x.get('timestamp', ''), 
            reverse=True
        )
        return jsonify(sorted_chats)
    except Exception as e:
        print(f"Error fetching active chats: {e}")
        return jsonify([])

@app.route('/static/image/kitchen.jpeg.png')
def serve_hero_image():
    return send_from_directory(os.path.join(BASE_DIR, 'static'), 'Kitchen.jpeg', mimetype='image/jpeg')

@app.route('/<path:path>')
def serve_any_file(path):
    return send_from_directory(BASE_DIR, path)

@app.route('/logout')
def logout_redirect():
    return root()

@app.route('/reduce_stock', methods=['POST'])
def reduce_stock():
    data = request.json
    item_id = data.get('id')
    reduce_by = int(data.get('reduceBy', 1))

    # MongoDB: $inc with a negative number reduces the value
    result = db.menu.update_one(
        {"id": item_id},
        {"$inc": {"quantity": -reduce_by}}
    )

    if result.modified_count > 0:
        return jsonify({"success": True}), 200
    return jsonify({"error": "Item not found"}), 404

# --- DYNAMIC FESTIVE LOGIC ---

# Storage for festive settings
festive_config = {
    "active": False,
    "title": "Hungry? Order Now!",
    "image_url": "https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=500&q=60",
    "theme_color": "#e67e22"
}

# Serve the uploaded festive images
@app.route('/static/uploads/festive/<filename>')
def serve_festive_image(filename):
    return send_from_directory(app.config['FESTIVE_UPLOAD_FOLDER'], filename)

# Website gets settings
@app.route('/get_festive_settings', methods=['GET'])
def get_festive_settings():
    return jsonify(festive_config)

@app.route('/')
def login_page():
    # This makes index.html (your login) the very first page
    return render_template('customer/index.html')

import os
from flask import Flask, render_template # ensure these are imported

@app.route('/home')
def customer_home():
    # Construct the path to check if the file exists
    template_path = os.path.join('templates', 'customer', 'home.html')
    if not os.path.exists(template_path):
        return f"ERROR: File not found at {template_path}. Check your folder names!", 404
    return render_template('customer/home.html')

@app.route('/admin_hub')
def admin_hub_view():
    template_path = os.path.join('templates', 'master', 'admin_hub.html')
    if not os.path.exists(template_path):
        return f"ERROR: File not found at {template_path}. Check your folder names!", 404
    return render_template('master/admin_hub.html')

# Master App updates settings (with image upload)
@app.route('/update_festive', methods=['POST'])
def handle_festive_save():  # I changed the name from 'update_festive' to 'handle_festive_save'
    global festive_config
    
    # Handle Image Upload if present
    if 'image' in request.files:
        file = request.files['image']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['FESTIVE_UPLOAD_FOLDER'], filename))
            # Build URL for your Render app
            festive_config['image_url'] = f"https://oxela-kitchen.onrender.com/static/uploads/festive/{filename}"

    # Update text and toggle from Form Data
    festive_config['active'] = request.form.get('active') == 'true'
    festive_config['title'] = request.form.get('title', festive_config['title'])
    festive_config['theme_color'] = request.form.get('theme_color', festive_config['theme_color'])
    
    return jsonify({"message": "Festive theme updated successfully!", "current": festive_config})
# 1. THE FACE: This shows you the Master Dashboard
@app.route('/oxela_admin_panel') 
def master_dashboard():
    # We tell Flask to look specifically in the 'master' subfolder
    return render_template('master/settings.html')
    
    # ... (All your existing code for handling images and form data) ...
    
    return jsonify({"message": "Festive theme updated successfully!", "current": festive_config})



if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"O'XELA KITCHEN PRO STARTING ON PORT {port}...")
    app.run(host='0.0.0.0', port=port)