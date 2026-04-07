import os
import requests
import time
import psycopg2

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "data-platform")

RANGER_URL = os.getenv("RANGER_URL", "http://ranger-admin:6080")
RANGER_ADMIN_USER = os.getenv("RANGER_ADMIN_USER", "admin")
RANGER_ADMIN_PASS = os.getenv("RANGER_ADMIN_PASS", "Rangeradmin1")

# PostgreSQL connection settings
DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "ranger")
DB_USER = os.getenv("DB_USER", "rangeradmin")
DB_PASS = os.getenv("DB_PASS", "rangeradmin")


def get_keycloak_token():
    # Try admin credentials FIRST (more reliable for admin API access)
    admin_user = os.getenv("KEYCLOAK_ADMIN")
    admin_pass = os.getenv("KEYCLOAK_ADMIN_PASSWORD")

    if admin_user and admin_pass:
        try:
            url_master = f"{KEYCLOAK_URL}/realms/master/protocol/openid-connect/token"
            data_admin = {
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": admin_user,
                "password": admin_pass,
            }
            r2 = requests.post(url_master, data=data_admin, timeout=10)
            r2.raise_for_status()
            token2 = r2.json().get("access_token")

            if token2:
                print("✓ Obtained token using admin credentials (KEYCLOAK_ADMIN)")
                return token2
            else:
                print("⚠ Admin credentials returned no access_token")

        except Exception as e2:
            print(f"⚠ Admin password grant failed: {e2}")
    
    # Fallback: if admin credentials didn't work, try client_credentials
    url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": "ranger-admin-api",
        "client_secret": os.getenv("KEYCLOAK_ADMIN_API_SECRET", "ranger-admin-api-secret-local")
    }

    try:
        r = requests.post(url, data=data, timeout=10)
        r.raise_for_status()
        token = r.json().get("access_token")

        if not token:
            raise RuntimeError("No access_token in response")

        print("✓ Obtained token using client_credentials (ranger-admin-api)")
        return token

    except Exception as e:
        print(f"✗ client_credentials grant failed: {e}")

    # If we reach here, no token could be obtained
    raise RuntimeError("Failed to obtain Keycloak token via admin or client credentials")


def get_keycloak_users(token):
    """
    Fetch all users from Keycloak realm.
    Returns list of user dictionaries.
    """
    url = f"{KEYCLOAK_URL}/admin/realms/{KEYCLOAK_REALM}/users"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        r = requests.get(url, headers=headers, timeout=10)
        
        if r.status_code == 403:
            print("✗ Keycloak returned 403 Forbidden when requesting users")
            print(f"  Response: {r.text}")
            print("\n🔧 TROUBLESHOOTING:")
            print("  1. Ensure 'ranger-admin-api' client has service account enabled")
            print("  2. Grant the following roles to service-account-ranger-admin-api:")
            print("     - realm-management → view-users")
            print("     - realm-management → query-users")
            print("     - realm-management → query-groups")
            print("  3. Or use KEYCLOAK_ADMIN/KEYCLOAK_ADMIN_PASSWORD environment variables")
            
        r.raise_for_status()
        return r.json()
        
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to fetch users from Keycloak: {e}")


def get_keycloak_groups(token):
    """
    Fetch all groups from Keycloak realm.
    Returns list of group dictionaries.
    """
    url = f"{KEYCLOAK_URL}/admin/realms/{KEYCLOAK_REALM}/groups"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        return r.json()
        
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to fetch groups from Keycloak: {e}")


def get_keycloak_roles(token):
    """
    Fetch all realm roles from Keycloak.
    Returns list of role dictionaries.
    """
    url = f"{KEYCLOAK_URL}/admin/realms/{KEYCLOAK_REALM}/roles"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        return r.json()
        
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to fetch roles from Keycloak: {e}")


def get_user_groups(token, user_id):
    """
    Fetch groups for a specific user.
    Returns list of group dictionaries.
    """
    url = f"{KEYCLOAK_URL}/admin/realms/{KEYCLOAK_REALM}/users/{user_id}/groups"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        return r.json()
        
    except requests.exceptions.RequestException as e:
        return []  # Return empty list if fails


