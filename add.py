import os
import sqlite3
import secrets
import re
from datetime import datetime
from functools import wraps

from flask import (
    Flask, request, redirect, url_for, session,
    flash, render_template_string, g
)

app = Flask(__name__)
app.secret_key = os.environ.get(
    "GRAMCONNECT_SECRET",
    "change-this-secret-key-before-deployment"
)

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "gramconnect.db")

ADMIN_PASSWORD = os.environ.get(
    "GRAMCONNECT_ADMIN_PASSWORD",
    "change-this-password"
)

STATUSES = [
    "Submitted",
    "Under Review",
    "In Progress",
    "Resolved",
    "Rejected"
]

CATEGORIES = [
    "Roads",
    "Water Supply",
    "Sanitation",
    "Streetlights",
    "Drainage",
    "Public Facilities",
    "Other"
]


# ---------------- DATABASE ----------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    db = sqlite3.connect(DATABASE)

    db.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tracking_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            category TEXT NOT NULL,
            subject TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Submitted',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            note TEXT DEFAULT '',
            changed_at TEXT NOT NULL,
            FOREIGN KEY (submission_id)
                REFERENCES submissions(id)
                ON DELETE CASCADE
        )
    """)

    db.commit()
    db.close()


# ---------------- ADMIN SECURITY ----------------

def admin_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            flash("Please log in as admin.", "error")
            return redirect(url_for("admin_login"))
        return function(*args, **kwargs)
    return wrapper


# ---------------- COMMON DESIGN ----------------

BASE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }} | GramConnect</title>

<style>
* {
    box-sizing: border-box;
}

body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: #101114;
    color: #f5f5f5;
}

nav {
    background: #191b20;
    border-bottom: 1px solid #383838;
    padding: 18px 6%;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 15px;
}

.logo {
    font-size: 24px;
    font-weight: bold;
    color: #e8b84b;
    text-decoration: none;
}

nav a {
    color: white;
    text-decoration: none;
    margin-left: 15px;
}

nav a:hover {
    color: #e8b84b;
}

.container {
    width: 90%;
    max-width: 1100px;
    margin: 45px auto;
}

.hero {
    padding: 45px 0;
}

h1 {
    font-size: 44px;
    line-height: 1.15;
}

h2 {
    color: #e8b84b;
}

p {
    color: #b8b8b8;
    line-height: 1.7;
}

.card {
    background: #1b1d22;
    border: 1px solid #383a40;
    border-radius: 15px;
    padding: 25px;
    margin-bottom: 22px;
}

.grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 20px;
}

button, .btn {
    background: #e8b84b;
    color: #171717;
    padding: 12px 18px;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-weight: bold;
    text-decoration: none;
    display: inline-block;
}

.secondary {
    background: #34363d;
    color: white;
}

.danger {
    background: #a93636;
    color: white;
}

input, textarea, select {
    width: 100%;
    padding: 13px;
    background: #101114;
    border: 1px solid #484a50;
    border-radius: 8px;
    color: white;
    margin-top: 7px;
}

textarea {
    min-height: 130px;
    resize: vertical;
}

label {
    display: block;
    margin-top: 17px;
    font-weight: bold;
}

.flash {
    padding: 13px;
    background: #39301c;
    color: #f6d783;
    border-radius: 8px;
    margin-bottom: 15px;
}

.flash.error {
    background: #482528;
    color: #ffbcbc;
}

.table-wrap {
    overflow-x: auto;
}

table {
    width: 100%;
    border-collapse: collapse;
    min-width: 750px;
}

th, td {
    text-align: left;
    padding: 13px;
    border-bottom: 1px solid #414141;
    vertical-align: top;
}

th {
    color: #e8b84b;
}

td {
    overflow-wrap: anywhere;
}

.status {
    color: #e8b84b;
    font-weight: bold;
}

.timeline {
    border-left: 2px solid #e8b84b;
    padding-left: 20px;
    margin-left: 8px;
}

.event {
    margin-bottom: 20px;
}

.small {
    font-size: 12px;
    color: #aaa;
}

.footer {
    text-align: center;
    padding: 25px;
    color: #888;
    border-top: 1px solid #333;
}

@media(max-width:700px) {
    .grid {
        grid-template-columns: 1fr;
    }

    h1 {
        font-size: 34px;
    }

    nav {
        align-items: flex-start;
    }

    nav a {
        margin-left: 0;
        margin-right: 12px;
    }
}
</style>
</head>

<body>

<nav>
    <a class="logo" href="{{ url_for('home') }}">
        GramConnect
    </a>

    <div>
        <a href="{{ url_for('home') }}">Home</a>
        <a href="{{ url_for('submit') }}">Submit</a>
        <a href="{{ url_for('track') }}">Track</a>

        {% if session.get('admin_logged_in') %}
            <a href="{{ url_for('admin_dashboard') }}">Dashboard</a>
            <a href="{{ url_for('admin_logout') }}">Logout</a>
        {% else %}
            <a href="{{ url_for('admin_login') }}">Admin</a>
        {% endif %}
    </div>
</nav>

<div class="container">

{% with messages = get_flashed_messages(with_categories=true) %}
    {% for category, message in messages %}
        <div class="flash {{ 'error' if category == 'error' else '' }}">
            {{ message }}
        </div>
    {% endfor %}
{% endwith %}

{{ content|safe }}

</div>

<div class="footer">
    GramConnect | Your Voice. Your Village. Your Future.
</div>

<script>
document.addEventListener("DOMContentLoaded", function () {
    const form = document.querySelector(".card form");

    if (!form || !form.querySelector('[name="name"]')) return;

    form.addEventListener("submit", function (event) {
        const name = form.querySelector('[name="name"]').value.trim();
        const phone = form.querySelector('[name="phone"]').value.trim();
        const subject = form.querySelector('[name="subject"]').value.trim();
        const description = form.querySelector('[name="description"]').value.trim();
        const category = form.querySelector('[name="category"]').value;

        let error = "";

        const namePattern = /^[^\W\d_]+(?:[ .'-][^\W\d_]+)*$/u;
        const phonePattern = /^(?:\+91[- ]?)?[6-9][0-9]{9}$/;

        if (!name || !phone || !category || !subject || !description) {
            error = "Please fill in all required fields.";
        } else if (!namePattern.test(name) || name.length < 2 || name.length > 100) {
            error = "Invalid name. Please use letters only.";
        } else if (!phonePattern.test(phone)) {
            error = "Enter a valid Indian mobile number.";
        } else if (subject.length < 5 || subject.length > 150) {
            error = "Subject must contain 5 to 150 characters.";
        } else if (description.length < 20 || description.length > 5000) {
            error = "Description must contain 20 to 5000 characters.";
        }

        if (error) {
            event.preventDefault();
            alert(error);
        }
    });
});
</script>
</body>
</html>
"""


