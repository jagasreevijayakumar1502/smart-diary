from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
from datetime import datetime, timedelta
import random, smtplib
from email.message import EmailMessage
from textblob import TextBlob
import matplotlib.pyplot as plt
import os

app = Flask(__name__)
app.secret_key = "secret123"

# ---------------- DB ----------------
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="admin",
    database="testdb1"
)
cursor = db.cursor(dictionary=True)

# ---------------- EMAIL CONFIG ----------------
SENDER_EMAIL = "smartdiaryonline.app@gmail.com"
APP_PASSWORD = "lgtz ezel wfhb tifu"

def send_otp(email, otp):
    msg = EmailMessage()
    msg["Subject"] = "SmartDiary OTP Verification"
    msg["From"] = SENDER_EMAIL
    msg["To"] = email
    msg.set_content(f"Your OTP is {otp}. Valid for 10 minutes.")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.send_message(msg)

# ---------------- LOGIN ----------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]

        cursor.execute(
            "SELECT * FROM users WHERE username=%s AND password=%s AND verified=1",
            (u, p)
        )
        user = cursor.fetchone()

        if user:
            session["username"] = u
            return redirect(url_for("dashboard"))

        return render_template("login.html", error="Invalid credentials")

    return render_template("login.html")

# ---------------- REGISTER EMAIL ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        otp = str(random.randint(100000, 999999))

        cursor.execute("DELETE FROM email_otps WHERE email=%s", (email,))
        cursor.execute(
            "INSERT INTO email_otps (email, otp, created_at) VALUES (%s,%s,%s)",
            (email, otp, datetime.now())
        )
        db.commit()

        send_otp(email, otp)
        return redirect(url_for("verify_register", email=email))

    return render_template("register.html")

# ---------------- VERIFY OTP ----------------
@app.route("/verify-register", methods=["GET", "POST"])
def verify_register():
    email = request.args.get("email")

    if request.method == "POST":
        email = request.form["email"]
        otp = request.form["otp"]
        username = request.form["username"]
        password = request.form["password"]

        cursor.execute(
            "SELECT * FROM email_otps WHERE email=%s AND otp=%s",
            (email, otp)
        )
        record = cursor.fetchone()

        if not record:
            return render_template(
                "verify_register.html",
                email=email,
                error="Invalid or expired OTP"
            )

        cursor.execute(
            """
            INSERT INTO users (username,password,email,verified,created_at)
            VALUES (%s,%s,%s,1,%s)
            """,
            (username, password, email, datetime.now())
        )
        cursor.execute("DELETE FROM email_otps WHERE email=%s", (email,))
        db.commit()

        return redirect(url_for("login"))

    return render_template("verify_register.html", email=email)

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html")

# ---------------- NEW ENTRY ----------------
@app.route("/new_entry", methods=["GET", "POST"])
def new_entry():
    if "username" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        text = request.form["entry_text"]
        polarity = TextBlob(text).sentiment.polarity

        if polarity > 0.15:
            mood = "Happy 😊"
        elif polarity < -0.15:
            mood = "Sad 😔"
        else:
            mood = "Neutral 😌"

        cursor.execute(
            """
            INSERT INTO diary_entries (username,entry_text,mood,created_at)
            VALUES (%s,%s,%s,%s)
            """,
            (session["username"], text, mood, datetime.now())
        )
        db.commit()

        return redirect(url_for("diary"))

    return render_template("new_entry.html")

# ---------------- DIARY ----------------
@app.route("/diary")
def diary():
    if "username" not in session:
        return redirect(url_for("login"))

    cursor.execute(
        "SELECT * FROM diary_entries WHERE username=%s ORDER BY created_at",
        (session["username"],)
    )
    entries = cursor.fetchall()

    return render_template("diary.html", entries=entries)

# ---------------- INSIGHTS (GRAPH + AI) ----------------
@app.route("/insights")
def insights():
    if "username" not in session:
        return redirect(url_for("login"))

    cursor.execute(
        "SELECT created_at, mood FROM diary_entries WHERE username=%s",
        (session["username"],)
    )
    data = cursor.fetchall()

    if not data:
        return render_template(
            "insights.html",
            graph=None,
            advice="Start writing entries to unlock insights 🌱"
        )

    dates = []
    values = []

    mood_map = {"Happy 😊": 1, "Neutral 😌": 0, "Sad 😔": -1}

    for row in data:
        dates.append(row["created_at"].date())
        values.append(mood_map.get(row["mood"], 0))

    # ----- GRAPH -----
    plt.figure(figsize=(6,3))
    plt.plot(dates, values, marker="o")
    plt.yticks([-1,0,1], ["Sad","Neutral","Happy"])
    plt.xlabel("Date")
    plt.ylabel("Mood")
    plt.tight_layout()

    if not os.path.exists("static"):
        os.mkdir("static")

    graph_path = "static/mood_graph.png"
    plt.savefig(graph_path)
    plt.close()

    avg = sum(values)/len(values)

    # ----- AI STYLE ADVICE -----
    if avg > 0.3:
        advice = (
            "Your emotional trend shows consistent positivity. "
            "You’re emotionally resilient and in a healthy mental phase. "
            "Keep journaling, practicing gratitude, and maintaining routines."
        )
    elif avg < -0.3:
        advice = (
            "Your recent emotional pattern suggests emotional strain. "
            "This is not a failure—it's a signal. Consider slowing down, "
            "talking to someone you trust, and doing grounding activities."
        )
    else:
        advice = (
            "Your emotions fluctuate naturally, indicating balance with moments "
            "of stress. Try mindfulness, better sleep routines, and self-reflection."
        )

    return render_template(
        "insights.html",
        
    dates=dates,
    mood_values=values,
    advice=advice
)


# ---------------- LOGOUT ----------------
@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)
