import hmac
import os
import re
import secrets
import uuid
from datetime import date, timedelta

import click
from flask import Flask, jsonify, render_template, request, send_from_directory, session
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect, CSRFError #security
from flask_talisman import Talisman #security import
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import selectinload
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from models import (
	db, UserDataTable, Major, Player, SportSeason, SportSeasonPlayer,
	AdminAccount, RecruitmentSubmission, ScheduleEvent, TeamStaff, SeasonRecord
)

#security import
from dotenv import load_dotenv
load_dotenv()

SITE_DIR = os.path.dirname(os.path.abspath(__file__))
SITE_FILES = {"index.html", "main.html", "admin.html", "script.js", "admin.js", "style.css"}

# These must match the <option> values in the join form in index.html.
POSITION_CHOICES = {
	"Loosehead Prop (1)", "Hooker (2)", "Tighthead Prop (3)", "Lock (4)", "Lock (5)",
	"Blindside Flanker (6)", "Openside Flanker (7)", "Number 8 (8)",
	"Scrum-half (9)", "Fly-half (10)", "Left Wing (11)", "Inside Centre (12)",
	"Outside Centre (13)", "Right Wing (14)", "Full-back (15)", "Not Sure Yet"
}
EXPERIENCE_CHOICES = {"None", "Beginner", "Intermediate", "Advanced"}

EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
MIN_ADMIN_PASSWORD_LENGTH = 10

# Routes under /api/ that do not require the X-API-Key header.
PUBLIC_API_PATHS = {"/api/recruitment", "/api/events", "/api/staff", "/api/season-records"}
SESSION_API_PREFIX = "/api/admin/"

EVENT_TYPE_CHOICES = {"game", "practice"}
HOME_AWAY_CHOICES = {"home", "away"}
EVENT_STATUS_CHOICES = {"scheduled", "cancelled", "postponed"}
STAFF_CONFIG_ID = "main"
SEASON_LABEL_PATTERN = re.compile(r"^\d{4}-\d{4}$")
STAFF_UPLOAD_DIR = os.path.join(SITE_DIR, "uploads", "staff")
STAFF_IMAGE_SIZE = (200, 200)
STAFF_IMAGE_FIELDS = {
	"president": "PresidentImage",
	"coach": "CoachImage",
	"captain": "CaptainImage"
}
ALLOWED_STAFF_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}

DEFAULT_CORS_ORIGINS = (
	"http://localhost:3000,"
	"http://127.0.0.1:3000,"
	"http://localhost:5173,"
	"http://127.0.0.1:5173"
)

csrf = CSRFProtect() #security

def csv_env(name, default):
	return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]

def column_max_length(model, column_name):
	column = model.__table__.columns.get(column_name)
	return getattr(getattr(column, "type", None), "length", None)

# This validates a string, making sure that it is a valid string within the required length and having necessary data.
def validate_string(value, field_name, required=False, max_length=None):
	if value is None:
		return (None, f"Missing {field_name} field") if required else (None, None)

	if not isinstance(value, str):
		return None, f"{field_name} is not a String"

	value = value.strip()

	if not value:
		return (None, f"Missing {field_name}") if required else (None, None)

	if max_length is not None and len(value) > max_length:
		return None, f"{field_name} must be less than {max_length} characters in length"
	return value, None

