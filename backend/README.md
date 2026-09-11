# CG-CRM — Backend

Django 5.2 + DRF API for the Cedar Grove CRM. Email-based auth, JWT, and a
role/permission system driven by a database-backed catalog.

## Getting started

```bash
cd backend
venv/Scripts/activate          # Windows;  source venv/bin/activate elsewhere
pip install -r requirements.txt
python manage.py migrate
python manage.py seed --email you@example.com
python manage.py runserver
```

`seed` prints a generated password once and flags the account to change it at
first sign-in. Pass `--password` to choose one yourself.

Settings are selected by `.env`:

```
settings_module=config.settings.local
```

## API docs

| | |
|---|---|
| Swagger UI | http://localhost:8000/api/docs/ |
| ReDoc | http://localhost:8000/api/redoc/ |
| OpenAPI schema | http://localhost:8000/api/schema/ |

Or generate the schema as a file — useful for frontend codegen, or to import
into Postman (*Import → File → schema.yml*, which builds a collection):

```bash
python manage.py spectacular --fail-on-warn --file schema.yml
```

`--fail-on-warn` is worth keeping in CI. It catches views the schema generator
cannot describe, which is usually a sign something is mis-wired.

## Endpoints

All under `/api/v1/`. Everything except `auth/login/` requires
`Authorization: Bearer <access>`.

| Method | Path | Permission |
|---|---|---|
| POST | `auth/login/` | — |
| POST | `auth/change-password/` | any signed-in user |
| POST | `auth/token/refresh/` · `verify/` · `blacklist/` | — |
| GET | `permissions/` | any signed-in user |
| GET, POST | `roles/` | `role.detail` · `role.create` |
| GET, PATCH, DELETE | `roles/{id}/` | `role.detail` · `role.update` · `role.delete` |
| GET, POST | `users/` | `user.detail` · `user.create` |
| GET, PATCH | `users/{id}/` | `user.detail` · `user.update` |
| GET | `users/me/` | any signed-in user |
| POST | `users/{id}/block/` · `unblock/` | `user.block` · `user.unblock` |
| POST | `users/{id}/change-password/` | `user.change_password` |

`GET /permissions/` returns the catalog grouped `Module → Resource → Actions`
for the checkbox tree. `GET /users/me/` returns the signed-in account with its
role and effective permission codenames — the frontend renders its menus from
that list.

## Access control

All policy lives in one function, `apps/roles/permissions.py::check_access`.
Two wrappers call it and nothing else, so the rules cannot drift apart:

```python
# viewsets
class RoleViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, HasRolePermission]
    required_permissions = {'list': 'role.detail', 'create': 'role.create'}

# plain view methods
@require_permission('user.create')
def post(self, request): ...
```

Checks run in this order:

1. **Authenticated** → else 401.
2. **Not blocked** → else 403 `account_blocked`.
3. **No pending forced password change** → else 403 `password_change_required`.
4. **Superuser** → pass, without consulting a role.
5. **Role holds the codename** → else 403 `permission_denied`.

Steps 2 and 3 sit *above* the superuser bypass on purpose: a blocked or
just-reset admin is held to the same rule as anyone else.

Refusals carry a machine-readable `code` in the response body, because the
frontend has to tell "you lack this permission" (show an error) from "you must
change your password" (redirect).

**Fails closed.** An action missing from a view's `required_permissions` is
denied. Forgetting a codename should cost a 403 in a test, not leave an
endpoint open. Use `ANY_AUTHENTICATED` to open one deliberately.

**The allow-list.** `POST auth/change-password/` and `GET users/me/` stay
reachable while a forced change is pending — gate the endpoint that clears the
flag on the flag being clear and the user can never get out.

## The permission catalog

`apps/roles/catalog.py` is the source of truth. Ten permissions across two
modules: `user.create|update|detail|block|unblock|change_password` and
`role.create|update|detail|delete`.

Adding one takes **two** steps:

1. Add it to `catalog.py`.
2. Add a data migration alongside it (see
   `roles/migrations/0002_seed_permissions.py`).