def page(title, html, **data):
    content = render_template_string(html, **data)
    return render_template_string(BASE, title=title, content=content)


# ---------------- HOME PAGE ----------------

HOME = """
<div class="hero">
    <p style="color:#e8b84b;font-weight:bold">
        YOUR VOICE MATTERS
    </p>

    <h1>
        A Better Village Begins With
        <span style="color:#e8b84b">Your Voice.</span>
    </h1>

    <p>
        Welcome to GramConnect, a digital platform where
        citizens can submit complaints and suggestions
        directly to their Gram Panchayat.
    </p>

    <br>

    <a class="btn" href="{{ url_for('submit') }}">
        Submit Complaint / Suggestion
    </a>

    <a class="btn secondary" href="{{ url_for('track') }}">
        Track Submission
    </a>
</div>

<div class="grid">

    <div class="card">
        <h2>Submit Your Concern</h2>
        <p>
            Report problems related to roads, water,
            sanitation, drainage and other village services.
        </p>
    </div>

    <div class="card">
        <h2>Track Your Progress</h2>
        <p>
            Use your unique tracking ID to follow the
            progress of your complaint or suggestion.
        </p>
    </div>

</div>
"""


@app.route("/")
def home():
    return page("Home", HOME)


# ---------------- SUBMISSION PAGE ----------------

