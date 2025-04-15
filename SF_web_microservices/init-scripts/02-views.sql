-- Create views for Masters Pro Scheduling App

-- View for calendar display
CREATE VIEW calendar_events AS
SELECT 
    e.event_id,
    e.title,
    e.start_time,
    e.end_time,
    e.status,
    r.name AS resource_name,
    u.full_name AS organizer_name,
    COUNT(ep.participant_id) AS current_participants,
    e.max_participants
FROM 
    events e
LEFT JOIN 
    resources r ON e.resource_id = r.resource_id
LEFT JOIN 
    users u ON e.organizer_id = u.user_id
LEFT JOIN 
    event_participants ep ON e.event_id = ep.event_id AND ep.status = 'accepted'
GROUP BY 
    e.event_id, r.name, u.full_name;

-- View for resource utilization
CREATE VIEW resource_utilization AS
SELECT 
    r.resource_id,
    r.name,
    r.type,
    DATE_TRUNC('day', e.start_time) AS usage_date,
    COUNT(e.event_id) AS event_count,
    SUM(EXTRACT(EPOCH FROM (e.end_time - e.start_time))/3600) AS hours_used
FROM 
    resources r
LEFT JOIN 
    events e ON r.resource_id = e.resource_id
WHERE 
    e.status != 'canceled'
GROUP BY 
    r.resource_id, r.name, r.type, usage_date; 