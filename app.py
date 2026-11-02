import hmac
import os
import re
import uuid
from datetime import date

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import selectinload

from models import db, UserDataTable, Major, Player, SportSeason, SportSeasonPlayer

DEFAULT_CORS_ORIGINS = (
	"http://localhost:3000,"
	"http://127.0.0.1:3000,"
	"http://localhost:5173,"
	"http://127.0.0.1:5173"
)

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
	database_url = os.getenv("DATABASE_URL", "sqlite:///school.db")

	if database_url.startswith("postgres://"):
		database_url = "postgresql://" + database_url[len("postgres://"):]

	app.config.update(
		SQLALCHEMY_DATABASE_URI=database_url,
		SQLALCHEMY_TRACK_MODIFICATIONS=False,
		API_KEY=os.getenv("API_KEY")
	)

def configure_extensions(app):
	db.init_app(app)
	CORS(
		app,
		resources={r"/api/*": {"origins": csv_env("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)}},
		allow_headers=["Content-Type", "X-API-Key"],
		methods=["GET", "POST", "OPTIONS"],
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
	@app.route("/", methods=["GET"])
	@limiter.limit("30 per minute", override_defaults=False)
	def index():
		return jsonify({"name": "Student/Sports API", "version": "1.0", "status": "online"})

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
		print("Database initialized.")

def create_app():
	app = Flask(__name__)
	configure_app(app)
	limiter = configure_extensions(app)
	register_security(app)
	register_error_handlers(app)
	register_health_route(app, limiter)
	register_user_routes(app, limiter)
	register_major_routes(app, limiter)
	register_player_routes(app, limiter)
	register_season_routes(app, limiter)
	register_cli_commands(app)
	return app

app = create_app()

if __name__ == "__main__":
	debug = os.getenv("FLASK_DEBUG", "false").strip().lower() in {"1", "true", "yes"}
	create_tables = os.getenv("CREATE_TABLES_ON_STARTUP", "false").strip().lower() in {
		"1", "true", "yes"
	}

	if create_tables:
		with app.app_context():
			db.create_all()

	app.run(
		host=os.getenv("HOST", "127.0.0.1"),
		port=int(os.getenv("PORT", "5000")),
		debug=debug
	)
