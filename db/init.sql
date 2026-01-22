CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

INSERT INTO users (email, name)
VALUES ('test@example.com', 'Test User');