SUBMIT = """
<div class="card">
    <h1>Submit Your Concern</h1>

    <p>
        Fill in the details below to submit your complaint
        or suggestion to the Gram Panchayat.
    </p>

    <form method="POST">

        <label>Your Name *</label>
       <input
            name="name"
            type="text"
            minlength="2"
            maxlength="100"
            placeholder="Enter your full name"
            autocomplete="name"
            required>
        <label>Phone Number *</label>
        <input
            name="phone"
            type="tel"
            maxlength="15"
            placeholder="Enter 10-digit mobile number"
            pattern="(?:\+91[- ]?)?[6-9][0-9]{9}"
            title="Enter a valid 10-digit Indian mobile number"
            required>

        <label>Category *</label>
        <select name="category" required>
            <option value="">Select Category</option>
            {% for category in categories %}
                <option value="{{ category }}">{{ category }}</option>
            {% endfor %}
        </select>

        <label>Subject *</label>
        <input name="subject" minlength="5" maxlength="150" required>
        <label>Description *</label>
        <textarea
            name="description"
            minlength="20"
            maxlength="5000"
            placeholder="Explain your complaint or suggestion..."
            required></textarea>

        <br><br>
        <button type="submit">Submit</button>

    </form>
</div>
"""


@app.route("/submit", methods=["GET", "POST"])