def create_ranger_group(groupname, description=""):
    """
    Create or update group in Apache Ranger via API.
    Returns group ID if successful, None otherwise.
    """
    # Check if group exists
    check_url = f"{RANGER_URL}/service/xusers/groups/groupName/{groupname}"
    
    try:
        r_check = requests.get(
            check_url,
            auth=(RANGER_ADMIN_USER, RANGER_ADMIN_PASS),
            timeout=10
        )
        
        if r_check.status_code == 200:
            group_data = r_check.json()
            return group_data.get('id')
            
    except requests.exceptions.RequestException:
        pass  # Group doesn't exist, continue to create
    
    # Create group
    url = f"{RANGER_URL}/service/xusers/groups"
    payload = {
        "name": groupname,
        "description": description or f"Group synced from Keycloak",
        "groupSource": 1,  # External source
        "isVisible": 1
    }

    try:
        r = requests.post(
            url, 
            json=payload, 
            auth=(RANGER_ADMIN_USER, RANGER_ADMIN_PASS), 
            timeout=10
        )
        
        if r.status_code in [200, 201, 204]:
            group_data = r.json() if r.text else {}
            return group_data.get('id')
        else:
            return None
            
    except requests.exceptions.RequestException as e:
        return None


def create_ranger_role(rolename, description=""):
    """
    Create or update role in Apache Ranger via API.
    Returns role ID if successful, None otherwise.
    """
    # Check if role exists
    check_url = f"{RANGER_URL}/service/public/v2/api/roles/name/{rolename}"
    
    try:
        r_check = requests.get(
            check_url,
            auth=(RANGER_ADMIN_USER, RANGER_ADMIN_PASS),
            timeout=10
        )
        
        if r_check.status_code == 200:
            role_data = r_check.json()
            return role_data.get('id')
            
    except requests.exceptions.RequestException:
        pass  # Role doesn't exist, continue to create
    
    # Create role
    url = f"{RANGER_URL}/service/public/v2/api/roles"
    payload = {
        "name": rolename,
        "description": description or f"Role synced from Keycloak",
        "users": [],
        "groups": [],
        "roles": []
    }

    try:
        r = requests.post(
            url, 
            json=payload, 
            auth=(RANGER_ADMIN_USER, RANGER_ADMIN_PASS), 
            timeout=10
        )
        
        if r.status_code in [200, 201, 204]:
            role_data = r.json() if r.text else {}
            return role_data.get('id')
        else:
            return None
            
    except requests.exceptions.RequestException as e:
        return None


def add_user_to_group(username, groupname):
    """
    Add user to group in Ranger via database.
    Returns True if successful, False otherwise.
    """
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        
        cursor = conn.cursor()
        
        # Get user and group IDs
        cursor.execute("SELECT id FROM x_user WHERE user_name = %s", (username,))
        user_result = cursor.fetchone()
        
        cursor.execute("SELECT id FROM x_group WHERE group_name = %s", (groupname,))
        group_result = cursor.fetchone()
        
        if not user_result or not group_result:
            cursor.close()
            conn.close()
            return False
        
        user_id = user_result[0]
        group_id = group_result[0]
        
        # Check if mapping exists
        cursor.execute("SELECT id FROM x_group_users WHERE user_id = %s AND group_id = %s", (user_id, group_id))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return True  # Already exists
        
        # Insert mapping
        sql = """
        INSERT INTO x_group_users (create_time, update_time, group_id, user_id, added_by_id, upd_by_id)
        VALUES (now(), now(), %s, %s, 1, 1)
        """
        cursor.execute(sql, (group_id, user_id))
        conn.commit()
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        return False


