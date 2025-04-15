-- Initialize Masters Pro Scheduling App Database Schema

-- Roles table
CREATE TABLE roles (
    role_id SERIAL PRIMARY KEY,
    role_name VARCHAR(50) UNIQUE NOT NULL,
    permissions JSONB NOT NULL
);

-- Insert default roles
INSERT INTO roles (role_name, permissions) VALUES 
('admin', '{"can_edit_events": true, "can_view_reports": true, "can_manage_users": true}'),
('manager', '{"can_edit_events": true, "can_view_reports": true, "can_manage_users": false}'),
('client', '{"can_edit_events": false, "can_view_reports": false, "can_manage_users": false}');

-- Users table
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    full_name VARCHAR(100),
    role_id INT REFERENCES roles(role_id),
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Create indexes for users table
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role_id);

-- User integrations table
CREATE TABLE user_integrations (
    integration_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id) ON DELETE CASCADE,
    service_name VARCHAR(50) NOT NULL,
    access_token TEXT,
    refresh_token TEXT,
    external_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Resources table
CREATE TABLE resources (
    resource_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(50) NOT NULL,
    capacity INT,
    location VARCHAR(100),
    is_available BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Events table
CREATE TABLE events (
    event_id SERIAL PRIMARY KEY,
    organizer_id INT REFERENCES users(user_id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    type VARCHAR(50) NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'planned',
    resource_id INT REFERENCES resources(resource_id),
    max_participants INT,
    payment_required BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for events table
CREATE INDEX idx_events_organizer ON events(organizer_id);
CREATE INDEX idx_events_start_time ON events(start_time);
CREATE INDEX idx_events_type ON events(type);
CREATE INDEX idx_events_resource ON events(resource_id);
CREATE INDEX idx_events_status ON events(status);

-- Event participants table
CREATE TABLE event_participants (
    participant_id SERIAL PRIMARY KEY,
    event_id INT REFERENCES events(event_id) ON DELETE CASCADE,
    user_id INT REFERENCES users(user_id),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for event participants table
CREATE INDEX idx_event_participants_event ON event_participants(event_id);
CREATE INDEX idx_event_participants_user ON event_participants(user_id);
CREATE INDEX idx_event_participants_status ON event_participants(status);

-- Clients table
CREATE TABLE clients (
    client_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id),
    external_id VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(20),
    address TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'new'
);

-- Create indexes for clients table
CREATE INDEX idx_clients_user ON clients(user_id);
CREATE INDEX idx_clients_email ON clients(email);
CREATE INDEX idx_clients_status ON clients(status);

-- Client interactions table
CREATE TABLE client_interactions (
    interaction_id SERIAL PRIMARY KEY,
    client_id INT REFERENCES clients(client_id) ON DELETE CASCADE,
    event_id INT REFERENCES events(event_id),
    notes TEXT,
    files JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    created_by INT REFERENCES users(user_id)
);

-- Create indexes for client interactions
CREATE INDEX idx_client_interactions_client ON client_interactions(client_id);
CREATE INDEX idx_client_interactions_event ON client_interactions(event_id);

-- Payments table
CREATE TABLE payments (
    payment_id SERIAL PRIMARY KEY,
    event_id INT REFERENCES events(event_id),
    user_id INT REFERENCES users(user_id),
    amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    transaction_id VARCHAR(255),
    payment_method VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for payments table
CREATE INDEX idx_payments_event ON payments(event_id);
CREATE INDEX idx_payments_user ON payments(user_id);
CREATE INDEX idx_payments_status ON payments(status);

-- Event stats table for analytics
CREATE TABLE event_stats (
    stat_id SERIAL PRIMARY KEY,
    event_id INT REFERENCES events(event_id) ON DELETE CASCADE,
    participants_count INT DEFAULT 0,
    avg_rating DECIMAL(3, 2),
    revenue DECIMAL(10, 2) DEFAULT 0,
    recorded_date DATE NOT NULL
);

-- Create indexes for event stats
CREATE INDEX idx_event_stats_event ON event_stats(event_id);
CREATE INDEX idx_event_stats_date ON event_stats(recorded_date);

-- User activity table for tracking
CREATE TABLE user_activity (
    activity_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id),
    action_type VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW(),
    metadata JSONB
);

-- Create indexes for user activity
CREATE INDEX idx_user_activity_user ON user_activity(user_id);
CREATE INDEX idx_user_activity_action ON user_activity(action_type);
CREATE INDEX idx_user_activity_timestamp ON user_activity(timestamp); 