# This parses the date from a String
def parse_date(value):
	if value is None or value == "":
		return None

	if not isinstance(value, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
		return None

	try:
		return date.fromisoformat(value)

	except ValueError:
		return None

def request_object():
	data = request.get_json(silent=True)

	if isinstance(data, dict):
		return data, None

	return None, (jsonify({"error": "No request body was found"}), 400)

def pagination_values():
	try:
		page = int(request.args.get("page", "1"))
		per_page = int(request.args.get("per_page", "25"))
	except (TypeError, ValueError):
		return None, None, (jsonify({"error": "page and per_page must be integers"}), 400)

	if page < 1 or per_page < 1:
		return None, None, (jsonify({"error": "page and per_page must be positive integers"}), 400)
	return page, min(per_page, 100), None

def paginated_response(key, pagination, serializer):
	return jsonify({
		key: [serializer(item) for item in pagination.items],
		"page": pagination.page,
		"per_page": pagination.per_page,
		"total": pagination.total,
		"pages": pagination.pages
	})

def player_error(message):
	return jsonify({"error": message}), 400

# This validates the data for each player.
def validate_player_data(data):
	first_name, error = validate_string(
		data.get("FirstName"), "FirstName", True, column_max_length(Player, "FirstName")
	)
	if error:
		return None, error

	last_name, error = validate_string(
		data.get("LastName"), "LastName", True, column_max_length(Player, "LastName")
	)
	if error:
		return None, error

	major_id, error = validate_major_id(data.get("MajorID"))
	if error:
		return None, error

	stockton_id, error = validate_stockton_id(data.get("StocktonID"))
	if error:
		return None, error

	date_of_birth, error = validate_player_date(data.get("DateOfBirth"), "DateOfBirth")
	if error:
		return None, error

	graduation_date, error = validate_player_date(
		data.get("GraduationDateExpected"), "GraduationDateExpected"
	)
	if error:
		return None, error

	if date_of_birth and graduation_date and graduation_date <= date_of_birth:
		return None, "Graduation Date must be after the Date of Birth"

	return {
		"MajorID": major_id,
		"StocktonID": stockton_id,
		"FirstName": first_name,
		"LastName": last_name,
		"DateOfBirth": date_of_birth,
		"GraduationDateExpected": graduation_date
	}, None


def validate_major_id(value):
	if value is None or value == "":
		return None, None
	if not isinstance(value, str) or not value.strip():
		return None, "MajorID is a invalid string"

	major_id = value.strip()
	if db.session.get(Major, major_id) is None:
		return None, "Major not found"
	return major_id, None


def validate_stockton_id(value):
	if value is None:
		return None, None
	if isinstance(value, bool) or not isinstance(value, (str, int)):
		return None, "StocktonID must be a integer or string"

	stockton_id = str(value).strip()
	if not stockton_id:
		return None, None

	max_length = column_max_length(Player, "StocktonID")
	if max_length is not None and len(stockton_id) > max_length:
		return None, f"StocktonID must be equal to or less than {max_length} characters"
	return stockton_id, None

def validate_player_date(value, field_name):
	parsed_date = parse_date(value)
	if value not in (None, "") and parsed_date is None:
		return None, f"{field_name} is not a valid date or is not in YYYY-MM-DD format."
	return parsed_date, None

def player_to_dict(player):
	major = player.major
	return {
		"PlayerID": player.PlayerID,
		"MajorID": player.MajorID,
		"major": {
			"MajorUUID": major.MajorUUID,
			"MajorName": major.MajorName
		}

		if major else None,
		"StocktonID": player.StocktonID,
		"FirstName": player.FirstName,
		"LastName": player.LastName,
		"DateOfBirth": player.DateOfBirth.isoformat() if player.DateOfBirth else None,
		"GraduationDateExpected": player.GraduationDateExpected.isoformat()
		if player.GraduationDateExpected else None
	}

def major_to_dict(major):
	return {"MajorUUID": major.MajorUUID, "MajorName": major.MajorName}

def season_to_dict(season):
	return {
		"SportUUID": season.SportUUID,
		"SportName": season.SportName,
		"StartDate": season.StartDate.isoformat() if season.StartDate else None,
		"EndDate": season.EndDate.isoformat() if season.EndDate else None
	}

# This configures the app and changes the database url if it is incompatible.
def configure_app(app):
	# Use a stable project-local SQLite path so cwd/PyCharm differences don't create empty DBs.
	default_sqlite_path = os.path.join(SITE_DIR, "instance", "school.db").replace("\\", "/")
	database_url = os.getenv("DATABASE_URL", f"sqlite:///{default_sqlite_path}")

	if database_url.startswith("postgres://"):
		database_url = "postgresql://" + database_url[len("postgres://"):]

	if database_url.startswith("sqlite:///"):
		sqlite_path = database_url.replace("sqlite:///", "", 1)
		sqlite_dir = os.path.dirname(sqlite_path)
		if sqlite_dir:
			os.makedirs(sqlite_dir, exist_ok=True)

	# Local SQLite runs work with no env vars. Non-SQLite / production still requires SECRET_KEY.
	secret_key = os.getenv("SECRET_KEY")
	using_sqlite = database_url.startswith("sqlite:")
	force_production = os.getenv("FLASK_ENV", "").strip().lower() == "production" or os.getenv(
		"REQUIRE_SECRET_KEY", ""
	).strip().lower() in {"1", "true", "yes"}

	if not secret_key:
		if force_production or not using_sqlite:
			raise ValueError("FATAL: SECRET_KEY environment variable is not set. Refusing to start in production.")
		secret_key = "dev-local-secret"
		app.logger.warning("SECRET_KEY is not set; using built-in local development key.")

	app.config.update(
		SQLALCHEMY_DATABASE_URI=database_url,
		SQLALCHEMY_TRACK_MODIFICATIONS=False,
		API_KEY=os.getenv("API_KEY"),
		SECRET_KEY=secret_key,
		SESSION_COOKIE_HTTPONLY=True,
		SESSION_COOKIE_SAMESITE="Strict",
		SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "false").strip().lower() in {"1", "true", "yes"},
		PERMANENT_SESSION_LIFETIME=timedelta(hours=8)
	)

#security changes
def configure_extensions(app):
	db.init_app(app)
	csrf.init_app(app)
