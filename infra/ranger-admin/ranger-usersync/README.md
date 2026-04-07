# Keycloak to Ranger User/Group/Role Sync

This service automatically synchronizes users, groups, and roles from Keycloak to Apache Ranger.

## Features

✅ **User Sync**: Syncs all users from Keycloak realm to Ranger
✅ **Group Sync**: Creates groups in Ranger based on Keycloak groups
✅ **Role Sync**: Creates roles in Ranger based on Keycloak realm roles
✅ **User-Group Mapping**: Associates users with their groups
✅ **Portal Visibility**: Ensures users appear in Ranger Admin UI
✅ **Role Assignment**: Automatically assigns ROLE_USER to synced users

## Sync Results

Based on the latest sync from Keycloak realm `data-platform`:

| Resource | Count | Status |
|----------|-------|--------|
| **Users** | 13 | ✅ Synced (12 visible in UI) |
| **Groups** | 11 | ✅ Synced |
| **Roles** | 25 | ✅ Synced |
| **User-Group Mappings** | 19 | ⚠️ Partially synced |

## Synced Groups

From Keycloak:
1. Analytics Team
2. Business Users
3. Data Analysts
4. Data Engineering Team
5. Data Engineers
6. ML Engineering Team
7. Platform Administrators
8. Streaming Team
9. Superset Administrators
10. Superset Editors
11. Superset Viewers

## Synced Roles

From Keycloak:
1. airflow-admin
2. airflow-user
3. airflow-viewer
4. analytics-user
5. business-user
6. data-analyst
7. data-engineer
8. data-scientist
9. datahub-admin
10. datahub-editor
11. datahub-viewer
12. flink-admin
13. flink-developer
14. ml-engineer
15. platform-admin
16. ranger-admin
17. ranger-auditor
18. ranger-user
19. spark-admin
20. spark-developer
21. superset-admin
22. superset-editor
23. superset-viewer
24. trino-admin
25. trino-user

## Synced Users

From Keycloak (12 users + 1 admin):
1. admin@dataplatform.local
2. analyst-1@analytics.local
3. business-user-1@dataplatform.local
4. data-analyst-1@dataplatform.local
5. data-engineer-1@dataplatform.local
6. data-scientist-1@dataplatform.local
7. engineer-1@analytics.local
8. ml-engineer-1@dataplatform.local
9. platform-admin@analytics.local
10. stream-engineer-1@dataplatform.local
11. superset-admin@analytics.local
12. superset-editor@analytics.local
13. superset-viewer@analytics.local

## How It Works

### 1. Authentication
- Connects to Keycloak using admin credentials or service account
- Obtains OAuth2 access token for Admin API access

### 2. Data Fetching
- Fetches all users from Keycloak realm
- Fetches all groups from Keycloak realm
- Fetches all realm roles (filters out default Keycloak roles)
- Fetches user-group memberships for each user

### 3. Ranger Sync
- **Groups**: Creates groups via `/service/xusers/groups` endpoint
- **Roles**: Creates roles via `/service/public/v2/api/roles` endpoint
- **Users**: Creates users via `/service/users/default` endpoint
- **Portal Sync**: Inserts users into `x_portal_user` table for UI visibility
- **Role Assignment**: Assigns `ROLE_USER` to all synced users
- **User-Group Mapping**: Links users to groups in `x_group_users` table

### 4. Database Operations
Direct PostgreSQL operations for:
- Copying users from `x_user` to `x_portal_user` table
- Assigning `ROLE_USER` via `x_portal_user_role` table
- Creating user-group associations via `x_group_users` table

## Configuration

Environment variables used by the sync service:

```bash
# Keycloak Configuration
KEYCLOAK_URL=http://keycloak:8080
KEYCLOAK_REALM=data-platform
KEYCLOAK_ADMIN=admin
KEYCLOAK_ADMIN_PASSWORD=admin123
KEYCLOAK_ADMIN_API_SECRET=ranger-admin-api-secret-local

# Ranger Configuration
RANGER_URL=http://ranger-admin:6080
RANGER_ADMIN_USER=admin
RANGER_ADMIN_PASS=Rangeradmin1

# PostgreSQL Configuration
DB_HOST=postgres
DB_PORT=5432
DB_NAME=ranger
DB_USER=rangeradmin
DB_PASS=rangeradmin
```

## Accessing Ranger UI

1. Open browser: http://localhost:6080
2. Login with:
   - Username: `admin`
   - Password: `Rangeradmin1`
3. Navigate to: **Settings → Users/Groups/Roles**

### View Users
- Go to **Users** tab
- You'll see all 13 synced users with emails ending in `@keycloak.local`

### View Groups
- Go to **Groups** tab
- You'll see 11 groups synced from Keycloak + 1 default "public" group

### View Roles
- Go to **Roles** tab
- You'll see 25 roles synced from Keycloak

## Technical Details

### User Table Mapping
Ranger uses two separate tables for users:
- `x_user`: External users (created by API)
- `x_portal_user`: Internal users (shown in UI)

The sync script automatically handles both tables to ensure users are visible in the UI.

### Password Management
- Synced users receive a default password: `RangerUser123!`
- Password hash (SHA256): `9f95f14ba218fe13b08600af7004c9f4da6f5c71d56dd948f71ba4668ae0f12e`
- Users can login to Ranger UI with this password

### Database Schema
Key tables involved:
- `x_user`: External user definitions
- `x_portal_user`: Portal/UI user definitions
- `x_portal_user_role`: User role assignments
- `x_group`: Group definitions
- `x_group_users`: User-group memberships
- `x_role`: Role definitions

## Troubleshooting

### Users not visible in UI
- Check `x_portal_user` table: Users must exist here to be visible
- Check `x_portal_user_role` table: Users must have at least `ROLE_USER`
- Restart Ranger Admin to clear cache: `docker restart ranger-admin`

### Groups not syncing
- Verify Keycloak admin credentials have `view-users` and `query-groups` roles
- Check Ranger logs: `docker logs ranger-admin`

### Roles not syncing
- Check database directly: `SELECT * FROM x_role;`
- Ranger roles API may not expose all roles immediately
- Verify via Ranger UI: Settings → Roles

### User-Group mappings failing
- Ensure groups are created before user sync
- Check `x_group_users` table for mappings
- Verify user and group IDs exist in respective tables

## Manual Operations

### Check sync status
```bash
docker logs ranger-usersync
```

### Re-run sync
```bash
docker compose --profile ranger up -d ranger-usersync
```

### Verify users in database
```sql
SELECT login_id, email, status 
FROM x_portal_user 
WHERE user_src = 0 
AND login_id NOT IN ('admin', 'rangertagsync', 'rangerusersync', 'keyadmin');
```

### Verify groups in database
```sql
SELECT id, group_name, descr 
FROM x_group 
WHERE group_name != 'public';
```

### Verify roles in database
```sql
SELECT id, name, description 
FROM x_role 
WHERE name NOT LIKE 'ROLE_%';
```

## Future Enhancements

- [ ] Sync role-user assignments
- [ ] Sync role-group assignments
- [ ] Incremental sync (only changed users/groups)
- [ ] Scheduled periodic sync
- [ ] Sync user attributes/metadata
- [ ] Two-way sync (Ranger → Keycloak)
- [ ] Support for nested groups
- [ ] Policy template assignment based on roles

## License

Part of the Lakehouse OSS project.
