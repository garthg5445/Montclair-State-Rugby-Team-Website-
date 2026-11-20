from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def utc_now():
    return datetime.now(timezone.utc)


class UserDataTable(db.Model):
    __tablename__ = "userdata"

    UUID = db.Column("UUID", db.Text, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    PasswordWithSalt = db.Column("PasswordWithSalt", db.Text, nullable=False)


class Major(db.Model):
    __tablename__ = "major"

    MajorUUID = db.Column("MajorUUID", db.Text, primary_key=True)
    MajorName = db.Column(db.String(50), nullable=False)


class PasswordSalt(db.Model):
    __tablename__ = "password_salt"

    UUID = db.Column("UUID", db.Text, primary_key=True)
    PasswordSalt = db.Column("PasswordSalt", db.Text)


class Player(db.Model):
    __tablename__ = "player"

    PlayerID = db.Column("PlayerID", db.Text, primary_key=True)

    MajorID = db.Column(
        "MajorID",
        db.Text,
        db.ForeignKey("major.MajorUUID")
    )

    major = db.relationship(
        "Major",
        foreign_keys=[MajorID]
    )

    StocktonID = db.Column(db.String(20))
    FirstName = db.Column(db.String(50))
    LastName = db.Column(db.String(50))
    DateOfBirth = db.Column(db.Date)
    GraduationDateExpected = db.Column(db.Date)


class SportSeason(db.Model):
    __tablename__ = "sportseason"

    SportUUID = db.Column("SportUUID", db.Text, primary_key=True)
    SportName = db.Column(db.String(50))
    StartDate = db.Column(db.Date)
    EndDate = db.Column(db.Date)


class SportSeasonPlayer(db.Model):
    __tablename__ = "sportseasonplayer"

    SportUUID = db.Column(
        "SportUUID",
        db.Text,
        db.ForeignKey("sportseason.SportUUID"),
        primary_key=True
    )

    PlayerID = db.Column(
        "PlayerID",
        db.Text,
        db.ForeignKey("player.PlayerID"),
        primary_key=True
    )

    sport = db.relationship(
        "SportSeason",
        foreign_keys=[SportUUID]
    )

    player = db.relationship(
        "Player",
        foreign_keys=[PlayerID]
    )


class AdminAccount(db.Model):
    __tablename__ = "admin_account"

    AdminID = db.Column("AdminID", db.Text, primary_key=True)
    Email = db.Column(db.String(254), nullable=False, unique=True)
    PasswordHash = db.Column(db.Text, nullable=False)
    CreatedAt = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    #jaosn22 changes 11/13/26
    FailedLoginAttempts = db.Column(db.Integer, nullable=False, default=0)
    LockedUntil = db.Column(db.DateTime, nullable=True)
    TOTPSecret = db.Column(db.Text, nullable=True) #for MFA


class RecruitmentSubmission(db.Model):
    __tablename__ = "recruitment_submission"

    SubmissionID = db.Column("SubmissionID", db.Text, primary_key=True)
    FullName = db.Column(db.String(100), nullable=False)
    Email = db.Column(db.String(254), nullable=False)
    Position = db.Column(db.String(50), nullable=False)
    ExperienceLevel = db.Column(db.String(50), nullable=False)
    Comments = db.Column(db.String(300))
    SubmittedAt = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, index=True)


class ScheduleEvent(db.Model):
    __tablename__ = "schedule_event"

    EventID = db.Column("EventID", db.Text, primary_key=True)
    EventType = db.Column(db.String(20), nullable=False)  # game | practice
    Opponent = db.Column(db.String(100))  # opposing team for games; optional label for practices
    HomeAway = db.Column(db.String(10))  # home | away (games only)
    Status = db.Column(db.String(20), nullable=False, default="scheduled")
    EventDate = db.Column(db.Date, nullable=False, index=True)
    EventTime = db.Column(db.String(20), nullable=False)
    Location = db.Column(db.String(150))
    CreatedAt = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class TeamStaff(db.Model):
    __tablename__ = "team_staff"

    ConfigID = db.Column("ConfigID", db.Text, primary_key=True)
    PresidentName = db.Column(db.String(100))
    PresidentEmail = db.Column(db.String(254))
    PresidentImage = db.Column(db.String(255))
    CoachName = db.Column(db.String(100))
    CoachEmail = db.Column(db.String(254))
    CoachImage = db.Column(db.String(255))
    CaptainName = db.Column(db.String(100))
    CaptainEmail = db.Column(db.String(254))
    CaptainImage = db.Column(db.String(255))
    UpdatedAt = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class SeasonRecord(db.Model):
    __tablename__ = "season_record"

    RecordID = db.Column("RecordID", db.Text, primary_key=True)
    SeasonLabel = db.Column(db.String(20), nullable=False, unique=True)  # e.g. 2024-2025
    Wins = db.Column(db.Integer, nullable=False, default=0)
    Losses = db.Column(db.Integer, nullable=False, default=0)
    CreatedAt = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)