The migration carries a *frozen* copy rather than importing `catalog.py` — a
migration has to keep describing the world as it was, or replaying history
produces whatever today's catalog happens to say. `test_catalog_matches_the_database`
fails if you do step 1 without step 2.

| Command | Use |
|---|---|
| `manage.py seed` | Fresh environment: catalog + Super Admin role + first admin |
| `manage.py seed_permissions` | Routine deploys: catalog only |
| `manage.py seed_permissions --prune` | Drop permissions no longer in the catalog |

Both are idempotent. `seed` never resets an existing account's password, so
re-running it is not a way to take over an account.

## Auth notes

**Login** returns `access`, `refresh`, `must_change_password`, and the full
`user` object (saving an immediate round trip to `users/me/`). It distinguishes
three failures by `code`: `invalid_credentials`, `account_blocked`,
`account_inactive`.

The specific reason is only disclosed *after* the password is proven correct —
a blocked account with the wrong password returns exactly what an unknown
address returns. Otherwise the endpoint is an account-enumeration oracle.

**Token invalidation** uses `User.token_version`, stamped into every JWT and
checked on each request. The blacklist app only covers *refresh* tokens; access
tokens are stateless and would stay valid for up to `ACCESS_TOKEN_LIFETIME`
after a block. Bumping the counter closes that window immediately and costs
nothing — authentication already loads the user row. Blocking does both.

`token_version` is bumped on block, on an admin password reset, and on a
self-serve password change (which ends your *other* sessions; the endpoint
hands back a fresh pair so you keep the one you are in).

There is **no `POST auth/token/`**. SimpleJWT's stock view cannot tell the
failure modes apart, does not report `must_change_password`, and mints tokens
with no version stamp — a permanent hole in blocking.

## Model notes

- **`User`** — `AbstractBaseUser` + `PermissionsMixin`, email as
  `USERNAME_FIELD`, no username. Email is lowercased whole (not just the
  domain) so the unique constraint cannot be defeated by `Ada@` vs `ada@`.
- **`login_type`** — an **auth provider** field: `local` or `sso`. Not a user
  category; `Role` covers that. An SSO account holds no local password and is
  not flagged `must_change_password`, which would strand it.
- **`User.role`** — `on_delete=PROTECT`. A role that is still assigned must not
  be deletable; `RoleDeleteSerializer` turns the resulting `ProtectedError`
  into a readable 400, but the database is what guarantees it. A serializer
  alone would be bypassed by a shell session or a `queryset.delete()`.
- **No user delete route.** Accounts are deactivated (`is_active`) or blocked
  (`is_blocked`), so records referencing them keep making sense.

## Tests

```bash
python manage.py test apps          # 180 tests
python manage.py test apps.roles
```

The three parts most worth reading, because they encode decisions rather than
mechanics:

| | Where |
|---|---|
| Role delete guard | `apps/roles/tests.py::RoleDeleteGuardTests` |
| Blocked-user login | `apps/users/test_auth.py::LoginTests`, `BlockUnblockTests` |
| Forced password change | `apps/roles/test_access.py::PasswordChangeGateEndToEndTests` |

## Layout

```
backend/
  config/settings/{base,local,dev,prod}.py
  apps/
    users/    User, auth, JWT, the user API
    roles/    Permission, Role, the catalog, check_access
```

`manage.py startapp <name>` creates apps under `apps/` and rewrites the
generated `AppConfig` to its dotted path. Add it to `LOCAL_APPS`.

## Known gaps

- **No pagination.** List endpoints return plain JSON lists. Fine for roles;
  `users/` will want `DEFAULT_PAGINATION_CLASS` before the table grows.
- **`dev.py` and `prod.py` are empty.** Only `local.py` is filled in, and its
  `SECRET_KEY` is the checked-in development one.
- **No rate limiting on login.** Worth adding before this is public.
- **SSO is a field, not an integration.** Nothing implements `login_type=sso`
  yet.
