-- Auth Service Database Schema (to be executed on auth_service database)

-- Auth tables
CREATE TABLE auth_tokens (
    token_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
); 