# 🛡️ Blockchain-Assisted Privacy-Preserving Secure File Sharing

> A full-stack secure file sharing system that combines **facial biometric authentication**, **email OTP verification**, and an **immutable blockchain ledger** to ensure only the right person can access your files.

---

## 📌 Table of Contents

- [About the Project](#about-the-project)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [System Architecture](#system-architecture)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [How It Works](#how-it-works)
- [Email Notifications](#email-notifications)
- [Blockchain Ledger](#blockchain-ledger)
- [Security Design](#security-design)
- [Screenshots](#screenshots)
- [Author](#author)

---

## About the Project

**HBA Vault** is a privacy-first file sharing platform built as an academic project at **SRM Institute of Science and Technology, Vadapalani**. It addresses the critical limitations of conventional file sharing systems — which rely solely on passwords — by introducing a **multi-layered security model**:

1. Password-based login
2. Live facial biometric verification (LBPH algorithm)
3. Email OTP confirmation for every upload and download
4. SHA-256 file fingerprinting recorded on an in-memory blockchain

Every action taken on the platform — login, upload, download — is immutably recorded as a blockchain transaction, creating a tamper-proof audit trail.

---

## Features

### 🔐 Authentication
- Two-step login: **password + live facial recognition**
- Face enrolment during registration using the device camera
- LBPH (Local Binary Pattern Histogram) face recogniser with a confidence threshold of < 75
- Haar Cascade face detection for strict face region extraction

### 📤 Sender Dashboard
- Upload files to a specific registered receiver
- Email OTP sent to the sender to authorise every upload
- SHA-256 hash generated and stored for file integrity verification
- All upload events recorded on the blockchain

### 📥 Receiver Dashboard
- View all files shared specifically with your account
- Email OTP sent to the receiver before every download
- File type icons for quick identification (PDF, image, Word, Excel, ZIP, video, etc.)
- Colour-coded download limit badges (unlimited / X of Y used / limit reached)
- In-browser file preview via the View button

### 📧 Email Notifications
- **Welcome email** on successful registration with account details
- **Upload notification** to the receiver when a file is shared with them (includes filename, sender, SHA-256 hash, how-to-download guide)
- **OTP emails** for upload and download authorisation

### 🔗 Blockchain Ledger
- Custom Python blockchain (`blockchain.py`) records every login, upload, and download
- Each transaction stores: sender, recipient, action type, timestamp
- Full transaction history visible on both dashboards

### 🎨 UI / UX
- Premium dark glassmorphism design (near-black background, cyan + violet accents)
- Syne + Space Mono typography
- Animated grid overlay, ambient orbs, particle system
- Smooth page transitions on every navigation link
- Slide-in toast notifications for all flash messages (green/red/blue/yellow)
- Responsive layout — works on desktop and mobile

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3, Flask |
| Database | SQLite (`users.db`) |
| Face Recognition | OpenCV (`cv2`), LBPH Face Recogniser |
| Email | Flask-Mail, Gmail SMTP (SSL, port 465) |
| Blockchain | Custom Python implementation |
| Frontend | HTML5, CSS3, Bootstrap 5, Font Awesome 6 |
| Fonts | Google Fonts — Syne, Space Mono |
| File Handling | Werkzeug `secure_filename` |

---

## System Architecture

```
User Browser
     │
     ▼
┌─────────────────────────────────────┐
│           Flask Web App             │
│                                     │
│  /register  →  Face Enrolment       │
│  /login     →  Password Check       │
│  /face_verify → LBPH Biometric     │
│  /sender    →  Upload + OTP         │
│  /receiver  →  Download + OTP       │
│  /verify_upload / /verify_download  │
└──────────┬──────────────────────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
SQLite DB    Blockchain
(users,      (in-memory
 files,       chain of
 hashes)      blocks)
    │
    ▼
Gmail SMTP
(welcome / OTP / upload notification emails)
```

---

## Project Structure

```
hba-vault/
│
├── app.py                    # Main Flask application
├── blockchain.py             # Custom blockchain implementation
├── users.db                  # SQLite database (auto-created)
│
├── static/
│   ├── logo.png              # HBA Vault logo
│   └── uploads/              # Uploaded files stored here
│
└── templates/
    ├── base.html             # Base layout (index, face_verify)
    ├── layout.html           # Auth layout (login, register, OTP)
    ├── index.html            # Landing page
    ├── login.html            # Login page
    ├── register.html         # Registration + face enrolment
    ├── face_verify.html      # Biometric verification (step 2)
    ├── sender.html           # Sender dashboard
    ├── receiver.html         # Receiver dashboard
    ├── upload_verify.html    # OTP verification (upload & download)
    └── verify.html           # Legacy verify page
```

---

## Getting Started

### Prerequisites

- Python 3.8+
- pip
- A Gmail account with an **App Password** enabled (not your regular Gmail password)

### Installation

**1. Clone the repository**
```bash
git clone https://github.com/hari1715/hba-vault.git
cd hba-vault
```

**2. Install dependencies**
```bash
pip install flask flask-mail opencv-python opencv-contrib-python numpy werkzeug
```

**3. Place the logo**

Put your `logo.png` inside the `static/` folder:
```
static/logo.png
```

**4. Configure email**

Open `app.py` and update the mail credentials:
```python
app.config["MAIL_USERNAME"] = "your-email@gmail.com"
app.config["MAIL_PASSWORD"] = "your-app-password"   # Gmail App Password
```

> ⚠️ Never commit real credentials to GitHub. Use environment variables or a `.env` file in production.

**5. Create the uploads folder**
```bash
mkdir -p static/uploads
```

**6. Run the application**
```bash
python app.py
```

**7. Open in browser**
```
http://127.0.0.1:5000
```

---

## How It Works

### Registration
1. User fills in username, email, password, and role (Sender or Receiver)
2. Camera captures a live face image
3. Haar Cascade detects and extracts the face region
4. Face ROI is serialised with `pickle` and stored in the database
5. A welcome HTML email is sent to the registered email

### Login
1. User enters username and password
2. On success, redirected to `/face_verify`
3. Live camera feed is shown — user clicks **Authenticate Identity**
4. Captured frame is compared against the stored face using the LBPH recogniser
5. If confidence < 75, login is approved and the event is logged to the blockchain

### Upload (Sender)
1. Sender selects a file and a target receiver
2. File is saved to `static/uploads/`
3. A 6-digit OTP is emailed to the sender
4. Sender enters the OTP on the verification page
5. On success: SHA-256 hash computed, permission saved to DB, transaction recorded on blockchain, upload notification email sent to the receiver

### Download (Receiver)
1. Receiver sees all files shared with them on the dashboard
2. Clicks **Request Download** on a file
3. A 6-digit OTP is emailed to the receiver
4. Receiver enters the OTP
5. On success: file served as an attachment, download event recorded on blockchain

---

## Email Notifications

| Trigger | Recipient | Content |
|---|---|---|
| Successful registration | New user | Welcome email with account details, security reminder, next steps |
| Upload OTP | Sender | 6-digit OTP to authorise the upload |
| File shared | Receiver | File name, sender, SHA-256 hash, how-to-download guide |
| Download OTP | Receiver | 6-digit OTP to authorise the download |

All emails are sent as styled HTML via Gmail SMTP over SSL (port 465).

---

## Blockchain Ledger

The custom blockchain (`blockchain.py`) records:

| Event | Sender field | Recipient field | Amount field |
|---|---|---|---|
| Login | username | System | `AUTH:SUCCESS:sender` |
| Upload | username | receiver | `FILE_HASH:<sha256>` |
| Download | Network | username | `DL:<filename>` |

Each block contains:
- Block index
- Unix timestamp
- List of transactions
- Proof of work value
- SHA-256 hash of the previous block

The genesis block is created automatically on startup with `previous_hash='1'`.

---

## Security Design

| Threat | Mitigation |
|---|---|
| Stolen password | Facial biometric second factor required |
| Spoofed face image | Live camera capture only; LBPH confidence threshold |
| Unauthorised download | Receiver must be explicitly authorised by sender; OTP required |
| File tampering | SHA-256 hash stored at upload time and recorded on blockchain |
| Replay attacks | Single-use 6-digit OTP per upload/download session |
| Audit trail gaps | Every auth, upload, and download event is an immutable blockchain transaction |

---

## Screenshots

> Add screenshots of the following pages to this section:
> - Landing page (`/`)
> - Registration page with face camera
> - Sender dashboard
> - Receiver dashboard with file cards
> - OTP verification screen
> - Welcome email received in inbox

---

## Author

**Harish E R**
- 📧 harisher1505@gmail.com
- 🔗 [LinkedIn](https://www.linkedin.com/in/erharish15)
- 🐙 [GitHub](https://github.com/hari1715)

**Institution:** SRM Institute of Science and Technology, Vadapalani, Chennai
**Location:** Chennai – 600 026, Tamil Nadu, India

---

> Built with purpose — privacy is not a feature, it's a foundation.