def submit():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        category = request.form.get("category", "").strip()
        subject = request.form.get("subject", "").strip()
        description = request.form.get("description", "").strip()

        # 1. Check empty fields
        if not all([name, phone, category, subject, description]):
            flash("Please fill all required fields.", "error")
            return redirect(url_for("submit"))

        # 2. Validate name
        name_pattern = r"[^\W\d_]+(?:[ .'-][^\W\d_]+)*"

        if not re.fullmatch(name_pattern, name, flags=re.UNICODE):
            flash("Invalid name. Use valid letters only.", "error")
            return redirect(url_for("submit"))

        if len(name) < 2 or len(name) > 100:
            flash("Name must contain 2 to 100 characters.", "error")
            return redirect(url_for("submit"))

        # 3. Validate Indian mobile number
        if not re.fullmatch(r"(?:\+91[- ]?)?[6-9][0-9]{9}", phone):
            flash("Enter a valid Indian mobile number.", "error")
            return redirect(url_for("submit"))

        phone_digits = re.sub(r"\D", "", phone)

        if phone_digits.startswith("91") and len(phone_digits) == 12:
            phone_digits = phone_digits[2:]

        phone = phone_digits

        # 4. Validate category
        if category not in CATEGORIES:
            flash("Please select a valid category.", "error")
            return redirect(url_for("submit"))

        # 5. Validate subject
        if len(subject) < 5 or len(subject) > 150:
            flash("Subject must contain 5 to 150 characters.", "error")
            return redirect(url_for("submit"))

        if sum(ch.isalpha() for ch in subject) < 3:
            flash("Please enter a meaningful subject.", "error")
            return redirect(url_for("submit"))

        # 6. Validate description
        if len(description) < 20 or len(description) > 5000:
            flash("Description must contain 20 to 5000 characters.", "error")
            return redirect(url_for("submit"))

        if sum(ch.isalpha() for ch in description) < 10:
            flash("Please enter a meaningful complaint or suggestion.", "error")
            return redirect(url_for("submit"))

        # 7. Generate unique tracking ID
        tracking_id = "GC-" + secrets.token_hex(4).upper()

        now = datetime.now().strftime("%d %b %Y, %I:%M %p")

        # 8. Save complaint to database
        db = get_db()

        cursor = db.execute("""
            INSERT INTO submissions
            (tracking_id, name, phone, category, subject,
             description, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            tracking_id, name, phone, category, subject,
            description, "Submitted", now, now
        ))

        submission_id = cursor.lastrowid

        # 9. Save initial progress history
        db.execute("""
            INSERT INTO status_history
            (submission_id, status, note, changed_at)
            VALUES (?, ?, ?, ?)
        """, (
            submission_id,
            "Submitted",
            "Submission received by GramConnect.",
            now
        ))

        db.commit()

        # 10. Show successful submission page
        return redirect(url_for(
            "submitted",
            tracking_id=tracking_id
        ))

    return page("Submit", SUBMIT, categories=CATEGORIES)


# ---------------- SUBMISSION SUCCESS ----------------

SUCCESS = """
<div class="card">
    <h1>Thank You!</h1>

    <p>
        Your submission has been received successfully.
    </p>

    <h2>Your Tracking ID</h2>

    <h1 style="color:#e8b84b">{{ tracking_id }}</h1>

    <p>
        Save this tracking ID. You will need it to check
        your submission progress.
    </p>

    <a class="btn"
       href="{{ url_for('track', tracking_id=tracking_id) }}">
       Track Submission
    </a>

    <a class="btn secondary" href="{{ url_for('home') }}">
        Home
    </a>
</div>
"""


@app.route("/submitted/<tracking_id>")
def submitted(tracking_id):

    db = get_db()

    submission = db.execute(
        "SELECT * FROM submissions WHERE tracking_id = ?",
        (tracking_id,)
    ).fetchone()

    if not submission:
        flash("Submission not found.", "error")
        return redirect(url_for("track"))

    return page(
        "Submission Received",
        SUCCESS,
        tracking_id=tracking_id
    )


# ---------------- TRACK SUBMISSION ----------------

TRACK = """
<div class="card">

    <h1>Track Your Submission</h1>

    <form method="POST">

        <label>Enter Your Tracking ID</label>

        <input name="tracking_id"
               value="{{ tracking_id }}"
               placeholder="Example: GC-A1B2C3D4"
               required>

        <br><br>

        <button type="submit">Track</button>

    </form>

</div>

{% if submission %}

<div class="card">

    <h2>{{ submission['subject'] }}</h2>

    <p>
        Tracking ID:
        <strong>{{ submission['tracking_id'] }}</strong>
    </p>

    <p>
        Current Status:
        <span class="status">{{ submission['status'] }}</span>
    </p>

    <p>Category: {{ submission['category'] }}</p>
    <p>Submitted: {{ submission['created_at'] }}</p>

    <h3>Description</h3>
    <p>{{ submission['description'] }}</p>

    <h2>Progress Timeline</h2>

    <div class="timeline">

        {% for event in history %}

            <div class="event">

                <strong>{{ event['status'] }}</strong>

                <p class="small">
                    {{ event['changed_at'] }}
                </p>

                {% if event['note'] %}
                    <p>{{ event['note'] }}</p>
                {% endif %}

            </div>

        {% endfor %}

    </div>

</div>

{% endif %}
"""


@app.route("/track", methods=["GET", "POST"])
def track():

    tracking_id = request.args.get("tracking_id", "").strip()

    if request.method == "POST":
        tracking_id = request.form.get(
            "tracking_id", ""
        ).strip().upper()

    submission = None
    history = []

    if tracking_id:

        db = get_db()

        submission = db.execute("""
            SELECT * FROM submissions
            WHERE tracking_id = ?
        """, (tracking_id,)).fetchone()

        if submission:

            history = db.execute("""
                SELECT * FROM status_history
                WHERE submission_id = ?
                ORDER BY id DESC
            """, (submission["id"],)).fetchall()

        else:
            flash("Invalid tracking ID.", "error")

    return page(
        "Track",
        TRACK,
        tracking_id=tracking_id,
        submission=submission,
        history=history
    )


# ---------------- ADMIN LOGIN ----------------

LOGIN = """
<div class="card">

    <h1>Admin Login</h1>

    <p>Login to manage GramConnect submissions.</p>

    <form method="POST">

        <label>Admin Password</label>

        <input type="password"
               name="password"
               required>

        <br><br>

        <button type="submit">Login</button>

    </form>

</div>
"""


@app.route("/admin", methods=["GET", "POST"])
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if session.get("admin_logged_in"):
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":

        password = request.form.get("password", "")

        if password == ADMIN_PASSWORD:

            session.clear()
            session["admin_logged_in"] = True

            flash("Admin login successful.")

            return redirect(url_for("admin_dashboard"))

        flash("Incorrect password.", "error")

    return page("Admin Login", LOGIN)


# ---------------- ADMIN DASHBOARD ----------------

DASHBOARD = """
<h1>Admin Dashboard</h1>

<p>
    Manage complaints and suggestions submitted by citizens.
</p>

<div class="grid">

    <div class="card">
        <h2>{{ total }}</h2>
        <p>Total Submissions</p>
    </div>

    <div class="card">
        <h2>{{ active }}</h2>
        <p>Pending / In Progress</p>
    </div>

</div>

<div class="card">

    <h2>All Submissions</h2>

    <div class="table-wrap">

    <table>

        <thead>
            <tr>
                <th>Submission</th>
                <th>Citizen</th>
                <th>Category</th>
                <th>Status</th>
                <th>Update</th>
                <th>Delete</th>
            </tr>
        </thead>

        <tbody>

        {% for s in submissions %}

            <tr>

                <td>
                    <strong>{{ s['subject'] }}</strong>
                    <p class="small">{{ s['tracking_id'] }}</p>
                    <p class="small">{{ s['created_at'] }}</p>
                    <p>{{ s['description'] }}</p>
                </td>

                <td>
                    {{ s['name'] }}
                    <p class="small">{{ s['phone'] }}</p>
                </td>

                <td>{{ s['category'] }}</td>

                <td>
                    <span class="status">{{ s['status'] }}</span>
                </td>

                <td>

                    <form method="POST"
                          action="{{ url_for('admin_update', submission_id=s['id']) }}">

                        <select name="status">

                            {% for status in statuses %}

                                <option value="{{ status }}"
                                    {% if status == s['status'] %}
                                        selected
                                    {% endif %}>
                                    {{ status }}
                                </option>

                            {% endfor %}

                        </select>

                        <input name="note"
                               placeholder="Optional update note">

                        <br><br>

                        <button type="submit">Save</button>

                    </form>

                </td>

                <td>

                    <form method="POST"
                          action="{{ url_for('admin_delete', submission_id=s['id']) }}"
                          onsubmit="return confirm('Are you sure you want to permanently delete this submission?');">

                        <button type="submit" class="danger">
                            Delete
                        </button>

                    </form>

                </td>

            </tr>

        {% else %}

            <tr>
                <td colspan="6">
                    No submissions found.
                </td>
            </tr>

        {% endfor %}

        </tbody>

    </table>

    </div>

</div>
"""


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():

    db = get_db()

    submissions = db.execute("""
        SELECT * FROM submissions
        ORDER BY id DESC
    """).fetchall()

    total = len(submissions)

    active = sum(
        1 for s in submissions
        if s["status"] in [
            "Submitted",
            "Under Review",
            "In Progress"
        ]
    )

    return page(
        "Admin Dashboard",
        DASHBOARD,
        submissions=submissions,
        statuses=STATUSES,
        total=total,
        active=active
    )


# ---------------- UPDATE SUBMISSION STATUS ----------------

@app.route(
    "/admin/update/<int:submission_id>",
    methods=["POST"]
)
@admin_required
def admin_update(submission_id):

    status = request.form.get("status", "")
    note = request.form.get("note", "").strip()

    if status not in STATUSES:
        flash("Invalid status.", "error")
        return redirect(url_for("admin_dashboard"))

    db = get_db()

    submission = db.execute("""
        SELECT id FROM submissions WHERE id = ?
    """, (submission_id,)).fetchone()

    if not submission:
        flash("Submission not found.", "error")
        return redirect(url_for("admin_dashboard"))

    now = datetime.now().strftime("%d %b %Y, %I:%M %p")

    db.execute("""
        UPDATE submissions
        SET status = ?, updated_at = ?
        WHERE id = ?
    """, (status, now, submission_id))

    db.execute("""
        INSERT INTO status_history
        (submission_id, status, note, changed_at)
        VALUES (?, ?, ?, ?)
    """, (
        submission_id,
        status,
        note or "Status updated by Gram Panchayat admin.",
        now
    ))

    db.commit()

    flash("Submission updated successfully.")

    return redirect(url_for("admin_dashboard"))


# ---------------- DELETE SUBMISSION ----------------

@app.route(
    "/admin/delete/<int:submission_id>",
    methods=["POST"]
)
@admin_required
def admin_delete(submission_id):

    db = get_db()

    db.execute("""
        DELETE FROM submissions
        WHERE id = ?
    """, (submission_id,))

    db.commit()

    flash("Submission and its history deleted successfully.")

    return redirect(url_for("admin_dashboard"))


# ---------------- ADMIN LOGOUT ----------------

@app.route("/admin/logout")
@admin_required
def admin_logout():

    session.clear()

    flash("You have been logged out.")

    return redirect(url_for("home"))


# ---------------- RUN APPLICATION ----------------

init_db()

if __name__ == "__main__":

    print("--------------------------------")
    print("       GRAMCONNECT STARTED")
    print("--------------------------------")
    print("Website: http://127.0.0.1:5000")
    print("Admin:   http://127.0.0.1:5000/admin")
    print("Default admin password: change-this-password")
    print("--------------------------------")

    app.run(debug=True)
