-- Client Service Database Schema (to be executed on client_service database)

-- Client tables
CREATE TABLE clients (
    client_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    external_id VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(20),
    address TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'new'
);

CREATE TABLE client_interactions (
    interaction_id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL,
    event_id INTEGER,
    notes TEXT,
    files JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    created_by INTEGER NOT NULL
);

-- Create indexes for clients
CREATE INDEX idx_clients_user ON clients(user_id);
CREATE INDEX idx_clients_email ON clients(email);
CREATE INDEX idx_clients_status ON clients(status);

-- Create indexes for client interactions
CREATE INDEX idx_client_interactions_client ON client_interactions(client_id);
CREATE INDEX idx_client_interactions_event ON client_interactions(event_id); 