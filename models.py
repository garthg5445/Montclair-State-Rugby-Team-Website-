from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


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