import os
import cv2
import numpy as np
import base64
import hashlib
import random
import time
import datetime
import psycopg2
import psycopg2.extras
from psycopg2 import sql
import pickle
import secrets
import io
from dotenv import load_dotenv
from cryptography.fernet import Fernet
from werkzeug.security import generate_password_hash, check_password_hash
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    send_from_directory,
    send_file,
)
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from blockchain import Blockchain

app = Flask(__name__)
app.secret_key = "strict_security_key"
load_dotenv()
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024
app.config["UPLOAD_FOLDER"] = "static/uploads"

# --- EMAIL CONFIGURATION ---
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 465
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME", "hbavault@gmail.com")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD", "")
app.config["MAIL_USE_TLS"] = False
app.config["MAIL_USE_SSL"] = True

mail = Mail(app)
blockchain = Blockchain()

# --- BIOMETRIC INITIALIZATION ---
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)
# Use LBPH for texture-based recognition instead of color-based histograms
recognizer = cv2.face.LBPHFaceRecognizer_create()


# --- DATABASE AND HELPERS ---
def init_db():
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    # Users table
    c.execute(
        """CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, email TEXT, role TEXT, face_data BYTEA)"""
    )

    # Updated: Table now includes columns for limits and encryption
    c.execute(
        """CREATE TABLE IF NOT EXISTS file_permissions 
                 (filename TEXT, owner TEXT, authorized_receiver TEXT, file_hash TEXT,
                  max_downloads INTEGER DEFAULT 1, current_downloads INTEGER DEFAULT 0,
                  is_burned INTEGER DEFAULT 0, encryption_key TEXT)"""
    )
    
    # SQLite legacy logic removed. PostgreSQL creation is handled purely above natively.

    conn.commit()
    conn.close()


def hash_data(data):
    return hashlib.sha256(data.encode()).hexdigest()

