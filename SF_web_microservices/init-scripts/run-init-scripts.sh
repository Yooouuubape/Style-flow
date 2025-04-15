#!/bin/bash
set -e

# This script should be the only one executed during postgres initialization

# Create all required databases
echo "Creating databases for all microservices..."
psql -U salyukovgleb033 -d "Style Flow" <<-EOSQL
CREATE DATABASE auth_service;
CREATE DATABASE user_service;
CREATE DATABASE event_service;
CREATE DATABASE resource_service;
CREATE DATABASE client_service;
CREATE DATABASE payment_service;
EOSQL

# Run the init script for user_service
echo "Initializing user_service database..."
psql -U salyukovgleb033 -d user_service -f /init-scripts/01-init-schema.sql

# Create views for user_service
echo "Creating views for user_service database..."
psql -U salyukovgleb033 -d user_service -f /init-scripts/02-views.sql

# Initialize auth_service database
echo "Initializing auth_service database..."
psql -U salyukovgleb033 -d auth_service -f /init-scripts/02-auth-service.sql

# Initialize event_service database
echo "Initializing event_service database..."
psql -U salyukovgleb033 -d event_service -f /init-scripts/03-event-service.sql

# Initialize resource_service database
echo "Initializing resource_service database..."
psql -U salyukovgleb033 -d resource_service -f /init-scripts/04-resource-service.sql

# Initialize client_service database
echo "Initializing client_service database..."
psql -U salyukovgleb033 -d client_service -f /init-scripts/05-client-service.sql

# Initialize payment_service database
echo "Initializing payment_service database..."
psql -U salyukovgleb033 -d payment_service -f /init-scripts/06-payment-service.sql

echo "All database initialization completed successfully." 