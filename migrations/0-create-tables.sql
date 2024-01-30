-- Users table
CREATE TABLE IF NOT EXISTS users (
	id INTEGER NOT NULL, -- sqlite
	id SERIAL NOT NULL, -- postgresql
	username CHAR(20) NOT NULL UNIQUE,
	password_hash CHAR(100) NOT NULL,
	PRIMARY KEY (id)
);

-- Auth table
CREATE TABLE IF NOT EXISTS auth (
	id INTEGER NOT NULL, -- sqlite
	id SERIAL NOT NULL, -- postgresql
	user_id INTEGER NOT NULL,
	device_id INTEGER NOT NULL,
	token_id INTEGER NOT NULL,
	family_id INTEGER NOT NULL,
	is_invalidated BOOLEAN NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY (user_id) REFERENCES users (id)
);

-- Game settings table
CREATE TABLE IF NOT EXISTS game_settings (
	id INTEGER NOT NULL, -- sqlite
	id SERIAL NOT NULL, -- postgresql
	user_id INTEGER NOT NULL,
	theme INTEGER NOT NULL DEFAULT 0,
	initial_zoom BOOLEAN NOT NULL DEFAULT FALSE,
	action_toggle BOOLEAN NOT NULL DEFAULT TRUE,
	default_action VARCHAR(4) NOT NULL CHECK (default_action IN ('dig', 'mark')) DEFAULT 'dig',
	long_tap_delay INTEGER NOT NULL CHECK(long_tap_delay >= 0) DEFAULT 150,
	easy_digging BOOLEAN NOT NULL DEFAULT FALSE,
	vibration BOOLEAN NOT NULL DEFAULT TRUE,
	vibration_intensity INTEGER NOT NULL CHECK(vibration_intensity >= 0) DEFAULT 100,
	modified_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (id),
	FOREIGN KEY (user_id) REFERENCES users (id)
);

-- Games table
CREATE TABLE IF NOT EXISTS games (
	id INTEGER NOT NULL, -- sqlite
	id SERIAL NOT NULL, -- postgresql
	user_id INTEGER NOT NULL,
	difficulty INTEGER NOT NULL,
	encoded_game TEXT NOT NULL,
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	UNIQUE (user_id, difficulty),
	PRIMARY KEY (id),
	FOREIGN KEY (user_id) REFERENCES users (id)
);

-- Time records table
CREATE TABLE IF NOT EXISTS time_records (
	id VARCHAR NOT NULL,
	user_id INTEGER NOT NULL,
	difficulty INTEGER NOT NULL,
	time INTEGER NOT NULL,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id, user_id),
	FOREIGN KEY (user_id) REFERENCES users (id)
);
