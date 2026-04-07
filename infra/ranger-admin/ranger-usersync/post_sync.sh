#!/bin/bash
# Post-sync script to ensure Keycloak users appear in Ranger UI
# This script copies users from x_user to x_portal_user table

echo "============================================================"
echo "Post-Sync: Copying users to x_portal_user for UI visibility"
echo "============================================================"

# Wait a moment for sync to complete
sleep 5

# SQL to copy users from x_user to x_portal_user
SQL="INSERT INTO x_portal_user (create_time, update_time, login_id, password, first_name, email, status, user_src, added_by_id, upd_by_id)
SELECT 
    now(), 
    now(), 
    x.user_name, 
    '9f95f14ba218fe13b08600af7004c9f4da6f5c71d56dd948f71ba4668ae0f12e', 
    x.user_name, 
    x.user_name || '@keycloak.local', 
    1, 
    0, 
    1, 
    1 
FROM x_user x 
WHERE x.user_name NOT IN ('rangertagsync', 'rangerusersync', 'keyadmin', 'rangertruststore', 'admin', '{USER}', '{OWNER}', 'ranger-admin') 
AND x.user_name NOT IN (SELECT login_id FROM x_portal_user);"

# Execute SQL via postgres container
docker exec postgres psql -U rangeradmin -d ranger -c "$SQL" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    # Count users in portal
    COUNT=$(docker exec postgres psql -U rangeradmin -d ranger -t -c "SELECT COUNT(*) FROM x_portal_user WHERE user_src = 0 AND login_id NOT IN ('admin', 'rangertagsync', 'rangerusersync', 'keyadmin');")
    echo "✓ Successfully synced users to x_portal_user table"
    echo "  Total Keycloak users visible in UI: $COUNT"
else
    echo "✗ Failed to sync users to x_portal_user"
    exit 1
fi

echo "============================================================"
