CREATE TABLE users (
  user_id VARCHAR(32) PRIMARY KEY,
  name VARCHAR(20) NOT NULL,
  email VARCHAR(150) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  license_plate VARCHAR(20),
  membership_tier VARCHAR(20) DEFAULT 'Guld',
  verification_key VARCHAR(32),
  verified_at TIMESTAMP NULL,
  reset_token VARCHAR(32),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE wash_halls (
  hall_id VARCHAR(32) PRIMARY KEY,
  name VARCHAR(150) NOT NULL,
  address VARCHAR(255) NOT NULL
);

CREATE TABLE washes (
  wash_id VARCHAR(32) PRIMARY KEY,
  user_id VARCHAR(32) NOT NULL,
  hall_id VARCHAR(32) NOT NULL,
  tier VARCHAR(20) NOT NULL,
  washed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(user_id),
  FOREIGN KEY (hall_id) REFERENCES wash_halls(hall_id)
);

INSERT INTO wash_halls (hall_id, name, address) VALUES
  ('11111111111111111111111111111111', 'Wash World Nørrebro', 'Rebslagervej 19, 2400 København NV'),
  ('22222222222222222222222222222222', 'Wash World Søborg', 'Dynamovej 4, 2860 Søborg');