def hash_file_bytes(filepath):
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        # Read and update hash in chunks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def get_face_roi(image_base64):
    """Extracts a grayscale face region for high-security texture analysis."""
    try:
        if not image_base64:
            return None
        encoded_data = image_base64.split(",")[1]
        nparr = np.frombuffer(base64.b64decode(encoded_data), np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Strict detection parameters
        faces = face_cascade.detectMultiScale(gray, 1.2, 5)

        if len(faces) == 0:
            return None

        (x, y, w, h) = faces[0]
        # Crop and resize to standard dimensions for the recognizer
        face_roi = cv2.resize(gray[y : y + h, x : x + w], (200, 200))
        return face_roi
    except Exception as e:
        print(f"AI DEBUG: Processing error: {e}")
        return None


init_db()

# --- ROUTES ---


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        email = request.form["email"]
        role = request.form["role"]
        image_data = request.form.get("face_data")

        face_roi = get_face_roi(image_data)
        if face_roi is None:
            flash("Biometric Enrollment Failed: No face detected.")
            return redirect(request.url)

        face_blob = pickle.dumps(face_roi)
        hashed_password = generate_password_hash(password)
        try:
            conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
            c = conn.cursor()
            c.execute(
                "INSERT INTO users (username, password, email, role, face_data) VALUES (%s, %s, %s, %s, %s)",
                (username, hashed_password, email, role, psycopg2.Binary(face_blob)),
            )
            conn.commit()
            conn.close()
            # Send welcome email
            try:
                welcome = Message(
                    "Welcome to HBA Vault — Account Created",
                    sender=app.config["MAIL_USERNAME"],
                    recipients=[email],
                )
                welcome.html = f"""
                <div style="font-family:Arial,sans-serif;max-width:540px;margin:auto;background:#05070f;color:#f1f5f9;border-radius:14px;overflow:hidden;border:1px solid rgba(99,202,255,0.15);">
                  <!-- Header -->
                  <div style="background:linear-gradient(135deg,#63caff,#a78bfa);padding:30px 32px;text-align:center;">
                    <div style="font-size:2.2rem;margin-bottom:8px;">&#x1F6E1;</div>
                    <h2 style="margin:0;color:#05070f;font-size:1.4rem;font-weight:800;letter-spacing:-0.02em;">Welcome to HBA Vault</h2>
                    <p style="margin:6px 0 0;color:rgba(5,7,15,0.7);font-size:0.82rem;">Your account has been successfully created</p>
                  </div>
                  <!-- Body -->
                  <div style="padding:28px 32px;">
                    <p style="margin:0 0 18px;font-size:0.96rem;">Hi <strong>{username}</strong>, you're all set!</p>
                    <!-- Account details table -->
                    <table style="width:100%;border-collapse:collapse;border-radius:10px;overflow:hidden;margin-bottom:20px;">
                      <tr>
                        <td style="padding:10px 14px;background:#0d1f3c;color:#63caff;font-family:monospace;font-size:0.78rem;width:38%;">Username</td>
                        <td style="padding:10px 14px;background:#0d1f3c;font-size:0.88rem;">{username}</td>
                      </tr>
                      <tr>
                        <td style="padding:10px 14px;background:#0a1628;color:#63caff;font-family:monospace;font-size:0.78rem;">Email</td>
                        <td style="padding:10px 14px;background:#0a1628;font-size:0.88rem;">{email}</td>
                      </tr>
                      <tr>
                        <td style="padding:10px 14px;background:#0d1f3c;color:#63caff;font-family:monospace;font-size:0.78rem;">Role</td>
                        <td style="padding:10px 14px;background:#0d1f3c;font-size:0.88rem;">{role.capitalize()}</td>
                      </tr>
                    </table>
                    <!-- Security note -->
                    <div style="background:rgba(251,191,36,0.07);border:1px solid rgba(251,191,36,0.2);border-radius:8px;padding:12px 14px;margin-bottom:20px;">
                      <p style="margin:0;font-size:0.78rem;color:#fbbf24;line-height:1.6;">
                        &#x1F512; <strong>Security reminder:</strong> Never share your password or OTP with anyone. HBA Vault staff will never ask for them.
                      </p>
                    </div>
                    <!-- What's next -->
                    <p style="margin:0 0 10px;font-size:0.82rem;color:rgba(241,245,249,0.55);">What's next?</p>
                    <ul style="margin:0 0 0 16px;padding:0;font-size:0.84rem;color:rgba(241,245,249,0.75);line-height:2;">
                      <li>Log in with your username and password</li>
                      <li>Complete facial biometric verification</li>
                      <li>Start securely {'uploading files' if role == 'sender' else 'receiving files'}</li>
                    </ul>
                  </div>
                  <!-- Footer -->
                  <div style="padding:14px 32px;background:#0a1628;display:flex;justify-content:space-between;align-items:center;">
                    <span style="font-size:0.72rem;color:#475569;">HBA Vault &mdash; Blockchain-Secured File Sharing</span>
                    <span style="font-size:0.72rem;color:#475569;">SRM Vadapalani, Chennai</span>
                  </div>
                </div>"""
                mail.send(welcome)
            except Exception as e:
                print(f"Welcome email error: {e}")
            flash("Registration Successful!", "success")
            return redirect(url_for("login"))
        except Exception as e:
            print(f"DATABASE/REGISTRATION ERROR: {e}")
            flash("Username taken or database error. Check logs.")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["pre_user"] = username
            session["role"] = user["role"]
            session["email"] = user["email"]
            return redirect(url_for("face_verify"))
        else:
            flash("Invalid Password")
    return render_template("login.html")


@app.route("/face_verify", methods=["GET", "POST"])
def face_verify():
    if "pre_user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        image_data = request.form.get("image")
        login_face = get_face_roi(image_data)

        conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute(
            "SELECT face_data, role FROM users WHERE username = %s",
            (session["pre_user"],),
        )
        user_row = c.fetchone()
        conn.close()

        if login_face is None:
            flash("Biometric Scan Failed: No face detected.")
            return redirect(url_for("face_verify"))

        is_match = False
        if user_row and user_row["face_data"]:
            stored_face = pickle.loads(user_row["face_data"])

            # Train the recognizer on the single stored face
            recognizer.train([stored_face], np.array([1]))
            # Predict returns [Label, Confidence]. LOWER confidence means BETTER match.
            label, confidence = recognizer.predict(login_face)

            print(
                f"SECURITY AUDIT: User '{session['pre_user']}' Confidence: {round(confidence, 2)}"
            )

            # Threshold: Usually confidence below 75 is a good match for LBPH
            if confidence < 75:
                is_match = True

        if is_match:
            session["username"] = session.pop("pre_user")
            blockchain.new_transaction(
                session["username"], "System", f'AUTH:SUCCESS:{session["role"]}'
            )
            blockchain.new_block(proof=123)
            return redirect(
                url_for(
                    "sender_dashboard"
                    if session["role"] == "sender"
                    else "receiver_dashboard"
                )
            )
        else:
            flash("Biometric Mismatch. Access Denied.")
            return redirect(url_for("login"))

    return render_template("face_verify.html")


# --- SENDER LOGIC ---
@app.route("/sender", methods=["GET", "POST"])
def sender_dashboard():
    if "username" not in session or session.get("role") != "sender":
        return redirect(url_for("login"))

    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT username FROM users WHERE role = 'receiver'")
    receivers = c.fetchall()
    conn.close()

    if request.method == "POST":
        file = request.files.get("file")
        target_receiver = request.form.get("target_receiver")

        if file and target_receiver:
            filename = secure_filename(file.filename)
            otp = str(secrets.randbelow(900000) + 100000)

            session["upload_otp"] = otp
            session["pending_filename"] = filename
            session["target_receiver"] = target_receiver
            session["max_downloads"] = int(request.form.get("max_downloads", 1))
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

            try:
                msg = Message(
                    "Upload Authorization",
                    sender=app.config["MAIL_USERNAME"],
                    recipients=[session["email"]],
                )
                msg.body = f"OTP to authorize upload of '{filename}' for receiver '{target_receiver}': {otp}"
                mail.send(msg)
                flash(f"OTP sent to {session['email']}.")
                return redirect(url_for("verify_upload"))
            except Exception as e:
                flash(f"Mail Error: {e}")

    user_history = [
        tx
        for block in blockchain.chain
        for tx in block["transactions"]
        if tx["sender"] == session["username"]
    ]
    return render_template("sender.html", receivers=receivers, history=user_history)

@app.route("/view_file/<filename>")
def view_file(filename):
    if "username" not in session:
        return redirect(url_for("login"))

    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute(
        "SELECT encryption_key, is_burned FROM file_permissions WHERE filename = %s AND (owner = %s OR authorized_receiver = %s)",
        (filename, session["username"], session["username"])
    )
    perm = c.fetchone()
    conn.close()

    if not perm or perm["is_burned"]:
        flash("File not found or has been burned.", "danger")
        return redirect(url_for("sender_dashboard" if session.get("role") == "sender" else "receiver_dashboard"))

    try:
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        
        if perm["encryption_key"]:
            f_crypto = Fernet(perm["encryption_key"].encode())
            with open(file_path, "rb") as enc_file:
                encrypted_data = enc_file.read()
            decrypted_data = f_crypto.decrypt(encrypted_data)
        else:
            with open(file_path, "rb") as regular_file:
                decrypted_data = regular_file.read()
        
        return send_file(
            io.BytesIO(decrypted_data),
            download_name=filename,
            as_attachment=False
        )
    except Exception as e:
        flash(f"Error viewing file: {e}", "danger")
        return redirect(url_for("sender_dashboard" if session.get("role") == "sender" else "receiver_dashboard"))



@app.route("/verify_upload", methods=["GET", "POST"])
def verify_upload():
    if "upload_otp" not in session:
        return redirect(url_for("sender_dashboard"))

    if request.method == "POST":
        user_otp = request.form.get("otp")

        if user_otp == session.get("upload_otp"):
            filename = session.pop("pending_filename")
            receiver = session.pop("target_receiver")
            session.pop("upload_otp", None)

            # 1. Generate the Digital Fingerprint (Hash) using file contents
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            current_file_hash = hash_file_bytes(file_path)

            max_dl = session.pop("max_downloads", 1)

            # 1.5 Encrypt the file for Zero-Knowledge Vault
            key = Fernet.generate_key()
            f = Fernet(key)
            with open(file_path, "rb") as file_to_enc:
                file_data = file_to_enc.read()
            encrypted_data = f.encrypt(file_data)
            with open(file_path, "wb") as file_to_enc:
                file_to_enc.write(encrypted_data)

            # 2. Save Hash and Permission to SQLite Database
            conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
            c = conn.cursor()
            c.execute(
                "INSERT INTO file_permissions (filename, owner, authorized_receiver, file_hash, max_downloads, encryption_key) VALUES (%s, %s, %s, %s, %s, %s)",
                (filename, session["username"], receiver, current_file_hash, max_dl, key.decode()),
            )
            conn.commit()
            conn.close()

            # 3. Save Hash to Blockchain Transaction
            blockchain.new_transaction(
                session["username"], receiver, f"FILE_HASH:{current_file_hash}"
            )
            blockchain.new_block(proof=12345)

            # 4. Send upload notification email to receiver
            try:
                conn_n = psycopg2.connect(os.environ.get("DATABASE_URL"))
                c_n = conn_n.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                c_n.execute("SELECT email FROM users WHERE username = %s", (receiver,))
                recv_row = c_n.fetchone()
                conn_n.close()

                if recv_row and recv_row["email"]:
                    timestamp = datetime.datetime.now().strftime("%d %b %Y, %I:%M %p")
                    notif = Message(
                        f"HBA Vault — New File Shared With You: {filename}",
                        sender=app.config["MAIL_USERNAME"],
                        recipients=[recv_row["email"]],
                    )
                    notif.html = f"""
                    <div style="font-family:Arial,sans-serif;max-width:540px;margin:auto;background:#05070f;color:#f1f5f9;border-radius:14px;overflow:hidden;border:1px solid rgba(99,202,255,0.15);">
                      <div style="background:linear-gradient(135deg,#63caff,#a78bfa);padding:28px 32px;text-align:center;">
                        <div style="font-size:2.2rem;margin-bottom:8px;">&#x1F4E5;</div>
                        <h2 style="margin:0;color:#05070f;font-size:1.3rem;font-weight:800;">New File Shared With You</h2>
                        <p style="margin:6px 0 0;color:rgba(5,7,15,0.7);font-size:0.82rem;">A sender has securely shared a file with your account</p>
                      </div>
                      <div style="padding:28px 32px;">
                        <p style="margin:0 0 18px;font-size:0.96rem;">Hi <strong>{receiver}</strong>,</p>
                        <p style="margin:0 0 18px;font-size:0.88rem;color:rgba(241,245,249,0.7);"><strong>{session['username']}</strong> has shared a file with you on HBA Vault. You can now request to download it after completing OTP verification.</p>
                        <table style="width:100%;border-collapse:collapse;border-radius:10px;overflow:hidden;margin-bottom:20px;">
                          <tr>
                            <td style="padding:10px 14px;background:#0d1f3c;color:#63caff;font-family:monospace;font-size:0.78rem;width:38%;">File Name</td>
                            <td style="padding:10px 14px;background:#0d1f3c;font-size:0.88rem;word-break:break-all;">{filename}</td>
                          </tr>
                          <tr>
                            <td style="padding:10px 14px;background:#0a1628;color:#63caff;font-family:monospace;font-size:0.78rem;">Shared By</td>
                            <td style="padding:10px 14px;background:#0a1628;font-size:0.88rem;">{session['username']}</td>
                          </tr>
                          <tr>
                            <td style="padding:10px 14px;background:#0d1f3c;color:#63caff;font-family:monospace;font-size:0.78rem;">Shared On</td>
                            <td style="padding:10px 14px;background:#0d1f3c;font-size:0.88rem;">{timestamp}</td>
                          </tr>
                        </table>
                        <div style="background:rgba(99,202,255,0.06);border:1px solid rgba(99,202,255,0.18);border-radius:10px;padding:14px 16px;margin-bottom:20px;">
                          <p style="margin:0 0 8px;font-size:0.8rem;color:#63caff;font-weight:700;">&#x2139;&#xFE0F; How to download</p>
                          <ol style="margin:0;padding-left:18px;font-size:0.82rem;color:rgba(241,245,249,0.65);line-height:2;">
                            <li>Log in to HBA Vault with your credentials</li>
                            <li>Complete facial biometric verification</li>
                            <li>Find the file on your Receiver Dashboard</li>
                            <li>Click <strong>Request Download</strong> and enter the OTP sent to your email</li>
                          </ol>
                        </div>
                        <div style="background:rgba(251,191,36,0.07);border:1px solid rgba(251,191,36,0.2);border-radius:8px;padding:12px 14px;">
                          <p style="margin:0;font-size:0.78rem;color:#fbbf24;line-height:1.6;">&#x1F512; <strong>Security reminder:</strong> Never share your OTP with anyone. HBA Vault staff will never ask for it.</p>
                        </div>
                      </div>
                      <div style="padding:14px 32px;background:#0a1628;display:flex;justify-content:space-between;">
                        <span style="font-size:0.72rem;color:#475569;">HBA Vault &mdash; Blockchain-Secured File Sharing</span>
                        <span style="font-size:0.72rem;color:#475569;">SRM Vadapalani, Chennai</span>
                      </div>
                    </div>"""
                    mail.send(notif)
                    print(f"Upload notification sent to {recv_row['email']}")
                else:
                    print(f"No email found for receiver: {receiver}")
            except Exception as e:
                print(f"Receiver notification email error: {e}")

            flash("Upload Authorized and Recorded on Blockchain!", "success")
            return redirect(url_for("sender_dashboard"))

        else:
            # FIX: If OTP is wrong, we MUST return a redirect or render
            flash("Invalid OTP. Please try again.", "danger")
            return render_template(
                "upload_verify.html",
                title="Authorize Upload",
                target=session.get("pending_filename"),
            )

    # Default GET request behavior
    return render_template(
        "upload_verify.html",
        title="Authorize Upload",
        target=session.get("pending_filename"),
    )


# --- RECEIVER LOGIC ---
@app.route("/receiver")
def receiver_dashboard():
    if "username" not in session or session.get("role") != "receiver":
        return redirect(url_for("login"))

    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute(
        "SELECT filename, max_downloads, current_downloads, is_burned FROM file_permissions WHERE authorized_receiver = %s",
        (session["username"],),
    )
    allowed_files = [dict(row) for row in c.fetchall()]
    conn.close()

    user_history = [
        tx
        for block in blockchain.chain
        for tx in block["transactions"]
        if tx["sender"] == session["username"] or tx["recipient"] == session["username"]
    ]

    return render_template("receiver.html", files=allowed_files, history=user_history)


@app.route("/request_download/<filename>")
def request_download(filename):
    if "username" not in session:
        return redirect(url_for("login"))

    if "email" not in session or not session["email"]:
        conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT email FROM users WHERE username = %s", (session["username"],))
        user = c.fetchone()
        conn.close()
        if user:
            session["email"] = user["email"]

    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute(
        "SELECT * FROM file_permissions WHERE filename = %s AND authorized_receiver = %s",
        (filename, session["username"]),
    )
    permission = c.fetchone()
    conn.close()

    if not permission:
        flash("Access Denied!")
        return redirect(url_for("receiver_dashboard"))

    if permission["is_burned"]:
        flash("This file has been burned and is no longer accessible.", "danger")
        return redirect(url_for("receiver_dashboard"))

    otp = str(secrets.randbelow(900000) + 100000)
    session["download_otp"] = otp
    session["target_file"] = filename

    print(f"DEBUG OTP for Download '{filename}': {otp}")
    try:
        msg = Message(
            "Download Authorization",
            sender=app.config["MAIL_USERNAME"],
            recipients=[session["email"]],
        )
        msg.body = f"OTP for secure download of '{filename}': {otp}"
        try:
            mail.send(msg)
            flash(f"OTP sent to {session['email']}.")
        except Exception as e:
            print(f"Mail delivery failed: {e}")
            flash("OTP generated. See console for OTP. (Email blocked by SMTP server)", "warning")
            
        return redirect(url_for("verify_download"))
    except Exception as e:
        flash(f"Verification preparation failed: {e}", "danger")

    return redirect(url_for("receiver_dashboard"))


@app.route("/verify_download", methods=["GET", "POST"])
def verify_download():
    if "download_otp" not in session:
        return redirect(url_for("receiver_dashboard"))

    if request.method == "POST":
        if request.form.get("otp") == session.get("download_otp"):
            filename = session.pop("target_file")
            session.pop("download_otp", None)

            blockchain.new_transaction("Network", session["username"], f"DL:{filename}")
            blockchain.new_block(proof=12345)

            # Handle decryption and limits
            try:
                conn_dl = psycopg2.connect(os.environ.get("DATABASE_URL"))
                c_dl = conn_dl.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                c_dl.execute(
                    "SELECT owner, max_downloads, current_downloads, encryption_key FROM file_permissions WHERE filename = %s AND authorized_receiver = %s",
                    (filename, session["username"])
                )
                perm = c_dl.fetchone()

                # Count how many times this receiver has downloaded this file
                dl_count = sum(
                    1 for block in blockchain.chain
                    for tx in block["transactions"]
                    if tx["recipient"] == session["username"] and f"DL:{filename}" in tx["amount"]
                )

                if perm:
                    new_curr = perm["current_downloads"] + 1
                    is_burned = 1 if new_curr >= perm["max_downloads"] else 0

                    c_dl.execute(
                        "UPDATE file_permissions SET current_downloads = %s, is_burned = %s WHERE filename = %s AND authorized_receiver = %s",
                        (new_curr, is_burned, filename, session["username"])
                    )
                    conn_dl.commit()

                    sender_name = perm["owner"]
                    enc_key = perm["encryption_key"]
                    c_dl.execute("SELECT email FROM users WHERE username = %s", (sender_name,))
                    sender_row = c_dl.fetchone()
                    conn_dl.close()

                    # -- Email Notification --
                    if sender_row and sender_row["email"]:
                        timestamp = datetime.datetime.now().strftime("%d %b %Y, %I:%M %p")
                        receipt = Message(
                            f"HBA Vault — Download Receipt: {filename}",
                            sender=app.config["MAIL_USERNAME"],
                            recipients=[sender_row["email"]],
                        )
                        receipt.html = f"""
                        <div style="font-family:Arial,sans-serif;max-width:540px;margin:auto;background:#05070f;color:#f1f5f9;border-radius:14px;overflow:hidden;border:1px solid rgba(99,202,255,0.15);">
                          <div style="background:linear-gradient(135deg,#34d399,#63caff);padding:28px 32px;text-align:center;">
                            <div style="font-size:2.2rem;margin-bottom:8px;">&#x2705;</div>
                            <h2 style="margin:0;color:#05070f;font-size:1.3rem;font-weight:800;">Your File Was Downloaded</h2>
                            <p style="margin:6px 0 0;color:rgba(5,7,15,0.7);font-size:0.82rem;">A receiver has successfully downloaded your shared file</p>
                          </div>
                          <div style="padding:28px 32px;">
                            <p style="margin:0 0 18px;font-size:0.96rem;">Hi <strong>{sender_name}</strong>,</p>
                            <p style="margin:0 0 18px;font-size:0.88rem;color:rgba(241,245,249,0.7);"><strong>{session['username']}</strong> has downloaded your file after completing OTP verification.</p>
                            <table style="width:100%;border-collapse:collapse;border-radius:10px;overflow:hidden;margin-bottom:20px;">
                              <tr>
                                <td style="padding:10px 14px;background:#0d1f3c;color:#63caff;font-family:monospace;font-size:0.78rem;width:38%;">File Name</td>
                                <td style="padding:10px 14px;background:#0d1f3c;font-size:0.88rem;word-break:break-all;">{filename}</td>
                              </tr>
                              <tr>
                                <td style="padding:10px 14px;background:#0a1628;color:#63caff;font-family:monospace;font-size:0.78rem;">Downloaded By</td>
                                <td style="padding:10px 14px;background:#0a1628;font-size:0.88rem;">{session['username']}</td>
                              </tr>
                              <tr>
                                <td style="padding:10px 14px;background:#0d1f3c;color:#63caff;font-family:monospace;font-size:0.78rem;">Downloaded On</td>
                                <td style="padding:10px 14px;background:#0d1f3c;font-size:0.88rem;">{timestamp}</td>
                              </tr>
                              <tr>
                                <td style="padding:10px 14px;background:#0a1628;color:#63caff;font-family:monospace;font-size:0.78rem;">Download Count</td>
                                <td style="padding:10px 14px;background:#0a1628;font-size:0.88rem;">#{new_curr} by {session['username']}</td>
                              </tr>
                            </table>
                            <div style="background:rgba(52,211,153,0.07);border:1px solid rgba(52,211,153,0.2);border-radius:10px;padding:14px 16px;">
                              <p style="margin:0;font-size:0.82rem;color:#34d399;line-height:1.6;">&#x1F4CB; This is an automated receipt. The download was OTP-verified and recorded on the blockchain ledger.</p>
                            </div>
                          </div>
                        </div>"""
                        try:
                            mail.send(receipt)
                        except Exception as e:
                            print(f"Receipt email failed: {e}")
                        
                    # -- Decrypt and Burn --
                    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                    
                    if enc_key:
                        f_crypto = Fernet(enc_key.encode())
                        with open(file_path, "rb") as enc_file:
                            encrypted_data = enc_file.read()
                        decrypted_data = f_crypto.decrypt(encrypted_data)
                    else:
                        with open(file_path, "rb") as regular_file:
                            decrypted_data = regular_file.read()

                    # Auto-Burn Mechanism
                    if is_burned:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                        blockchain.new_transaction("Network", "Burn Address", f"BURN:{filename}")
                        blockchain.new_block(proof=12345)
                    
                    return send_file(
                        io.BytesIO(decrypted_data),
                        download_name=filename,
                        as_attachment=True
                    )
                else:
                    conn_dl.close()
            except Exception as e:
                print(f"Decryption/Download error: {e}")
                flash("Failed to process the download. File might be burned.", "danger")
                return redirect(url_for("receiver_dashboard"))


        flash("Incorrect OTP.", "danger")
    return render_template(
        "upload_verify.html",
        title="Authorize Download",
        target=session.get("target_file"),
    )


@app.route("/request_burn/<filename>")
def request_burn(filename):
    if "username" not in session or session.get("role") != "receiver":
        return redirect(url_for("login"))

    if "email" not in session or not session["email"]:
        conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT email FROM users WHERE username = %s", (session["username"],))
        user = c.fetchone()
        conn.close()
        if user:
            session["email"] = user["email"]

    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute(
        "SELECT is_burned FROM file_permissions WHERE filename = %s AND authorized_receiver = %s",
        (filename, session["username"]),
    )
    permission = c.fetchone()
    conn.close()

    if not permission or permission[0]:
        flash("Access Denied or file already burned!")
        return redirect(url_for("receiver_dashboard"))

    otp = str(secrets.randbelow(900000) + 100000)
    session["burn_otp"] = otp
    session["target_burn_file"] = filename

    print(f"DEBUG OTP for Burn '{filename}': {otp}")
    try:
        msg = Message(
            "Manual Burn Verification",
            sender=app.config["MAIL_USERNAME"],
            recipients=[session["email"]],
        )
        msg.body = f"OTP to manually DESTROY '{filename}': {otp}"
        try:
            mail.send(msg)
            flash(f"Burn OTP sent to {session['email']}.")
        except Exception as e:
            print(f"Mail delivery failed: {e}")
            flash("OTP generated. See console for OTP. (Email blocked by SMTP server)", "warning")
        return redirect(url_for("verify_burn"))
    except Exception as e:
        flash(f"Verification preparation failed: {e}", "danger")

    return redirect(url_for("receiver_dashboard"))


@app.route("/verify_burn", methods=["GET", "POST"])
def verify_burn():
    if "burn_otp" not in session:
        return redirect(url_for("receiver_dashboard"))

    if request.method == "POST":
        if request.form.get("otp") == session.get("burn_otp"):
            filename = session.pop("target_burn_file")
            session.pop("burn_otp", None)

            # Mark as burned in DB and delete file
            conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
            c = conn.cursor()
            c.execute(
                "UPDATE file_permissions SET is_burned = 1, current_downloads = max_downloads WHERE filename = %s AND authorized_receiver = %s",
                (filename, session["username"])
            )
            conn.commit()
            conn.close()

            file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            if os.path.exists(file_path):
                os.remove(file_path)

            blockchain.new_transaction("Network", session["username"], f"MANUAL_BURN:{filename}")
            blockchain.new_block(proof=12345)

            flash(f"File {filename} has been securely destroyed.", "success")
            return redirect(url_for("receiver_dashboard"))

        flash("Incorrect OTP.", "danger")
    
    return render_template(
        "upload_verify.html",
        title="Authorize Manual Burn",
        target=session.get("target_burn_file"),
    )


@app.route("/explorer")
def blockchain_explorer():
    if "username" not in session:
        return redirect(url_for("login"))
    chain = blockchain.chain[::-1]
    
    display_chain = []
    for b in chain:
        b_copy = b.copy()
        b_copy["hash"] = blockchain.hash(b)
        
        if isinstance(b_copy["timestamp"], float):
            b_copy["timestamp_str"] = datetime.datetime.fromtimestamp(b_copy["timestamp"]).strftime('%Y-%m-%d %H:%M:%S')
        else:
            b_copy["timestamp_str"] = str(b_copy["timestamp"])
            
        display_chain.append(b_copy)
        
    return render_template("explorer.html", chain=display_chain)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    if not os.path.exists(app.config["UPLOAD_FOLDER"]):
        os.makedirs(app.config["UPLOAD_FOLDER"])
    app.run(debug=True)