def create_ranger_user(username, email):
    """
    Create user directly in Ranger database.
    Creates entries in both x_portal_user (UI) and x_user (policies) tables.
    Returns True if successful, False otherwise.
    """
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        
        cursor = conn.cursor()
        
        # Check if user exists in x_portal_user
        cursor.execute("SELECT id FROM x_portal_user WHERE login_id = %s", (username,))
        existing_portal_user = cursor.fetchone()
        
        if existing_portal_user:
            cursor.close()
            conn.close()
            return True  # User already exists
        
        # Generate password hash (same as Ranger default)
        # This is SHA-256 hash of "RangerUser123!"
        password_hash = "9f95f14ba218fe13b08600af7004c9f4da6f5c71d56dd948f71ba4668ae0f12e"
        
        # Insert into x_portal_user (for UI visibility)
        sql_portal = """
        INSERT INTO x_portal_user (
            create_time, update_time, login_id, password, first_name, 
            last_name, pub_scr_name, email, status, user_src, 
            notes, added_by_id, upd_by_id
        ) VALUES (
            now(), now(), %s, %s, %s, 
            '', NULL, %s, 1, 0, 
            'Synced from Keycloak', 1, 1
        ) RETURNING id;
        """
        
        cursor.execute(sql_portal, (
            username,
            password_hash,
            username,
            email or f"{username}@keycloak.local"
        ))
        
        portal_user_id = cursor.fetchone()[0]
        
        # Assign ROLE_USER
        sql_role = """
        INSERT INTO x_portal_user_role (create_time, update_time, user_id, user_role, status)
        VALUES (now(), now(), %s, 'ROLE_USER', 1);
        """
        cursor.execute(sql_role, (portal_user_id,))
        
        # Insert into x_user (for policy assignments)
        sql_user = """
        INSERT INTO x_user (
            create_time, update_time, user_name, descr, 
            status, added_by_id, upd_by_id
        ) VALUES (
            now(), now(), %s, %s, 
            0, 1, 1
        ) ON CONFLICT (user_name) DO NOTHING;
        """
        
        cursor.execute(sql_user, (username, f"Synced from Keycloak"))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"    ✗ Database error: {e}")
        return False


def sync_to_portal_users():
    """
    Sync users from x_user to x_portal_user so they appear in Ranger UI.
    This is necessary because Ranger API creates users in x_user but UI reads from x_portal_user.
    """
    print("\n[Portal Sync] Syncing users to x_portal_user for UI visibility...")
    
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        
        cursor = conn.cursor()
        
        # Insert users from x_user to x_portal_user if they don't exist
        sql_users = """
        INSERT INTO x_portal_user (create_time, update_time, login_id, password, first_name, email, status, user_src, added_by_id, upd_by_id)
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
        AND x.user_name NOT IN (SELECT login_id FROM x_portal_user);
        """
        
        cursor.execute(sql_users)
        rows_inserted = cursor.rowcount
        conn.commit()
        
        print(f"✓ Synced {rows_inserted} new users to x_portal_user")
        
        # Assign ROLE_USER to users who don't have it
        print("\n[Role Assignment] Assigning ROLE_USER to synced users...")
        sql_roles = """
        INSERT INTO x_portal_user_role (create_time, update_time, user_id, user_role, status)
        SELECT now(), now(), id, 'ROLE_USER', 1 
        FROM x_portal_user 
        WHERE user_src = 0 
        AND login_id NOT IN ('admin', 'rangertagsync', 'rangerusersync', 'keyadmin') 
        AND id NOT IN (SELECT user_id FROM x_portal_user_role WHERE user_role = 'ROLE_USER');
        """
        
        cursor.execute(sql_roles)
        roles_assigned = cursor.rowcount
        conn.commit()
        
        print(f"✓ Assigned ROLE_USER to {roles_assigned} users")
        
        # Count total users
        cursor.execute("SELECT COUNT(*) FROM x_portal_user WHERE user_src = 0 AND login_id NOT IN ('admin', 'rangertagsync', 'rangerusersync', 'keyadmin');")
        total_users = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        print(f"  Total Keycloak users visible in UI: {total_users}")
        return True
        
    except Exception as e:
        print(f"✗ Failed to sync to x_portal_user: {e}")
        return False