#security headers (CSP, HSTS, etc.)
	#also added X-CSRF-Token under allow_headers
	Talisman(
		app,
		content_security_policy={
			'default-src': '\'self\'',
			'script-src': ['\'self\'', 'https://cdn.jsdelivr.net'],
			'style-src': ['\'self\'', '\'unsafe-inline\'', 'https://cdn.jsdelivr.net'],
			'img-src': ['\'self\'', 'data:', 'https://images.unsplash.com', 'https://*.unsplash.com'],
			'font-src': ['\'self\'', 'https://cdn.jsdelivr.net'],
		},
		force_https=os.getenv("SESSION_COOKIE_SECURE", "false").strip().lower() in {"1", "true", "yes"},
	)

	CORS(
		app,
		resources={r"/api/*": {"origins": csv_env("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)}},
		allow_headers=["Content-Type", "X-API-Key", "X-CSRF-Token"],
		methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
		supports_credentials=False
	)

	return Limiter(
		key_func=get_remote_address,
		app=app,
		default_limits=["200 per minute"],
		storage_uri=os.getenv("RATELIMIT_STORAGE_URI", "memory://")
	)

# This is the security for the login registration
def register_security(app):
	@app.before_request
	def require_api_key():
		if not request.path.startswith("/api/") or request.method == "OPTIONS":
			return None

		if (
			request.path in PUBLIC_API_PATHS
			or request.path.startswith(SESSION_API_PREFIX)
		):
			return None

		configured_key = app.config.get("API_KEY")
		# This checks to make sure the API key is valid
		if not configured_key:
			return jsonify({"error": "The API has no or a incorrect configration"}), 503

		if not hmac.compare_digest(request.headers.get("X-API-Key", ""), configured_key):
			return jsonify({"error": "Unauthorized"}), 401
		return None

# This creates the error handlers for the API.
def register_error_handlers(app):
	@app.errorhandler(404)
	def not_found(_error):
		return jsonify({"error": "The resource not found"}), 404

	# If the rate limit is exceeded, this is thrown.
	@app.errorhandler(429)
	def rate_limit_exceeded(_error):
		return jsonify({
			"error": "The rate limit was exceeded",
			"message": "There were too many requests."
		}), 429

	@app.errorhandler(IntegrityError)
	def integrity_error(_error):
		db.session.rollback()
		return jsonify({"error": "The database data does not match the request."}), 409

	@app.errorhandler(SQLAlchemyError)
	def database_error(_error):
		db.session.rollback()
		app.logger.exception("Database operation failed")
		return jsonify({"error": "The database operation failed"}), 500

	@app.errorhandler(500)
	def internal_error(_error):
		db.session.rollback()
		return jsonify({"error": "Internal server error"}), 500

def register_health_route(app, limiter):
	@app.route("/health", methods=["GET"])
	@limiter.limit("30 per minute", override_defaults=False)
	def health():
		return jsonify({"name": "Student/Sports API", "version": "1.0", "status": "online"})

def register_site_routes(app):
	@app.route("/", methods=["GET"])
	def home_page():
		return render_template("index.html")

	@app.route("/admin", methods=["GET"])
	def admin_page():
		return render_template("admin.html")

	@app.route("/uploads/staff/<path:filename>", methods=["GET"])
	def staff_upload_file(filename):
		return send_from_directory(STAFF_UPLOAD_DIR, filename)

	@app.route("/images/<path:filename>", methods=["GET"])
	def site_image_file(filename):
		return send_from_directory(os.path.join(SITE_DIR, "images"), filename)

	@app.route("/<string:filename>", methods=["GET"])
	def site_file(filename):
		if filename not in SITE_FILES:
			return jsonify({"error": "The resource not found"}), 404
		return send_from_directory(SITE_DIR, filename)

	#added error handler for csrf
	@app.errorhandler(CSRFError)
	def handle_csrf_error(e):
		return jsonify({"error": "CSRF token missing or invalid. Please refresh the page."}), 400

def validate_choice(value, field_name, choices):
	value, error = validate_string(value, field_name, required=True)
	if error:
		return None, error
	if value not in choices:
		return None, f"{field_name} is not a valid option"
	return value, None

def validate_email(value, field_name="Email"):
	email, error = validate_string(
		value, field_name, True, column_max_length(RecruitmentSubmission, "Email")
	)
	if error:
		return None, error
	if EMAIL_PATTERN.fullmatch(email) is None:
		return None, f"{field_name} is not a valid email address"
	return email.lower(), None

def validate_recruitment_data(data):
	full_name, error = validate_string(
		data.get("FullName"), "FullName", True, column_max_length(RecruitmentSubmission, "FullName")
	)
	if error:
		return None, error

	email, error = validate_email(data.get("Email"))
	if error:
		return None, error

	position, error = validate_choice(data.get("Position"), "Position", POSITION_CHOICES)
	if error:
		return None, error

	experience, error = validate_choice(
		data.get("ExperienceLevel"), "ExperienceLevel", EXPERIENCE_CHOICES
	)
	if error:
		return None, error

	comments, error = validate_string(
		data.get("Comments"), "Comments", False, column_max_length(RecruitmentSubmission, "Comments")
	)
	if error:
		return None, error

	return {
		"FullName": full_name,
		"Email": email,
		"Position": position,
		"ExperienceLevel": experience,
		"Comments": comments
	}, None

def submission_to_dict(submission):
	return {
		"SubmissionID": submission.SubmissionID,
		"FullName": submission.FullName,
		"Email": submission.Email,
		"Position": submission.Position,
		"ExperienceLevel": submission.ExperienceLevel,
		"Comments": submission.Comments,
		"SubmittedAt": submission.SubmittedAt.isoformat() if submission.SubmittedAt else None
	}

def current_admin():
	admin_id = session.get("admin_id")
	if not admin_id:
		return None
	admin = db.session.get(AdminAccount, admin_id)
	if admin is None:
		session.clear()
	return admin

def register_recruitment_routes(app, limiter):
	@app.route("/api/recruitment", methods=["POST"])
	@limiter.limit("5 per minute; 30 per day", override_defaults=False)
	def create_recruitment_submission():
		data, error = request_object()
		if error:
			return error

		submission_data, validation_error = validate_recruitment_data(data)
		if validation_error:
			return jsonify({"error": validation_error}), 400

		submission = RecruitmentSubmission(SubmissionID=str(uuid.uuid4()), **submission_data)
		db.session.add(submission)
		db.session.commit()
		return jsonify({"message": "Submission received"}), 201

def register_admin_routes(app, limiter):
	# Compared against when the email is unknown so login timing doesn't reveal which emails exist.
	dummy_password_hash = generate_password_hash(secrets.token_hex(16))

	@app.route("/api/admin/login", methods=["POST"])
	@limiter.limit("5 per minute", override_defaults=False)
	def admin_login():
		data, error = request_object()
		if error:
			return error

		email = data.get("Email")
		password = data.get("Password")
		if not isinstance(email, str) or not isinstance(password, str) or not email or not password:
			return jsonify({"error": "Email and Password are required"}), 400

		admin = db.session.scalar(
			select(AdminAccount).where(AdminAccount.Email == email.strip().lower())
		)
		password_hash = admin.PasswordHash if admin else dummy_password_hash
		if not check_password_hash(password_hash, password) or admin is None:
			return jsonify({"error": "Invalid email or password"}), 401

		session.clear()
		session.permanent = True
		session["admin_id"] = admin.AdminID
		return jsonify({"Email": admin.Email})

	@app.route("/api/admin/logout", methods=["POST"])
	def admin_logout():
		session.clear()
		return jsonify({"message": "Logged out"})

	@app.route("/api/admin/me", methods=["GET"])
	def admin_me():
		admin = current_admin()
		if admin is None:
			return jsonify({"error": "Unauthorized"}), 401
		return jsonify({"Email": admin.Email})

	@app.route("/api/admin/recruitment", methods=["GET"])
	@limiter.limit("60 per minute", override_defaults=False)
	def admin_list_recruitment():
		if current_admin() is None:
			return jsonify({"error": "Unauthorized"}), 401

		page, per_page, error = pagination_values()
		if error:
			return error
		pagination = db.paginate(
			select(RecruitmentSubmission).order_by(
				RecruitmentSubmission.SubmittedAt.desc(), RecruitmentSubmission.SubmissionID
			),
			page=page,
			per_page=per_page,
			error_out=False
		)
		return paginated_response("submissions", pagination, submission_to_dict)

	@app.route("/api/admin/recruitment/<string:submission_id>", methods=["DELETE"])
	@limiter.limit("30 per minute", override_defaults=False)
	def admin_delete_recruitment(submission_id):
		if current_admin() is None:
			return jsonify({"error": "Unauthorized"}), 401

		submission = db.session.get(RecruitmentSubmission, submission_id)
		if submission is None:
			return jsonify({"error": "Submission was not found"}), 404
		db.session.delete(submission)
		db.session.commit()
		return jsonify({"message": "Submission deleted"})

	@app.route("/api/admin/events", methods=["GET"])
	@limiter.limit("60 per minute", override_defaults=False)
	def admin_list_events():
		if current_admin() is None:
			return jsonify({"error": "Unauthorized"}), 401
		events = db.session.scalars(
			select(ScheduleEvent).order_by(ScheduleEvent.EventDate, ScheduleEvent.EventTime, ScheduleEvent.EventID)
		).all()
		return jsonify({"events": [event_to_dict(event) for event in events]})

	@app.route("/api/admin/events", methods=["POST"])
	@limiter.limit("30 per minute", override_defaults=False)
	def admin_create_event():
		if current_admin() is None:
			return jsonify({"error": "Unauthorized"}), 401
		data, error = request_object()
		if error:
			return error
		event_data, validation_error = validate_event_data(data)
		if validation_error:
			return jsonify({"error": validation_error}), 400
		event = ScheduleEvent(EventID=str(uuid.uuid4()), **event_data)
		db.session.add(event)
		db.session.commit()
		return jsonify(event_to_dict(event)), 201

	@app.route("/api/admin/events/<string:event_id>", methods=["PUT"])
	@limiter.limit("30 per minute", override_defaults=False)
	def admin_update_event(event_id):
		if current_admin() is None:
			return jsonify({"error": "Unauthorized"}), 401
		event = db.session.get(ScheduleEvent, event_id)
		if event is None:
			return jsonify({"error": "Event was not found"}), 404
		data, error = request_object()
		if error:
			return error
		event_data, validation_error = validate_event_data(data)
		if validation_error:
			return jsonify({"error": validation_error}), 400
		for key, value in event_data.items():
			setattr(event, key, value)
		db.session.commit()
		return jsonify(event_to_dict(event))

	@app.route("/api/admin/events/<string:event_id>", methods=["DELETE"])
	@limiter.limit("30 per minute", override_defaults=False)
	def admin_delete_event(event_id):
		if current_admin() is None:
			return jsonify({"error": "Unauthorized"}), 401
		event = db.session.get(ScheduleEvent, event_id)
		if event is None:
			return jsonify({"error": "Event was not found"}), 404
		db.session.delete(event)
		db.session.commit()
		return jsonify({"message": "Event deleted"})

	@app.route("/api/admin/staff", methods=["GET"])
	@limiter.limit("60 per minute", override_defaults=False)
	def admin_get_staff():
		if current_admin() is None:
			return jsonify({"error": "Unauthorized"}), 401
		return jsonify(staff_to_dict(get_or_create_staff()))

	@app.route("/api/admin/staff", methods=["PUT"])
	@limiter.limit("20 per minute", override_defaults=False)
	def admin_update_staff():
		if current_admin() is None:
			return jsonify({"error": "Unauthorized"}), 401
		data, error = request_object()
		if error:
			return error
		staff_data, validation_error = validate_staff_data(data)
		if validation_error:
			return jsonify({"error": validation_error}), 400
		staff = get_or_create_staff()
		for key, value in staff_data.items():
			setattr(staff, key, value)
		db.session.commit()
		return jsonify(staff_to_dict(staff))

	@app.route("/api/admin/staff/<string:role>/image", methods=["POST"])
	@limiter.limit("20 per minute", override_defaults=False)
	def admin_upload_staff_image(role):
		if current_admin() is None:
			return jsonify({"error": "Unauthorized"}), 401

		role_key = (role or "").strip().lower()
		image_field = STAFF_IMAGE_FIELDS.get(role_key)
		if image_field is None:
			return jsonify({"error": "Staff role was not found"}), 404

		upload = request.files.get("image")
		if upload is None or not upload.filename:
			return jsonify({"error": "An image file is required"}), 400

		content_type = (upload.mimetype or "").lower()
		if content_type not in ALLOWED_STAFF_IMAGE_TYPES:
			return jsonify({"error": "Image must be a JPG, PNG, or WEBP file"}), 400

		try:
			from PIL import Image
			image = Image.open(upload.stream).convert("RGB")
			image = crop_to_square(image).resize(STAFF_IMAGE_SIZE, Image.Resampling.LANCZOS)
		except Exception:
			return jsonify({"error": "Could not read that image file"}), 400

		os.makedirs(STAFF_UPLOAD_DIR, exist_ok=True)
		filename = f"{role_key}-{uuid.uuid4().hex}.jpg"
		filepath = os.path.join(STAFF_UPLOAD_DIR, filename)
		image.save(filepath, format="JPEG", quality=90)

		staff = get_or_create_staff()
		old_name = getattr(staff, image_field, None)
		setattr(staff, image_field, filename)
		db.session.commit()

		if old_name and old_name != filename:
			old_path = os.path.join(STAFF_UPLOAD_DIR, secure_filename(old_name))
			if os.path.isfile(old_path):
				try:
					os.remove(old_path)
				except OSError:
					pass

		return jsonify({"imageUrl": f"/uploads/staff/{filename}", "filename": filename})

	@app.route("/api/admin/season-records", methods=["GET"])
	@limiter.limit("60 per minute", override_defaults=False)
	def admin_list_season_records():
		if current_admin() is None:
			return jsonify({"error": "Unauthorized"}), 401
		return jsonify({"records": list_season_records()})

	@app.route("/api/admin/season-records", methods=["POST"])
	@limiter.limit("30 per minute", override_defaults=False)
	def admin_create_season_record():
		if current_admin() is None:
			return jsonify({"error": "Unauthorized"}), 401
		data, error = request_object()
		if error:
			return error
		record_data, validation_error = validate_season_record_data(data)
		if validation_error:
			return jsonify({"error": validation_error}), 400
		existing = db.session.scalar(
			select(SeasonRecord).where(SeasonRecord.SeasonLabel == record_data["SeasonLabel"])
		)
		if existing is not None:
			return jsonify({"error": "A record for that season already exists"}), 409
		record = SeasonRecord(RecordID=str(uuid.uuid4()), **record_data)
		db.session.add(record)
		db.session.commit()
		return jsonify(season_record_to_dict(record)), 201

	@app.route("/api/admin/season-records/<string:record_id>", methods=["PUT"])
	@limiter.limit("30 per minute", override_defaults=False)
	def admin_update_season_record(record_id):
		if current_admin() is None:
			return jsonify({"error": "Unauthorized"}), 401
		record = db.session.get(SeasonRecord, record_id)
		if record is None:
			return jsonify({"error": "Season record was not found"}), 404
		data, error = request_object()
		if error:
			return error
		record_data, validation_error = validate_season_record_data(data)
		if validation_error:
			return jsonify({"error": validation_error}), 400
		duplicate = db.session.scalar(
			select(SeasonRecord).where(
				SeasonRecord.SeasonLabel == record_data["SeasonLabel"],
				SeasonRecord.RecordID != record_id
			)
		)
		if duplicate is not None:
			return jsonify({"error": "A record for that season already exists"}), 409
		for key, value in record_data.items():
			setattr(record, key, value)
		db.session.commit()
		return jsonify(season_record_to_dict(record))

	@app.route("/api/admin/season-records/<string:record_id>", methods=["DELETE"])
	@limiter.limit("30 per minute", override_defaults=False)
	def admin_delete_season_record(record_id):
		if current_admin() is None:
			return jsonify({"error": "Unauthorized"}), 401
		record = db.session.get(SeasonRecord, record_id)
		if record is None:
			return jsonify({"error": "Season record was not found"}), 404
		db.session.delete(record)
		db.session.commit()
		return jsonify({"message": "Season record deleted"})

def event_to_dict(event):
	return {
		"EventID": event.EventID,
		"EventType": event.EventType,
		"Opponent": event.Opponent,
		"HomeAway": event.HomeAway,
		"Status": event.Status,
		"EventDate": event.EventDate.isoformat() if event.EventDate else None,
		"EventTime": event.EventTime,
		"Location": event.Location
	}

def staff_image_url(filename):
	if not filename:
		return ""
	return f"/uploads/staff/{secure_filename(filename)}"

def staff_to_dict(staff):
	return {
		"PresidentName": staff.PresidentName or "",
		"CoachName": staff.CoachName or "",
		"CaptainName": staff.CaptainName or "",
		"PresidentImage": staff_image_url(getattr(staff, "PresidentImage", None)),
		"CoachImage": staff_image_url(getattr(staff, "CoachImage", None)),
		"CaptainImage": staff_image_url(getattr(staff, "CaptainImage", None))
	}

def get_or_create_staff():
	staff = db.session.get(TeamStaff, STAFF_CONFIG_ID)
	if staff is None:
		staff = TeamStaff(ConfigID=STAFF_CONFIG_ID)
		db.session.add(staff)
		db.session.commit()
	return staff

def crop_to_square(image):
	width, height = image.size
	side = min(width, height)
	left = (width - side) // 2
	top = (height - side) // 2
	return image.crop((left, top, left + side, top + side))

def ensure_staff_image_columns():
	os.makedirs(STAFF_UPLOAD_DIR, exist_ok=True)
	with db.engine.begin() as connection:
		existing = {
			row[1]
			for row in connection.execute(text("PRAGMA table_info(team_staff)")).fetchall()
		}
		for column_name in ("PresidentImage", "CoachImage", "CaptainImage"):
			if column_name not in existing:
				connection.execute(text(f"ALTER TABLE team_staff ADD COLUMN {column_name} VARCHAR(255)"))

def validate_event_data(data):
	event_type, error = validate_choice(data.get("EventType"), "EventType", EVENT_TYPE_CHOICES)
	if error:
		return None, error

	status, error = validate_choice(data.get("Status"), "Status", EVENT_STATUS_CHOICES)
	if error:
		return None, error

	event_date = parse_date(data.get("EventDate"))
	if event_date is None:
		return None, "EventDate is not a valid date or is not in YYYY-MM-DD format."

	event_time, error = validate_string(
		data.get("EventTime"), "EventTime", True, column_max_length(ScheduleEvent, "EventTime")
	)
	if error:
		return None, error

	location, error = validate_string(
		data.get("Location"), "Location", False, column_max_length(ScheduleEvent, "Location")
	)
	if error:
		return None, error

	opponent, error = validate_string(
		data.get("Opponent"), "Opponent", False, column_max_length(ScheduleEvent, "Opponent")
	)
	if error:
		return None, error

	home_away = None
	if event_type == "game":
		if not opponent:
			return None, "Opponent is required for games"
		home_away, error = validate_choice(data.get("HomeAway"), "HomeAway", HOME_AWAY_CHOICES)
		if error:
			return None, error
	else:
		raw_home_away = data.get("HomeAway")
		if raw_home_away not in (None, ""):
			home_away, error = validate_choice(raw_home_away, "HomeAway", HOME_AWAY_CHOICES)
			if error:
				return None, error
		if not opponent:
			opponent = "Team Practice"

	return {
		"EventType": event_type,
		"Opponent": opponent,
		"HomeAway": home_away,
		"Status": status,
		"EventDate": event_date,
		"EventTime": event_time,
		"Location": location
	}, None

def validate_staff_data(data):
	fields = {}
	for field_name in (
		"PresidentName", "CoachName", "CaptainName"
	):
		value, error = validate_string(
			data.get(field_name), field_name, False, column_max_length(TeamStaff, field_name)
		)
		if error:
			return None, error
		fields[field_name] = value

	return fields, None

def season_record_to_dict(record):
	return {
		"RecordID": record.RecordID,
		"SeasonLabel": record.SeasonLabel,
		"Wins": record.Wins,
		"Losses": record.Losses
	}

def current_academic_season_label(today=None):
	today = today or date.today()
	start_year = today.year if today.month >= 8 else today.year - 1
	return f"{start_year}-{start_year + 1}"

def season_sort_key(label):
	try:
		return int(label.split("-")[0])
	except (TypeError, ValueError, IndexError):
		return 0

def list_season_records():
	records = db.session.scalars(select(SeasonRecord)).all()
	return sorted(
		[season_record_to_dict(record) for record in records],
		key=lambda item: season_sort_key(item["SeasonLabel"]),
		reverse=True
	)

def season_records_summary():
	records = list_season_records()
	current_label = current_academic_season_label()
	current = next((record for record in records if record["SeasonLabel"] == current_label), None)
	total_wins = sum(record["Wins"] for record in records)
	total_losses = sum(record["Losses"] for record in records)
	return {
		"records": records,
		"currentSeason": current_label,
		"currentRecord": current or {"SeasonLabel": current_label, "Wins": 0, "Losses": 0},
		"allTime": {"Wins": total_wins, "Losses": total_losses}
	}

def validate_season_record_data(data):
	season_label, error = validate_string(
		data.get("SeasonLabel"), "SeasonLabel", True, column_max_length(SeasonRecord, "SeasonLabel")
	)
	if error:
		return None, error
	if SEASON_LABEL_PATTERN.fullmatch(season_label) is None:
		return None, "SeasonLabel must look like 2024-2025"

	start_year, end_year = season_label.split("-")
	if int(end_year) != int(start_year) + 1:
		return None, "SeasonLabel years must be consecutive (for example 2024-2025)"

	def parse_count(value, field_name):
		if isinstance(value, bool) or not isinstance(value, (int, str)):
			return None, f"{field_name} must be a whole number"
		if isinstance(value, str):
			value = value.strip()
			if not value.isdigit():
				return None, f"{field_name} must be a whole number"
			value = int(value)
		if value < 0:
			return None, f"{field_name} cannot be negative"
		return value, None

	wins, error = parse_count(data.get("Wins"), "Wins")
	if error:
		return None, error
	losses, error = parse_count(data.get("Losses"), "Losses")
	if error:
		return None, error

	return {
		"SeasonLabel": season_label,
		"Wins": wins,
		"Losses": losses
	}, None

def register_public_content_routes(app, limiter):
	@app.route("/api/events", methods=["GET"])
	@limiter.limit("60 per minute", override_defaults=False)
	def list_events():
		events = db.session.scalars(
			select(ScheduleEvent).order_by(ScheduleEvent.EventDate, ScheduleEvent.EventTime, ScheduleEvent.EventID)
		).all()
		return jsonify({"events": [event_to_dict(event) for event in events]})

	@app.route("/api/staff", methods=["GET"])
	@limiter.limit("60 per minute", override_defaults=False)
	def list_staff():
		return jsonify(staff_to_dict(get_or_create_staff()))

	@app.route("/api/season-records", methods=["GET"])
	@limiter.limit("60 per minute", override_defaults=False)
	def list_public_season_records():
		return jsonify(season_records_summary())

def register_user_routes(app, limiter):
	@app.route("/api/users", methods=["GET"])
	@limiter.limit("30 per minute", override_defaults=False)
	def get_users():
		page, per_page, error = pagination_values()
		if error:
			return error
		pagination = db.paginate(
			select(UserDataTable).order_by(UserDataTable.username),
			page=page,
			per_page=per_page,
			error_out=False
		)
		return paginated_response(
			"users", pagination,
			lambda user: {"UUID": user.UUID, "username": user.username}
		)

	@app.route("/api/users/<string:user_id>", methods=["GET"])
	@limiter.limit("30 per minute", override_defaults=False)
	def get_user(user_id):
		user = db.session.get(UserDataTable, user_id)
		if user is None:
			return jsonify({"error": "User was not found"}), 404
		return jsonify({"UUID": user.UUID, "username": user.username})

def register_major_routes(app, limiter):
	@app.route("/api/majors", methods=["GET"])
	@limiter.limit("60 per minute", override_defaults=False)
	def get_majors():
		page, per_page, error = pagination_values()
		if error:
			return error
		pagination = db.paginate(
			select(Major).order_by(Major.MajorName),
			page=page,
			per_page=per_page,
			error_out=False
		)
		return paginated_response("majors", pagination, major_to_dict)

	@app.route("/api/majors/<string:major_id>", methods=["GET"])
	@limiter.limit("60 per minute", override_defaults=False)
	def get_major(major_id):
		major = db.session.get(Major, major_id)
		if major is None:
			return jsonify({"error": "Major was not found"}), 404
		return jsonify(major_to_dict(major))

	@app.route("/api/majors", methods=["POST"])
	@limiter.limit("10 per minute", override_defaults=False)
	def create_major():
		data, error = request_object()
		if error:
			return error

		major_name, validation_error = validate_string(
			data.get("MajorName"),
			"MajorName",
			required=True,
			max_length=column_max_length(Major, "MajorName")
		)
		if validation_error:
			return jsonify({"error": validation_error}), 400

		major = Major(MajorUUID=str(uuid.uuid4()), MajorName=major_name)
		db.session.add(major)
		db.session.commit()
		return jsonify(major_to_dict(major)), 201


def register_player_routes(app, limiter):
	@app.route("/api/players", methods=["GET"])
	@limiter.limit("60 per minute", override_defaults=False)
	def get_players():
		page, per_page, error = pagination_values()
		if error:
			return error
		statement = select(Player).options(
			selectinload(Player.major)
		).order_by(Player.LastName, Player.FirstName, Player.PlayerID)
		pagination = db.paginate(
			statement, page=page, per_page=per_page, error_out=False
		)
		return paginated_response("players", pagination, player_to_dict)

	@app.route("/api/players/<string:player_id>", methods=["GET"])
	@limiter.limit("60 per minute", override_defaults=False)
	def get_player(player_id):
		player = db.session.scalar(
			select(Player)
			.options(selectinload(Player.major))
			.where(Player.PlayerID == player_id)
		)
		if player is None:
			return jsonify({"error": "Player was not found"}), 404
		return jsonify(player_to_dict(player))

	@app.route("/api/players", methods=["POST"])
	@limiter.limit("10 per minute", override_defaults=False)
	def create_player():
		data, error = request_object()
		if error:
			return error

		player_data, validation_error = validate_player_data(data)
		if validation_error:
			return player_error(validation_error)

		player = Player(PlayerID=str(uuid.uuid4()), **player_data)
		db.session.add(player)
		db.session.commit()
		db.session.refresh(player)
		return jsonify(player_to_dict(player)), 201

	@app.route("/api/players/<string:player_id>/seasons", methods=["GET"])
	@limiter.limit("60 per minute", override_defaults=False)
	def get_player_seasons(player_id):
		player = db.session.scalar(
			select(Player)
			.options(selectinload(Player.major))
			.where(Player.PlayerID == player_id)
		)
		if player is None:
			return jsonify({"error": "Player was not found"}), 404

		page, per_page, error = pagination_values()
		if error:
			return error

		statement = select(SportSeasonPlayer).options(
			selectinload(SportSeasonPlayer.sport)
		).where(
			SportSeasonPlayer.PlayerID == player_id
		).order_by(SportSeasonPlayer.SportUUID)
		pagination = db.paginate(
			statement, page=page, per_page=per_page, error_out=False
		)
		seasons = [
			season_to_dict(record.sport)
			for record in pagination.items
			if record.sport is not None
		]
		return jsonify({
			"player": player_to_dict(player),
			"seasons": seasons,
			"page": pagination.page,
			"per_page": pagination.per_page,
			"total": pagination.total,
			"pages": pagination.pages
		})


def register_season_routes(app, limiter):
	@app.route("/api/seasons", methods=["GET"])
	@limiter.limit("60 per minute", override_defaults=False)
	def get_seasons():
		page, per_page, error = pagination_values()
		if error:
			return error
		pagination = db.paginate(
			select(SportSeason).order_by(SportSeason.SportName, SportSeason.SportUUID),
			page=page,
			per_page=per_page,
			error_out=False
		)

		return paginated_response("seasons", pagination, season_to_dict)

	@app.route("/api/seasons/<string:season_id>", methods=["GET"])
	@limiter.limit("60 per minute", override_defaults=False)
	def get_season(season_id):
		season = db.session.get(SportSeason, season_id)
		if season is None:
			return jsonify({"error": "Sport season was not found"}), 404
		return jsonify(season_to_dict(season))

	@app.route("/api/seasons/<string:season_id>/players", methods=["GET"])
	@limiter.limit("60 per minute", override_defaults=False)
	def get_season_players(season_id):
		season = db.session.get(SportSeason, season_id)
		if season is None:
			return jsonify({"error": "Sport season was not found"}), 404

		page, per_page, error = pagination_values()
		if error:
			return error

		statement = (select(SportSeasonPlayer).options(selectinload(SportSeasonPlayer.player).selectinload(Player.major))
					 .where(SportSeasonPlayer.SportUUID == season_id).order_by(SportSeasonPlayer.PlayerID))
		pagination = db.paginate(
			statement, page=page, per_page=per_page, error_out=False
		)

		players = [
			player_to_dict(record.player)
			for record in pagination.items
			if record.player is not None
		]

		return jsonify({
			"season": season_to_dict(season),
			"players": players,
			"page": pagination.page,
			"per_page": pagination.per_page,
			"total": pagination.total,
			"pages": pagination.pages
		})

# This creates the Command Line Interface commands.
def register_cli_commands(app):
	@app.cli.command("init-db")
	def init_db():
		db.create_all()
		ensure_staff_image_columns()
		print("Database initialized.")

	@app.cli.command("create-admin")
	@click.option("--email", prompt=True)
	@click.password_option()
	def create_admin(email, password):
		email, error = validate_email(email)
		if error:
			raise click.BadParameter(error, param_hint="--email")
		if len(password) < MIN_ADMIN_PASSWORD_LENGTH:
			raise click.BadParameter(
				f"Password must be at least {MIN_ADMIN_PASSWORD_LENGTH} characters", param_hint="--password"
			)

		db.create_all()
		admin = db.session.scalar(select(AdminAccount).where(AdminAccount.Email == email))
		if admin is None:
			db.session.add(AdminAccount(
				AdminID=str(uuid.uuid4()), Email=email, PasswordHash=generate_password_hash(password)
			))
			print(f"Admin account created for {email}.")
		else:
			admin.PasswordHash = generate_password_hash(password)
			print(f"Password updated for {email}.")
		db.session.commit()

	@app.cli.command("delete-admin")
	@click.option("--email", prompt=True)
	def delete_admin(email):
		admin = db.session.scalar(
			select(AdminAccount).where(AdminAccount.Email == email.strip().lower())
		)
		if admin is None:
			print(f"No admin account found for {email}.")
			return
		db.session.delete(admin)
		db.session.commit()
		print(f"Admin account {admin.Email} deleted.")

def ensure_default_admin():
	"""Create a shared local admin account if none exists yet."""
	existing = db.session.scalar(select(AdminAccount).limit(1))
	if existing is not None:
		return

	email = os.getenv("DEFAULT_ADMIN_EMAIL", "coach@example.com").strip().lower()
	password = os.getenv("DEFAULT_ADMIN_PASSWORD", "supersecret1")
	db.session.add(AdminAccount(
		AdminID=str(uuid.uuid4()),
		Email=email,
		PasswordHash=generate_password_hash(password)
	))
	db.session.commit()
	print(f"Default admin created: {email} / {password}")

def ensure_database_ready(app):
	"""Create missing tables automatically so local teammates can run without extra setup."""
	database_url = str(app.config.get("SQLALCHEMY_DATABASE_URI", ""))
	using_sqlite = database_url.startswith("sqlite:")
	flag = os.getenv("CREATE_TABLES_ON_STARTUP", "auto").strip().lower()

	# Opt out only with an explicit false. SQLite always auto-prepares by default.
	if flag in {"0", "false", "no"}:
		return
	if not using_sqlite and flag not in {"1", "true", "yes"}:
		return

	with app.app_context():
		db.create_all()
		ensure_staff_image_columns()
		if using_sqlite:
			ensure_default_admin()

def create_app():
	app = Flask(__name__, template_folder=SITE_DIR) #added template folder
	configure_app(app)
	limiter = configure_extensions(app)
	register_security(app)
	register_error_handlers(app)
	register_health_route(app, limiter)
	register_site_routes(app)
	register_recruitment_routes(app, limiter)
	register_public_content_routes(app, limiter)
	register_admin_routes(app, limiter)
	register_user_routes(app, limiter)
	register_major_routes(app, limiter)
	register_player_routes(app, limiter)
	register_season_routes(app, limiter)
	register_cli_commands(app)
	ensure_database_ready(app)
	return app

app = create_app()

if __name__ == "__main__":
	debug = os.getenv("FLASK_DEBUG", "false").strip().lower() in {"1", "true", "yes"}

	app.run(
		host=os.getenv("HOST", "127.0.0.1"),
		port=int(os.getenv("PORT", "5000")),
		debug=debug
	)
