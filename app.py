import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "unique-elite-dev-key")

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY"),
)

# ---------- CENTRAL CLUB INFO ----------
CLUB_INFO = {
    "name": "Unique Elite Club",
    "slogan": "Togetherness We Rise",
    "location": "Falade Street, Shomolu/Bariga, Lagos",
    "day": "Every Sunday",
    "membership": "Subject to Approval",
    "email": "UniqueEliteClub26@gmail.com",
}

@app.context_processor
def inject_club():
    return {"club": CLUB_INFO}

# ---------- HELPERS ----------
def get_profile(user_id):
    try:
        return supabase.table("profiles").select("*").eq("id", user_id).single().execute().data
    except Exception:
        return None

def is_admin():
    return session.get("role") == "admin"

# ---------- PUBLIC ----------
@app.route("/")
def home():
    return render_template("index.html", page="home")

@app.route("/membership")
def membership_info():
    return render_template("index.html", page="membership")

# ---------- APPLY ----------
@app.route("/apply", methods=["POST"])
def apply():
    data = {
        "full_name": request.form["full_name"].strip(),
        "email": request.form["email"].strip().lower(),
        "phone": request.form["phone"].strip(),
        "address": request.form["address"].strip(),
        "occupation": request.form.get("occupation", "").strip(),
        "reason": request.form.get("reason", "").strip(),
        "status": "pending",
    }
    try:
        existing = supabase.table("applications").select("id").eq("email", data["email"]).execute()
        if existing.data:
            flash("An application with this email already exists.")
            return redirect(url_for("membership_info"))
        supabase.table("applications").insert(data).execute()
        flash("Application submitted! You will be contacted after admin review.")
    except Exception as e:
        flash(f"Error: {str(e)}")
    return redirect(url_for("membership_info"))

# ---------- AUTH ----------
@app.route("/register", methods=["POST"])
def register():
    email = request.form["email"].strip().lower()
    password = request.form["password"]
    full_name = request.form["full_name"].strip()

    approved = supabase.table("applications").select("*").eq("email", email).eq("status", "approved").execute()
    if not approved.data:
        flash("Your email is not on the approved member list. Please apply first.")
        return redirect(url_for("home"))

    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        if res.user:
            count = supabase.table("profiles").select("id", count="exact").execute()
            member_no = f"UEC-{1000 + (count.count or 0) + 1}"

            supabase.table("profiles").insert({
                "id": res.user.id,
                "full_name": full_name,
                "email": email,
                "role": "member",
                "membership_no": member_no,
            }).execute()

            supabase.table("applications").update({"status": "registered"}).eq("email", email).execute()
            flash(f"Account created! Your membership number is {member_no}. Please log in.")
        else:
            flash("Registration failed.")
    except Exception as e:
        flash(f"Error: {str(e)}")
    return redirect(url_for("home"))

@app.route("/login", methods=["POST"])
def login():
    email = request.form["email"].strip().lower()
    password = request.form["password"]
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if res.user:
            session["user_id"] = res.user.id
            profile = get_profile(res.user.id)
            if profile:
                session["full_name"] = profile.get("full_name")
                session["role"] = profile.get("role", "member")
                session["membership_no"] = profile.get("membership_no")
            return redirect(url_for("admin_panel") if is_admin() else url_for("dashboard"))
        flash("Invalid credentials.")
    except Exception:
        flash("Incorrect email or password.")
    return redirect(url_for("home"))

@app.route("/logout")
def logout():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    session.clear()
    return redirect(url_for("home"))

# ---------- MEMBER ----------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("home"))
    return render_template("index.html", page="dashboard")

# ---------- ADMIN ----------
@app.route("/admin")
def admin_panel():
    if not is_admin():
        return "Access denied: Admins only", 403
    apps = supabase.table("applications").select("*").order("created_at", desc=True).execute().data
    members = supabase.table("profiles").select("*").order("created_at", desc=True).execute().data
    return render_template("index.html", page="admin", applications=apps, members=members)

@app.route("/admin/approve/<app_id>", methods=["POST"])
def approve(app_id):
    if not is_admin():
        return "Access denied", 403
    supabase.table("applications").update({"status": "approved"}).eq("id", app_id).execute()
    flash("Application approved. Applicant may now register.")
    return redirect(url_for("admin_panel"))

@app.route("/admin/reject/<app_id>", methods=["POST"])
def reject(app_id):
    if not is_admin():
        return "Access denied", 403
    supabase.table("applications").update({"status": "rejected"}).eq("id", app_id).execute()
    flash("Application rejected.")
    return redirect(url_for("admin_panel"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