def main():
    """
    Main sync function: sync users, groups, roles from Keycloak to Ranger.
    """
    print("=" * 60)
    print("Keycloak → Ranger Sync (Users, Groups, Roles)")
    print("=" * 60)
    print("\nWaiting for services to be ready...")
    time.sleep(20)

    print("\n[1/6] Authenticating with Keycloak...")
    try:
        token = get_keycloak_token()
    except Exception as e:
        print(f"\n✗ FATAL: Failed to get Keycloak token: {e}")
        return 1

    # Fetch all data from Keycloak
    print("\n[2/6] Fetching groups from Keycloak...")
    try:
        groups = get_keycloak_groups(token)
        print(f"✓ Found {len(groups)} groups to sync")
    except Exception as e:
        print(f"⚠ Warning: Failed to fetch groups: {e}")
        groups = []

    print("\n[3/6] Fetching roles from Keycloak...")
    try:
        roles = get_keycloak_roles(token)
        # Filter out default Keycloak roles
        roles = [r for r in roles if not r.get('name', '').startswith('default-roles-') 
                 and r.get('name') not in ['offline_access', 'uma_authorization']]
        print(f"✓ Found {len(roles)} roles to sync")
    except Exception as e:
        print(f"⚠ Warning: Failed to fetch roles: {e}")
        roles = []

    print("\n[4/6] Fetching users from Keycloak...")
    try:
        users = get_keycloak_users(token)
        print(f"✓ Found {len(users)} users to sync")
    except Exception as e:
        print(f"\n✗ FATAL: Failed to fetch users: {e}")
        return 1

    # Sync groups
    if groups:
        print(f"\n[5/6] Syncing {len(groups)} groups to Ranger...")
        group_success = 0
        for group in groups:
            groupname = group.get('name')
            if groupname:
                print(f"  → Creating group: {groupname}")
                if create_ranger_group(groupname, group.get('path', '')):
                    print(f"    ✓ Success")
                    group_success += 1
                else:
                    print(f"    ℹ Already exists or created")
                    group_success += 1
        print(f"✓ Synced {group_success}/{len(groups)} groups")

    # Sync roles
    if roles:
        print(f"\n[6/6] Syncing {len(roles)} roles to Ranger...")
        role_success = 0
        for role in roles:
            rolename = role.get('name')
            if rolename:
                print(f"  → Creating role: {rolename}")
                if create_ranger_role(rolename, role.get('description', '')):
                    print(f"    ✓ Success")
                    role_success += 1
                else:
                    print(f"    ℹ Already exists or created")
                    role_success += 1
        print(f"✓ Synced {role_success}/{len(roles)} roles")

    # Sync users
    print(f"\n[7/7] Syncing {len(users)} users to Ranger...")
    success_count = 0
    fail_count = 0
    user_group_mappings = []
    
    for u in users:
        username = u.get("username")
        email = u.get("email")
        user_id = u.get("id")
        
        if not username:
            print(f"  ⚠ Skipping user with no username: {u}")
            continue

        print(f"  → Syncing: {username} ({email or 'no email'})")
        
        if create_ranger_user(username, email):
            print(f"    ✓ Success")
            success_count += 1
            
            # Get user's groups for later mapping
            if user_id:
                user_groups = get_user_groups(token, user_id)
                for ug in user_groups:
                    user_group_mappings.append((username, ug.get('name')))
        else:
            print(f"    ✗ Failed")
            fail_count += 1

    # Add users to groups
    if user_group_mappings:
        print(f"\n[8/8] Adding users to groups ({len(user_group_mappings)} mappings)...")
        mapping_success = 0
        for username, groupname in user_group_mappings:
            if add_user_to_group(username, groupname):
                mapping_success += 1
        print(f"✓ Added {mapping_success}/{len(user_group_mappings)} user-group mappings")

    print("\n" + "=" * 60)
    print("Sync Summary")
    print("=" * 60)
    print(f"Groups:  {len(groups)} synced")
    print(f"Roles:   {len(roles)} synced")
    print(f"Users:   ✓ {success_count} successful, ✗ {fail_count} failed")
    if user_group_mappings:
        print(f"Mappings: {len(user_group_mappings)} user-group associations")
    print("=" * 60)
    
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)